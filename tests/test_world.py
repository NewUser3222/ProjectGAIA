# Step 1: Import the unittest framework
import unittest


# Step 2: Import the World State
from src.gaia.simulation.world import WorldState


# Step 3: Define World State tests
class TestWorldState(unittest.TestCase):

    # Step 4: Test the default world dimensions
    def test_default_dimensions(self):
        world = WorldState()

        self.assertEqual(world.width, 100)
        self.assertEqual(world.height, 100)

    # Step 5: Test the initial world tick
    def test_initial_tick(self):
        world = WorldState()

        self.assertEqual(world.current_tick, 0)

    # Step 6: Test advancing the world
    def test_advance_tick(self):
        world = WorldState()

        world.advance_tick()

        self.assertEqual(world.current_tick, 1)

    # Step 7: Test initial entities
    def test_initial_entities(self):
        world = WorldState()

        self.assertEqual(len(world.citizens), 0)
        self.assertEqual(len(world.buildings), 0)

    # Step 8: Test initial resources
    def test_initial_resources(self):
        world = WorldState()

        self.assertEqual(world.resources["food"], 0)
        self.assertEqual(world.resources["water"], 0)
        self.assertEqual(world.resources["wood"], 0)
        self.assertEqual(world.resources["stone"], 0)
        self.assertEqual(world.resources["metal"], 0)
        self.assertEqual(world.resources["energy"], 0)


# Step 9: Run the tests
if __name__ == "__main__":
    unittest.main()