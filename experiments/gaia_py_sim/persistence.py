"""SQLite persistence for the GAIA civilization sim.

One connection is opened at import and reused for every call; failures are
logged and swallowed so a broken disk can never take the sim down.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)
DB_PATH = Path(__file__).with_name("gaia.db")
_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS citizens (
  id TEXT PRIMARY KEY,
  name TEXT, personality TEXT,
  age INTEGER, alive INTEGER,
  x REAL, y REAL,
  grain INTEGER, wood INTEGER, coins INTEGER, hunger INTEGER,
  parent_ids TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tick INTEGER, event_type TEXT, citizen_id TEXT,
  payload TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (
  tick INTEGER PRIMARY KEY, state TEXT
);
CREATE TABLE IF NOT EXISTS buildings (
  id TEXT PRIMARY KEY,
  type TEXT, x REAL, y REAL, owner_id TEXT, built_tick INTEGER,
  district_id INTEGER DEFAULT 1
);
"""


def _connect() -> sqlite3.Connection | None:
    try:
        connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(_SCHEMA)
        connection.commit()
        return connection
    except sqlite3.Error as error:
        _LOGGER.warning("gaia.db unavailable (%s); running without persistence", error)
        return None


_CONNECTION = _connect()


def save_citizens(citizens: list[dict[str, Any]]) -> None:
    """Upsert every citizen snapshot by id (living and dead alike)."""

    if _CONNECTION is None or not citizens:
        return
    rows = [
        (
            str(citizen.get("id", "")),
            citizen.get("name", ""),
            citizen.get("personality", ""),
            int(citizen.get("age", 0)),
            int(bool(citizen.get("alive", True))),
            float(citizen.get("x", 0.0)),
            float(citizen.get("y", 0.0)),
            int(citizen.get("grain", 0)),
            int(citizen.get("wood", 0)),
            int(citizen.get("coins", 0)),
            int(citizen.get("hunger", 0)),
            json.dumps(list(citizen.get("parent_ids") or [])),
        )
        for citizen in citizens
    ]
    with _LOCK:
        try:
            _CONNECTION.executemany(
                """
                INSERT INTO citizens (id, name, personality, age, alive, x, y, grain, wood, coins, hunger, parent_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    personality = excluded.personality,
                    age = excluded.age,
                    alive = excluded.alive,
                    x = excluded.x,
                    y = excluded.y,
                    grain = excluded.grain,
                    wood = excluded.wood,
                    coins = excluded.coins,
                    hunger = excluded.hunger,
                    parent_ids = excluded.parent_ids
                """,
                rows,
            )
            _CONNECTION.commit()
        except sqlite3.Error as error:
            _LOGGER.warning("citizens write failed: %s", error)


def save_event(tick: int, event_type: str, citizen_id: str | None, payload: Any) -> None:
    """Append one history entry; payload is stored as JSON."""

    if _CONNECTION is None:
        return
    with _LOCK:
        try:
            _CONNECTION.execute(
                "INSERT INTO events (tick, event_type, citizen_id, payload) VALUES (?, ?, ?, ?)",
                (int(tick), str(event_type), citizen_id, json.dumps(payload, default=str)),
            )
            _CONNECTION.commit()
        except sqlite3.Error as error:
            _LOGGER.warning("event write failed: %s", error)


def save_snapshot(tick: int, full_state: dict[str, Any]) -> None:
    """Store the full world JSON for one tick."""

    if _CONNECTION is None:
        return
    with _LOCK:
        try:
            _CONNECTION.execute(
                "INSERT OR REPLACE INTO snapshots (tick, state) VALUES (?, ?)",
                (int(tick), json.dumps(full_state, default=str)),
            )
            _CONNECTION.commit()
        except sqlite3.Error as error:
            _LOGGER.warning("snapshot write failed: %s", error)


