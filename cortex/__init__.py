"""Frozen sensory/expression cortex interfaces for Ninereeds experiments."""

from .config import CortexConfig
from .intention import IntentionHead
from .student import CortexStudent

__all__ = ["CortexConfig", "CortexStudent", "IntentionHead"]
