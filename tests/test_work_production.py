# Step 1: Import unittest
import unittest

# Step 2: Import GAIA models
from src.gaia.agents.action import ActionExecutor, ActionOption
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job


class TestWorkProduction(unittest.TestCase):

    # Step 3: Test successful configured production
    def test_work_produces_configured_resource(self):
        citizen = Citizen("CIT-001", "Farmer")

        job = Job(
            "farmer",
            "Farmer",
            required_skills={"farming": 25},
            production={"food": 3},
            energy_cost=10,
            wage=5,
        )

        citizen.change_skill("farming", 50)
        citizen.set_job(job)

        action = ActionOption("work", "Work")
        executor = ActionExecutor()

        energy_before = citizen.energy

        result = executor.execute(
            citizen,
            action,
            {"tick": 10}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "work")
        self.assertEqual(result["production"], {"food": 3})
        self.assertEqual(citizen.get_item_quantity("food"), 3)
        self.assertEqual(citizen.energy, energy_before - 10)

    # Step 4: Test production follows the configured job rule
    def test_work_does_not_create_unconfigured_resources(self):
        citizen = Citizen("CIT-001", "Farmer")

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 3},
            energy_cost=5,
        )

        citizen.set_job(job)

        action = ActionOption("work", "Work")
        executor = ActionExecutor()

        result = executor.execute(citizen, action)

        self.assertTrue(result["success"])
        self.assertEqual(citizen.get_item_quantity("food"), 3)
        self.assertEqual(citizen.get_item_quantity("wood"), 0)
        self.assertEqual(citizen.get_item_quantity("metal"), 0)

    # Step 5: Test skill requirements prevent work
    def test_work_requires_job_skills(self):
        citizen = Citizen("CIT-001", "Farmer")

        job = Job(
            "farmer",
            "Farmer",
            required_skills={"farming": 50},
            production={"food": 3},
        )

        # Assignment itself should fail because the citizen lacks the skill.
        with self.assertRaises(ValueError):
            citizen.set_job(job)

    # Step 6: Test no-job work fails
    def test_work_without_job_fails(self):
        citizen = Citizen("CIT-001", "Unemployed")
        action = ActionOption("work", "Work")
        executor = ActionExecutor()

        result = executor.execute(citizen, action)

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "Citizen has no job.")

    # Step 7: Test insufficient energy prevents work
    def test_work_requires_energy(self):
        citizen = Citizen("CIT-001", "Farmer")
        citizen.energy = 5

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 3},
            energy_cost=10,
        )

        citizen.set_job(job)

        action = ActionOption("work", "Work")
        executor = ActionExecutor()

        result = executor.execute(citizen, action)

        self.assertFalse(result["success"])
        self.assertEqual(
            result["reason"],
            "Citizen does not have enough energy."
        )
        self.assertEqual(citizen.get_item_quantity("food"), 0)
        self.assertEqual(citizen.energy, 5)

    # Step 8: Test dead citizens cannot work
    def test_dead_citizen_cannot_work(self):
        citizen = Citizen("CIT-001", "Farmer")

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 3},
        )

        citizen.set_job(job)
        citizen.die()

        action = ActionOption("work", "Work")
        executor = ActionExecutor()

        result = executor.execute(citizen, action)

        self.assertFalse(result["success"])
        self.assertEqual(
            result["reason"],
            "Dead citizens cannot work."
        )
        self.assertEqual(citizen.get_item_quantity("food"), 0)

    # Step 9: Test inactive jobs cannot produce
    def test_inactive_job_cannot_work(self):
        citizen = Citizen("CIT-001", "Farmer")

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 3},
        )

        citizen.set_job(job)
        job.deactivate()

        action = ActionOption("work", "Work")
        executor = ActionExecutor()

        result = executor.execute(citizen, action)

        self.assertFalse(result["success"])
        self.assertEqual(
            result["reason"],
            "Citizen does not have an active job."
        )
        self.assertEqual(citizen.get_item_quantity("food"), 0)

    # Step 10: Test invalid production is rejected before mutation
    def test_invalid_production_is_atomic(self):
        citizen = Citizen("CIT-001", "Worker")

        job = Job(
            "worker",
            "Worker",
            production={"food": 2, "wood": -1},
        )

        citizen.set_job(job)

        action = ActionOption("work", "Work")
        executor = ActionExecutor()

        result = executor.execute(citizen, action)

        self.assertFalse(result["success"])
        self.assertEqual(
            result["reason"],
            "Production quantity must be positive."
        )
        self.assertEqual(citizen.get_item_quantity("food"), 0)
        self.assertEqual(citizen.get_item_quantity("wood"), 0)
        self.assertEqual(citizen.energy, 100.0)


if __name__ == "__main__":
    unittest.main()
