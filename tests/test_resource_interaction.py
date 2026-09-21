# Step 1: Import the unittest framework
import unittest


# Step 2: Import the World State
from src.gaia.simulation.world import WorldState


# Step 3: Import the Citizen entity
from src.gaia.agents.citizen import Citizen


# Step 4: Define resource interaction tests
class TestResourceInteraction(unittest.TestCase):

    # Step 5: Test transferring a resource from the world to a citizen
    def test_transfer_resource_to_citizen(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")

        world.set_resource("food", 100)

        world.transfer_resource_to_citizen(citizen, "food", 25)

        self.assertEqual(world.get_resource("food"), 75)
        self.assertEqual(citizen.get_item_quantity("food"), 25)

    # Step 6: Test transferring a resource from a citizen back to the world
    def test_transfer_resource_from_citizen(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")

        citizen.add_item("wood", 20)

        world.transfer_resource_from_citizen(citizen, "wood", 10)

        self.assertEqual(citizen.get_item_quantity("wood"), 10)
        self.assertEqual(world.get_resource("wood"), 10)

    # Step 7: Test consuming a resource from a citizen
    def test_consume_resource(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")

        citizen.add_item("food", 10)

        world.consume_resource(citizen, "food", 4)

        self.assertEqual(citizen.get_item_quantity("food"), 6)

    # Step 8: Test insufficient world resources
    def test_transfer_from_world_insufficient_resources(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")

        world.set_resource("food", 5)

        with self.assertRaises(ValueError):
            world.transfer_resource_to_citizen(citizen, "food", 10)

    # Step 9: Test insufficient citizen resources
    def test_transfer_from_citizen_insufficient_resources(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")

        citizen.add_item("wood", 5)

        with self.assertRaises(ValueError):
            world.transfer_resource_from_citizen(citizen, "wood", 10)

    # Step 10: Test consuming insufficient citizen resources
    def test_consume_insufficient_resources(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")

        citizen.add_item("food", 5)

        with self.assertRaises(ValueError):
            world.consume_resource(citizen, "food", 10)

    # Step 11: Test invalid resource name
    def test_invalid_resource_name(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")

        with self.assertRaises(ValueError):
            world.transfer_resource_to_citizen(citizen, "gold", 10)

    # Step 12: Test zero quantity
    def test_zero_quantity(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")

        with self.assertRaises(ValueError):
            world.transfer_resource_to_citizen(citizen, "food", 0)

    # Step 13: Test negative quantity
    def test_negative_quantity(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")

        with self.assertRaises(ValueError):
            world.consume_resource(citizen, "food", -1)

    # Step 14: Test invalid citizen type
    def test_invalid_citizen(self):
        world = WorldState()

        with self.assertRaises(TypeError):
            world.transfer_resource_to_citizen("not a citizen", "food", 1)


# Step 15: Run the tests directly
if __name__ == "__main__":
    unittest.main()
