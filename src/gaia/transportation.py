from src.gaia.agents.citizen import Citizen
from src.gaia.vehicle import Vehicle


class TransportationSystem:
    """World-owned transportation registry and travel service."""

    def __init__(self, world):
        if world is None:
            raise ValueError("World cannot be None.")

        self.world = world
        self.vehicles = []

    # Step 73: Register a vehicle with the world transportation system.
    def add_vehicle(self, vehicle):
        if not isinstance(vehicle, Vehicle):
            raise TypeError("Only Vehicle objects can be added.")

        if any(
            existing.vehicle_id == vehicle.vehicle_id
            for existing in self.vehicles
        ):
            raise ValueError("A vehicle with this ID already exists.")

        if not self.world._is_valid_location(vehicle.location):
            raise ValueError("Vehicle location is outside world bounds.")

        self.vehicles.append(vehicle)

    def remove_vehicle(self, vehicle):
        if vehicle in self.vehicles:
            self.vehicles.remove(vehicle)

    def get_vehicle(self, vehicle_id):
        for vehicle in self.vehicles:
            if vehicle.vehicle_id == vehicle_id:
                return vehicle
        return None

    def get_vehicles(self):
        return list(self.vehicles)

    # Step 74: Assign vehicle ownership.
    def set_owner(self, vehicle, owner):
        if vehicle not in self.vehicles:
            raise ValueError("Vehicle is not registered with this world.")

        if owner is not None and not isinstance(owner, Citizen):
            raise TypeError("Vehicle owner must be a Citizen or None.")

        if owner is not None and not owner.is_alive():
            raise ValueError("Dead citizens cannot own vehicles.")

        vehicle.set_owner(owner)

    # Step 74: Determine whether a citizen can use a vehicle.
    def can_use_vehicle(self, citizen, vehicle):
        if not isinstance(citizen, Citizen):
            return False
        if vehicle not in self.vehicles:
            return False
        return vehicle.can_be_used_by(citizen)

    # Step 74: Move a citizen using an available vehicle.
    def travel(self, citizen, vehicle, destination):
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can travel.")

        if not isinstance(vehicle, Vehicle):
            raise TypeError("Only Vehicle objects can be used for travel.")

        if vehicle not in self.vehicles:
            return {
                "success": False,
                "reason": "Vehicle is not registered with this world.",
            }

        if not self.can_use_vehicle(citizen, vehicle):
            return {
                "success": False,
                "reason": "Citizen cannot use this vehicle.",
            }

        if not self.world._is_valid_location(destination):
            return {
                "success": False,
                "reason": "Destination is outside world bounds.",
            }

        previous_location = citizen.location
        vehicle.move_to(destination)
        citizen.location = tuple(destination)

        return {
            "success": True,
            "citizen_id": citizen.citizen_id,
            "vehicle_id": vehicle.vehicle_id,
            "from": previous_location,
            "to": tuple(destination),
        }
