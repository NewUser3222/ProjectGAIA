# Step 1: Define the World State
class WorldState:
    def __init__(self, width=100, height=100):
        self.width = width
        self.height = height
        self.current_tick = 0

        # Step 2: Create world entity collections
        self.citizens = []
        self.buildings = []

        # Step 3: Create world resources
        self.resources = {
            "food": 0,
            "water": 0,
            "wood": 0,
            "stone": 0,
            "metal": 0,
            "energy": 0
        }

    # Step 4: Advance the world's time
    def advance_tick(self):
        self.current_tick += 1

    # Step 5: Display basic world information
    def describe(self):
        print(f"World size: {self.width} x {self.height}")
        print(f"World tick: {self.current_tick}")
        print(f"Citizens: {len(self.citizens)}")
        print(f"Buildings: {len(self.buildings)}")
        print(f"Resources: {self.resources}")


# Step 6: Run a basic world test
if __name__ == "__main__":
    world = WorldState()

    world.describe()

    world.advance_tick()

    world.describe()