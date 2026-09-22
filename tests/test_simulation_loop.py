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

        self.assertEqual(self.alice.hunger, 51.0)
        self.assertEqual(self.alice.energy, 99.4)
        self.assertEqual(self.alice.needs["hunger"], self.alice.hunger)
        self.assertEqual(self.alice.needs["energy"], self.alice.energy)
        self.assertEqual(self.alice.get_item_quantity("food"), 1)

    def test_citizens_process_needs_and_actions_independently(self):
        self.sim.start()

        self.alice.hunger = 70.0
        self.alice.needs["hunger"] = 70.0
        self.alice.energy = 100.0
        self.alice.needs["energy"] = 100.0

        self.bob.hunger = 0.0
        self.bob.needs["hunger"] = 0.0
        self.bob.energy = 20.0
        self.bob.needs["energy"] = 20.0

        self.sim.step()

        self.assertEqual(self.alice.hunger, 71.0)
        self.assertEqual(self.alice.needs["hunger"], 71.0)
        self.assertEqual(self.alice.energy, 99.4)
        self.assertEqual(self.alice.needs["energy"], 99.4)
        self.assertEqual(self.alice.get_item_quantity("food"), 1)

        self.assertEqual(self.bob.hunger, 1.0)
        self.assertEqual(self.bob.needs["hunger"], 1.0)
        self.assertEqual(self.bob.energy, 69.4)
        self.assertEqual(self.bob.needs["energy"], 69.4)

        self.assertNotEqual(self.alice.hunger, self.bob.hunger)
        self.assertNotEqual(self.alice.energy, self.bob.energy)

    def test_simulation_owns_shared_world_state(self):
        self.assertIsNotNone(self.sim.world)
        self.assertIs(self.sim.world.citizens[0], self.alice)
        self.assertIs(self.sim.world.citizens[1], self.bob)

    def test_world_tick_tracks_simulation_tick(self):
        self.sim.start()

        self.assertEqual(self.sim.tick, 0)
        self.assertEqual(self.sim.world.current_tick, 0)

        self.sim.step()

        self.assertEqual(self.sim.tick, 1)
        self.assertEqual(self.sim.world.current_tick, 1)

        self.sim.step()

        self.assertEqual(self.sim.tick, 2)
        self.assertEqual(self.sim.world.current_tick, 2)

    def test_world_context_is_available_to_actions(self):
        self.sim.start()

        self.alice.add_item("food", 1)
        self.alice.hunger = 70.0
        self.alice.needs["hunger"] = 70.0

        self.sim.world.set_resource("food", 10)

        self.sim.step()

        self.assertEqual(self.alice.get_item_quantity("food"), 0)
        self.assertEqual(self.sim.world.get_resource("food"), 11)
        self.assertEqual(self.alice.hunger, 31.0)

    def test_social_interaction_in_loop(self):
        self.sim.start()
        self.sim.step()

        alice_memories = [
            m.text if hasattr(m, "text") else str(m)
            for m in self.alice.memories
        ]
        has_talk_memory = any(
            "conversation" in m.lower() or "talk" in m.lower()
            for m in alice_memories
        )
        self.assertTrue(has_talk_memory)




    # Step 40: Test multiple consecutive ticks preserve independent state
    def test_multiple_ticks_preserve_independent_citizen_state(self):
        self.sim.start()

        self.alice.hunger = 10.0
        self.alice.needs["hunger"] = 10.0

        self.bob.hunger = 70.0
        self.bob.needs["hunger"] = 70.0
        self.bob.add_item("food", 3)

        self.sim.world.set_resource("food", 20)

        self.sim.step()
        alice_hunger_after_first = self.alice.hunger
        bob_hunger_after_first = self.bob.hunger

        self.sim.step()
        self.sim.step()

        self.assertEqual(self.sim.tick, 3)
        self.assertEqual(self.sim.world.current_tick, 3)

        self.assertNotEqual(
            self.alice.hunger,
            self.bob.hunger
        )
        self.assertLess(
            self.alice.get_need("food"),
            100
        )
        self.assertLess(
            self.alice.get_need("water"),
            100
        )
        self.assertLess(
            self.alice.get_need("shelter"),
            100
        )

        self.assertLessEqual(
            self.bob.get_item_quantity("food"),
            3
        )
        self.assertLessEqual(
            self.alice.hunger,
            alice_hunger_after_first + 3
        )
        self.assertLessEqual(
            self.bob.hunger,
            bob_hunger_after_first + 3
        )

    # Step 40: Test dead citizen is skipped while another remains active
    def test_dead_citizen_is_skipped_in_multi_citizen_loop(self):
        self.sim.start()

        self.alice.die()

        bob_energy_before = self.bob.energy
        alice_needs_before = self.alice.needs.copy()

        self.sim.step()

        self.assertFalse(self.alice.is_alive())
        self.assertEqual(self.alice.needs, alice_needs_before)
        self.assertLess(self.bob.energy, bob_energy_before)

        bob_talks = any(
            "conversation" in str(memory).lower()
            or "talk" in str(memory).lower()
            for memory in self.bob.memories
        )
        self.assertFalse(bob_talks)

if __name__ == "__main__":
    unittest.main()
