"""Read-only queries over the persisted GAIA history.

Every function only reads; nothing here ever writes to gaia.db.
"""

from __future__ import annotations

import json
from typing import Any

import persistence


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload")
    try:
        row["payload"] = json.loads(payload) if payload is not None else None
    except (TypeError, json.JSONDecodeError):
        row["payload"] = payload
    return row


def get_events(limit: int = 50, since_tick: int | None = None) -> list[dict[str, Any]]:
    """Newest events first, optionally only those after ``since_tick``."""

    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 50
    if since_tick is None:
        rows = persistence.fetch_all(
            "SELECT id, tick, event_type, citizen_id, payload FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    else:
        rows = persistence.fetch_all(
            "SELECT id, tick, event_type, citizen_id, payload FROM events WHERE tick > ? ORDER BY id DESC LIMIT ?",
            (int(since_tick), limit),
        )
    return [_decode(row) for row in rows]


def get_citizen_history(citizen_id: str) -> dict[str, Any]:
    """Birth, death and every stored event that names this citizen."""

    rows = persistence.fetch_all(
        "SELECT id, tick, event_type, citizen_id, payload FROM events "
        "WHERE citizen_id = ? OR payload LIKE ? ORDER BY id ASC",
        (citizen_id, f'%"{citizen_id}"%'),
    )
    events = [_decode(row) for row in rows]

    def _own(event: dict[str, Any], kind: str) -> bool:
        payload = event.get("payload")
        return (
            event.get("event_type") == kind
            and isinstance(payload, dict)
            and payload.get("id") == citizen_id
        )

    birth = next((event for event in events if _own(event, "birth")), None)
    death = next((event for event in events if _own(event, "death")), None)
    return {"citizen_id": citizen_id, "birth": birth, "death": death, "events": events}


def get_population_over_time() -> list[dict[str, int]]:
    """Population recorded at each stored snapshot tick, oldest first."""

    rows = persistence.fetch_all("SELECT tick, state FROM snapshots ORDER BY tick ASC")
    series: list[dict[str, int]] = []
    for row in rows:
        try:
            state = json.loads(row["state"])
        except (TypeError, json.JSONDecodeError):
            continue
        series.append({"tick": int(row["tick"]), "population": int(state.get("population", 0))})
    return series


def _gini(values: list[float]) -> float:
    """Standard Gini: sum(|x_i - x_j|) / (2 * n^2 * mean), 0 when empty or mean 0."""

    n = len(values)
    if n == 0:
        return 0.0
    mean = sum(values) / n
    if mean == 0:
        return 0.0
    spread = sum(abs(first - second) for first in values for second in values)
    return round(spread / (2 * n * n * mean), 2)


def get_summary() -> dict[str, Any]:
    """Lifetime totals plus the current living population, tick and real Gini."""

    totals = {
        row["event_type"]: int(row["count"])
        for row in persistence.fetch_all("SELECT event_type, COUNT(*) AS count FROM events GROUP BY event_type")
    }
    living_rows = persistence.fetch_all(
        "SELECT COUNT(*) AS living, MAX(age) AS oldest FROM citizens WHERE alive = 1"
    )
    living = living_rows[0] if living_rows else {"living": 0, "oldest": None}
    snapshot_rows = persistence.fetch_all("SELECT MAX(tick) AS tick FROM snapshots")
    latest_tick = snapshot_rows[0]["tick"] if snapshot_rows else None
    coin_rows = persistence.fetch_all("SELECT coins FROM citizens WHERE alive = 1")
    gini = _gini([float(row["coins"] or 0) for row in coin_rows])
    return {
        "total_births": totals.get("birth", 0),
        "total_deaths": totals.get("death", 0),
        "living_count": int(living.get("living") or 0),
        "oldest_age": int(living.get("oldest") or 0),
        "current_tick": int(latest_tick or 0),
        "gini": gini,
    }
