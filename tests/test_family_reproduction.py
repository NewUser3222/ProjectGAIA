import unittest

from src.gaia.agents.citizen import Citizen
from src.gaia.core.simulation import Simulation


class TestFamilyReproduction(unittest.TestCase):

    def test_parent_child_relationships_persist(self):
        parent = Citizen("CIT-68-01", "Parent")
        child = Citizen("CIT-68-02", "Child", age=0)

        parent.add_child(child.citizen_id)
        child.add_parent(parent.citizen_id)

        self.assertTrue(parent.has_child(child.citizen_id))
        self.assertTrue(child.has_parent(parent.citizen_id))
        self.assertEqual(parent.get_children(), ["CIT-68-02"])
        self.assertEqual(child.get_parents(), ["CIT-68-01"])

    def test_create_child_registers_newborn(self):
        simulation = Simulation()
        parent_a = Citizen("CIT-68-03", "Ava", age=30)
        parent_b = Citizen("CIT-68-04", "Leo", age=31)

        simulation.add_citizen(parent_a)
        simulation.add_citizen(parent_b)

        child = simulation.create_child(
            parent_a,
            parent_b,
            "CIT-68-05",
            "Mia"
        )

        self.assertEqual(child.age, 0)
        self.assertEqual(child.life_stage, "Child")
        self.assertTrue(child.is_alive())
        self.assertIn(child, simulation.citizens)
        self.assertIn(child, simulation.world.citizens)

    def test_create_child_establishes_both_parent_links(self):
        simulation = Simulation()
        parent_a = Citizen("CIT-68-06", "Ava", age=30)
        parent_b = Citizen("CIT-68-07", "Leo", age=31)

        simulation.add_citizen(parent_a)
        simulation.add_citizen(parent_b)

        child = simulation.create_child(
            parent_a,
            parent_b,
            "CIT-68-08",
            "Mia"
        )

        self.assertEqual(
            child.get_parents(),
            ["CIT-68-06", "CIT-68-07"]
        )
        self.assertEqual(parent_a.get_children(), ["CIT-68-08"])
        self.assertEqual(parent_b.get_children(), ["CIT-68-08"])

    def test_birth_is_recorded_in_history(self):
        simulation = Simulation()
        parent_a = Citizen("CIT-68-09", "Ava", age=30)
        parent_b = Citizen("CIT-68-10", "Leo", age=31)

        simulation.add_citizen(parent_a)
        simulation.add_citizen(parent_b)

        child = simulation.create_child(
            parent_a,
            parent_b,
            "CIT-68-11",
            "Mia"
        )

        self.assertEqual(
            child.history,
            ["Citizen created.", "Citizen was born."]
        )

    def test_dead_parent_cannot_create_child(self):
        simulation = Simulation()
        parent_a = Citizen("CIT-68-12", "Ava", age=30)
        parent_b = Citizen("CIT-68-13", "Leo", age=31)

        parent_a.die()

        with self.assertRaises(ValueError):
            simulation.create_child(
                parent_a,
                parent_b,
                "CIT-68-14",
                "Mia"
            )

    def test_duplicate_child_id_is_rejected(self):
        simulation = Simulation()
        parent_a = Citizen("CIT-68-15", "Ava", age=30)
        parent_b = Citizen("CIT-68-16", "Leo", age=31)
        existing = Citizen("CIT-68-17", "Existing")

        simulation.add_citizen(parent_a)
        simulation.add_citizen(parent_b)
        simulation.add_citizen(existing)

        with self.assertRaises(ValueError):
            simulation.create_child(
                parent_a,
                parent_b,
                "CIT-68-17",
                "Mia"
            )


if __name__ == "__main__":
    unittest.main()
