# Step 1: Define the World State
class WorldState:
    def __init__(self, width=100, height=100):
        self.width = width
        self.height = height
        self.current_tick = 0

    # Step 2: Advance the world's time
    def advance_tick(self):
        self.current_tick += 1

    # Step 3: Display basic world information
    def describe(self):
        print(f"World size: {self.width} x {self.height}")
        print(f"World tick: {self.current_tick}")


# Step 4: Run a basic world test
if __name__ == "__main__":
    world = WorldState()

    world.describe()

    world.advance_tick()

    world.describe()