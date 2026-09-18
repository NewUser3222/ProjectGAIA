import unittest
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.decision import DecisionEngine, ActionOption

class TestDecisionEngine(unittest.TestCase):

    def test_action_option_initialization(self):
        action = ActionOption("eat", "Find Food", urgency_score=75.0, requirements={"item": "apple"})
        self.assertEqual(action.action_id, "eat")
        self.assertEqual(action.name, "Find Food")
        self.assertEqual(action.urgency_score, 75.0)
        self.assertEqual(action.requirements, {"item": "apple"})

    def test_action_option_validation(self):
        with self.assertRaises(ValueError):
            ActionOption("", "Find Food")
        with self.assertRaises(ValueError):
            ActionOption("eat", "")

    def test_decision_engine_evaluation(self):
        citizen = Citizen("CIT-001", "Test Citizen")
        citizen.needs["hunger"] = 80
        citizen.needs["energy"] = 10

        engine = DecisionEngine()
        options = engine.evaluate_needs(citizen)

        self.assertEqual(len(options), 2)
        # Energy deficiency urgency = 100 - 10 = 90 (higher priority than hunger 80)
        self.assertEqual(options[0].action_id, "rest")
        self.assertEqual(options[1].action_id, "eat")

    def test_decision_engine_select_best_action(self):
        citizen = Citizen("CIT-001", "Test Citizen")
        citizen.needs["hunger"] = 65
        citizen.needs["energy"] = 100

        engine = DecisionEngine()
        best_action = engine.select_best_action(citizen)

        self.assertIsNotNone(best_action)
        self.assertEqual(best_action.action_id, "eat")
        self.assertEqual(best_action.urgency_score, 65.0)

    def test_execute_action_eat(self):
        citizen = Citizen("CIT-001", "Test Citizen")
        citizen.needs["hunger"] = 80

        engine = DecisionEngine()
        action = ActionOption("eat", "Find Food", urgency_score=80.0)
        result = engine.execute_action(citizen, action)

        self.assertTrue(result["success"])
        self.assertEqual(citizen.needs["hunger"], 40)
        self.assertTrue(len(citizen.memories) > 0)

    def test_execute_action_rest(self):
        citizen = Citizen("CIT-001", "Test Citizen")
        citizen.needs["energy"] = 20

        engine = DecisionEngine()
        action = ActionOption("rest", "Sleep / Rest", urgency_score=80.0)
        result = engine.execute_action(citizen, action)

        self.assertTrue(result["success"])
        self.assertEqual(citizen.needs["energy"], 70)
        self.assertTrue(len(citizen.memories) > 0)

    def test_execute_invalid_action(self):
        citizen = Citizen("CIT-001", "Test Citizen")
        engine = DecisionEngine()
        
        result_none = engine.execute_action(citizen, None)
        self.assertFalse(result_none["success"])

        unknown_action = ActionOption("fly", "Fly Around")
        result_unknown = engine.execute_action(citizen, unknown_action)
        self.assertFalse(result_unknown["success"])

if __name__ == "__main__":
    unittest.main()
