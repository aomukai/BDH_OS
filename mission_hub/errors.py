"""Mission Hub error taxonomy."""


class MissionHubError(RuntimeError):
    """Base class for expected Mission Hub failures."""


class ConfigError(MissionHubError):
    """Configuration is absent, inconsistent, or invalid."""


class ConflictError(MissionHubError):
    """An idempotency or optimistic-concurrency invariant was violated."""


class NotFoundError(MissionHubError):
    """A requested durable entity does not exist."""


class TransitionError(MissionHubError):
    """A lifecycle transition is not legal from the current state."""


class SafetyError(MissionHubError):
    """A safety policy refused an action."""


class ProtocolError(MissionHubError):
    """A machine-boundary envelope is invalid or incompatible."""


class EvidenceError(MissionHubError):
    """Legacy evidence could not be preserved without ambiguity."""
