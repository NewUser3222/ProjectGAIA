import unittest
from unittest import mock

from src.gaia.agents.action import ActionOption
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.building import Building
from src.gaia.construction import BuildingDefinition, ConstructionProject
from src.gaia.core.simulation import Simulation
from src.gaia.vehicle import Vehicle
from src.gaia.visualization import Camera, build_scene_frame, snapshot_simulation


class TestVehicleTickMovement(unittest.TestCase):
    def make_simulation(self):
        simulation = Simulation()
        simulation.world.width = 10
        simulation.world.height = 8
        return simulation

    def test_registered_route_advances_by_speed_per_tick_and_is_visualized(self):
        simulation = self.make_simulation()
        vehicle = Vehicle("cart", "handcart", (1, 1), speed=2.0)
        simulation.world.transportation.add_vehicle(vehicle)
        result = simulation.world.transportation.assign_destination(vehicle, (7, 5))
        self.assertTrue(result["success"])

        simulation.start()
        simulation.step()

        expected_distance = (2.0 / (52 ** 0.5))
        self.assertAlmostEqual(vehicle.location[0], 1 + 6 * expected_distance)
        self.assertAlmostEqual(vehicle.location[1], 1 + 4 * expected_distance)
        scene = snapshot_simulation(simulation)
        frame = build_scene_frame(scene, Camera((0, 0), 100, 80, 10))
        record = next(item for item in frame.entities if item.entity_id == "cart")
        self.assertEqual(record.position, vehicle.location)
        self.assertEqual(simulation.tick, 1)

    def test_routes_are_reproducible_and_arrive_without_leaving_bounds(self):
        simulations = [self.make_simulation(), self.make_simulation()]
        for simulation in simulations:
            vehicle = Vehicle("edge", "cart", (8, 6), speed=1.5)
            simulation.world.transportation.add_vehicle(vehicle)
            self.assertTrue(
                simulation.world.transportation.assign_destination(vehicle, (9.5, 7.5))["success"]
            )
            simulation.start()

        for _ in range(4):
            for simulation in simulations:
                simulation.step()
        first, second = (sim.world.transportation.get_vehicle("edge") for sim in simulations)
        self.assertEqual(first.location, second.location)
        self.assertEqual(first.location, (9.5, 7.5))
        self.assertIsNone(first.destination)
        self.assertTrue(simulations[0].world.is_valid_location(first.location))

    def test_stationary_disabled_invalid_and_out_of_world_destinations_are_safe(self):
        simulation = self.make_simulation()
        stationary = Vehicle("still", "cart", (2, 2))
        disabled = Vehicle("disabled", "truck", (3, 3), operational_state="disabled")
        simulation.world.transportation.add_vehicle(stationary)
        simulation.world.transportation.add_vehicle(disabled)
        self.assertFalse(simulation.world.transportation.assign_destination(stationary, (10, 2))["success"])
        self.assertFalse(simulation.world.transportation.assign_destination(disabled, (5, 5))["success"])

        before = stationary.location
        simulation.start()
        simulation.step()
        self.assertEqual(stationary.location, before)
        self.assertEqual(disabled.location, (3, 3))

        corrupt = Vehicle("corrupt", "cart", (4, 4))
        simulation.world.transportation.add_vehicle(corrupt)
        simulation.world.transportation.assign_destination(corrupt, (8, 4))
        corrupt.location = (10, 4)
        simulation.step()
        self.assertEqual(corrupt.location, (10, 4))

    def test_vehicle_rejects_non_finite_or_non_positive_speed(self):
        for speed in (0, -1, float("nan"), float("inf")):
            with self.subTest(speed=speed), self.assertRaises(ValueError):
                Vehicle("invalid", "cart", speed=speed)

    def test_legacy_travel_remains_immediate_and_clears_any_route(self):
        simulation = self.make_simulation()
        citizen = Citizen("traveler", "Traveler", location=(1, 1))
        vehicle = Vehicle("cart", "cart", (1, 1))
        simulation.add_citizen(citizen)
        simulation.world.transportation.add_vehicle(vehicle)
        simulation.world.transportation.assign_destination(vehicle, (5, 5))
        result = simulation.world.transportation.travel(citizen, vehicle, (8, 6))
        self.assertTrue(result["success"])
        self.assertEqual(vehicle.location, (8, 6))
        self.assertIsNone(vehicle.destination)


