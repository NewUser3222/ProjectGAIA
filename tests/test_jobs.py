# Step 1: Import unittest
import unittest

# Step 2: Import job and citizen models
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job


class TestJobs(unittest.TestCase):

    # Step 3: Test job configuration
    def test_job_initialization(self):
        job = Job(
            "farmer",
            "Farmer",
            required_skills={"farming": 25},
            production={"food": 2},
            wage=10,
            energy_cost=5,
        )

        self.assertEqual(job.job_id, "farmer")
        self.assertEqual(job.name, "Farmer")
        self.assertEqual(job.required_skills["farming"], 25)
        self.assertEqual(job.production["food"], 2)
        self.assertEqual(job.wage, 10.0)
        self.assertEqual(job.energy_cost, 5.0)
        self.assertTrue(job.active)

    # Step 4: Test eligible citizen
    def test_job_eligibility(self):
        citizen = Citizen("CIT-001", "Alex")
        citizen.change_skill("farming", 50)

        job = Job(
            "farmer",
            "Farmer",
            required_skills={"farming": 25},
        )

        self.assertTrue(citizen.can_perform_job(job))

    # Step 5: Test insufficient skills
    def test_job_rejects_insufficient_skill(self):
        citizen = Citizen("CIT-001", "Alex")

        job = Job(
            "farmer",
            "Farmer",
            required_skills={"farming": 25},
        )

        self.assertFalse(citizen.can_perform_job(job))

        with self.assertRaises(ValueError):
            citizen.set_job(job)

    # Step 6: Test assigning a job
    def test_assign_job(self):
        citizen = Citizen("CIT-001", "Alex")
        job = Job("farmer", "Farmer")

        citizen.set_job(job)

        self.assertIs(citizen.get_job(), job)
        self.assertEqual(citizen.get_occupation(), "Farmer")
        self.assertTrue(citizen.has_active_job())

    # Step 7: Test clearing a job
    def test_clear_job(self):
        citizen = Citizen("CIT-001", "Alex")
        job = Job("farmer", "Farmer")

        citizen.set_job(job)
        citizen.clear_job()

        self.assertIsNone(citizen.get_job())
        self.assertIsNone(citizen.get_occupation())
        self.assertFalse(citizen.has_active_job())

    # Step 8: Test inactive job
    def test_inactive_job_cannot_be_active(self):
        citizen = Citizen("CIT-001", "Alex")
        job = Job("farmer", "Farmer")
        job.deactivate()

        self.assertFalse(citizen.can_perform_job(job))

        with self.assertRaises(ValueError):
            citizen.set_job(job)

    # Step 9: Test dead citizen cannot hold an active job
    def test_dead_citizen_cannot_take_job(self):
        citizen = Citizen("CIT-001", "Alex")
        citizen.die()

        job = Job("farmer", "Farmer")

        self.assertFalse(citizen.can_perform_job(job))

        with self.assertRaises(ValueError):
            citizen.set_job(job)

    # Step 10: Test a citizen does not need employment
    def test_unemployed_citizen(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertIsNone(citizen.get_job())
        self.assertFalse(citizen.has_active_job())


if __name__ == "__main__":
    unittest.main()
