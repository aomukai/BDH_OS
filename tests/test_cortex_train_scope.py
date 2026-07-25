from __future__ import annotations

import torch
from torch import nn

from cortex.student import CortexStudent


def _stub_student() -> CortexStudent:
    student = CortexStudent.__new__(CortexStudent)
    nn.Module.__init__(student)
    student.core = nn.Linear(4, 4)
    student.ingress = nn.Module()
    student.ingress.projector = nn.Linear(4, 4)
    student.intention = nn.Linear(4, 4)
    student.expression = nn.Module()
    student.expression.projector = nn.Linear(4, 4)
    return student


def test_expression_bridge_scope_freezes_core_and_ingress() -> None:
    student = _stub_student()

    result = student.set_train_scope("expression_bridge")

    assert result["scope"] == "expression_bridge"
    assert not any(parameter.requires_grad for parameter in student.core.parameters())
    assert not any(
        parameter.requires_grad for parameter in student.ingress.projector.parameters()
    )
    assert all(parameter.requires_grad for parameter in student.intention.parameters())
    assert all(
        parameter.requires_grad
        for parameter in student.expression.projector.parameters()
    )
    assert list(student.trainable_parameters())


def test_unknown_cortex_train_scope_is_rejected() -> None:
    student = _stub_student()
    try:
        student.set_train_scope("core_bypass")
    except ValueError as exc:
        assert "unsupported Cortex train scope" in str(exc)
    else:
        raise AssertionError("unsupported train scope was accepted")
