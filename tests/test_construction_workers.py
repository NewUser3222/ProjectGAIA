# Step 63: Construction project and worker tests
import unittest

from src.gaia.agents.action import ActionExecutor, ActionOption
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.construction import (
    BuildingDefinition,
    ConstructionProject,
)
from src.gaia.simulation.world import WorldState


class TestConstructionProject(unittest.TestCase):

    def create_project(self):
        world = WorldState()
        world.set_resource("wood", 100)

        definition = BuildingDefinition(
            "house",
            required_materials={"wood": 20},
        )

        project = ConstructionProject(
            "PROJECT-631",
            world,
            definition,
            "BUILDING-631",
            (10, 20),
            work_required=30,
        )

        return world, project

    def test_project_requires_materials_before_starting(self):
        world = WorldState()
        world.set_resource("wood", 10)

        definition = BuildingDefinition(
            "house",
            required_materials={"wood": 20},
        )

        project = ConstructionProject(
            "PROJECT-632",
            world,
            definition,
            "BUILDING-632",
            (1, 1),
        )

        result = project.start()

        self.assertFalse(result["success"])
        self.assertEqual(project.status, "planned")
        self.assertEqual(world.get_resource("wood"), 10)
        self.assertEqual(len(world.get_buildings()), 0)

    def test_start_consumes_materials_and_creates_building(self):
        world, project = self.create_project()

        result = project.start()

        self.assertTrue(result["success"])
        self.assertEqual(project.status, "under_construction")
        self.assertTrue(project.materials_consumed)
        self.assertEqual(world.get_resource("wood"), 80)
        self.assertEqual(len(world.get_buildings()), 1)
        self.assertEqual(
            world.get_building("BUILDING-631").construction_status,
            "under_construction",
        )

    def test_worker_progress_completes_building(self):
        world, project = self.create_project()
        project.start()

        worker = Citizen("CIT-631", "Builder")
        job = Job(
            "JOB-631",
            "Construction Worker",
            energy_cost=1,
        )

        project.set_worker_job(job)
        self.assertTrue(project.add_worker(worker))

        first = project.perform_work(worker, 10)
        second = project.perform_work(worker, 20)

        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(project.work_completed, 30)
        self.assertTrue(project.is_complete())
        self.assertEqual(
            project.building.construction_status,
            "completed",
        )

    def test_multiple_workers_contribute_independently(self):
        world, project = self.create_project()
        project.start()

        worker_one = Citizen("CIT-632", "Builder One")
        worker_two = Citizen("CIT-633", "Builder Two")

        job = Job(
            "JOB-632",
            "Construction Worker",
        )

        project.set_worker_job(job)

        self.assertTrue(project.add_worker(worker_one))
        self.assertTrue(project.add_worker(worker_two))

        self.assertTrue(
            project.perform_work(worker_one, 10)["success"]
        )
        self.assertTrue(
            project.perform_work(worker_two, 10)["success"]
        )

        self.assertEqual(project.work_completed, 20)
        self.assertFalse(project.is_complete())

    def test_dead_worker_cannot_continue(self):
        world, project = self.create_project()
        project.start()

        worker = Citizen("CIT-634", "Builder")
        job = Job("JOB-633", "Construction Worker")

        project.set_worker_job(job)
        self.assertTrue(project.add_worker(worker))

        worker.die()

        result = project.perform_work(worker, 10)

        self.assertFalse(result["success"])
        self.assertEqual(project.work_completed, 0)

    def test_unassigned_worker_cannot_work(self):
        world, project = self.create_project()
        project.start()

        worker = Citizen("CIT-635", "Builder")

        result = project.perform_work(worker, 10)

        self.assertFalse(result["success"])
        self.assertEqual(project.work_completed, 0)

    def test_construct_action_uses_existing_action_executor(self):
        world, project = self.create_project()
        project.start()

        worker = Citizen("CIT-636", "Builder")
        job = Job("JOB-634", "Construction Worker")

        project.set_worker_job(job)
        self.assertTrue(project.add_worker(worker))

        action = ActionOption(
            "construct",
            "Construct Building",
            requirements={
                "project": project,
                "work_amount": 15,
            },
        )

        result = ActionExecutor().execute(
            worker,
            action,
            {
                "tick": 1,
                "world": world,
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(project.work_completed, 15)
        self.assertEqual(len(worker.memories), 1)


if __name__ == "__main__":
    unittest.main()

