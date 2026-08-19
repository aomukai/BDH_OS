from __future__ import annotations

import unittest

import pytest

torch = pytest.importorskip(
    "torch", reason="Cortex tests run in the isolated ninereeds-cortex environment",
)

from bdh import BDH, BDHConfig
from cortex import IntentionHead


class EmbeddedBDHTests(unittest.TestCase):
    def setUp(self) -> None:
        torch.manual_seed(7)
        self.config = BDHConfig(
            n_layer=2,
            n_embd=16,
            n_head=4,
            mlp_internal_dim_multiplier=4,
            vocab_size=32,
            dropout=0.0,
        )
        self.model = BDH(self.config).eval()

    def test_token_and_preembedded_paths_are_identical(self) -> None:
        token_ids = torch.tensor([[1, 2, 3, 4]])
        with torch.no_grad():
            token_logits, _ = self.model(token_ids)
            embedded_logits, _ = self.model.forward_embeds(self.model.embed(token_ids))
        torch.testing.assert_close(token_logits, embedded_logits, rtol=0, atol=0)

    def test_encode_embeds_returns_native_width(self) -> None:
        observations = torch.randn(2, 5, self.config.n_embd)
        hidden = self.model.encode_embeds(observations)
        self.assertEqual(tuple(hidden.shape), (2, 5, self.config.n_embd))

    def test_wrong_ingress_width_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "embedding width"):
            self.model.encode_embeds(torch.randn(1, 3, self.config.n_embd + 1))

    def test_per_layer_core_can_be_partitioned(self) -> None:
        config = BDHConfig(
            n_layer=4,
            n_embd=16,
            n_head=4,
            mlp_internal_dim_multiplier=4,
            vocab_size=32,
            per_layer_weights=True,
            dropout=0.0,
        )
        model = BDH(config).eval()
        report = model.partition_layers(
            [torch.device("cpu"), torch.device("cpu")],
            split_at=2,
            dtype=torch.float32,
        )
        output = model.encode_embeds(torch.randn(1, 5, 16))
        self.assertEqual(tuple(output.shape), (1, 5, 16))
        self.assertEqual(report["split_at"], 2)


class IntentionHeadTests(unittest.TestCase):
    def test_intentions_have_fixed_length_and_backpropagate(self) -> None:
        head = IntentionHead(width=16, num_tokens=3, num_heads=4)
        hidden = torch.randn(2, 7, 16, requires_grad=True)
        mask = torch.tensor([[1, 1, 1, 1, 0, 0, 0], [1, 1, 1, 1, 1, 1, 1]])
        intentions = head(hidden, mask)
        self.assertEqual(tuple(intentions.shape), (2, 3, 16))
        intentions.square().mean().backward()
        self.assertIsNotNone(hidden.grad)


if __name__ == "__main__":
    unittest.main()
