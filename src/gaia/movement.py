"""Renderer-neutral, serializable requests for citizen movement."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class MovementIntent:
    """A destination request; accepting it does not move the citizen.

    ``destination`` is a world-space ``(x, y)`` point using the simulation's
    top-left origin, rightward X, downward Y coordinate convention. World
    bounds validation belongs to Simulation because it depends on a world.
    Optional target identifiers are descriptive references resolved by the
    Simulation; no engine objects are retained by this value.
    """

    destination: tuple
    reason: str = ""
    target_kind: str | None = None
    target_id: str | None = None

    def __post_init__(self):
        if not isinstance(self.destination, (tuple, list)) or len(self.destination) != 2:
            raise ValueError("Movement destination must contain two coordinates.")
        coordinates = []
        for value in self.destination:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Movement coordinates must be finite numbers.")
            value = float(value)
            if not math.isfinite(value):
                raise ValueError("Movement coordinates must be finite numbers.")
            coordinates.append(value)
        if not isinstance(self.reason, str):
            raise ValueError("Movement reason must be a string.")
        if (self.target_kind is None) != (self.target_id is None):
            raise ValueError("Movement target kind and ID must be provided together.")
        if self.target_kind is not None:
            if not isinstance(self.target_kind, str) or not self.target_kind:
                raise ValueError("Movement target kind cannot be empty.")
            if not isinstance(self.target_id, str) or not self.target_id:
                raise ValueError("Movement target ID cannot be empty.")
        object.__setattr__(self, "destination", tuple(coordinates))

    def to_dict(self):
        """Return a detached JSON-compatible description."""
        return {
            "destination": self.destination,
            "reason": self.reason,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
        }


@dataclass(frozen=True)
class MovementState:
    """Read-only movement status exposed by the Simulation to adapters."""

    status: str
    intent: MovementIntent | None = None
