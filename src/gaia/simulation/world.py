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

    # Step 5: Add a citizen to the world
    def add_citizen(self, citizen):
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can be added to the world.")

        self.citizens.append(citizen)

    # Step 6: Advance the world's time
    def advance_tick(self):
        self.current_tick += 1

    # Step 7: Display basic world information
    def describe(self):
        print(f"World size: {self.width} x {self.height}")
        print(f"World tick: {self.current_tick}")
        print(f"Citizens: {len(self.citizens)}")
        print(f"Buildings: {len(self.buildings)}")
        print(f"Resources: {self.resources}")


# Step 8: Run a basic world test
if __name__ == "__main__":
    world = WorldState()

    world.describe()

    world.advance_tick()

    world.describe()