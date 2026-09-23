import unittest

from src.gaia.agents.action import ActionExecutor, ActionOption
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.core.simulation import Simulation


class TestEconomicProductionLoop(unittest.TestCase):

    # Step 1: A qualified worker can produce through the normal work action.
    def test_work_produces_and_pays_worker(self):
        employer = Citizen("employer", "Employer")
        worker = Citizen("worker", "Worker")

        employer.change_money(100)

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 2},
            wage=15,
            energy_cost=5
        )

        worker.set_job(job)

        result = ActionExecutor().execute(
            worker,
            ActionOption("work", "Work"),
            {
                "tick": 1,
                "employer": employer
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(worker.get_item_quantity("food"), 2)
        self.assertEqual(worker.get_money(), 15)
        self.assertEqual(employer.get_money(), 85)
        self.assertEqual(worker.energy, 95)

    # Step 2: A paid job with no available payer cannot complete through
    # the integrated simulation path.
    def test_paid_work_without_payer_does_not_produce(self):
        simulation = Simulation()
        worker = Citizen("worker", "Worker")

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 2},
            wage=15,
            energy_cost=5
        )

        worker.set_job(job)
        simulation.add_citizen(worker)

        simulation.is_running = True
        simulation.step()

        self.assertEqual(worker.get_item_quantity("food"), 0)
        self.assertEqual(worker.get_money(), 0)
        self.assertAlmostEqual(worker.energy, 99.4)

    # Step 3: The decision engine recognizes available work.
    def test_decision_engine_selects_work(self):
        simulation = Simulation()

        employer = Citizen("employer", "Employer")
        worker = Citizen("worker", "Worker")

        employer.change_money(100)

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 2},
            wage=10,
            energy_cost=5
        )

        worker.set_job(job)

        simulation.add_citizen(employer)
        simulation.add_citizen(worker)

        action = simulation.decision_engine.select_best_action(
            worker,
            world=simulation.world
        )

        self.assertIsNotNone(action)
        self.assertEqual(action.action_id, "work")

    # Step 4: The integrated simulation performs work and payroll.
    def test_simulation_integrates_work_and_wage(self):
        simulation = Simulation()

        employer = Citizen("employer", "Employer")
        worker = Citizen("worker", "Worker")

        employer.change_money(100)

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 2},
            wage=10,
            energy_cost=5
        )

        worker.set_job(job)

        simulation.add_citizen(employer)
        simulation.add_citizen(worker)

        simulation.is_running = True
        simulation.step()

        self.assertEqual(worker.get_item_quantity("food"), 2)
        self.assertEqual(worker.get_money(), 10)
        self.assertEqual(employer.get_money(), 90)

    # Step 5: Total money remains conserved after integrated payroll.
    def test_money_is_conserved(self):
        simulation = Simulation()

        employer = Citizen("employer", "Employer")
        worker = Citizen("worker", "Worker")

        employer.change_money(100)

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 2},
            wage=10,
            energy_cost=5
        )

        worker.set_job(job)

        simulation.add_citizen(employer)
        simulation.add_citizen(worker)

        initial_money = (
            employer.get_money()
            + worker.get_money()
        )

        simulation.is_running = True
        simulation.step()

        final_money = (
            employer.get_money()
            + worker.get_money()
        )

        self.assertEqual(final_money, initial_money)

    # Step 6: Dead workers cannot enter the production loop.
    def test_dead_worker_does_not_work(self):
        simulation = Simulation()

        employer = Citizen("employer", "Employer")
        worker = Citizen("worker", "Worker")

        employer.change_money(100)

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 2},
            wage=10,
            energy_cost=5
        )

        worker.set_job(job)
        worker.die()

        simulation.add_citizen(employer)
        simulation.add_citizen(worker)

        simulation.is_running = True
        simulation.step()

        self.assertEqual(worker.get_item_quantity("food"), 0)
        self.assertEqual(worker.get_money(), 0)
        self.assertEqual(employer.get_money(), 100)


if __name__ == "__main__":
    unittest.main()
