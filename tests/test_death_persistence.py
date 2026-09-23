import unittest

from src.gaia.agents.citizen import Citizen
from src.gaia.core.simulation import Simulation


class TestDeathPersistence(unittest.TestCase):

    def test_dead_citizen_remains_in_simulation_history(self):
        simulation = Simulation()
        citizen = Citizen("CIT-67-01", "Ava")

        simulation.add_citizen(citizen)
        citizen.record_history("Built a home.")
        citizen.die()

        simulation.start()
        simulation.step()

        self.assertIn(citizen, simulation.citizens)
        self.assertIn(citizen, simulation.world.citizens)
        self.assertFalse(citizen.is_alive())
        self.assertEqual(
            citizen.history,
            ["Citizen created.", "Built a home.", "Citizen died."]
        )

    def test_dead_citizen_does_not_participate_in_normal_tick(self):
        simulation = Simulation()
        citizen = Citizen("CIT-67-02", "Leo")

        simulation.add_citizen(citizen)
        citizen.die()

        original_age = citizen.age
        original_hunger = citizen.hunger
        original_energy = citizen.energy

        simulation.start()
        simulation.step()

        self.assertEqual(citizen.age, original_age)
        self.assertEqual(citizen.hunger, original_hunger)
        self.assertEqual(citizen.energy, original_energy)
        self.assertFalse(citizen.is_alive())

    def test_relationship_to_deceased_citizen_persists(self):
        simulation = Simulation()
        living = Citizen("CIT-67-03", "Maya")
        deceased = Citizen("CIT-67-04", "Noah")

        simulation.add_citizen(living)
        simulation.add_citizen(deceased)

        living.add_relationship(deceased.citizen_id, "friend")
        deceased.die()

        simulation.start()
        simulation.step()

        relationship = living.get_relationship(deceased.citizen_id)

        self.assertIsNotNone(relationship)
        self.assertEqual(relationship["citizen_id"], deceased.citizen_id)
        self.assertEqual(relationship["type"], "friend")

    def test_death_is_permanent_across_simulation_ticks(self):
        simulation = Simulation()
        citizen = Citizen("CIT-67-05", "Eli")

        simulation.add_citizen(citizen)
        citizen.die()

        simulation.start()
        simulation.step()
        simulation.step()
        simulation.step()

        self.assertFalse(citizen.is_alive())
        self.assertEqual(citizen.history.count("Citizen died."), 1)
        self.assertIn(citizen, simulation.citizens)


if __name__ == "__main__":
    unittest.main()
