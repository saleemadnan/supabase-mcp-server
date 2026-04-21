from enum import Enum, IntEnum


class OperationRiskLevel(IntEnum):
    """Universal operation risk level mapping.

    Higher number reflects higher risk levels with 4 being the highest."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    EXTREME = 4


class SafetyMode(str, Enum):
    """Universal safety mode of a client (database, api, etc).
    Clients should always default to safe mode."""

    SAFE = "safe"
    UNSAFE = "unsafe"


class ClientType(str, Enum):
    """Types of clients that can be managed by the safety system."""

    DATABASE = "database"
    API = "api"
    META = "meta"
