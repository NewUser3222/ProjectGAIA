# Step 1: Import unittest
import math
import unittest

# Step 2: Import GAIA models
from src.gaia.agents.action import ActionExecutor, ActionOption
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.economy_transactions import EconomicTransaction


class TestWages(unittest.TestCase):

    # Step 3: Test direct wage transaction
    def test_pay_wage(self):
        payer = Citizen("CIT-001", "Payer")
        worker = Citizen("CIT-002", "Worker")

        payer.change_money(100)

        result = EconomicTransaction.pay_wage(
            payer,
            worker,
            25
        )

        self.assertTrue(result.success)
        self.assertEqual(result.transaction_type, "wage")
        self.assertEqual(result.amount, 25.0)
        self.assertEqual(payer.get_money(), 75)
        self.assertEqual(worker.get_money(), 25)

    # Step 4: Test work pays configured wage
    def test_work_pays_wage(self):
        employer = Citizen("CIT-001", "Employer")
        worker = Citizen("CIT-002", "Worker")

        employer.change_money(100)

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 2},
            wage=15,
            energy_cost=5,
        )

        worker.set_job(job)

        result = ActionExecutor().execute(
            worker,
            ActionOption("work", "Work"),
            {"tick": 5, "employer": employer}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["wage"], 15.0)
        self.assertEqual(employer.get_money(), 85)
        self.assertEqual(worker.get_money(), 15)
        self.assertEqual(worker.get_item_quantity("food"), 2)

    # Step 5: Test insufficient payer funds
    def test_insufficient_payer_funds(self):
        employer = Citizen("CIT-001", "Employer")
        worker = Citizen("CIT-002", "Worker")

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 2},
            wage=15,
        )

        worker.set_job(job)

        result = ActionExecutor().execute(
            worker,
            ActionOption("work", "Work"),
            {"tick": 5, "employer": employer}
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["reason"],
            "Wage payer does not have enough money."
        )

        # Work must be atomic on payment failure.
        self.assertEqual(worker.get_item_quantity("food"), 0)
        self.assertEqual(worker.energy, 100.0)
        self.assertEqual(worker.get_money(), 0)
        self.assertEqual(employer.get_money(), 0)

    # Step 6: Test missing wage payer
    def test_missing_wage_payer(self):
        worker = Citizen("CIT-001", "Worker")

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 2},
            wage=10,
        )

        worker.set_job(job)

        result = ActionExecutor().execute(
            worker,
            ActionOption("work", "Work")
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["reason"],
            "No wage payer provided."
        )
        self.assertEqual(worker.get_item_quantity("food"), 0)

    # Step 7: Test invalid wage
    def test_negative_wage_rejected(self):
        with self.assertRaises(ValueError):
            Job(
                "farmer",
                "Farmer",
                production={"food": 2},
                wage=-1,
            )

    # Step 8: Test dead worker receives no wage
    def test_dead_worker_receives_no_wage(self):
        employer = Citizen("CIT-001", "Employer")
        worker = Citizen("CIT-002", "Worker")

        employer.change_money(100)

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 2},
            wage=15,
        )

        worker.set_job(job)
        worker.die()

        result = ActionExecutor().execute(
            worker,
            ActionOption("work", "Work"),
            {"employer": employer}
        )

        self.assertFalse(result["success"])
        self.assertEqual(employer.get_money(), 100)
        self.assertEqual(worker.get_money(), 0)
        self.assertEqual(worker.get_item_quantity("food"), 0)

    # Step 9: Test wage conservation
    def test_money_is_conserved(self):
        employer = Citizen("CIT-001", "Employer")
        worker = Citizen("CIT-002", "Worker")

        employer.change_money(100)

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 1},
            wage=20,
        )

        worker.set_job(job)

        before = employer.get_money() + worker.get_money()

        result = ActionExecutor().execute(
            worker,
            ActionOption("work", "Work"),
            {"employer": employer}
        )

        after = employer.get_money() + worker.get_money()

        self.assertTrue(result["success"])
        self.assertEqual(before, after)

    def test_inactive_or_dead_participants_cannot_process_payroll(self):
        from src.gaia.business import Business

        worker = Citizen("worker", "Worker")
        business = Business("business", "Business")
        business.change_money(100)
        business.deactivate()

        with self.assertRaises(ValueError):
            EconomicTransaction.pay_wage(business, worker, 10)

        business.activate()
        worker.die()
        with self.assertRaises(ValueError):
            EconomicTransaction.pay_wage(business, worker, 10)

        self.assertEqual(business.get_money(), 100)
        self.assertEqual(worker.get_money(), 0)

    def test_non_finite_wages_are_rejected(self):
        payer = Citizen("payer", "Payer")
        worker = Citizen("worker", "Worker")
        payer.change_money(100)

        for wage in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                EconomicTransaction.pay_wage(payer, worker, wage)
            with self.assertRaises(ValueError):
                Job("job", "Job", production={"food": 1}, wage=wage)

        self.assertEqual(payer.get_money(), 100)
        self.assertEqual(worker.get_money(), 0)

    def test_payroll_balance_overflow_is_rejected_atomically(self):
        payer = Citizen("payer", "Payer")
        worker = Citizen("worker", "Worker")
        payer.change_money(1e308)
        worker.change_money(1e308)

        with self.assertRaises(ValueError):
            EconomicTransaction.pay_wage(payer, worker, 1e308)

        self.assertEqual(payer.get_money(), 1e308)
        self.assertEqual(worker.get_money(), 1e308)

    # Step 10: Test zero-wage jobs do not require a payer
    def test_zero_wage_job(self):
        worker = Citizen("CIT-001", "Worker")

        job = Job(
            "farmer",
            "Farmer",
            production={"food": 1},
            wage=0,
        )

        worker.set_job(job)

        result = ActionExecutor().execute(
            worker,
            ActionOption("work", "Work")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["wage"], 0.0)
        self.assertEqual(worker.get_item_quantity("food"), 1)


if __name__ == "__main__":
    unittest.main()
