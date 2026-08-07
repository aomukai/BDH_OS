# Copyright 2025 Pathway Technology, Inc.

import dataclasses
import math

import torch
import torch.nn.functional as F
from torch import nn


@dataclasses.dataclass
class BDHConfig:
    """Configuration for the BDH reference model.

    The default values preserve the upstream-style BDH implementation in this
    repository. Experimental fields are intentionally opt-in so older
    checkpoints and baseline training runs do not silently change behavior.

    Experimental variants:
    - ``bdh_v1``: default behavior; all temporal additions disabled.
    - ``temporal_decay``: enables causal attention distance decay.
    - ``ctm_lite``: enables the cheap CTM-inspired temporal knobs below.
    """

    n_layer: int = 6
    n_embd: int = 256
    dropout: float = 0.1
    n_head: int = 4
    mlp_internal_dim_multiplier: int = 128
    vocab_size: int = 256
    per_layer_weights: bool = False
    architecture_variant: str = "bdh_v1"

    # CTM-inspired temporal memory: mix each sparse activation vector with a
    # causal history of previous sparse activations before attention/MLP use.
    # 0.0 disables the path exactly.
    activation_history_mix: float = 0.0
    activation_history_decay: float = 0.5
    activation_history_target: str = "x"
    activation_history_max_mix: float = 0.5
    learned_activation_history: bool = False

    # Distance decay for causal attention. None disables the path exactly.
    # Values are positive decay rates; larger values forget distant tokens more.
    attention_decay: float | None = None
    learned_attention_decay: bool = False

    # Fixed whole-stack recurrent passes. A value of 1 is the original model.
    compute_ticks: int = 1

    # Inference-only adaptive compute. Generation can stop early when the last
    # token distribution stabilizes across compute ticks. The architecture
    # variants do not enable this automatically; set it for generation/eval
    # policy experiments.
    adaptive_compute: bool = False
    adaptive_min_ticks: int = 1
    adaptive_max_ticks: int = 1
    adaptive_logit_delta_threshold: float = 0.0


def bdh_v1_config(**overrides) -> BDHConfig:
    """Return the unchanged baseline BDH configuration."""
    return BDHConfig(**overrides)


def bdh_temporal_decay_config(**overrides) -> BDHConfig:
    """Return BDH with only causal attention distance decay enabled.

    This is the narrowest controlled variant: it tests whether explicit
    forgetting of distant activations improves stability without adding
    activation-history or adaptive-compute paths.
    """
    values = {
        "architecture_variant": "temporal_decay",
        "attention_decay": 0.001,
    }
    values.update(overrides)
    return BDHConfig(**values)


def bdh_ctm_lite_config(**overrides) -> BDHConfig:
    """Return the CTM-inspired BDH variant for exploratory runs.

    This combines two lightweight temporal mechanisms: causal attention decay
    and sparse activation history. Training still uses fixed compute ticks
    unless ``compute_ticks`` is explicitly raised above 1. Adaptive generation
    is intentionally left disabled unless requested separately.
    """
    values = {
        "architecture_variant": "ctm_lite",
        "attention_decay": 0.001,
        "activation_history_mix": 0.1,
        "activation_history_decay": 0.5,
        "activation_history_target": "x",
        "compute_ticks": 1,
    }
    values.update(overrides)
    return BDHConfig(**values)


def get_freqs(n, theta, dtype):
    def quantize(t, q=2):
        return (t / q).floor() * q

    return (
        1.0
        / (theta ** (quantize(torch.arange(0, n, 1, dtype=dtype)) / n))
        / (2 * math.pi)
    )


