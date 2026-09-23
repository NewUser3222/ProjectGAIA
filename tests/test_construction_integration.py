# Step 65: Integrated construction and physical-world loop tests

import unittest

from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.business import Business
from src.gaia.construction import BuildingDefinition, ConstructionProject
from src.gaia.core.simulation import Simulation


class TestIntegratedConstructionLoop(unittest.TestCase):

    def create_project(
        self,
        simulation,
        project_id,
        building_id,
        location,
        wood_required=20,
        work_required=20,
        owner=None,
    ):
        definition = BuildingDefinition(
            "workshop",
            required_materials={"wood": wood_required},
        )

        project = ConstructionProject(
            project_id,
            simulation.world,
            definition,
            building_id,
            location,
            owner=owner,
            work_required=work_required,
        )

        return project

    # Step 65: Projects can be registered with the simulation.
    def test_simulation_tracks_construction_projects(self):
        simulation = Simulation()

        project = self.create_project(
            simulation,
            "PROJECT-651",
            "BUILDING-651",
            (10, 10),
        )

        simulation.add_construction_project(project)

        self.assertEqual(
            simulation.get_construction_projects(),
            [project],
        )

    # Step 65: Construction consumes configured resources exactly once.
    def test_construction_consumes_resources_once(self):
        simulation = Simulation()
        simulation.world.set_resource("wood", 50)

        project = self.create_project(
            simulation,
            "PROJECT-652",
            "BUILDING-652",
            (10, 10),
        )

        self.assertTrue(project.start()["success"])
        self.assertEqual(simulation.world.get_resource("wood"), 30)

        self.assertFalse(project.start()["success"])
        self.assertEqual(simulation.world.get_resource("wood"), 30)

    # Step 65: Failed construction does not mutate the physical world.
    def test_failed_construction_does_not_create_building(self):
        simulation = Simulation()
        simulation.world.set_resource("wood", 5)

        project = self.create_project(
            simulation,
            "PROJECT-653",
            "BUILDING-653",
            (20, 20),
        )

        result = project.start()

        self.assertFalse(result["success"])
        self.assertEqual(simulation.world.get_resource("wood"), 5)
        self.assertIsNone(
            simulation.world.get_building("BUILDING-653")
        )

    # Step 65: Construction progress creates a completed usable building.
    def test_completed_construction_exists_in_world(self):
        simulation = Simulation()
        simulation.world.set_resource("wood", 20)

        worker = Citizen("CIT-651", "Builder")
        job = Job("JOB-651", "Construction Worker")

        project = self.create_project(
            simulation,
            "PROJECT-654",
            "BUILDING-654",
            (30, 30),
            work_required=20,
            owner=worker,
        )

        project.set_worker_job(job)

        self.assertTrue(project.start()["success"])
        self.assertTrue(project.add_worker(worker))

        self.assertTrue(project.perform_work(worker, 20)["success"])

        building = simulation.world.get_building("BUILDING-654")

        self.assertIsNotNone(building)
        self.assertTrue(building.is_completed())
        self.assertTrue(building.is_active())
        self.assertIs(building.owner, worker)

    # Step 65: Multiple construction projects remain independent.
    def test_multiple_projects_remain_independent(self):
        simulation = Simulation()
        simulation.world.set_resource("wood", 100)

        worker_one = Citizen("CIT-652", "Builder One")
        worker_two = Citizen("CIT-653", "Builder Two")

        project_one = self.create_project(
            simulation,
            "PROJECT-655-A",
            "BUILDING-655-A",
            (40, 40),
            work_required=20,
        )

        project_two = self.create_project(
            simulation,
            "PROJECT-655-B",
            "BUILDING-655-B",
            (50, 50),
            work_required=40,
        )

        job = Job("JOB-652", "Construction Worker")

        project_one.set_worker_job(job)
        project_two.set_worker_job(job)

        self.assertTrue(project_one.start()["success"])
        self.assertTrue(project_two.start()["success"])

        self.assertTrue(project_one.add_worker(worker_one))
        self.assertTrue(project_two.add_worker(worker_two))

        project_one.perform_work(worker_one, 20)
        project_two.perform_work(worker_two, 10)

        self.assertTrue(project_one.is_complete())
        self.assertFalse(project_two.is_complete())
        self.assertEqual(project_two.work_completed, 10)

    # Step 65: Dead construction workers stop participating on simulation ticks.
    def test_simulation_removes_dead_construction_workers(self):
        simulation = Simulation()
        simulation.world.set_resource("wood", 20)

        worker = Citizen("CIT-654", "Builder")
        job = Job("JOB-653", "Construction Worker")

        project = self.create_project(
            simulation,
            "PROJECT-656",
            "BUILDING-656",
            (60, 60),
        )

        project.set_worker_job(job)
        project.start()
        project.add_worker(worker)

        simulation.add_construction_project(project)

        worker.die()

        simulation.start()
        simulation.step()

        self.assertEqual(project.workers, [])

    # Step 65: Business relationships remain intact after construction.
    def test_completed_building_can_associate_with_business(self):
        simulation = Simulation()
        simulation.world.set_resource("wood", 20)

        worker = Citizen("CIT-655", "Builder")
        business = Business("BUS-651", "Workshop")

        project = self.create_project(
            simulation,
            "PROJECT-657",
            "BUILDING-657",
            (70, 70),
            owner=worker,
        )

        project.start()
        project.set_worker_job(Job("JOB-654", "Construction Worker"))
        project.add_worker(worker)
        project.perform_work(worker, 20)

        building = simulation.world.get_building("BUILDING-657")
        building.set_associated_business(business)

        self.assertIs(building.get_associated_business(), business)
        self.assertTrue(building.is_available_for_use())

    # Step 65: Occupancy works on the completed physical building.
    def test_completed_building_supports_occupancy(self):
        simulation = Simulation()
        simulation.world.set_resource("wood", 20)

        worker = Citizen("CIT-656", "Builder")

        project = self.create_project(
            simulation,
            "PROJECT-658",
            "BUILDING-658",
            (80, 80),
        )

        project.start()
        project.set_worker_job(Job("JOB-655", "Construction Worker"))
        project.add_worker(worker)
        project.perform_work(worker, 20)

        building = simulation.world.get_building("BUILDING-658")
        building.add_occupant(worker)

        self.assertTrue(building.has_occupant(worker))
        self.assertEqual(building.get_occupants(), [worker])


if __name__ == "__main__":
    unittest.main()
