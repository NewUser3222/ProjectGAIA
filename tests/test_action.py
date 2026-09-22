# Step 1: Import the unittest framework
import unittest


# Step 2: Import the action execution classes
from src.gaia.agents.action import ActionExecutor, ActionOption


# Step 3: Import the Citizen entity
from src.gaia.agents.citizen import Citizen


# Step 4: Define ActionExecutor tests
class TestActionExecutor(unittest.TestCase):

    # Step 5: Test the eat action
    def test_execute_eat(self):
        citizen = Citizen("C001", "Alice")
        citizen.needs["hunger"] = 80

        action = ActionOption("eat", "Find Food")
        executor = ActionExecutor()

        result = executor.execute(
            citizen,
            action,
            {"tick": 5}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "eat")
        self.assertEqual(citizen.needs["hunger"], 40)
        self.assertEqual(citizen.memories[-1]["tick"], 5)

    # Step 6: Test the rest action
    def test_execute_rest(self):
        citizen = Citizen("C001", "Alice")
        citizen.needs["energy"] = 20

        action = ActionOption("rest", "Sleep / Rest")
        executor = ActionExecutor()

        result = executor.execute(
            citizen,
            action,
            {"tick": 7}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "rest")
        self.assertEqual(citizen.needs["energy"], 70)
        self.assertEqual(citizen.memories[-1]["tick"], 7)

    # Step 7: Test invalid actions
    def test_execute_invalid_action(self):
        citizen = Citizen("C001", "Alice")
        executor = ActionExecutor()

        result = executor.execute(citizen, None)

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "Invalid action option.")

    # Step 8: Test unknown actions
    def test_execute_unknown_action(self):
        citizen = Citizen("C001", "Alice")
        action = ActionOption("unknown", "Unknown Action")
        executor = ActionExecutor()

        result = executor.execute(citizen, action)

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "Unknown action_id: unknown")


# Step 9: Run the tests directly
if __name__ == "__main__":
    unittest.main()
# Step 33: Verify eat action integrates with WorldState resources
def test_execute_eat_consumes_world_integrated_food(self):
    from src.gaia.simulation.world import WorldState

    citizen = Citizen("C001", "Alice")
    world = WorldState()

    citizen.add_item("food", 2)
    citizen.needs["hunger"] = 80
    citizen.needs["food"] = 50

    action = ActionOption("eat", "Find Food")
    executor = ActionExecutor()

    result = executor.execute(
        citizen,
        action,
        {
            "tick": 10,
            "world": world
        }
    )

    self.assertTrue(result["success"])
    self.assertEqual(result["action"], "eat")
    self.assertEqual(citizen.get_item_quantity("food"), 1)
    self.assertEqual(citizen.needs["food"], 51)
    self.assertEqual(citizen.needs["hunger"], 40)
    self.assertEqual(citizen.memories[-1]["tick"], 10)
