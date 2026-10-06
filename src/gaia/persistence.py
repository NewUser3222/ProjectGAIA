"""Caller-managed SQLite storage for immutable Project GAIA Observer exports."""

from collections.abc import Mapping
import hashlib
import json
import sqlite3


SCHEMA_VERSION = 1
_SCHEMA_TABLES = frozenset({
    "observer_reports", "citizen_archives", "historical_events",
    "world_snapshots", "governor_reports", "governor_findings",
})


class SQLiteHistoryStore:
    """Persist Observer exports without coupling storage to simulation or Observer."""

    def __init__(self, database_path, simulation_id="default"):
        if not isinstance(simulation_id, str) or not simulation_id:
            raise ValueError("simulation_id must be a non-empty string.")
        self._simulation_id = simulation_id
        database_name = str(database_path)
        self._connection = sqlite3.connect(
            database_name, uri=database_name.startswith("file:")
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._initialized = False
        self._closed = False

    @property
    def simulation_id(self):
        """Return the immutable scope used to separate simulation histories."""
        return self._simulation_id

    def initialize(self):
        """Create the version 1 schema if needed and return this store."""
        self._ensure_open()
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, SCHEMA_VERSION):
            raise RuntimeError(
                f"Unsupported GAIA history schema version: {version}."
            )
        existing_tables = {
            row[0] for row in self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }
        if version == 0 and existing_tables:
            raise RuntimeError("Unversioned database is not an empty GAIA history database.")
        if version == SCHEMA_VERSION and not _SCHEMA_TABLES <= existing_tables:
            raise RuntimeError("GAIA history database has an incomplete schema version 1.")

        statements = (
            """CREATE TABLE IF NOT EXISTS observer_reports (
                simulation_id TEXT NOT NULL,
                report_id TEXT NOT NULL,
                simulation_tick INTEGER NOT NULL,
                world_tick INTEGER NOT NULL,
                report_json TEXT NOT NULL,
                PRIMARY KEY (simulation_id, report_id)
            )""",
            """CREATE TABLE IF NOT EXISTS citizen_archives (
                simulation_id TEXT NOT NULL,
                citizen_id TEXT NOT NULL,
                incarnation INTEGER NOT NULL CHECK (incarnation > 0),
                first_observed_tick INTEGER NOT NULL,
                last_observed_tick INTEGER NOT NULL,
                archive_json TEXT NOT NULL,
                PRIMARY KEY (simulation_id, citizen_id, incarnation)
            )""",
            """CREATE TABLE IF NOT EXISTS historical_events (
                simulation_id TEXT NOT NULL,
                event_id TEXT NOT NULL CHECK (event_id <> ''),
                subject_id TEXT NOT NULL,
                subject_incarnation INTEGER NOT NULL CHECK (subject_incarnation > 0),
                event_type TEXT NOT NULL,
                source_tick INTEGER CHECK (source_tick IS NULL OR source_tick >= 0),
                observed_simulation_tick INTEGER NOT NULL,
                observed_world_tick INTEGER NOT NULL,
                sequence_no INTEGER NOT NULL,
                event_json TEXT NOT NULL,
                PRIMARY KEY (simulation_id, event_id)
            )""",
            """CREATE TABLE IF NOT EXISTS world_snapshots (
                simulation_id TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                sequence_no INTEGER NOT NULL,
                simulation_tick INTEGER NOT NULL,
                world_tick INTEGER NOT NULL,
                snapshot_json TEXT NOT NULL,
                PRIMARY KEY (simulation_id, snapshot_id)
            )""",
            """CREATE TABLE IF NOT EXISTS governor_reports (
                simulation_id TEXT NOT NULL,
                governor_report_id TEXT NOT NULL,
                sequence_no INTEGER NOT NULL,
                simulation_tick INTEGER NOT NULL,
                world_tick INTEGER NOT NULL,
                report_json TEXT NOT NULL,
                PRIMARY KEY (simulation_id, governor_report_id)
            )""",
            """CREATE TABLE IF NOT EXISTS governor_findings (
                simulation_id TEXT NOT NULL,
                governor_report_id TEXT NOT NULL,
                finding_id TEXT NOT NULL,
                category TEXT NOT NULL,
                subject TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                temporal_status TEXT NOT NULL,
                finding_json TEXT NOT NULL,
                PRIMARY KEY (simulation_id, governor_report_id, finding_id),
                FOREIGN KEY (simulation_id, governor_report_id)
                    REFERENCES governor_reports(simulation_id, governor_report_id)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_events_chronological "
            "ON historical_events(simulation_id, source_tick, "
            "observed_simulation_tick, observed_world_tick, sequence_no)",
            "CREATE INDEX IF NOT EXISTS idx_snapshots_chronological "
            "ON world_snapshots(simulation_id, simulation_tick, world_tick, sequence_no)",
            "CREATE INDEX IF NOT EXISTS idx_governor_reports_chronological "
            "ON governor_reports(simulation_id, simulation_tick, world_tick, sequence_no)",
        )
        try:
            with self._connection:
                for statement in statements:
                    self._connection.execute(statement)
                self._connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except Exception:
            self._initialized = False
            raise
        self._initialized = True
        return self

    def save_report(self, report):
        """Atomically persist an ObserverReport or its detached ``to_dict`` value.

        Returns a SHA-256 report identity. Saving the same export again is
        idempotent; later exports can still add newly observed history.
        """
        self._require_initialized()
        data = self._report_data(report)
        report_json = _canonical_json(data)
        report_id = _digest(report_json)
        simulation_tick = _integer(data, "simulation_tick")
        world_tick = _integer(data, "world_tick")

        citizens = _items(data, "citizens")
        events = _items(data, "events")
        snapshots = _items(data, "world_snapshots")
        governor_reports = _items(data, "governor_reports")
        # Validate and encode every item before beginning a transaction.
        citizen_rows = [self._citizen_row(item) for item in citizens]
        event_rows = [self._event_row(item) for item in events]
        snapshot_rows = [self._snapshot_row(item) for item in snapshots]
        governor_rows = [self._governor_row(item) for item in governor_reports]

        try:
            with self._connection:
                self._connection.execute(
                    """INSERT OR IGNORE INTO observer_reports
                    (simulation_id, report_id, simulation_tick, world_tick, report_json)
                    VALUES (?, ?, ?, ?, ?)""",
                    (self.simulation_id, report_id, simulation_tick, world_tick, report_json),
                )
                for row in citizen_rows:
                    self._connection.execute(
                        """INSERT INTO citizen_archives
                        (simulation_id, citizen_id, incarnation, first_observed_tick,
                         last_observed_tick, archive_json)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(simulation_id, citizen_id, incarnation) DO UPDATE SET
                            first_observed_tick = MIN(
                                citizen_archives.first_observed_tick,
                                excluded.first_observed_tick
                            ),
                            last_observed_tick = MAX(
                                citizen_archives.last_observed_tick,
                                excluded.last_observed_tick
                            ),
                            archive_json = CASE
                                WHEN excluded.last_observed_tick >=
                                     citizen_archives.last_observed_tick
                                THEN excluded.archive_json
                                ELSE citizen_archives.archive_json
                            END""",
                        (self.simulation_id, *row),
                    )
                for row in event_rows:
                    self._connection.execute(
                        """INSERT OR IGNORE INTO historical_events
                        (simulation_id, event_id, subject_id, subject_incarnation,
                         event_type, source_tick, observed_simulation_tick,
                         observed_world_tick, sequence_no, event_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (self.simulation_id, *row),
                    )
                for row in snapshot_rows:
                    self._connection.execute(
                        """INSERT OR IGNORE INTO world_snapshots
                        (simulation_id, snapshot_id, sequence_no, simulation_tick,
                         world_tick, snapshot_json)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (self.simulation_id, *row),
                    )
                for report_row, finding_rows in governor_rows:
                    self._connection.execute(
                        """INSERT OR IGNORE INTO governor_reports
                        (simulation_id, governor_report_id, sequence_no,
                         simulation_tick, world_tick, report_json)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (self.simulation_id, *report_row),
                    )
                    for finding_row in finding_rows:
                        self._connection.execute(
                            """INSERT OR IGNORE INTO governor_findings
                            (simulation_id, governor_report_id, finding_id,
                             category, subject, severity, message, temporal_status,
                             finding_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (self.simulation_id, report_row[0], *finding_row),
                        )
        except Exception:
            # sqlite3's connection context rolls back the complete write batch.
            raise
        return report_id

    def get_report(self, report_id):
        """Return one detached Observer export, or ``None`` if it is absent."""
        self._require_initialized()
        row = self._connection.execute(
            "SELECT report_json FROM observer_reports "
            "WHERE simulation_id = ? AND report_id = ?",
            (self.simulation_id, report_id),
        ).fetchone()
        return None if row is None else json.loads(row["report_json"])

    def list_simulation_ids(self):
        """Return all simulation identities represented in stored history."""
        self._require_initialized()
        rows = self._connection.execute(
            """SELECT simulation_id FROM (
                   SELECT simulation_id FROM observer_reports
                   UNION SELECT simulation_id FROM citizen_archives
                   UNION SELECT simulation_id FROM historical_events
                   UNION SELECT simulation_id FROM world_snapshots
                   UNION SELECT simulation_id FROM governor_reports
               ) ORDER BY simulation_id COLLATE BINARY"""
        )
        return tuple(row[0] for row in rows)

    def list_reports(self):
        """Return exports in deterministic simulation/world tick order."""
        self._require_initialized()
        rows = self._connection.execute(
            """SELECT report_json FROM observer_reports
            WHERE simulation_id = ?
            ORDER BY simulation_tick, world_tick, report_id""",
            (self.simulation_id,),
        )
        return tuple(json.loads(row["report_json"]) for row in rows)

    def list_events(self):
        """Return unique events in source/observation chronology."""
        self._require_initialized()
        rows = self._connection.execute(
            """SELECT event_json FROM historical_events
            WHERE simulation_id = ?
            ORDER BY COALESCE(source_tick, observed_simulation_tick),
                     observed_simulation_tick, observed_world_tick,
                     sequence_no, event_id""",
            (self.simulation_id,),
        )
        return tuple(json.loads(row["event_json"]) for row in rows)

    def list_citizen_archives(self):
        """Return the latest archive for each citizen ID/incarnation."""
        self._require_initialized()
        rows = self._connection.execute(
            """SELECT archive_json FROM citizen_archives
            WHERE simulation_id = ?
            ORDER BY citizen_id COLLATE BINARY, incarnation""",
            (self.simulation_id,),
        )
        return tuple(json.loads(row["archive_json"]) for row in rows)

    def list_world_snapshots(self):
        """Return immutable world snapshots in deterministic tick/sequence order."""
        self._require_initialized()
        rows = self._connection.execute(
            """SELECT snapshot_json FROM world_snapshots
            WHERE simulation_id = ?
            ORDER BY simulation_tick, world_tick, sequence_no, snapshot_id""",
            (self.simulation_id,),
        )
        return tuple(json.loads(row["snapshot_json"]) for row in rows)

    def get_latest_world_snapshot(self, simulation_id=None):
        """Return the latest persisted snapshot, detached from live state."""
        self._require_initialized()
        scope = self._scope(simulation_id)
        row = self._connection.execute(
            """SELECT snapshot_json FROM world_snapshots WHERE simulation_id = ?
               ORDER BY simulation_tick DESC, world_tick DESC, sequence_no DESC,
                        snapshot_id DESC LIMIT 1""", (scope,)
        ).fetchone()
        return None if row is None else json.loads(row["snapshot_json"])

    def list_world_snapshots_for(self, simulation_id, *, tick=None):
        self._require_initialized()
        scope, clause, args = self._tick_filter(simulation_id, tick, "simulation_tick")
        rows = self._connection.execute(
            "SELECT snapshot_json FROM world_snapshots WHERE simulation_id = ?" + clause +
            " ORDER BY simulation_tick, world_tick, sequence_no, snapshot_id",
            (scope, *args),
        )
        return tuple(json.loads(row["snapshot_json"]) for row in rows)

    def list_citizen_archives_for(self, simulation_id, *, citizen_id=None):
        self._require_initialized()
        scope = self._scope(simulation_id)
        clause = ""
        args = [scope]
        if citizen_id is not None:
            clause = " AND citizen_id = ?"
            args.append(citizen_id)
        rows = self._connection.execute(
            "SELECT archive_json FROM citizen_archives WHERE simulation_id = ?" + clause +
            " ORDER BY citizen_id COLLATE BINARY, incarnation", args,
        )
        return tuple(json.loads(row["archive_json"]) for row in rows)

    def list_events_for(self, simulation_id, *, source_tick=None, observed_tick=None):
        self._require_initialized()
        scope = self._scope(simulation_id)
        if source_tick is not None and observed_tick is not None:
            raise ValueError("Filter events by source_tick or observed_tick, not both.")
        tick = source_tick if source_tick is not None else observed_tick
        column = "source_tick" if source_tick is not None else "observed_simulation_tick"
        scope, clause, args = self._tick_filter(scope, tick, column)
        rows = self._connection.execute(
            "SELECT event_json FROM historical_events WHERE simulation_id = ?" + clause +
            " ORDER BY COALESCE(source_tick, observed_simulation_tick), "
            "observed_simulation_tick, observed_world_tick, sequence_no, event_id",
            (scope, *args),
        )
        return tuple(json.loads(row["event_json"]) for row in rows)

    def list_governor_reports(self):
        """Return immutable Governor reports in deterministic tick/sequence order."""
        self._require_initialized()
        rows = self._connection.execute(
            """SELECT report_json FROM governor_reports
            WHERE simulation_id = ?
            ORDER BY simulation_tick, world_tick, sequence_no, governor_report_id""",
            (self.simulation_id,),
        )
        return tuple(json.loads(row["report_json"]) for row in rows)

    def list_governor_findings(self):
        """Return findings ordered by report time then stable finding identity."""
        self._require_initialized()
        rows = self._connection.execute(
            """SELECT f.finding_json FROM governor_findings AS f
            JOIN governor_reports AS r
              ON r.simulation_id = f.simulation_id
             AND r.governor_report_id = f.governor_report_id
            WHERE f.simulation_id = ?
            ORDER BY r.simulation_tick, r.world_tick, r.sequence_no, f.finding_id""",
            (self.simulation_id,),
        )
        return tuple(json.loads(row["finding_json"]) for row in rows)

    def list_governor_reports_for(self, simulation_id, *, tick=None):
        self._require_initialized()
        scope, clause, args = self._tick_filter(simulation_id, tick, "simulation_tick")
        rows = self._connection.execute(
            "SELECT report_json FROM governor_reports WHERE simulation_id = ?" + clause +
            " ORDER BY simulation_tick, world_tick, sequence_no, governor_report_id",
            (scope, *args),
        )
        return tuple(json.loads(row["report_json"]) for row in rows)

    def list_governor_findings_for(self, simulation_id, *, tick=None):
        self._require_initialized()
        scope, clause, args = self._tick_filter(simulation_id, tick, "r.simulation_tick")
        rows = self._connection.execute(
            """SELECT f.finding_json FROM governor_findings AS f
               JOIN governor_reports AS r ON r.simulation_id = f.simulation_id
                    AND r.governor_report_id = f.governor_report_id
               WHERE f.simulation_id = ?""" + clause +
            " ORDER BY r.simulation_tick, r.world_tick, r.sequence_no, f.finding_id",
            (scope, *args),
        )
        return tuple(json.loads(row["finding_json"]) for row in rows)

    def _scope(self, simulation_id):
        return self.simulation_id if simulation_id is None else _valid_simulation_id(simulation_id)

    def _tick_filter(self, simulation_id, tick, column):
        scope = self._scope(simulation_id)
        if tick is None:
            return scope, "", ()
        if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
            raise ValueError("tick must be a non-negative integer.")
        return scope, f" AND {column} = ?", (tick,)

    def close(self):
        """Close the owned SQLite connection."""
        if not self._closed:
            self._connection.close()
            self._closed = True

    def __enter__(self):
        if not self._initialized:
            self.initialize()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def _report_data(self, report):
        if hasattr(report, "to_dict"):
            report = report.to_dict()
        if not isinstance(report, Mapping):
            raise TypeError("Expected an ObserverReport or mapping export.")
        # Round-trip to plain JSON-compatible values and reject non-finite data.
        return json.loads(_canonical_json(report))

    def _citizen_row(self, item):
        _mapping(item, "citizen archive")
        citizen_id = _text(item, "citizen_id")
        incarnation = _integer(item, "incarnation", minimum=1)
        first_seen = _integer(item, "first_observed_tick")
        last_seen = _integer(item, "last_observed_tick")
        if last_seen < first_seen:
            raise ValueError("Citizen archive last tick precedes first tick.")
        return (
            citizen_id, incarnation, first_seen, last_seen, _canonical_json(item)
        )

    def _event_row(self, item):
        _mapping(item, "historical event")
        event_id = _text(item, "event_id")
        subject_id = _text(item, "subject_id")
        incarnation = _integer(item, "subject_incarnation", minimum=1)
        event_type = _text(item, "event_type")
        source_tick = item.get("event_tick")
        if source_tick is not None:
            source_tick = _integer_value(source_tick, "event_tick")
        return (
            event_id,
            subject_id,
            incarnation,
            event_type,
            source_tick,
            _integer(item, "observed_simulation_tick"),
            _integer(item, "observed_world_tick"),
            _integer(item, "sequence"),
            _canonical_json(item),
        )

    def _snapshot_row(self, item):
        _mapping(item, "world snapshot")
        payload = _canonical_json(item)
        return (
            _digest(payload),
            _integer(item, "sequence"),
            _integer(item, "simulation_tick"),
            _integer(item, "world_tick"),
            payload,
        )

    def _governor_row(self, item):
        _mapping(item, "Governor report snapshot")
        payload = _canonical_json(item)
        governor_report_id = _digest(payload)
        report_row = (
            governor_report_id,
            _integer(item, "sequence"),
            _integer(item, "simulation_tick"),
            _integer(item, "world_tick"),
            payload,
        )
        findings = _items(item, "findings")
        finding_rows = []
        for finding in findings:
            if not isinstance(finding, (tuple, list)) or len(finding) != 7:
                raise ValueError("Governor finding snapshot must contain seven fields.")
            finding_id, category, severity, subject, message, evidence, temporal_status = finding
            values = (finding_id, category, severity, subject, message, temporal_status)
            if any(not isinstance(value, str) or not value for value in values):
                raise ValueError("Governor finding text fields must be non-empty strings.")
            normalized = {
                "finding_id": finding_id,
                "category": category,
                "severity": severity,
                "subject": subject,
                "message": message,
                "evidence": evidence,
                "temporal_status": temporal_status,
            }
            finding_rows.append((
                finding_id, category, subject, severity, message, temporal_status,
                _canonical_json(normalized),
            ))
        return report_row, finding_rows

    def _ensure_open(self):
        if self._closed:
            raise RuntimeError("SQLite history store is closed.")

    def _require_initialized(self):
        self._ensure_open()
        if not self._initialized:
            raise RuntimeError("Call initialize() before using the history store.")


def _canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mapping(value, label):
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object.")


def _items(data, key):
    value = data.get(key, ())
    if value is None:
        return ()
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"{key} must be a list or tuple.")
    return value


def _text(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string.")
    return value


def _integer(data, key, minimum=0):
    return _integer_value(data.get(key), key, minimum)


def _integer_value(value, label, minimum=0):
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}.")
    return value


def _valid_simulation_id(value):
    if not isinstance(value, str) or not value:
        raise ValueError("simulation_id must be a non-empty string.")
    return value
