from __future__ import annotations

import copy

import pytest

torch = pytest.importorskip(
    "torch", reason="Cortex tests run in the isolated ninereeds-cortex environment",
)

from bdh import BDH, BDHConfig
from training.diagnostics import GateCreditRecorder, vector_alignment
from training.optim import FactoredAdamW


def test_vector_alignment_signs_and_zero_signal() -> None:
    activity = torch.tensor([1.0, 2.0])
    assert vector_alignment(activity, -activity)["gate_credit_cosine"] == pytest.approx(1.0)
    assert vector_alignment(activity, activity)["gate_credit_cosine"] == pytest.approx(-1.0)
    orthogonal = vector_alignment(
        torch.tensor([1.0, 0.0]), torch.tensor([0.0, 1.0]),
    )
    assert orthogonal["gate_credit_cosine"] == pytest.approx(0.0)
    absent = vector_alignment(torch.zeros(2), torch.ones(2))
    assert absent["gate_credit_cosine"] is None
    assert absent["alignment_status"] == "insufficient_signal"


def _train_step(model: BDH, observations: torch.Tensor, *, recorder=None):
    names = {id(parameter): name for name, parameter in model.named_parameters()}
    optimizer = FactoredAdamW(
        model.parameters(), lr=1e-3,
        diagnostic_callback=(
            None if recorder is None else
            lambda parameter, gradient, update, lr: recorder.observe_optimizer_update(
                names[id(parameter)], parameter, gradient, update, lr,
            )
        ),
    )
    if recorder is not None:
        recorder.begin_step(1, epoch=1, source_metadata=[{"stage": "test"}])
    hidden = model.encode_embeds(observations, gate_credit_observer=recorder)
    loss = hidden.square().mean()
    loss.backward()
    gradients = {
        name: parameter.grad.detach().clone()
        for name, parameter in model.named_parameters()
        if parameter.grad is not None
    }
    optimizer.step()
    if recorder is not None:
        recorder.finish_step()
    return loss.detach(), gradients, copy.deepcopy(optimizer.state_dict())


def test_diagnostics_do_not_change_cpu_training_result_or_rng() -> None:
    torch.manual_seed(9)
    config = BDHConfig(
        n_layer=2, n_embd=8, n_head=2,
        mlp_internal_dim_multiplier=2, vocab_size=16, dropout=0.0,
        per_layer_weights=True,
    )
    control = BDH(config)
    observed = BDH(config)
    observed.load_state_dict(control.state_dict())
    observations = torch.randn(1, 4, 8)
    rng = torch.random.get_rng_state().clone()

    control_loss, control_gradients, control_optimizer = _train_step(control, observations)
    control_rng = torch.random.get_rng_state().clone()
    torch.random.set_rng_state(rng)
    recorder = GateCreditRecorder(log_every_n_steps=1, max_sampled_steps=1)
    observed_loss, observed_gradients, observed_optimizer = _train_step(
        observed, observations, recorder=recorder,
    )
    observed_rng = torch.random.get_rng_state().clone()

    torch.testing.assert_close(control_loss, observed_loss, rtol=0, atol=0)
    assert control_gradients.keys() == observed_gradients.keys()
    for name in control_gradients:
        torch.testing.assert_close(
            control_gradients[name], observed_gradients[name], rtol=0, atol=0,
        )
    for left, right in zip(control.parameters(), observed.parameters(), strict=True):
        torch.testing.assert_close(left, right, rtol=0, atol=0)
    assert control_optimizer.keys() == observed_optimizer.keys()
    torch.testing.assert_close(control_rng, observed_rng, rtol=0, atol=0)
    assert len(recorder.records) == 1
    assert len(recorder.records[0]["layers"]) == 2
    assert recorder.records[0]["source_metadata"] == [{"stage": "test"}]


def test_optimizer_observation_does_not_perturb_stochastic_rounding() -> None:
    initial = torch.ones(32, dtype=torch.bfloat16)

    def run(callback):
        parameter = torch.nn.Parameter(initial.clone())
        optimizer = FactoredAdamW(
            [parameter], lr=1e-3, stochastic_rounding=True,
            diagnostic_callback=callback,
        )
        parameter.grad = torch.linspace(-1, 1, 32, dtype=torch.bfloat16)
        optimizer.step()
        return parameter.detach().clone(), copy.deepcopy(optimizer.state_dict()), torch.random.get_rng_state().clone()

    torch.manual_seed(41)
    control_parameter, control_state, control_rng = run(None)
    torch.manual_seed(41)
    recorder = GateCreditRecorder(log_every_n_steps=1, max_sampled_steps=1)
    recorder.begin_step(1, epoch=1, source_metadata=[])
    observed_parameter, observed_state, observed_rng = run(
        lambda parameter, gradient, update, lr: recorder.observe_optimizer_update(
            "core.encoder.0", parameter, gradient, update, lr,
        )
    )
    torch.testing.assert_close(control_parameter, observed_parameter, rtol=0, atol=0)
    torch.testing.assert_close(control_rng, observed_rng, rtol=0, atol=0)
    assert control_state["param_groups"] == observed_state["param_groups"]
    for key, value in control_state["state"][0].items():
        other = observed_state["state"][0][key]
        if isinstance(value, torch.Tensor):
            torch.testing.assert_close(value, other, rtol=0, atol=0)
        else:
            assert value == other
