# Step 1: Import the Citizen entity
from src.gaia.agents.citizen import Citizen


# Step 2: Define the World State
class WorldState:
    def __init__(self, width=100, height=100):
        self.width = width
        self.height = height
        self.current_tick = 0

        # Step 3: Create world entity collections
        self.citizens = []
        self.buildings = []

        # Step 4: Create world resources
        self.resources = {
            "food": 0,
            "water": 0,
            "wood": 0,
            "stone": 0,
            "metal": 0,
            "energy": 0
        }

        # Step 5: Define maximum resource capacities
        self.resource_limits = {
            "food": 1000,
            "water": 1000,
            "wood": 1000,
            "stone": 1000,
            "metal": 1000,
            "energy": 1000
        }

        # Step 6: Define basic natural resource regeneration
        self.resource_regeneration = {
            "food": 1,
            "water": 2,
            "wood": 1,
            "stone": 0,
            "metal": 0,
            "energy": 1
        }

    # Step 7: Add a citizen to the world
    def add_citizen(self, citizen):
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can be added to the world.")

        self.citizens.append(citizen)

    # Step 8: Change a world resource amount
    def change_resource(self, resource_name, amount):
        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        new_amount = self.resources[resource_name] + amount
        maximum = self.resource_limits[resource_name]

        self.resources[resource_name] = max(0, min(maximum, new_amount))

    # Step 9: Set a world resource amount
    def set_resource(self, resource_name, amount):
        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        if amount < 0:
            raise ValueError("Resource amount cannot be negative.")

        maximum = self.resource_limits[resource_name]
        self.resources[resource_name] = min(maximum, amount)

    # Step 10: Get a world resource amount
    def get_resource(self, resource_name):
        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        return self.resources[resource_name]

    # Step 11: Transfer resources from the world to a citizen
    def transfer_resource_to_citizen(self, citizen, resource_name, quantity):
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can receive resources.")

        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        available = self.get_resource(resource_name)

        if quantity > available:
            raise ValueError("Not enough resources available in the world.")

        self.change_resource(resource_name, -quantity)
        citizen.add_item(resource_name, quantity)

    # Step 12: Transfer resources from a citizen back to the world
    def transfer_resource_from_citizen(self, citizen, resource_name, quantity):
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can transfer resources.")

        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        if citizen.get_item_quantity(resource_name) < quantity:
            raise ValueError("Not enough resources in citizen inventory.")

        citizen.remove_item(resource_name, quantity)
        self.change_resource(resource_name, quantity)

    # Step 13: Consume a resource from a citizen's inventory
    def consume_resource(self, citizen, resource_name, quantity):
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can consume resources.")

        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        if citizen.get_item_quantity(resource_name) < quantity:
            raise ValueError("Not enough resources in citizen inventory.")

        citizen.remove_item(resource_name, quantity)

    # Step 14: Regenerate natural resources
    def regenerate_resources(self):
        for resource_name, amount in self.resource_regeneration.items():
            self.change_resource(resource_name, amount)

    # Step 15: Advance the world's time
    def advance_tick(self):
        self.current_tick += 1
        self.regenerate_resources()

    # Step 16: Display basic world information
    def describe(self):
        print(f"World size: {self.width} x {self.height}")
        print(f"World tick: {self.current_tick}")
        print(f"Citizens: {len(self.citizens)}")
        print(f"Buildings: {len(self.buildings)}")
        print(f"Resources: {self.resources}")


# Step 17: Run a basic world test
if __name__ == "__main__":
    world = WorldState()

    world.describe()

    world.advance_tick()

    world.describe()