import unittest
from src.gaia.agents.citizen import Citizen
from src.gaia.reasoning.engine import LLMAdapter, ReasoningEngine

class TestReasoningFramework(unittest.TestCase):

    def setUp(self):
        self.alice = Citizen("CIT-001", "Alice")
        self.bob = Citizen("CIT-002", "Bob")
        self.engine = ReasoningEngine()

    def test_stub_adapter_output(self):
        adapter = LLMAdapter(provider="stub")
        res = adapter.generate_response("Hello world")
        self.assertIn("[LLM Stub Response]", res)

    def test_dialogue_generation(self):
        dialogue = self.engine.generate_dialogue(self.alice, self.bob, topic="trade")
        self.assertIsNotNone(dialogue)
        self.assertIn("Alice", dialogue)

    def test_plan_formulation(self):
        plan = self.engine.formulate_plan(self.alice, goal="Gather food")
        self.assertIsNotNone(plan)
        self.assertIn("Gather food", plan)

if __name__ == "__main__":
    unittest.main()
