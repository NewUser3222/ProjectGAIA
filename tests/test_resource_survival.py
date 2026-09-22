import unittest

from src.gaia.agents.action import ActionOption
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.decision import DecisionEngine
from src.gaia.core.simulation import Simulation
from src.gaia.simulation.world import WorldState


class TestResourceSurvival(unittest.TestCase):

    # Step 41: Gathering transfers only existing resources.
    def test_gather_resource_transfers_world_resource(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")

        world.set_resource("food", 5)
        gathered = world.gather_resource(citizen, "food", 2)

        self.assertEqual(gathered, 2)
        self.assertEqual(world.get_resource("food"), 3)
        self.assertEqual(citizen.get_item_quantity("food"), 2)

    def test_gather_cannot_create_missing_resources(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")

        with self.assertRaises(ValueError):
            world.gather_resource(citizen, "food", 1)

        self.assertEqual(world.get_resource("food"), 0)
        self.assertEqual(citizen.get_item_quantity("food"), 0)

    def test_gather_respects_world_location(self):
        world = WorldState(width=10, height=10)
        citizen = Citizen("C001", "Alice", location=(10, 10))
        world.set_resource("wood", 5)

        with self.assertRaises(ValueError):
            world.gather_resource(citizen, "wood", 1)

        self.assertEqual(world.get_resource("wood"), 5)

    # Step 42: Renewable resources regenerate but stay within limits.
    def test_renewable_resources_regenerate_with_cap(self):
        world = WorldState()
        world.set_resource("food", 999)
        world.set_resource("water", 999)
        world.set_resource("wood", 999)

        world.advance_tick()

        self.assertEqual(world.get_resource("food"), 1000)
        self.assertEqual(world.get_resource("water"), 1000)
        self.assertEqual(world.get_resource("wood"), 1000)

    def test_nonrenewable_resources_do_not_regenerate(self):
        world = WorldState()
        world.set_resource("stone", 10)
        world.set_resource("metal", 10)

        world.gather_resource(Citizen("C001", "Alice"), "stone", 4)
        world.gather_resource(Citizen("C002", "Bob"), "metal", 4)

        world.advance_tick()

        self.assertEqual(world.get_resource("stone"), 6)
        self.assertEqual(world.get_resource("metal"), 6)

    def test_multiple_citizens_cannot_overdraw_resource(self):
        world = WorldState()
        alice = Citizen("C001", "Alice")
        bob = Citizen("C002", "Bob")
        world.set_resource("food", 1)

        world.gather_resource(alice, "food", 1)

        with self.assertRaises(ValueError):
            world.gather_resource(bob, "food", 1)

        self.assertEqual(world.get_resource("food"), 0)
        self.assertEqual(alice.get_item_quantity("food"), 1)
        self.assertEqual(bob.get_item_quantity("food"), 0)

    # Step 43: Consumption must use actual inventory.
    def test_eat_consumes_inventory_and_reduces_hunger(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")
        citizen.needs["hunger"] = 80
        citizen.hunger = 80
        citizen.add_item("food", 1)

        result = DecisionEngine().execute_action(
            citizen,
            ActionOption("eat", "Eat Food"),
            {"tick": 1, "world": world}
        )

        self.assertTrue(result["success"])
        self.assertEqual(citizen.get_item_quantity("food"), 0)
        self.assertEqual(citizen.needs["food"], 100)
        self.assertEqual(citizen.hunger, 40)

    def test_eat_fails_without_inventory_food(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")
        citizen.needs["hunger"] = 80
        citizen.hunger = 80

        result = DecisionEngine().execute_action(
            citizen,
            ActionOption("eat", "Eat Food"),
            {"tick": 1, "world": world}
        )

        self.assertFalse(result["success"])
        self.assertEqual(citizen.get_item_quantity("food"), 0)
        self.assertEqual(citizen.hunger, 80)

    def test_two_citizens_keep_inventory_independent(self):
        world = WorldState()
        alice = Citizen("C001", "Alice")
        bob = Citizen("C002", "Bob")

        alice.add_item("food", 2)
        bob.add_item("food", 1)

        world.consume_resource_for_need(alice, "food", 1)

        self.assertEqual(alice.get_item_quantity("food"), 1)
        self.assertEqual(bob.get_item_quantity("food"), 1)

    # Step 44: Decisions reflect actual resources.
    def test_hungry_citizen_eats_when_inventory_food_exists(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")
        citizen.needs["hunger"] = 80
        citizen.add_item("food", 1)

        action = DecisionEngine().select_best_action(citizen, world)

        self.assertIsNotNone(action)
        self.assertEqual(action.action_id, "eat")

    def test_hungry_citizen_gathers_when_inventory_empty_and_world_has_food(self):
        world = WorldState()
        world.set_resource("food", 2)
        citizen = Citizen("C001", "Alice")
        citizen.needs["hunger"] = 80

        action = DecisionEngine().select_best_action(citizen, world)

        self.assertIsNotNone(action)
        self.assertEqual(action.action_id, "gather")
        self.assertEqual(action.requirements["resource"], "food")

    def test_hungry_citizen_has_no_eat_or_gather_when_food_unavailable(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")
        citizen.needs["hunger"] = 80

        actions = DecisionEngine().evaluate_needs(citizen, world)

        self.assertFalse(
            any(action.action_id in ("eat", "gather") for action in actions)
        )

    # Step 45: Complete multi-tick resource/survival loop.
    def test_integrated_resource_survival_loop(self):
        sim = Simulation()
        alice = Citizen("C001", "Alice")
        bob = Citizen("C002", "Bob")

        sim.add_citizen(alice)
        sim.add_citizen(bob)

        alice.needs["hunger"] = 80
        alice.hunger = 80
        bob.needs["hunger"] = 80
        bob.hunger = 80

        sim.world.set_resource("food", 1)
        sim.start()

        sim.step()

        self.assertEqual(alice.get_item_quantity("food"), 1)
        self.assertEqual(bob.get_item_quantity("food"), 1)
        self.assertEqual(sim.world.get_resource("food"), 0)

        sim.step()

        self.assertEqual(alice.get_item_quantity("food"), 0)
        self.assertLess(alice.hunger, 80)

        sim.step()

        self.assertEqual(sim.tick, 3)
        self.assertEqual(sim.world.current_tick, 3)
        self.assertGreaterEqual(sim.world.get_resource("food"), 0)
        self.assertGreaterEqual(alice.get_need("food"), 0)
        self.assertGreaterEqual(bob.get_need("food"), 0)

    def test_depleted_resource_changes_later_decision(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")
        citizen.needs["hunger"] = 80
        world.set_resource("food", 1)

        first = DecisionEngine().select_best_action(citizen, world)
        self.assertEqual(first.action_id, "gather")

        world.gather_resource(citizen, "food", 1)

        second = DecisionEngine().select_best_action(citizen, world)
        self.assertEqual(second.action_id, "eat")

    def test_dead_citizen_stops_participating(self):
        sim = Simulation()
        citizen = Citizen("C001", "Alice")
        sim.add_citizen(citizen)
        citizen.needs["hunger"] = 80
        citizen.hunger = 80
        citizen.die()

        sim.world.set_resource("food", 5)
        sim.start()
        sim.step()

        self.assertEqual(citizen.get_item_quantity("food"), 0)
        self.assertEqual(citizen.hunger, 80)
        self.assertFalse(citizen.is_alive())


if __name__ == "__main__":
    unittest.main()
