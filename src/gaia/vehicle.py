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
    ):
        if not vehicle_id:
            raise ValueError("Vehicle ID cannot be empty.")
        if not vehicle_type:
            raise ValueError("Vehicle type cannot be empty.")
        if not isinstance(location, (tuple, list)) or len(location) != 2:
            raise ValueError("Vehicle location must contain two coordinates.")
        if operational_state not in self.VALID_STATES:
            raise ValueError("Invalid vehicle operational state.")
        if speed <= 0:
            raise ValueError("Vehicle speed must be greater than zero.")

        self.vehicle_id = vehicle_id
        self.vehicle_type = vehicle_type
        self.location = tuple(location)
        self.owner = owner
        self.operational_state = operational_state
        self.speed = float(speed)

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
        if not isinstance(location, (tuple, list)) or len(location) != 2:
            raise ValueError("Vehicle destination must contain two coordinates.")
        self.location = tuple(location)
        return True

    def __repr__(self):
        return (
            f"Vehicle(vehicle_id={self.vehicle_id!r}, "
            f"vehicle_type={self.vehicle_type!r}, "
            f"location={self.location!r})"
        )
