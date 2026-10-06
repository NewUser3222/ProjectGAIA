"""Bounded citizen movement owned and advanced by the Simulation Engine."""

from dataclasses import FrozenInstanceError
import math
import unittest

from src.gaia.agents.action import ActionOption
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.building import Building
from src.gaia.business import Business
from src.gaia.construction import BuildingDefinition, ConstructionProject
from src.gaia.core.simulation import Simulation
from src.gaia.movement import MovementIntent
from src.gaia.observer import GAIAObserver
from src.gaia.persistence import SQLiteHistoryStore
from src.gaia.visualization import snapshot_simulation


class TestMovementIntent(unittest.TestCase):
    def test_intent_is_immutable_detached_and_json_compatible(self):
        destination = [4, 7.5]
        intent = MovementIntent(destination, "visit", "building", "house")
        destination[0] = 99
        self.assertEqual(intent.destination, (4.0, 7.5))
        self.assertEqual(intent.to_dict(), {
            "destination": (4.0, 7.5),
            "reason": "visit",
            "target_kind": "building",
            "target_id": "house",
        })
        with self.assertRaises(FrozenInstanceError):
            intent.reason = "changed"

    def test_invalid_coordinate_and_partial_target_values_are_rejected(self):
        for destination in ((1,), (True, 2), (math.nan, 2), (1, math.inf), ("2", 3)):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                MovementIntent(destination)
        with self.assertRaisesRegex(ValueError, "provided together"):
            MovementIntent((1, 2), target_kind="building")


