import math


# Step 73: Define the vehicle entity.
class Vehicle:
    """Persistent transportation entity managed by the simulation world."""

    VALID_STATES = {"operational", "disabled", "destroyed"}

    def __init__(
        self,
        vehicle_id,
        vehicle_type,
        location=(0, 0),
        owner=None,
        operational_state="operational",
        speed=1.0,
        destination=None,
    ):
        if not vehicle_id:
            raise ValueError("Vehicle ID cannot be empty.")
        if not vehicle_type:
            raise ValueError("Vehicle type cannot be empty.")
        if not isinstance(location, (tuple, list)) or len(location) != 2:
            raise ValueError("Vehicle location must contain two coordinates.")
        if operational_state not in self.VALID_STATES:
            raise ValueError("Invalid vehicle operational state.")
        if isinstance(speed, bool):
            raise ValueError("Vehicle speed must be greater than zero.")
        try:
            speed = float(speed)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("Vehicle speed must be a finite positive number.") from error
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError("Vehicle speed must be a finite positive number.")

        self.vehicle_id = vehicle_id
        self.vehicle_type = vehicle_type
        self.location = tuple(location)
        self.owner = owner
        self.operational_state = operational_state
        self.speed = speed
        self.destination = None
        if destination is not None:
            self.set_destination(destination)

    # Step 73: Determine whether the vehicle can currently travel.
    def is_operational(self):
        return self.operational_state == "operational"

    def set_owner(self, owner):
        self.owner = owner

    def can_be_used_by(self, citizen):
        if citizen is None or not citizen.is_alive():
            return False
        if not self.is_operational():
            return False
        return self.owner is None or self.owner is citizen

    def move_to(self, location):
        if not self.is_operational():
            return False
        self.location = self._coordinate(location, "Vehicle location")
        self.destination = None
        return True

    def set_destination(self, destination):
        """Set a world-space movement target; the transportation system checks bounds."""
        if not self.is_operational():
            return False
        self.destination = self._coordinate(destination, "Vehicle destination")
        return True

    def advance_movement(self, world):
        """Move at most ``speed`` world units toward the assigned destination."""
        if not self.is_operational() or self.destination is None:
            return False
        if not world._is_valid_location(self.location):
            return False
        if not world._is_valid_location(self.destination):
            return False

        x, y = self.location
        target_x, target_y = self.destination
        dx, dy = target_x - x, target_y - y
        distance = math.hypot(dx, dy)
        if distance == 0:
            self.location = tuple(self.destination)
            self.destination = None
            return False
        if distance <= self.speed:
            self.location = tuple(self.destination)
            self.destination = None
        else:
            scale = self.speed / distance
            self.location = (x + dx * scale, y + dy * scale)
        return True

    @staticmethod
    def _coordinate(value, label):
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError(f"{label} must contain two coordinates.")
        if any(
            isinstance(coordinate, bool)
            or not isinstance(coordinate, (int, float))
            or not math.isfinite(coordinate)
            for coordinate in value
        ):
            raise ValueError(f"{label} coordinates must be finite numbers.")
        return tuple(value)

    def __repr__(self):
        return (
            f"Vehicle(vehicle_id={self.vehicle_id!r}, "
            f"vehicle_type={self.vehicle_type!r}, "
            f"location={self.location!r})"
        )