def save_tick(
    tick: int,
    citizens: list[dict[str, Any]],
    buildings: list[dict[str, Any]],
    events: list[dict[str, Any]],
    full_state: dict[str, Any] | None,
) -> None:
    """Persist one whole tick in a single transaction: one disk sync instead of many.

    The auto loop runs at 10x (0.1 s per tick); committing per row made a tick cost
    ~0.3-0.6 s, which silently capped the speed multiplier.
    """

    if _CONNECTION is None:
        return
    rows = [
        (
            str(citizen.get("id", "")),
            citizen.get("name", ""),
            citizen.get("personality", ""),
            int(citizen.get("age", 0)),
            int(bool(citizen.get("alive", True))),
            float(citizen.get("x", 0.0)),
            float(citizen.get("y", 0.0)),
            int(citizen.get("grain", 0)),
            int(citizen.get("wood", 0)),
            int(citizen.get("coins", 0)),
            int(citizen.get("hunger", 0)),
            json.dumps(list(citizen.get("parent_ids") or [])),
        )
        for citizen in citizens
    ]
    with _LOCK:
        try:
            if rows:
                _CONNECTION.executemany(
                    """
                    INSERT INTO citizens (id, name, personality, age, alive, x, y, grain, wood, coins, hunger, parent_ids)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        personality = excluded.personality,
                        age = excluded.age,
                        alive = excluded.alive,
                        x = excluded.x,
                        y = excluded.y,
                        grain = excluded.grain,
                        wood = excluded.wood,
                        coins = excluded.coins,
                        hunger = excluded.hunger,
                        parent_ids = excluded.parent_ids
                    """,
                    rows,
                )
            for building in buildings:
                _CONNECTION.execute(
                    """
                    INSERT INTO buildings (id, type, x, y, owner_id, built_tick, district_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        type = excluded.type,
                        x = excluded.x,
                        y = excluded.y,
                        owner_id = excluded.owner_id,
                        built_tick = excluded.built_tick,
                        district_id = excluded.district_id
                    """,
                    (
                        str(building.get("id", "")),
                        str(building.get("type", "")),
                        float(building.get("x", 0.0)),
                        float(building.get("y", 0.0)),
                        str(building.get("owner_id", "")),
                        int(building.get("built_tick", 0)),
                        int(building.get("district_id") or 1),
                    ),
                )
            for entry in events:
                _CONNECTION.execute(
                    "INSERT INTO events (tick, event_type, citizen_id, payload) VALUES (?, ?, ?, ?)",
                    (
                        int(tick),
                        str(entry.get("event", "event")),
                        entry.get("citizen") or entry.get("id"),
                        json.dumps(entry, default=str),
                    ),
                )
            # The full-state JSON is by far the heaviest write. Callers may pass
            # None to skip it on ticks where a snapshot is not due; the citizen,
            # building and event rows above are still current every tick.
            if full_state is not None:
                _CONNECTION.execute(
                    "INSERT OR REPLACE INTO snapshots (tick, state) VALUES (?, ?)",
                    (int(tick), json.dumps(full_state, default=str)),
                )
            _CONNECTION.commit()
        except sqlite3.Error as error:
            _LOGGER.warning("tick %s persistence failed: %s", tick, error)
            try:
                _CONNECTION.rollback()
            except sqlite3.Error:
                pass


def load_latest() -> dict[str, Any] | None:
    """Return the newest stored snapshot, or None when the database is empty."""

    if _CONNECTION is None:
        return None
    with _LOCK:
        try:
            row = _CONNECTION.execute("SELECT state FROM snapshots ORDER BY tick DESC LIMIT 1").fetchone()
        except sqlite3.Error as error:
            _LOGGER.warning("snapshot read failed: %s", error)
            return None
    if not row:
        return None
    try:
        state = json.loads(row[0])
    except (TypeError, json.JSONDecodeError) as error:
        _LOGGER.warning("stored snapshot is unreadable: %s", error)
        return None
    return state if isinstance(state, dict) else None


def save_building(building: dict[str, Any]) -> None:
    """Upsert one structure; called on every build and each tick."""

    if _CONNECTION is None:
        return
    with _LOCK:
        try:
            _CONNECTION.execute(
                """
                INSERT INTO buildings (id, type, x, y, owner_id, built_tick, district_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type = excluded.type,
                    x = excluded.x,
                    y = excluded.y,
                    owner_id = excluded.owner_id,
                    built_tick = excluded.built_tick,
                    district_id = excluded.district_id
                """,
                (
                    str(building.get("id", "")),
                    str(building.get("type", "")),
                    float(building.get("x", 0.0)),
                    float(building.get("y", 0.0)),
                    str(building.get("owner_id", "")),
                    int(building.get("built_tick", 0)),
                    int(building.get("district_id") or 1),
                ),
            )
            _CONNECTION.commit()
        except sqlite3.Error as error:
            _LOGGER.warning("building write failed: %s", error)


def clear_all() -> None:
    """Remove every stored row; used by /reset."""

    if _CONNECTION is None:
        return
    with _LOCK:
        try:
            for table in ("citizens", "events", "snapshots", "buildings"):
                _CONNECTION.execute(f"DELETE FROM {table}")
            _CONNECTION.commit()
        except sqlite3.Error as error:
            _LOGGER.warning("clear_all failed: %s", error)


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Read-only helper for the observer; returns rows as dictionaries."""

    if _CONNECTION is None:
        return []
    with _LOCK:
        try:
            cursor = _CONNECTION.execute(sql, params)
            columns = [column[0] for column in cursor.description or []]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except sqlite3.Error as error:
            _LOGGER.warning("read failed: %s", error)
            return []