class TestSimulationCitizenMovement(unittest.TestCase):
    def make_simulation(self, location=(1, 1), speed=1.5):
        simulation = Simulation()
        simulation.world.width = 10
        simulation.world.height = 8
        citizen = Citizen("walker", "Walker", age=30, location=location)
        citizen.speed = speed
        simulation.add_citizen(citizen)
        return simulation, citizen

    def run_ticks(self, simulation, count):
        simulation.start()
        for _ in range(count):
            simulation.step()

    def test_request_is_validated_without_moving_and_duplicate_is_idempotent(self):
        simulation, citizen = self.make_simulation()
        original = citizen.location
        result = simulation.request_movement(citizen, (5, 1), reason="visit")
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "moving")
        self.assertEqual(citizen.location, original)
        state = simulation.get_movement_state(citizen)
        self.assertEqual(state.intent.destination, (5.0, 1.0))

        event_count = len(simulation.event_records)
        duplicate = simulation.request_movement(citizen, [5, 1], reason="visit")
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(len(simulation.event_records), event_count)

    def test_invalid_membership_liveness_coordinates_and_half_open_bounds(self):
        simulation, citizen = self.make_simulation()
        outsider = Citizen("outsider", "Outsider")
        self.assertFalse(simulation.request_movement(outsider, (2, 2))["success"])
        for destination in ((10, 2), (2, 8), (-0.01, 1), (math.nan, 1)):
            with self.subTest(destination=destination):
                self.assertFalse(simulation.request_movement(citizen, destination)["success"])
        citizen.die()
        self.assertFalse(simulation.request_movement(citizen, (2, 2))["success"])
        self.assertEqual(citizen.location, (1, 1))

    def test_movement_is_deterministic_bounded_and_snaps_without_overshoot(self):
        runs = []
        for _ in range(2):
            simulation, citizen = self.make_simulation()
            simulation.request_movement(citizen, (5, 1))
            self.run_ticks(simulation, 4)
            runs.append((citizen.location, simulation.get_movement_state(citizen).status))
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[0], ((5.0, 1.0), "arrived"))
        simulation, citizen = self.make_simulation(speed=20)
        simulation.request_movement(citizen, (9.9, 7.9))
        self.run_ticks(simulation, 1)
        self.assertEqual(citizen.location, (9.9, 7.9))
        self.assertTrue(simulation.world.is_valid_location(citizen.location))

        simulation, slow = self.make_simulation(speed=0.05)
        simulation.request_movement(slow, (1.2, 1))
        self.run_ticks(simulation, 1)
        self.assertAlmostEqual(slow.location[0], 1.05)

    def test_multiple_citizens_move_in_stable_order_and_empty_simulation_ticks(self):
        simulation, first = self.make_simulation(location=(1, 1))
        second = Citizen("second", "Second", age=30, location=(2, 2))
        second.speed = 1
        simulation.add_citizen(second)
        simulation.request_movement(first, (8, 1))
        simulation.request_movement(second, (2, 7))
        self.run_ticks(simulation, 1)
        self.assertEqual(first.location, (2.5, 1.0))
        self.assertEqual(second.location, (2.0, 3.0))

        empty = Simulation()
        empty.start()
        empty.step()
        self.assertEqual(empty.tick, 1)

    def test_already_reached_request_and_ticks_after_arrival_do_not_drift(self):
        simulation, citizen = self.make_simulation(location=(2, 2))
        result = simulation.request_movement(citizen, (2, 2), reason="arrived")
        self.assertEqual(result["status"], "arrived")
        self.assertEqual(simulation.get_movement_state(citizen).status, "arrived")
        self.run_ticks(simulation, 3)
        self.assertEqual(citizen.location, (2, 2))
        arrivals = [event for event in simulation.event_records if event.event_type == "movement_arrived"]
        self.assertEqual(len(arrivals), 1)

    def test_retarget_cancel_death_and_target_removal_are_handled(self):
        simulation, citizen = self.make_simulation()
        self.assertTrue(simulation.request_movement(citizen, (8, 1))["success"])
        self.run_ticks(simulation, 1)
        first_position = citizen.location
        self.assertTrue(simulation.request_movement(citizen, (1, 6))["success"])
        self.assertEqual(simulation.get_movement_state(citizen).intent.destination, (1.0, 6.0))
        self.assertTrue(any(event.event_type == "movement_cancelled" for event in simulation.event_records))
        self.assertTrue(simulation.cancel_movement(citizen, "test cancellation")["success"])
        self.assertEqual(citizen.location, first_position)
        self.assertFalse(simulation.cancel_movement(citizen)["success"])

        building = Building("site", "house", (7, 6), construction_status="completed")
        simulation.world.add_building(building)
        self.assertTrue(simulation.request_movement(
            citizen, (7, 6), target_kind="building", target_id="site"
        )["success"])
        simulation.world.remove_building(building)
        self.run_ticks(simulation, 1)
        self.assertEqual(simulation.get_movement_state(citizen).status, "cancelled")

        self.assertTrue(simulation.request_movement(citizen, (8, 6))["success"])
        citizen.die()
        before = citizen.location
        self.run_ticks(simulation, 1)
        self.assertEqual(citizen.location, before)
        self.assertEqual(simulation.get_movement_state(citizen).status, "cancelled")

    def test_observer_records_meaningful_movement_events_not_intermediate_steps(self):
        simulation, citizen = self.make_simulation(speed=1)
        simulation.request_movement(citizen, (4, 1), reason="test trip")
        self.run_ticks(simulation, 5)
        report = GAIAObserver().observe(simulation)
        kinds = [event.event_type for event in report.events]
        self.assertEqual(kinds.count("movement_intent_accepted"), 1)
        self.assertEqual(kinds.count("movement_arrived"), 1)
        self.assertNotIn("movement_step", kinds)
        self.assertIn("(1.0, 1.0)", next(
            event.description for event in report.events
            if event.event_type == "movement_intent_accepted"
        ))

        store = SQLiteHistoryStore(
            "file:gaia-movement-history?mode=memory&cache=shared",
            simulation_id="movement-test",
        ).initialize()
        try:
            store.save_report(report)
            stored_types = [event["event_type"] for event in store.list_events()]
            self.assertIn("movement_intent_accepted", stored_types)
            self.assertIn("movement_arrived", stored_types)
        finally:
            store.close()

    def test_stopped_simulation_does_not_move_pending_intents(self):
        simulation, citizen = self.make_simulation()
        simulation.request_movement(citizen, (8, 1))
        simulation.step()
        self.assertEqual(citizen.location, (1, 1))
        self.run_ticks(simulation, 1)
        self.assertNotEqual(citizen.location, (1, 1))

    def test_detached_visualization_reflects_engine_position_and_intent_state(self):
        simulation, citizen = self.make_simulation()
        simulation.request_movement(citizen, (5, 1), reason="visualized")
        first = snapshot_simulation(simulation)
        record = next(item for item in first.entities if item.entity_id == "walker")
        self.assertEqual(record.position, (1.0, 1.0))
        self.assertEqual(dict(record.details)["movement_status"], "moving")
        self.assertEqual(dict(record.details)["movement_destination"], (5.0, 1.0))

        self.run_ticks(simulation, 1)
        second = snapshot_simulation(simulation)
        moved_record = next(item for item in second.entities if item.entity_id == "walker")
        self.assertEqual(moved_record.position, (2.5, 1.0))
        self.assertEqual(dict(moved_record.details)["movement_status"], "moving")
        self.assertEqual(record.position, (1.0, 1.0))


