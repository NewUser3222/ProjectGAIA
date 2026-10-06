import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

from src.gaia.agents.citizen import Citizen
from src.gaia.core.simulation import Simulation
from src.gaia.governor import GAIAGovernor
from src.gaia.observer import GAIAObserver
from src.gaia.persistence import SCHEMA_VERSION, SQLiteHistoryStore
import src.gaia.observer as observer_module
import src.gaia.core.simulation as simulation_module
import src.gaia.governor as governor_module


class TestSQLiteHistoryStore(unittest.TestCase):
    def setUp(self):
        # In-memory SQLite databases are isolated per test and leave no artifacts.
        self.database_path = (
            f"file:gaia-history-{uuid.uuid4().hex}?mode=memory&cache=shared"
        )

    def make_report(self):
        simulation = Simulation()
        parent_a = Citizen("p1", "Parent A", age=30)
        parent_b = Citizen("p2", "Parent B", age=31)
        simulation.add_citizen(parent_a)
        simulation.add_citizen(parent_b)
        simulation.create_child(parent_a, parent_b, "child", "Child")
        simulation.tick = 4
        simulation.world.current_tick = 4

        governor = GAIAGovernor()
        observer = GAIAObserver()
        observer.record_governor_report(governor.observe(simulation))
        report = observer.observe(simulation)
        return simulation, report

    def test_initialization_schema_and_empty_retrieval(self):
        store = SQLiteHistoryStore(self.database_path).initialize()
        try:
            self.assertEqual(store.list_reports(), ())
            self.assertEqual(store.list_events(), ())
            self.assertEqual(store.list_citizen_archives(), ())
            self.assertEqual(store.list_world_snapshots(), ())
            self.assertEqual(store.list_governor_reports(), ())
            self.assertEqual(store.list_governor_findings(), ())
        finally:
            tables = {
                row[0] for row in store._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertTrue({
                "observer_reports", "citizen_archives", "historical_events",
                "world_snapshots", "governor_reports", "governor_findings",
            } <= tables)
            self.assertEqual(
                store._connection.execute("PRAGMA user_version").fetchone()[0],
                SCHEMA_VERSION,
            )
            store.close()

    def test_observer_export_round_trips_all_supported_history(self):
        _, report = self.make_report()
        store = SQLiteHistoryStore(self.database_path, simulation_id="world-a").initialize()
        try:
            report_id = store.save_report(report)
            self.assertEqual(store.get_report(report_id), report.to_dict())
            self.assertEqual(store.list_reports(), (report.to_dict(),))

            birth = next(item for item in store.list_events() if item["event_type"] == "birth")
            self.assertEqual(birth["event_tick"], 0)
            self.assertEqual(birth["observed_simulation_tick"], 4)
            self.assertEqual(birth["observed_world_tick"], 4)
            self.assertEqual(birth["related_citizen_ids"], ["p1", "p2"])
            legacy_event = next(
                item for item in store.list_events()
                if item["description"] == "Citizen created."
            )
            self.assertIsNone(legacy_event["event_tick"])
            self.assertEqual(legacy_event["observed_simulation_tick"], 4)

            archives = store.list_citizen_archives()
            self.assertEqual(
                [(item["citizen_id"], item["incarnation"]) for item in archives],
                [("child", 1), ("p1", 1), ("p2", 1)],
            )
            self.assertEqual(
                list(store.list_world_snapshots()), report.to_dict()["world_snapshots"]
            )
            self.assertEqual(
                list(store.list_governor_reports()), report.to_dict()["governor_reports"]
            )
            stored_findings = store.list_governor_findings()
            expected_findings = []
            for governor_report in report.to_dict()["governor_reports"]:
                for finding in governor_report["findings"]:
                    finding_id, category, severity, subject, message, evidence, temporal_status = finding
                    expected_findings.append({
                        "finding_id": finding_id,
                        "category": category,
                        "severity": severity,
                        "subject": subject,
                        "message": message,
                        "evidence": evidence,
                        "temporal_status": temporal_status,
                    })
            self.assertEqual(
                stored_findings, tuple(sorted(expected_findings, key=lambda item: item["finding_id"]))
            )
        finally:
            store.close()

    def test_repeated_export_is_idempotent_but_later_observations_are_kept(self):
        simulation, first_report = self.make_report()
        # A separate Observer starts its own snapshot sequence; repeatable exports
        # still produce identical report identities when their contents match.
        second_observer = GAIAObserver()
        second_observer.record_governor_report(GAIAGovernor().observe(simulation))
        matching_report = second_observer.observe(simulation)
        self.assertEqual(first_report.to_json(), matching_report.to_json())

        store = SQLiteHistoryStore(self.database_path).initialize()
        try:
            first_id = store.save_report(first_report)
            self.assertEqual(first_id, store.save_report(first_report.to_dict()))
            self.assertEqual(len(store.list_reports()), 1)
            self.assertEqual(len(store.list_events()), len(first_report.events))
            self.assertEqual(len(store.list_world_snapshots()), 1)
            governor_report_count = len(store.list_governor_reports())
            finding_count = len(store.list_governor_findings())
            self.assertEqual(governor_report_count, 1)
            self.assertGreater(finding_count, 0)

            later_report = second_observer.observe(simulation)
            self.assertNotEqual(store.save_report(later_report), first_id)
            self.assertEqual(len(store.list_reports()), 2)
            self.assertEqual(len(store.list_world_snapshots()), 2)
            self.assertEqual(len(store.list_events()), len(first_report.events))
            self.assertEqual(len(store.list_governor_reports()), governor_report_count)
            self.assertEqual(len(store.list_governor_findings()), finding_count)
        finally:
            store.close()

    def test_optional_history_collections_can_be_absent_or_null(self):
        store = SQLiteHistoryStore(self.database_path).initialize()
        try:
            report_id = store.save_report({
                "simulation_tick": 0,
                "world_tick": 0,
                "events": None,
                "citizens": None,
            })
            export = store.get_report(report_id)
            self.assertEqual(export["events"], None)
            self.assertEqual(store.list_events(), ())
            self.assertEqual(store.list_world_snapshots(), ())
            self.assertEqual(store.list_governor_reports(), ())
        finally:
            store.close()

    def test_reused_citizen_ids_persist_as_distinct_incarnations(self):
        simulation = Simulation()
        observer = GAIAObserver()
        first = Citizen("reused", "First")
        simulation.add_citizen(first)
        observer.observe(simulation)
        simulation.citizens.remove(first)
        second = Citizen("reused", "Second")
        simulation.add_citizen(second)
        report = observer.observe(simulation)

        store = SQLiteHistoryStore(self.database_path).initialize()
        try:
            store.save_report(report)
            records = [item for item in store.list_citizen_archives()
                       if item["citizen_id"] == "reused"]
            self.assertEqual(
                [(item["incarnation"], item["name"]) for item in records],
                [(1, "First"), (2, "Second")],
            )
        finally:
            store.close()

    def test_simulation_scope_is_part_of_persisted_identity(self):
        _, report = self.make_report()
        alpha = SQLiteHistoryStore(
            self.database_path, simulation_id="alpha"
        ).initialize()
        beta = SQLiteHistoryStore(
            self.database_path, simulation_id="beta"
        ).initialize()
        try:
            alpha.save_report(report)
            self.assertEqual(beta.list_reports(), ())
            beta.save_report(report)
            self.assertEqual(len(beta.list_reports()), 1)
            self.assertEqual(len(alpha.list_reports()), 1)
            with self.assertRaises(AttributeError):
                alpha.simulation_id = "beta"
        finally:
            alpha.close()
            beta.close()

    def test_invalid_export_is_rejected_without_partial_writes(self):
        malformed = {
            "simulation_tick": 0,
            "world_tick": 0,
            "events": [{"event_id": "e1"}],
            "citizens": [],
        }
        store = SQLiteHistoryStore(self.database_path).initialize()
        try:
            with self.assertRaises(ValueError):
                store.save_report(malformed)
            self.assertEqual(store.list_reports(), ())
            self.assertEqual(store.list_events(), ())
        finally:
            store.close()

    def test_database_constraint_failure_rolls_back_the_whole_export(self):
        simulation, report = self.make_report()
        before = (
            simulation.tick,
            simulation.world.current_tick,
            tuple(simulation.citizens),
            dict(simulation.world.resources),
        )
        store = SQLiteHistoryStore(self.database_path).initialize()
        store._connection.execute("""CREATE TRIGGER reject_history_event
            BEFORE INSERT ON historical_events
            BEGIN SELECT RAISE(ABORT, 'injected persistence failure'); END""")
        store._connection.commit()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                store.save_report(report)
            self.assertEqual(store.list_reports(), ())
            self.assertEqual(store.list_citizen_archives(), ())
            self.assertEqual(store.list_events(), ())
            self.assertEqual(before, (
                simulation.tick,
                simulation.world.current_tick,
                tuple(simulation.citizens),
                dict(simulation.world.resources),
            ))
        finally:
            store.close()

    def test_store_consumes_detached_exports_without_observer_sqlite_dependency(self):
        _, report = self.make_report()
        with SQLiteHistoryStore(self.database_path) as store:
            store.save_report(report.to_dict())
        self.assertFalse(hasattr(observer_module, "sqlite3"))
        self.assertFalse(hasattr(simulation_module, "sqlite3"))
        self.assertFalse(hasattr(governor_module, "sqlite3"))
        self.assertEqual(json.loads(report.to_json()), report.to_dict())

    def test_schema_version_initialization_is_explicit_and_repeatable(self):
        store = SQLiteHistoryStore(self.database_path).initialize()
        try:
            self.assertIs(store.initialize(), store)
        finally:
            store.close()
        unsupported_path = f"file:gaia-history-{uuid.uuid4().hex}?mode=memory&cache=shared"
        unsupported = SQLiteHistoryStore(unsupported_path)
        unsupported._connection.execute("PRAGMA user_version = 2")
        with self.assertRaisesRegex(RuntimeError, "Unsupported.*version: 2"):
            unsupported.initialize()
        unsupported.close()

        partial_path = f"file:gaia-history-{uuid.uuid4().hex}?mode=memory&cache=shared"
        partial = SQLiteHistoryStore(partial_path)
        partial._connection.execute("CREATE TABLE unrelated (value TEXT)")
        with self.assertRaisesRegex(RuntimeError, "Unversioned database"):
            partial.initialize()
        partial.close()

        incomplete_path = f"file:gaia-history-{uuid.uuid4().hex}?mode=memory&cache=shared"
        incomplete = SQLiteHistoryStore(incomplete_path)
        incomplete._connection.execute("PRAGMA user_version = 1")
        incomplete._connection.execute("CREATE TABLE observer_reports (simulation_id TEXT)")
        with self.assertRaisesRegex(RuntimeError, "incomplete schema"):
            incomplete.initialize()
        incomplete.close()

    def test_file_backed_round_trip_and_cleanup(self):
        _, report = self.make_report()
        project = Path(__file__).resolve().parents[1]
        fd, filename = tempfile.mkstemp(prefix=".gaia-sqlite-test-", suffix=".sqlite3", dir=project)
        os.close(fd)
        db_path = Path(filename)
        try:
            writer = SQLiteHistoryStore(db_path, simulation_id="file-world").initialize()
            report_id = writer.save_report(report)
            expected = report.to_dict()
            writer.close()
            self.assertTrue(db_path.is_file())

            reader = SQLiteHistoryStore(db_path, simulation_id="file-world").initialize()
            try:
                self.assertEqual(reader.get_report(report_id), expected)
                self.assertEqual(reader.list_reports(), (expected,))
                self.assertEqual(reader.list_events(), tuple(expected["events"]))
            finally:
                reader.close()
            self.assertTrue(db_path.exists())
        finally:
            db_path.unlink(missing_ok=True)
        self.assertFalse(db_path.exists())

    def test_file_backed_transaction_failure_rolls_back_without_simulation_mutation(self):
        simulation, report = self.make_report()
        before = (simulation.tick, simulation.world.current_tick, tuple(simulation.citizens))
        project = Path(__file__).resolve().parents[1]
        fd, filename = tempfile.mkstemp(prefix=".gaia-sqlite-test-", suffix=".sqlite3", dir=project)
        os.close(fd)
        db_path = Path(filename)
        try:
            store = SQLiteHistoryStore(db_path).initialize()
            store._connection.execute("""CREATE TRIGGER reject_file_event
                BEFORE INSERT ON historical_events
                BEGIN SELECT RAISE(ABORT, 'injected file persistence failure'); END""")
            store._connection.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                store.save_report(report)
            self.assertEqual(store.list_reports(), ())
            self.assertEqual(store.list_citizen_archives(), ())
            self.assertEqual(store.list_events(), ())
            store.close()
            check = SQLiteHistoryStore(db_path).initialize()
            try:
                self.assertEqual(check.list_reports(), ())
                self.assertEqual(check.list_world_snapshots(), ())
            finally:
                check.close()
            self.assertEqual(before, (simulation.tick, simulation.world.current_tick,
                                      tuple(simulation.citizens)))
        finally:
            db_path.unlink(missing_ok=True)

    def test_read_model_queries_are_filtered_deterministic_and_detached(self):
        _, report = self.make_report()
        alpha = SQLiteHistoryStore(self.database_path, "alpha").initialize()
        beta = SQLiteHistoryStore(self.database_path, "beta").initialize()
        try:
            alpha.save_report(report)
            beta.save_report(report)
            self.assertEqual(alpha.list_simulation_ids(), ("alpha", "beta"))
            self.assertEqual(alpha.get_latest_world_snapshot("alpha"), report.to_dict()["world_snapshots"][-1])
            self.assertEqual(alpha.list_world_snapshots_for("alpha", tick=4), alpha.list_world_snapshots())
            self.assertEqual(alpha.list_world_snapshots_for("beta", tick=5), ())
            self.assertEqual(alpha.list_events_for("alpha", observed_tick=4), tuple(
                event for event in report.to_dict()["events"]
                if event["observed_simulation_tick"] == 4
            ))
            self.assertEqual(alpha.list_events_for("alpha", source_tick=0), tuple(
                event for event in report.to_dict()["events"]
                if event["event_tick"] == 0
            ))
            self.assertEqual(alpha.list_citizen_archives_for("alpha", citizen_id="child")[0]["citizen_id"], "child")
            self.assertEqual(alpha.list_governor_reports_for("alpha", tick=4), alpha.list_governor_reports())
            self.assertEqual(alpha.list_governor_findings_for("alpha", tick=4), alpha.list_governor_findings())
            detached = alpha.list_events_for("alpha")
            detached[0]["description"] = "caller edit"
            self.assertNotEqual(alpha.list_events_for("alpha")[0]["description"], "caller edit")
            self.assertIsNone(alpha.get_latest_world_snapshot("missing"))
            with self.assertRaises(ValueError):
                alpha.list_events_for("alpha", observed_tick=-1)
        finally:
            alpha.close()
            beta.close()


if __name__ == "__main__":
    unittest.main()
