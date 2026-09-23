# Step 62: Construction materials and building cost tests
import unittest

from src.gaia.agents.citizen import Citizen
from src.gaia.construction import BuildingDefinition, ConstructionCostSystem
from src.gaia.simulation.world import WorldState


class TestBuildingDefinition(unittest.TestCase):

    # Step 62: Test configuration-driven building definitions
    def test_building_definition(self):
        definition = BuildingDefinition(
            "house",
            required_materials={
                "wood": 10,
                "stone": 5,
            },
            construction_cost=100.0,
        )

        self.assertEqual(definition.building_type, "house")
        self.assertEqual(
            definition.get_required_materials(),
            {"wood": 10, "stone": 5},
        )
        self.assertEqual(definition.get_construction_cost(), 100.0)

    # Step 62: Definitions reject invalid material quantities
    def test_invalid_material_quantity(self):
        with self.assertRaises(ValueError):
            BuildingDefinition(
                "house",
                required_materials={"wood": 0},
            )

        with self.assertRaises(ValueError):
            BuildingDefinition(
                "house",
                required_materials={"wood": -1},
            )

    # Step 62: Definitions reject negative construction costs
    def test_negative_construction_cost(self):
        with self.assertRaises(ValueError):
            BuildingDefinition("house", construction_cost=-1)


class TestConstructionCostSystem(unittest.TestCase):

    # Step 62: Materials can be afforded
    def test_can_afford_materials(self):
        world = WorldState()
        world.set_resource("wood", 100)
        world.set_resource("stone", 50)

        definition = BuildingDefinition(
            "house",
            required_materials={
                "wood": 10,
                "stone": 5,
            },
        )

        self.assertTrue(
            ConstructionCostSystem.can_afford(world, definition)
        )

    # Step 62: Missing materials prevent construction
    def test_missing_materials_prevent_construction(self):
        world = WorldState()
        world.set_resource("wood", 5)
        world.set_resource("stone", 50)

        definition = BuildingDefinition(
            "house",
            required_materials={
                "wood": 10,
                "stone": 5,
            },
        )

        self.assertFalse(
            ConstructionCostSystem.can_afford(world, definition)
        )

    # Step 62: Successful construction cost consumes materials
    def test_consume_materials(self):
        world = WorldState()
        world.set_resource("wood", 100)
        world.set_resource("stone", 50)

        definition = BuildingDefinition(
            "house",
            required_materials={
                "wood": 10,
                "stone": 5,
            },
        )

        result = ConstructionCostSystem.consume(
            world,
            definition,
        )

        self.assertTrue(result["success"])
        self.assertEqual(world.get_resource("wood"), 90)
        self.assertEqual(world.get_resource("stone"), 45)

    # Step 62: Failed construction consumes no materials
    def test_failed_material_check_is_atomic(self):
        world = WorldState()
        world.set_resource("wood", 100)
        world.set_resource("stone", 2)

        definition = BuildingDefinition(
            "house",
            required_materials={
                "wood": 10,
                "stone": 5,
            },
        )

        result = ConstructionCostSystem.consume(
            world,
            definition,
        )

        self.assertFalse(result["success"])
        self.assertEqual(world.get_resource("wood"), 100)
        self.assertEqual(world.get_resource("stone"), 2)

    # Step 62: Money requirement can be satisfied
    def test_money_requirement(self):
        world = WorldState()
        citizen = Citizen("CIT-621", "Builder")
        citizen.change_money(500)

        definition = BuildingDefinition(
            "workshop",
            required_materials={"wood": 10},
            construction_cost=100,
        )

        world.set_resource("wood", 10)

        self.assertTrue(
            ConstructionCostSystem.can_afford(
                world,
                definition,
                citizen,
            )
        )

    # Step 62: Insufficient money prevents construction
    def test_insufficient_money_prevents_construction(self):
        world = WorldState()
        citizen = Citizen("CIT-622", "Builder")
        citizen.change_money(50)

        definition = BuildingDefinition(
            "workshop",
            required_materials={"wood": 10},
            construction_cost=100,
        )

        world.set_resource("wood", 10)

        self.assertFalse(
            ConstructionCostSystem.can_afford(
                world,
                definition,
                citizen,
            )
        )

    # Step 62: Successful construction consumes both materials and money
    def test_consume_materials_and_money(self):
        world = WorldState()
        citizen = Citizen("CIT-623", "Builder")
        citizen.change_money(500)
        world.set_resource("wood", 20)

        definition = BuildingDefinition(
            "workshop",
            required_materials={"wood": 10},
            construction_cost=100,
        )

        result = ConstructionCostSystem.consume(
            world,
            definition,
            citizen,
        )

        self.assertTrue(result["success"])
        self.assertEqual(world.get_resource("wood"), 10)
        self.assertEqual(citizen.get_money(), 400)

    # Step 62: Failed money check does not consume materials or money
    def test_failed_money_check_is_atomic(self):
        world = WorldState()
        citizen = Citizen("CIT-624", "Builder")
        citizen.change_money(50)
        world.set_resource("wood", 20)

        definition = BuildingDefinition(
            "workshop",
            required_materials={"wood": 10},
            construction_cost=100,
        )

        result = ConstructionCostSystem.consume(
            world,
            definition,
            citizen,
        )

        self.assertFalse(result["success"])
        self.assertEqual(world.get_resource("wood"), 20)
        self.assertEqual(citizen.get_money(), 50)

    # Step 62: Reusable definitions do not mutate configuration
    def test_definition_is_reusable(self):
        world = WorldState()
        world.set_resource("wood", 30)

        definition = BuildingDefinition(
            "house",
            required_materials={"wood": 10},
        )

        first = ConstructionCostSystem.consume(world, definition)
        second = ConstructionCostSystem.consume(world, definition)

        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(world.get_resource("wood"), 10)
        self.assertEqual(
            definition.get_required_materials(),
            {"wood": 10},
        )


if __name__ == "__main__":
    unittest.main()