class TestMovementActivityIntegration(unittest.TestCase):
    def test_construction_work_waits_for_site_arrival_and_consumes_material_once(self):
        simulation = Simulation()
        simulation.world.width = 20
        simulation.world.height = 20
        simulation.world.set_resource("wood", 5)
        worker = Citizen("builder", "Builder", age=30, location=(1, 1))
        simulation.add_citizen(worker)
        project = ConstructionProject(
            "site-work", simulation.world,
            BuildingDefinition("workshop", {"wood": 2}),
            "workshop", (4, 1), work_required=20,
        )
        self.assertTrue(project.start()["success"])
        self.assertTrue(project.add_worker(worker))
        simulation.add_construction_project(project)
        remaining_material = simulation.world.get_resource("wood")

        simulation.start()
        simulation.step()
        self.assertEqual(worker.location, (2.0, 1.0))
        self.assertEqual(project.work_completed, 0)
        simulation.step()
        self.assertEqual(worker.location, (3.0, 1.0))
        self.assertEqual(project.work_completed, 0)
        simulation.step()
        self.assertEqual(worker.location, (4.0, 1.0))
        self.assertEqual(project.work_completed, 0)
        self.assertEqual(simulation.get_movement_state(worker).status, "arrived")
        simulation.step()
        self.assertEqual(project.work_completed, 10)
        simulation.step()
        self.assertEqual(project.work_completed, 20)
        self.assertTrue(project.is_complete())
        self.assertEqual(simulation.world.get_resource("wood"), remaining_material + 10)

    def test_associated_business_work_requires_arrival_but_unassociated_work_stays_abstract(self):
        simulation = Simulation()
        simulation.world.width = 30
        simulation.world.height = 20
        worker = Citizen("employee", "Employee", age=30, location=(1, 1))
        simulation.add_citizen(worker)
        business = Business("shop", "Shop")
        simulation.add_business(business)
        site = Building("shop-site", "shop", (5, 1), construction_status="completed")
        site.set_associated_business(business)
        simulation.world.add_building(site)
        job = Job("shop-job", "Shop worker", production={"food": 1})
        business.add_job(job)
        business.employ(worker, job)
        simulation.start()

        simulation.step()
        self.assertEqual(worker.location, (2.0, 1.0))
        self.assertEqual(business.get_item_quantity("food"), 0)
        simulation.step()
        simulation.step()
        simulation.step()
        self.assertEqual(worker.location, (5.0, 1.0))
        self.assertEqual(business.get_item_quantity("food"), 0)
        simulation.step()
        self.assertEqual(business.get_item_quantity("food"), 1)

    def test_registered_action_with_destination_moves_then_executes_only_after_arrival(self):
        simulation = Simulation()
        simulation.world.width = 12
        simulation.world.height = 12
        citizen = Citizen("visitor", "Visitor", age=30, location=(1, 1))
        simulation.add_citizen(citizen)
        executions = []
        simulation.decision_engine.register_action_provider(
            lambda subject, world, context: [ActionOption(
                "visit", "Visit", 10,
                requirements={"destination": (3, 1), "movement_reason": "visit"},
            )]
        )
        simulation.decision_engine.action_executor.register_handler(
            "visit",
            lambda subject, action, context: executions.append(subject.citizen_id)
            or {"success": True, "action": "visit"},
        )
        simulation.start()
        simulation.step()
        self.assertEqual(citizen.location, (2.0, 1.0))
        self.assertEqual(executions, [])
        simulation.step()
        self.assertEqual(citizen.location, (3.0, 1.0))
        self.assertEqual(executions, [])
        simulation.step()
        self.assertEqual(executions, ["visitor"])

    def test_business_without_spatial_association_keeps_abstract_work_activity(self):
        simulation = Simulation()
        worker = Citizen("employee", "Employee")
        simulation.add_citizen(worker)
        business = Business("remote", "Remote")
        simulation.add_business(business)
        job = Job("remote-job", "Remote worker", production={"food": 1})
        business.add_job(job)
        business.employ(worker, job)
        simulation.start()
        simulation.step()
        self.assertEqual(worker.location, (0, 0))
        self.assertEqual(business.get_item_quantity("food"), 1)


if __name__ == "__main__":
    unittest.main()