class TestDecisionDrivenConstructionProgression(unittest.TestCase):
    def make_simulation(self, *, initial_metal=8, work_required=25):
        simulation = Simulation()
        simulation.world.set_resource("metal", initial_metal)
        worker = Citizen("builder", "Builder", age=30, location=(4, 4))
        simulation.add_citizen(worker)
        project = ConstructionProject(
            "workshop-project", simulation.world,
            BuildingDefinition("workshop", {"metal": 3}),
            "workshop", (5, 5), dimensions=(3, 2),
            work_required=work_required,
        )
        project.set_worker_job(Job("builder-job", "Builder"))
        simulation.add_construction_project(project)
        return simulation, worker, project

    def test_materials_gate_start_and_are_consumed_once_at_start(self):
        simulation, worker, project = self.make_simulation(initial_metal=2)
        self.assertFalse(project.start()["success"])
        self.assertEqual(project.status, "planned")
        self.assertEqual(simulation.world.get_resource("metal"), 2)
        self.assertFalse(project.add_worker(worker))
        simulation.start()
        simulation.step()
        self.assertEqual(project.work_completed, 0)

    def test_assigned_live_worker_progresses_building_through_completion_once(self):
        simulation, worker, project = self.make_simulation()
        self.assertTrue(project.start()["success"])
        self.assertEqual(simulation.world.get_resource("metal"), 5)
        self.assertTrue(project.add_worker(worker))
        self.assertTrue(project.add_worker(worker))
        simulation.start()

        simulation.step()
        self.assertEqual(project.work_completed, 0)
        self.assertEqual(simulation.get_movement_state(worker).status, "moving")
        simulation.step()
        self.assertEqual(project.work_completed, 0)
        self.assertEqual(worker.location, (5.0, 5.0))
        simulation.step()
        self.assertEqual(project.work_completed, 10)
        self.assertEqual(project.building.construction_status, "under_construction")
        simulation.step()
        self.assertEqual(project.work_completed, 20)
        simulation.step()
        self.assertEqual(project.work_completed, 25)
        self.assertEqual(project.status, "completed")
        self.assertEqual(project.building.construction_status, "completed")
        self.assertEqual(simulation.world.get_resource("metal"), 5)

        simulation.step()
        self.assertEqual(project.work_completed, 25)
        self.assertEqual(simulation.world.get_resource("metal"), 5)
        self.assertIs(simulation.world.get_building("workshop"), project.building)

        frame = build_scene_frame(
            snapshot_simulation(simulation), Camera((0, 0), 1000, 1000, 10),
        )
        building_record = next(item for item in frame.entities if item.entity_id == "workshop")
        self.assertEqual(building_record.state, "completed")

    def test_no_worker_dead_worker_or_ineligible_job_produces_no_work(self):
        simulation, worker, project = self.make_simulation()
        project.start()
        simulation.start()
        simulation.step()
        self.assertEqual(project.work_completed, 0)

        self.assertTrue(project.add_worker(worker))
        worker.die()
        simulation.step()
        self.assertEqual(project.work_completed, 0)
        self.assertEqual(project.workers, [])

    def test_only_registered_citizens_can_select_construction_work(self):
        simulation, worker, project = self.make_simulation()
        project.start()
        outsider = Citizen("outsider", "Outsider")
        self.assertTrue(project.add_worker(outsider))
        simulation.start()
        simulation.step()
        self.assertEqual(project.work_completed, 0)
        self.assertIn(outsider, project.workers)

    def test_selected_construct_action_is_not_applied_twice_in_one_tick(self):
        simulation, worker, project = self.make_simulation(work_required=100)
        project.start()
        self.assertTrue(project.add_worker(worker))
        simulation.start()
        construct = ActionOption(
            "construct", "Construct", requirements={"project": project, "work_amount": 5},
        )
        with mock.patch.object(simulation.decision_engine, "select_best_action", return_value=construct):
            simulation.step()
            self.assertEqual(project.work_completed, 0)
            simulation.step()
            self.assertEqual(project.work_completed, 0)
            simulation.step()
        self.assertEqual(project.work_completed, 5)
        self.assertEqual(project._worker_last_work_tick[worker], simulation.tick)

    def test_completed_and_abandoned_projects_stop_progressing(self):
        simulation, worker, project = self.make_simulation(work_required=10)
        project.start()
        project.add_worker(worker)
        simulation.start()
        simulation.step()
        self.assertFalse(project.is_complete())
        simulation.step()
        self.assertFalse(project.is_complete())
        simulation.step()
        self.assertTrue(project.is_complete())
        self.assertEqual(project.work_completed, 10)

        other = ConstructionProject(
            "abandoned", simulation.world, BuildingDefinition("shed", {"metal": 1}),
            "shed", (8, 8), work_required=10,
        )
        other.start()
        other.add_worker(worker)
        other.status = "abandoned"
        simulation.add_construction_project(other)
        simulation.step()
        self.assertEqual(other.work_completed, 0)

    def test_one_citizen_selects_at_most_one_project_per_tick(self):
        simulation, worker, first = self.make_simulation()
        first.project_id = "a-project"
        second = ConstructionProject(
            "b-project", simulation.world,
            BuildingDefinition("shed", {"metal": 1}),
            "shed", (8, 8), work_required=100,
        )
        self.assertTrue(first.start()["success"])
        self.assertTrue(second.start()["success"])
        self.assertTrue(first.add_worker(worker))
        self.assertTrue(second.add_worker(worker))
        simulation.add_construction_project(second)
        simulation.start()
        simulation.step()
        self.assertEqual(first.work_completed, 0)
        self.assertEqual(second.work_completed, 0)
        self.assertEqual(
            simulation.get_movement_state(worker).intent.target_id,
            "a-project",
        )

    def test_deactivated_worker_job_blocks_tick_progress(self):
        simulation, worker, project = self.make_simulation()
        self.assertTrue(project.start()["success"])
        self.assertTrue(project.add_worker(worker))
        project.worker_job.deactivate()
        simulation.start()
        simulation.step()
        self.assertEqual(project.work_completed, 0)

    def test_project_from_another_world_cannot_be_registered(self):
        simulation = Simulation()
        other_world = Simulation().world
        project = ConstructionProject(
            "foreign", other_world, BuildingDefinition("shed", {"wood": 1}),
            "foreign-shed", (1, 1),
        )
        with self.assertRaisesRegex(ValueError, "belong to this simulation"):
            simulation.add_construction_project(project)


if __name__ == "__main__":
    unittest.main()
