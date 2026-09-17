# Step 1: Import the unittest framework
import unittest


# Step 2: Import the World State
from src.gaia.simulation.world import WorldState


# Step 3: Import the Citizen entity
from src.gaia.agents.citizen import Citizen


# Step 4: Define World State tests
class TestWorldState(unittest.TestCase):

    # Step 5: Test the default world dimensions
    def test_default_dimensions(self):
        world = WorldState()

        self.assertEqual(world.width, 100)
        self.assertEqual(world.height, 100)

    # Step 6: Test the initial world tick
    def test_initial_tick(self):
        world = WorldState()

        self.assertEqual(world.current_tick, 0)

    # Step 7: Test advancing the world
    def test_advance_tick(self):
        world = WorldState()

        world.advance_tick()

        self.assertEqual(world.current_tick, 1)

    # Step 8: Test initial entities
    def test_initial_entities(self):
        world = WorldState()

        self.assertEqual(len(world.citizens), 0)
        self.assertEqual(len(world.buildings), 0)

    # Step 9: Test initial resources
    def test_initial_resources(self):
        world = WorldState()

        self.assertEqual(world.resources["food"], 0)
        self.assertEqual(world.resources["water"], 0)
        self.assertEqual(world.resources["wood"], 0)
        self.assertEqual(world.resources["stone"], 0)
        self.assertEqual(world.resources["metal"], 0)
        self.assertEqual(world.resources["energy"], 0)

    # Step 10: Test adding a citizen to the world
    def test_add_citizen(self):
        world = WorldState()
        citizen = Citizen("CIT-001", "Alex")

        world.add_citizen(citizen)

        self.assertEqual(len(world.citizens), 1)
        self.assertIs(world.citizens[0], citizen)

    # Step 11: Test that only Citizen objects can be added
    def test_add_invalid_citizen(self):
        world = WorldState()

        with self.assertRaises(TypeError):
            world.add_citizen("Not a citizen")


# Step 12: Run the tests
if __name__ == "__main__":
    unittest.main()