class Attention(torch.nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config
        nh = config.n_head
        D = config.n_embd
        N = config.mlp_internal_dim_multiplier * D // nh
        self.freqs = torch.nn.Buffer(
            get_freqs(N, theta=2**16, dtype=torch.float32).view(1, 1, 1, N)
        )
        if config.attention_decay is not None and config.learned_attention_decay:
            raw_decay = math.log(math.expm1(max(float(config.attention_decay), 1e-6)))
            decay = torch.full((nh, 1, 1), raw_decay)
            self.attention_decay = nn.Parameter(decay)
        else:
            self.attention_decay = None

    @staticmethod
    def phases_cos_sin(phases):
        phases = (phases % 1) * (2 * math.pi)
        phases_cos = torch.cos(phases)
        phases_sin = torch.sin(phases)
        return phases_cos, phases_sin

    @staticmethod
    def rope(phases, v):
        v_rot = torch.stack((-v[..., 1::2], v[..., ::2]), dim=-1).view(*v.size())
        phases_cos, phases_sin = Attention.phases_cos_sin(phases)
        return (v * phases_cos).to(v.dtype) + (v_rot * phases_sin).to(v.dtype)

    def forward(self, Q, K, V):
        assert self.freqs.dtype == torch.float32
        assert K is Q
        _, _, T, _ = Q.size()
        freqs = self.freqs.to(Q.device)

        r_phases = (
            torch.arange(
                0,
                T,
                device=Q.device,
                dtype=freqs.dtype,
            ).view(1, 1, -1, 1)
        ) * freqs
        QR = self.rope(r_phases, Q)
        KR = QR

        # Current attention
        scores = (QR @ KR.mT).tril(diagonal=-1)
        if self.config.attention_decay is not None:
            if self.attention_decay is None:
                decay = torch.as_tensor(
                    self.config.attention_decay,
                    device=scores.device,
                    dtype=scores.dtype,
                )
            else:
                decay = F.softplus(self.attention_decay).to(scores.dtype)

            positions = torch.arange(T, device=scores.device)
            distance = (positions.view(T, 1) - positions.view(1, T)).clamp_min(0)
            decay_mask = torch.exp(-decay * distance.to(scores.dtype))
            scores = scores * decay_mask.view(1, -1, T, T)
        return scores @ V


class BDH(nn.Module):
    def __init__(self, config: BDHConfig):
        super().__init__()
        assert config.vocab_size is not None
        self._fill_missing_config_defaults(config)
        self._validate_config(config)
        self.config = config
        nh = config.n_head
        D = config.n_embd
        N = config.mlp_internal_dim_multiplier * D // nh
        if config.per_layer_weights:
            self.decoder = nn.ParameterList(
                [nn.Parameter(torch.zeros((nh * N, D)).normal_(std=0.02)) for _ in range(config.n_layer)]
            )
            self.encoder = nn.ParameterList(
                [nn.Parameter(torch.zeros((nh, D, N)).normal_(std=0.02)) for _ in range(config.n_layer)]
            )
            self.encoder_v = nn.ParameterList(
                [nn.Parameter(torch.zeros((nh, D, N)).normal_(std=0.02)) for _ in range(config.n_layer)]
            )
        else:
            self.decoder = nn.Parameter(torch.zeros((nh * N, D)).normal_(std=0.02))
            self.encoder = nn.Parameter(torch.zeros((nh, D, N)).normal_(std=0.02))
            self.encoder_v = nn.Parameter(torch.zeros((nh, D, N)).normal_(std=0.02))

        self.attn = Attention(config)
        if config.learned_activation_history and config.activation_history_mix != 0.0:
            max_mix = max(float(config.activation_history_max_mix), 1e-6)
            bounded_mix = max(min(float(config.activation_history_mix), max_mix * 0.999), 1e-6)
            mix_ratio = bounded_mix / max_mix
            raw_mix = math.log(mix_ratio / (1.0 - mix_ratio))
            bounded_decay = max(min(float(config.activation_history_decay), 0.999), 0.001)
            raw_decay = math.log(bounded_decay / (1.0 - bounded_decay))
            self.activation_history_mix = nn.Parameter(
                torch.full((nh, 1, 1), raw_mix)
            )
            self.activation_history_decay = nn.Parameter(
                torch.full((nh, 1, 1), raw_decay)
            )
        else:
            self.activation_history_mix = None
            self.activation_history_decay = None

        self.ln = nn.LayerNorm(D, elementwise_affine=False, bias=False)
        self.embed = nn.Embedding(config.vocab_size, D)
        self.drop = nn.Dropout(config.dropout)

        self.lm_head = nn.Parameter(
            torch.zeros((D, config.vocab_size)).normal_(std=0.02)
        )

        self.apply(self._init_weights)

    @staticmethod
    def _fill_missing_config_defaults(config: BDHConfig):
        for field in dataclasses.fields(BDHConfig):
            if hasattr(config, field.name):
                continue
            if field.default is not dataclasses.MISSING:
                setattr(config, field.name, field.default)
            elif field.default_factory is not dataclasses.MISSING:
                setattr(config, field.name, field.default_factory())

    @staticmethod
    def _validate_config(config: BDHConfig):
        valid_variants = {"bdh_v1", "temporal_decay", "ctm_lite"}
        if config.architecture_variant not in valid_variants:
            raise ValueError(
                f"architecture_variant must be one of {sorted(valid_variants)}, "
                f"got {config.architecture_variant!r}."
            )
        if config.compute_ticks < 1:
            raise ValueError("compute_ticks must be >= 1.")
        if config.adaptive_min_ticks < 1:
            raise ValueError("adaptive_min_ticks must be >= 1.")
        if config.adaptive_max_ticks < config.adaptive_min_ticks:
            raise ValueError("adaptive_max_ticks must be >= adaptive_min_ticks.")
        if not 0.0 <= config.activation_history_decay <= 1.0:
            raise ValueError("activation_history_decay must be in [0, 1].")
        valid_history_targets = {"x", "y", "both", "pre_gate"}
        if config.activation_history_target not in valid_history_targets:
            raise ValueError(
                "activation_history_target must be one of "
                f"{sorted(valid_history_targets)}, got {config.activation_history_target!r}."
            )
        if config.activation_history_max_mix <= 0:
            raise ValueError("activation_history_max_mix must be > 0.")
        if config.attention_decay is not None and config.attention_decay < 0:
            raise ValueError("attention_decay must be >= 0 when enabled.")

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def _apply_activation_history(self, x_sparse):
        C = self.config
        if C.activation_history_mix == 0.0:
            return x_sparse

        if self.activation_history_mix is None:
            mix = torch.as_tensor(
                C.activation_history_mix,
                device=x_sparse.device,
                dtype=x_sparse.dtype,
            )
            decay = torch.as_tensor(
                C.activation_history_decay,
                device=x_sparse.device,
                dtype=x_sparse.dtype,
            )
        else:
            max_mix = torch.as_tensor(
                C.activation_history_max_mix,
                device=x_sparse.device,
                dtype=x_sparse.dtype,
            )
            mix = torch.sigmoid(self.activation_history_mix).to(x_sparse.dtype) * max_mix
            decay = torch.sigmoid(self.activation_history_decay).to(x_sparse.dtype)

        history = torch.zeros_like(x_sparse)
        running = torch.zeros_like(x_sparse[:, :, 0, :])
        for t in range(x_sparse.size(2)):
            history[:, :, t, :] = running
            running = decay * running + (1.0 - decay) * x_sparse[:, :, t, :]
        return x_sparse + mix * history

    @staticmethod
    def _activation_stats(name, tensor):
        active = tensor > 0
        density = active.to(torch.float32).mean()
        magnitude = tensor.detach().abs().mean()
        return {
            f"{name}_density": float(density.detach().cpu()),
            f"{name}_mean_abs": float(magnitude.detach().cpu()),
        }

    def _layer_block(
        self, x, level, B, T, N, nh, collect_diagnostics=False,
        gate_credit_observer=None, tick=1,
    ):
        C = self.config
        if C.per_layer_weights:
            encoder = self.encoder[level]
            encoder_v = self.encoder_v[level]
            decoder = self.decoder[level]
            x = x.to(device=encoder.device, dtype=encoder.dtype)
        else:
            encoder = self.encoder
            encoder_v = self.encoder_v
            decoder = self.decoder

        x_latent = x @ encoder

        x_sparse = F.relu(x_latent)  # B, nh, T, N
        x_base_sparse = x_sparse
        if C.activation_history_target in {"x", "both"}:
            x_sparse = self._apply_activation_history(x_sparse)

        yKV = self.attn(
            Q=x_sparse,
            K=x_sparse,
            V=x,
        )
        yKV = self.ln(yKV)

        y_latent = yKV @ encoder_v
        y_sparse = F.relu(y_latent)
        y_base_sparse = y_sparse
        if C.activation_history_target in {"y", "both"}:
            y_sparse = self._apply_activation_history(y_sparse)
        if C.activation_history_target == "pre_gate":
            x_sparse = self._apply_activation_history(x_base_sparse)
            y_sparse = self._apply_activation_history(y_base_sparse)
        xy_sparse = x_sparse * y_sparse  # B, nh, T, N
        raw_xy_sparse = xy_sparse

        xy_sparse = self.drop(xy_sparse)
        if gate_credit_observer is not None:
            gate_credit_observer.observe_gate(
                layer=level, tick=tick, raw_gate=raw_xy_sparse,
                effective_gate=xy_sparse,
            )

        yMLP = (
            xy_sparse.transpose(1, 2).reshape(B, 1, T, N * nh) @ decoder
        )  # B, 1, T, D
        y = self.ln(yMLP)
        x_next = self.ln(x + y)
        if not collect_diagnostics:
            return x_next, None

        diagnostics = {
            "layer": level,
            **self._activation_stats("x_sparse", x_sparse),
            **self._activation_stats("y_sparse", y_sparse),
            **self._activation_stats("xy_sparse", xy_sparse),
        }
        fire_rates = (xy_sparse > 0).to(torch.float32).mean(dim=(0, 2))
        mean_abs = xy_sparse.detach().abs().to(torch.float32).mean(dim=(0, 2))
        neuron_scores = fire_rates * torch.log1p(mean_abs)
        top_count = min(16, int((neuron_scores > 0).sum().detach().cpu()))
        top_values, top_indices = torch.topk(neuron_scores.reshape(-1), top_count)
        diagnostics["top_neurons"] = [
            {
                "head": int(index // N),
                "neuron": int(index % N),
                "fire_rate": float(fire_rates.reshape(-1)[index].detach().cpu()),
                "mean_abs": float(mean_abs.reshape(-1)[index].detach().cpu()),
                "score": float(score.detach().cpu()),
            }
            for score, index in zip(top_values, top_indices, strict=True)
        ]
        return x_next, diagnostics

    def _initial_state(self, idx):
        return self._initial_state_from_embeddings(self.embed(idx))

    def _initial_state_from_embeddings(self, embeddings):
        """Build BDH state from observations already expressed at ``n_embd``.

        The normal byte-token path still enters through ``self.embed`` above.  This
        second entrance is for frozen sensory cortexes (for example LFM Encoder or
        SigLIP2) whose observations have been projected into Ninereeds' native
        width.  Keeping the projection outside BDH preserves the baseline model
        and checkpoint format.
        """
        C = self.config
        if embeddings.ndim != 3:
            raise ValueError(
                "embeddings must have shape [batch, sequence, n_embd], "
                f"got {tuple(embeddings.shape)}"
            )
        B, T, D = embeddings.size()
        if D != C.n_embd:
            raise ValueError(
                f"embedding width must equal config.n_embd ({C.n_embd}), got {D}"
            )
        nh = C.n_head
        N = D * C.mlp_internal_dim_multiplier // nh

        x = embeddings.unsqueeze(1)

        # The layer norm is part of the original token path and must also define
        # the scale expected from projected sensory observations.
        return self.ln(x), B, T, D, nh, N  # B, 1, T, D

    def _run_one_tick(
        self, x, B, T, N, nh, collect_diagnostics=False,
        gate_credit_observer=None, tick=1,
    ):
        diagnostics = []
        for level in range(self.config.n_layer):
            x, layer_diagnostics = self._layer_block(
                x,
                level,
                B,
                T,
                N,
                nh,
                collect_diagnostics=collect_diagnostics,
                gate_credit_observer=gate_credit_observer,
                tick=tick,
            )
            if layer_diagnostics is not None:
                diagnostics.append(layer_diagnostics)
        return x, diagnostics

    def _forward_hidden_from_state(
        self, x, B, T, D, nh, N, compute_ticks=None,
        gate_credit_observer=None,
    ):
        C = self.config
        ticks = C.compute_ticks if compute_ticks is None else compute_ticks
        if ticks < 1:
            raise ValueError("compute_ticks must be >= 1.")

        for tick in range(ticks):
            x, _ = self._run_one_tick(
                x, B, T, N, nh,
                gate_credit_observer=gate_credit_observer,
                tick=tick + 1,
            )

        return x.view(B, T, D)

    def _forward_hidden(self, idx, compute_ticks=None):
        state = self._initial_state(idx)
        return self._forward_hidden_from_state(*state, compute_ticks=compute_ticks)

    def _forward_hidden_embeds(
        self, embeddings, compute_ticks=None, gate_credit_observer=None,
    ):
        state = self._initial_state_from_embeddings(embeddings)
        return self._forward_hidden_from_state(
            *state, compute_ticks=compute_ticks,
            gate_credit_observer=gate_credit_observer,
        )

    def _forward_logits(self, idx, compute_ticks=None):
        hidden = self._forward_hidden(idx, compute_ticks=compute_ticks)
        return hidden @ self.lm_head

    def encode(self, idx, compute_ticks=None):
        """Return contextual Ninereeds states without applying the byte LM head."""
        return self._forward_hidden(idx, compute_ticks=compute_ticks)

    def encode_embeds(
        self, embeddings, compute_ticks=None, gate_credit_observer=None,
    ):
        """Process projected sensory observations and return Ninereeds states."""
        return self._forward_hidden_embeds(
            embeddings, compute_ticks=compute_ticks,
            gate_credit_observer=gate_credit_observer,
        )

    @torch.no_grad()
    def encode_embeds_with_diagnostics(self, embeddings, compute_ticks=None):
        """Return embedded-input states together with per-layer activation health.

        This is the Cortex-native counterpart to :meth:`diagnostics`.  It avoids
        the byte embedding and language-model head, neither of which participates
        in the LFM Encoder -> Ninereeds -> LFM path.
        """
        C = self.config
        ticks = C.compute_ticks if compute_ticks is None else compute_ticks
        if ticks < 1:
            raise ValueError("compute_ticks must be >= 1.")
        was_training = self.training
        self.eval()
        try:
            x, B, T, D, nh, N = self._initial_state_from_embeddings(embeddings)
            all_layers = []
            previous = None
            hidden_deltas = []
            for tick in range(ticks):
                x, layer_stats = self._run_one_tick(
                    x,
                    B,
                    T,
                    N,
                    nh,
                    collect_diagnostics=True,
                )
                for stats in layer_stats:
                    stats["tick"] = tick + 1
                    all_layers.append(stats)
                hidden = x.view(B, T, D)
                if previous is not None:
                    delta = (hidden - previous).abs().mean()
                    hidden_deltas.append(float(delta.detach().cpu()))
                previous = hidden.detach()
            return hidden, {
                "hidden_mean_abs": float(hidden.detach().abs().mean().cpu()),
                "hidden_std": float(hidden.detach().to(torch.float32).std().cpu()),
                "hidden_delta_mean": (
                    sum(hidden_deltas) / len(hidden_deltas)
                    if hidden_deltas
                    else 0.0
                ),
                "attention_half_life_tokens": self.attention_half_life_tokens(),
                "layers": all_layers,
            }
        finally:
            self.train(was_training)

    def partition_layers(
        self,
        devices,
        *,
        split_at=None,
        dtype=None,
    ):
        """Place a per-layer BDH across two devices without parameter gathers.

        The activation sequence crosses the device boundary once in the forward
        pass (and once during backward). This is intentionally narrower than
        FSDP and matches the current dual-3060 x16/x4 topology.
        """
        if not self.config.per_layer_weights:
            raise ValueError("layer partitioning requires per_layer_weights=True")
        if len(devices) != 2:
            raise ValueError("exactly two layer devices are required")
        boundary = self.config.n_layer // 2 if split_at is None else int(split_at)
        if not 0 < boundary < self.config.n_layer:
            raise ValueError("split_at must be inside the layer range")
        for level in range(self.config.n_layer):
            device = devices[0] if level < boundary else devices[1]
            for collection in (self.encoder, self.encoder_v, self.decoder):
                parameter = collection[level]
                parameter.data = parameter.data.to(device=device, dtype=dtype)
        self.embed.to(device=devices[0], dtype=dtype)
        self.lm_head.data = self.lm_head.data.to(device=devices[1], dtype=dtype)
        if self.activation_history_mix is not None:
            self.activation_history_mix.data = self.activation_history_mix.data.to(devices[0])
        if self.activation_history_decay is not None:
            self.activation_history_decay.data = self.activation_history_decay.data.to(devices[0])
        if self.attn.attention_decay is not None:
            self.attn.attention_decay.data = self.attn.attention_decay.data.to(devices[0])
        return {
            "split_at": boundary,
            "devices": [str(device) for device in devices],
            "layer_devices": [
                str(self.encoder[level].device) for level in range(self.config.n_layer)
            ],
        }

    @torch.no_grad()
    def diagnostics(self, idx):
        C = self.config
        was_training = self.training
        self.eval()
        try:
            x, B, T, D, nh, N = self._initial_state(idx)
            all_layers = []
            last_logits = None
            logit_deltas = []
            for tick in range(C.compute_ticks):
                x, layer_stats = self._run_one_tick(
                    x,
                    B,
                    T,
                    N,
                    nh,
                    collect_diagnostics=True,
                )
                for stats in layer_stats:
                    stats["tick"] = tick + 1
                    all_layers.append(stats)
                logits = x.view(B, T, D) @ self.lm_head
                if last_logits is not None:
                    delta = (logits[:, -1, :] - last_logits[:, -1, :]).abs().mean()
                    logit_deltas.append(float(delta.detach().cpu()))
                last_logits = logits

            probs = F.softmax(last_logits[:, -1, :], dim=-1)
            entropy = -(probs * torch.log(probs.clamp_min(1e-12))).sum(dim=-1).mean()
            summary = {
                "logit_entropy": float(entropy.detach().cpu()),
                "logit_delta_mean": sum(logit_deltas) / len(logit_deltas) if logit_deltas else 0.0,
                "attention_half_life_tokens": self.attention_half_life_tokens(),
                "layers": all_layers,
            }
            return summary
        finally:
            self.train(was_training)

    def attention_half_life_tokens(self):
        if self.config.attention_decay is None:
            return None
        if self.attn.attention_decay is None:
            decay = float(self.config.attention_decay)
        else:
            decay = float(F.softplus(self.attn.attention_decay).detach().mean().cpu())
        if decay <= 0:
            return None
        return math.log(2.0) / decay

    def forward(self, idx, targets=None, compute_ticks=None):
        logits = self._forward_logits(idx, compute_ticks=compute_ticks)
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))

        return logits, loss

    def forward_embeds(self, embeddings, targets=None, compute_ticks=None):
        """Run projected observations through BDH using the existing byte head.

        The byte head is retained here for controlled ingress-only experiments.
        The eventual LFM expression path should consume ``encode_embeds`` through
        a separate intention head instead.
        """
        hidden = self._forward_hidden_embeds(embeddings, compute_ticks=compute_ticks)
        logits = hidden @ self.lm_head
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        return logits, loss

    def _adaptive_next_logits(self, idx):
        C = self.config
        x, B, T, D, nh, N = self._initial_state(idx)
        previous = None
        logits = None
        for tick in range(1, C.adaptive_max_ticks + 1):
            x, _ = self._run_one_tick(x, B, T, N, nh)
            logits = (x.view(B, T, D) @ self.lm_head)[:, -1, :]
            if (
                tick >= C.adaptive_min_ticks
                and previous is not None
                and C.adaptive_logit_delta_threshold > 0
            ):
                delta = (logits - previous).abs().mean(dim=-1).max()
                if delta <= C.adaptive_logit_delta_threshold:
                    break
            previous = logits
        return logits

    @torch.no_grad()
    def generate(
        self,
        idx: torch.Tensor,
        max_new_tokens: int,
        temperature: float = 1.0,
        top_k: int | None = None,
    ) -> torch.Tensor:
        was_training = self.training
        self.eval()
        try:
            for _ in range(max_new_tokens):
                idx_cond = idx
                if self.config.adaptive_compute and self.config.adaptive_max_ticks > 1:
                    logits = self._adaptive_next_logits(idx_cond)
                else:
                    logits, _ = self(idx_cond)
                    logits = logits[:, -1, :]
                logits = logits / temperature
                if top_k is not None:
                    values, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                    logits[logits < values[:, [-1]]] = float("-inf")
                probs = F.softmax(logits, dim=-1)
                idx_next = torch.multinomial(probs, num_samples=1)
                idx = torch.cat((idx, idx_next), dim=1)
            return idx
        finally:
            self.train(was_training)
