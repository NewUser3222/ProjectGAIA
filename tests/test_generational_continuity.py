import unittest

from src.gaia.agents.citizen import Citizen
from src.gaia.core.simulation import Simulation


class TestGenerationalContinuity(unittest.TestCase):

    def test_initial_citizen_is_generation_zero(self):
        citizen = Citizen("CIT-69-01", "Founder")

        self.assertEqual(citizen.generation, 0)

    def test_child_receives_next_generation(self):
        simulation = Simulation()
        parent_a = Citizen("CIT-69-02", "Parent A", age=30)
        parent_b = Citizen("CIT-69-03", "Parent B", age=31)

        simulation.add_citizen(parent_a)
        simulation.add_citizen(parent_b)

        child = simulation.create_child(
            parent_a,
            parent_b,
            "CIT-69-04",
            "Child"
        )

        self.assertEqual(parent_a.generation, 0)
        self.assertEqual(parent_b.generation, 0)
        self.assertEqual(child.generation, 1)

    def test_grandchild_receives_next_generation(self):
        simulation = Simulation()
        parent_a = Citizen("CIT-69-05", "Parent A", age=30)
        parent_b = Citizen("CIT-69-06", "Parent B", age=31)

        simulation.add_citizen(parent_a)
        simulation.add_citizen(parent_b)

        child = simulation.create_child(
            parent_a,
            parent_b,
            "CIT-69-07",
            "Child"
        )

        second_parent = Citizen("CIT-69-08", "Second Parent", age=25)
        simulation.add_citizen(second_parent)

        grandchild = simulation.create_child(
            child,
            second_parent,
            "CIT-69-09",
            "Grandchild"
        )

        self.assertEqual(grandchild.generation, 2)

    def test_ancestry_survives_parent_death(self):
        simulation = Simulation()
        grandparent_a = Citizen("CIT-69-10", "Grandparent A", age=70)
        grandparent_b = Citizen("CIT-69-11", "Grandparent B", age=70)

        simulation.add_citizen(grandparent_a)
        simulation.add_citizen(grandparent_b)

        parent = simulation.create_child(
            grandparent_a,
            grandparent_b,
            "CIT-69-12",
            "Parent"
        )

        second_parent = Citizen("CIT-69-13", "Second Parent", age=30)
        simulation.add_citizen(second_parent)

        child = simulation.create_child(
            parent,
            second_parent,
            "CIT-69-14",
            "Child"
        )

        grandparent_a.die()
        grandparent_b.die()

        ancestors = simulation.get_ancestors(child)
        ancestor_ids = {ancestor.citizen_id for ancestor in ancestors}

        self.assertIn(parent.citizen_id, ancestor_ids)
        self.assertIn(grandparent_a.citizen_id, ancestor_ids)
        self.assertIn(grandparent_b.citizen_id, ancestor_ids)
        self.assertFalse(grandparent_a.is_alive())
        self.assertFalse(grandparent_b.is_alive())

    def test_child_ages_normally_after_birth(self):
        simulation = Simulation()
        parent_a = Citizen("CIT-69-15", "Parent A", age=30)
        parent_b = Citizen("CIT-69-16", "Parent B", age=31)

        simulation.add_citizen(parent_a)
        simulation.add_citizen(parent_b)

        child = simulation.create_child(
            parent_a,
            parent_b,
            "CIT-69-17",
            "Child"
        )

        self.assertEqual(child.age, 0)
        self.assertEqual(child.life_stage, "Child")

        child.age_up(13)

        self.assertEqual(child.age, 13)
        self.assertEqual(child.life_stage, "Young Adult")
        self.assertTrue(child.is_alive())

    def test_birth_and_death_change_living_population_naturally(self):
        simulation = Simulation()
        parent_a = Citizen("CIT-69-18", "Parent A", age=30)
        parent_b = Citizen("CIT-69-19", "Parent B", age=31)

        simulation.add_citizen(parent_a)
        simulation.add_citizen(parent_b)

        child = simulation.create_child(
            parent_a,
            parent_b,
            "CIT-69-20",
            "Child"
        )

        living_before_death = sum(
            citizen.is_alive() for citizen in simulation.citizens
        )

        child.die()

        living_after_death = sum(
            citizen.is_alive() for citizen in simulation.citizens
        )

        self.assertEqual(living_before_death, 3)
        self.assertEqual(living_after_death, 2)
        self.assertIn(child, simulation.citizens)
        self.assertIn(child, simulation.world.citizens)


if __name__ == "__main__":
    unittest.main()
