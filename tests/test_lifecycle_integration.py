import unittest

from src.gaia.agents.citizen import Citizen
from src.gaia.core.simulation import Simulation


class TestLifecycleIntegration(unittest.TestCase):

    def test_simulation_tick_ages_living_citizen(self):
        simulation = Simulation()
        citizen = Citizen("CIT-66-01", "Ava", age=20)

        simulation.add_citizen(citizen)
        simulation.start()
        simulation.step()

        self.assertEqual(citizen.age, 21)
        self.assertTrue(citizen.is_alive())

    def test_simulation_tick_transitions_life_stage(self):
        simulation = Simulation()
        citizen = Citizen("CIT-66-02", "Leo", age=12)

        simulation.add_citizen(citizen)
        simulation.start()
        simulation.step()

        self.assertEqual(citizen.age, 13)
        self.assertEqual(citizen.life_stage, "Young Adult")

    def test_dead_citizen_does_not_age(self):
        simulation = Simulation()
        citizen = Citizen("CIT-66-03", "Mia", age=40)

        simulation.add_citizen(citizen)
        citizen.die()

        simulation.start()
        simulation.step()

        self.assertEqual(citizen.age, 40)
        self.assertFalse(citizen.is_alive())
        self.assertIn("Citizen died.", citizen.history)

    def test_lifecycle_history_persists_after_death(self):
        simulation = Simulation()
        citizen = Citizen("CIT-66-04", "Noah", age=59)

        simulation.add_citizen(citizen)
        citizen.record_history("Reached adulthood milestone.")
        citizen.die()

        simulation.start()
        simulation.step()

        self.assertEqual(citizen.age, 59)
        self.assertEqual(
            citizen.history,
            ["Citizen created.", "Reached adulthood milestone.", "Citizen died."]
        )


if __name__ == "__main__":
    unittest.main()

