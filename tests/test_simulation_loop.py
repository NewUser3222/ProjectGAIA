import unittest
from src.gaia.core.simulation import Simulation
from src.gaia.agents.citizen import Citizen

class TestSimulationLoopIntegration(unittest.TestCase):

    def setUp(self):
        self.sim = Simulation()
        self.alice = Citizen("CIT-001", "Alice")
        self.bob = Citizen("CIT-002", "Bob")
        
        self.sim.add_citizen(self.alice)
        self.sim.add_citizen(self.bob)

    def test_multi_agent_step_execution(self):
        self.sim.start()
        
        # Advance 3 ticks
        for _ in range(3):
            self.sim.step()

        self.assertEqual(self.sim.tick, 3)
        self.assertTrue(len(self.alice.memories) > 0)
        self.assertTrue(len(self.bob.memories) > 0)

    def test_tick_changes_needs_and_allows_decision_processing(self):
        self.sim.start()

        self.alice.needs["hunger"] = 50
        self.alice.needs["energy"] = 100
        self.alice.hunger = 50
        self.alice.energy = 100

        self.sim.step()

        # The tick increases hunger, then the decision/action cycle
        # recognizes the significant need and executes eat.
        self.assertLess(self.alice.hunger, 50)
        self.assertLess(self.alice.energy, 100)
        self.assertEqual(self.alice.needs["hunger"], self.alice.hunger)
        self.assertEqual(self.alice.needs["energy"], self.alice.energy)
        self.assertEqual(self.alice.hunger, 11.0)
        self.assertEqual(self.alice.energy, 99.4)

    def test_social_interaction_in_loop(self):
        self.sim.start()
        self.sim.step()

        # Alice and Bob should now have interacted and logged memories
        alice_memories = [m.text if hasattr(m, 'text') else str(m) for m in self.alice.memories]
        has_talk_memory = any("conversation" in m.lower() or "talk" in m.lower() for m in alice_memories)
        self.assertTrue(has_talk_memory)

if __name__ == "__main__":
    unittest.main()
