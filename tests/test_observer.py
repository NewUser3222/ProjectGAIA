import unittest
import json
from unittest import mock

from src.gaia.agents.citizen import Citizen
from src.gaia.building import Building
from src.gaia.business import Business
from src.gaia.construction import BuildingDefinition, ConstructionProject
from src.gaia.core.simulation import Simulation
from src.gaia.governor import GAIAGovernor
from src.gaia.observer import GAIAObserver, HistoricalEvent
from src.gaia.vehicle import Vehicle


class TestGAIAObserver(unittest.TestCase):
    def setUp(self):
        self.simulation = Simulation()
        self.observer = GAIAObserver()

    def test_empty_world_returns_empty_immutable_history(self):
        report = self.observer.observe(self.simulation)

        self.assertEqual(report.events, ())
        self.assertEqual(report.citizens, ())
        self.assertEqual(len(report.world_snapshots), 1)
        with self.assertRaises(AttributeError):
            report.simulation_tick = 3

    def test_records_history_and_memory_once_in_deterministic_order(self):
        citizen = Citizen("c1", "Ada")
        citizen.record_history("Citizen was born.")
        citizen.add_memory("Met another citizen", tick=2)
        self.simulation.add_citizen(citizen)
        self.simulation.tick = 3
        self.simulation.world.current_tick = 3

        first = self.observer.observe(self.simulation)
        second = self.observer.observe(self.simulation)

        self.assertEqual(first.events, second.events)
        self.assertEqual(len(second.world_snapshots), 2)
        fresh = GAIAObserver().observe(self.simulation)
        self.assertEqual(first, fresh)
        self.assertEqual(first.to_json(), fresh.to_json())
        self.assertEqual(json.loads(first.to_json())["simulation_tick"], 3)
        self.assertEqual(
            [event.sequence for event in first.events], [0, 1, 2]
        )
        self.assertEqual(
            [event.event_type for event in first.events],
            ["citizen_created", "birth", "citizen_memory"],
        )
        self.assertEqual(first.events[2].event_tick, 2)
        self.assertEqual(first.events[1].event_tick, None)
        self.assertEqual(first.events[1].observed_world_tick, 3)
        self.assertTrue(all(isinstance(event, HistoricalEvent) for event in first.events))

    def test_records_death_once_and_keeps_archive_after_active_removal(self):
        parent = Citizen("p1", "Parent")
        other_parent = Citizen("p2", "Other Parent")
        self.simulation.add_citizen(parent)
        self.simulation.add_citizen(other_parent)
        citizen = self.simulation.create_child(
            parent, other_parent, "c1", "Ada"
        )
        citizen.die()

        first = self.observer.observe(self.simulation)
        self.simulation.citizens.remove(citizen)
        second = self.observer.observe(self.simulation)

        self.assertEqual(
            [event.event_type for event in first.events].count("death"), 1
        )
        self.assertEqual(len(second.events), len(first.events))
        archive = next(item for item in second.citizens if item.citizen_id == "c1")
        self.assertEqual(archive.lifecycle_state, "dead")
        self.assertEqual(archive.parents, ("p1", "p2"))
        self.assertEqual(archive.relationships, (("p1", "parent"), ("p2", "parent")))
        self.assertEqual(archive.first_observed_tick, 0)
        parent_archive = next(item for item in second.citizens if item.citizen_id == "p1")
        self.assertIn("c1", parent_archive.children)

    def test_archives_observed_life_stage_transitions_with_observation_context(self):
        citizen = Citizen("c1", "Ada", age=12)
        self.simulation.add_citizen(citizen)
        self.observer.observe(self.simulation)

        citizen.age_up(1)
        self.simulation.tick = self.simulation.world.current_tick = 1
        report = self.observer.observe(self.simulation)

        transition = next(
            event for event in report.events
            if event.event_type == "life_stage_transition"
        )
        self.assertEqual(transition.event_tick, None)
        self.assertEqual(transition.observed_world_tick, 1)
        self.assertEqual(
            transition.description,
            "Life stage changed from Child to Young Adult.",
        )
        self.assertEqual(citizen.history, ["Citizen created."])

    def test_observer_does_not_mutate_simulation_state(self):
        citizen = Citizen("c1", "Ada")
        citizen.add_memory("A recorded event", tick=0)
        self.simulation.add_citizen(citizen)
        before = (
            self.simulation.tick,
            self.simulation.world.current_tick,
            tuple(self.simulation.citizens),
            tuple(citizen.history),
            tuple(citizen.memories),
        )

        self.observer.observe(self.simulation)

        self.assertEqual(before, (
            self.simulation.tick,
            self.simulation.world.current_tick,
            tuple(self.simulation.citizens),
            tuple(citizen.history),
            tuple(citizen.memories),
        ))

    def test_world_snapshots_capture_supported_systems_as_copies(self):
        world = self.simulation.world
        world.set_resource("food", 12)
        building = Building("h1", "house", (1, 2), construction_status="completed")
        world.add_building(building)
        business = Business("b1", "Shop")
        business.add_item("food", 3)
        self.simulation.add_business(business)
        project = ConstructionProject(
            "p1", world, BuildingDefinition("house"), "h2", (3, 4)
        )
        self.simulation.add_construction_project(project)
        vehicle = Vehicle("v1", "cart")
        world.transportation.add_vehicle(vehicle)

        first = self.observer.observe(self.simulation).world_snapshots[-1]
        world.set_resource("food", 7)
        business.add_item("wood", 1)
        second = self.observer.observe(self.simulation).world_snapshots[-1]

        self.assertEqual(dict(first.resources)["food"], 12)
        self.assertEqual(dict(second.resources)["food"], 7)
        self.assertEqual(first.buildings[0][0], "h1")
        self.assertEqual(first.businesses[0][0], "b1")
        self.assertEqual(first.construction_projects[0][0], "p1")
        self.assertEqual(first.vehicles[0][0], "v1")
        self.assertNotEqual(first.businesses, second.businesses)

    def test_tracks_new_persistent_resolved_and_recurring_findings(self):
        governor = GAIAGovernor()
        for resource in self.simulation.world.resources:
            self.simulation.world.set_resource(resource, 500)
        self.simulation.world.set_resource("food", 50)

        first = self.observer.record_governor_report(
            governor.observe(self.simulation)
        )
        self.assertEqual(len(first.new), 1)
        self.assertEqual(first.new[0].status, "new")

        self.simulation.tick = self.simulation.world.current_tick = 1
        self.simulation.world.set_resource("food", 60)
        second = self.observer.record_governor_report(
            governor.observe(self.simulation)
        )
        self.assertEqual(len(second.persistent), 1)
        self.assertEqual(second.persistent[0].observations, 2)
        self.assertEqual(
            dict(self.observer.observe(self.simulation).finding_history[0].evidence)["amount"],
            60,
        )

        self.simulation.world.set_resource("food", 500)
        self.simulation.tick = self.simulation.world.current_tick = 2
        third = self.observer.record_governor_report(
            governor.observe(self.simulation)
        )
        self.assertEqual(len(third.resolved), 1)

        self.simulation.world.set_resource("food", 50)
        self.simulation.tick = self.simulation.world.current_tick = 3
        fourth = self.observer.record_governor_report(
            governor.observe(self.simulation)
        )
        self.assertEqual(len(fourth.recurring), 1)
        self.assertEqual(fourth.recurring[0].observations, 3)
        self.assertEqual(fourth.recurring[0].first_seen_tick, 0)
        self.assertEqual(fourth.recurring[0].last_seen_tick, 3)
        self.assertEqual(fourth.recurring[0].first_seen_world_tick, 0)
        self.assertEqual(fourth.recurring[0].last_seen_world_tick, 3)
        history = self.observer.observe(self.simulation).governor_reports
        self.assertEqual(len(history), 4)
        self.assertEqual(dict(history[0].resources)["food"], 50)
        self.assertEqual(dict(history[2].resources)["food"], 500)
        self.assertEqual(history[0].sequence, 0)
        self.assertEqual(history[-1].simulation_tick, 3)


    def test_serialization_is_deterministic_detached_and_performs_no_io(self):
        citizen = Citizen("c1", "Ada")
        self.simulation.add_citizen(citizen)
        report = self.observer.observe(self.simulation)

        with mock.patch("builtins.open", side_effect=AssertionError("I/O")):
            serialized = report.to_json()
            detached = report.to_dict()

        self.assertEqual(serialized, report.to_json())
        self.assertEqual(json.loads(serialized), detached)
        detached["events"].clear()
        self.assertEqual(len(report.events), 1)
        with self.assertRaises((AttributeError, TypeError)):
            report.events[0].description = "changed"

    def test_reused_citizen_id_keeps_distinct_historical_incarnations(self):
        first = Citizen("same-id", "First")
        self.simulation.add_citizen(first)
        before_removal = self.observer.observe(self.simulation)
        self.simulation.citizens.remove(first)
        replacement = Citizen("same-id", "Second")
        self.simulation.add_citizen(replacement)

        report = self.observer.observe(self.simulation)

        archives = [archive for archive in report.citizens if archive.citizen_id == "same-id"]
        self.assertEqual([(item.incarnation, item.name) for item in archives], [
            (1, "First"), (2, "Second")
        ])
        same_id_events = [event for event in report.events if event.subject_id == "same-id"]
        self.assertEqual({event.subject_incarnation for event in same_id_events}, {1, 2})
        self.assertEqual(len({event.event_id for event in same_id_events}), len(same_id_events))
        self.assertEqual(len(before_removal.citizens), 1)

    def test_repeated_observation_and_malformed_optional_memories_are_safe(self):
        citizen = Citizen("c1", "Ada")
        citizen.memories.extend([None, {}, {"event": "Boolean tick", "tick": True}])
        self.simulation.add_citizen(citizen)

        first = self.observer.observe(self.simulation)
        second = self.observer.observe(self.simulation)

        memories = [event for event in first.events if event.source == "memory"]
        self.assertEqual(len(memories), 1)
        self.assertIsNone(memories[0].event_tick)
        self.assertEqual(second.events, first.events)
        self.assertEqual(len(second.world_snapshots), 2)


    def test_missing_optional_history_collections_are_treated_as_empty(self):
        citizen = Citizen("c1", "Ada")
        del citizen.history
        del citizen.memories
        self.simulation.add_citizen(citizen)

        report = self.observer.observe(self.simulation)

        self.assertEqual(report.events, ())
        self.assertEqual(report.citizens[0].citizen_id, "c1")


    def test_simulation_remains_independent_of_optional_observer(self):
        simulation = Simulation()
        self.assertFalse(hasattr(simulation, "observer"))
        simulation.start()
        simulation.step()
        report = GAIAObserver().observe(simulation)
        self.assertEqual(report.simulation_tick, 1)
        self.assertFalse(hasattr(simulation, "observer"))


    def test_engine_events_preserve_source_ticks_without_duplicate_history(self):
        parent_a = Citizen("pa", "Parent A", age=30)
        parent_b = Citizen("pb", "Parent B", age=30)
        transitioning = Citizen("adulting", "Transition", age=12)
        dying = Citizen("dying", "Dying")
        dying.health = 1
        dying.hunger = 100
        for citizen in (parent_a, parent_b, transitioning, dying):
            self.simulation.add_citizen(citizen)
        child = self.simulation.create_child(parent_a, parent_b, "baby", "Baby")

        self.simulation.start()
        self.simulation.step()
        report = self.observer.observe(self.simulation)

        birth = next(event for event in report.events if event.event_type == "birth")
        transition = next(
            event for event in report.events
            if event.event_type == "life_stage_transition"
        )
        death = next(event for event in report.events if event.event_type == "death")
        self.assertEqual((birth.event_tick, birth.observed_simulation_tick), (0, 1))
        self.assertEqual(birth.related_citizen_ids, ("pa", "pb"))
        self.assertEqual(transition.event_tick, 1)
        self.assertEqual(death.event_tick, 1)
        self.assertEqual(death.subject_id, "dying")
        self.assertEqual(sum(event.event_type == "birth" for event in report.events), 1)
        self.assertEqual(sum(event.event_type == "death" for event in report.events), 1)

        repeated = self.observer.observe(self.simulation)
        self.assertEqual(repeated.events, report.events)
        with self.assertRaises(AttributeError):
            self.simulation.event_records[0].source_tick = 9
        with self.assertRaises(AttributeError):
            self.simulation.event_records.append(None)
        self.assertEqual(child.citizen_id, birth.subject_id)


if __name__ == "__main__":
    unittest.main()
