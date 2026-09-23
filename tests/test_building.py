# Step 61: Building entity foundation tests
import unittest

from src.gaia.building import Building
from src.gaia.simulation.world import WorldState


class TestBuilding(unittest.TestCase):

    # Step 61: Test basic building identity and state
    def test_building_initial_state(self):
        building = Building(
            "BLD-001",
            "house",
            (10, 20),
            dimensions=(10, 10),
        )

        self.assertEqual(building.building_id, "BLD-001")
        self.assertEqual(building.building_type, "house")
        self.assertEqual(building.location, (10, 20))
        self.assertEqual(building.dimensions, (10, 10))
        self.assertIsNone(building.owner)
        self.assertEqual(building.condition, "good")
        self.assertEqual(building.construction_status, "planned")
        self.assertEqual(building.occupants, [])
        self.assertEqual(building.associated_entities, [])
        self.assertFalse(building.is_completed())
        self.assertFalse(building.is_active())

    # Step 61: Buildings can exist independently of occupants
    def test_building_can_exist_without_occupants(self):
        building = Building(
            "BLD-002",
            "warehouse",
            (25, 30),
        )

        self.assertEqual(building.occupants, [])
        self.assertIsNotNone(building)

    # Step 61: Completed buildings become active
    def test_completed_building_is_active(self):
        building = Building(
            "BLD-003",
            "workshop",
            (5, 5),
            construction_status="completed",
        )

        self.assertTrue(building.is_completed())
        self.assertTrue(building.is_active())

    # Step 61: Destroyed buildings are not active
    def test_destroyed_building_is_not_active(self):
        building = Building(
            "BLD-004",
            "house",
            (5, 5),
            construction_status="completed",
            condition="destroyed",
        )

        self.assertTrue(building.is_completed())
        self.assertFalse(building.is_active())

    # Step 61: Invalid building identity is rejected
    def test_invalid_building_identity(self):
        with self.assertRaises(ValueError):
            Building("", "house", (1, 1))

        with self.assertRaises(ValueError):
            Building("BLD-005", "", (1, 1))

        with self.assertRaises(ValueError):
            Building("BLD-006", "house", None)


class TestWorldBuildingManagement(unittest.TestCase):

    # Step 61: World starts without buildings
    def test_world_starts_without_buildings(self):
        world = WorldState()

        self.assertEqual(world.get_buildings(), [])

    # Step 61: World accepts Building objects
    def test_add_building(self):
        world = WorldState()
        building = Building("BLD-101", "house", (10, 10))

        world.add_building(building)

        self.assertEqual(len(world.buildings), 1)
        self.assertIs(world.buildings[0], building)
        self.assertIs(world.get_building("BLD-101"), building)

    # Step 61: Invalid world building type is rejected
    def test_add_invalid_building(self):
        world = WorldState()

        with self.assertRaises(TypeError):
            world.add_building("Not a building")

    # Step 61: Building IDs must be unique within the world
    def test_duplicate_building_id_is_rejected(self):
        world = WorldState()

        world.add_building(
            Building("BLD-102", "house", (1, 1))
        )

        with self.assertRaises(ValueError):
            world.add_building(
                Building("BLD-102", "warehouse", (2, 2))
            )

    # Step 61: Multiple buildings remain independent
    def test_multiple_buildings_are_independent(self):
        world = WorldState()

        building_one = Building("BLD-103", "house", (1, 1))
        building_two = Building("BLD-104", "warehouse", (2, 2))

        world.add_building(building_one)
        world.add_building(building_two)

        self.assertEqual(len(world.get_buildings()), 2)
        self.assertIs(world.get_building("BLD-103"), building_one)
        self.assertIs(world.get_building("BLD-104"), building_two)

    # Step 61: Buildings can be removed independently
    def test_remove_building(self):
        world = WorldState()
        building = Building("BLD-105", "house", (3, 3))

        world.add_building(building)
        world.remove_building(building)

        self.assertEqual(world.get_buildings(), [])
        self.assertIsNone(world.get_building("BLD-105"))


if __name__ == "__main__":
    unittest.main()
