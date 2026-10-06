"""Storage-neutral, read-only contract for persisted GAIA history.

Consumers such as future visualizers depend on this interface, not on SQLite
or the live Simulation Engine. Returned mappings are detached export values.
"""

from typing import Protocol


class HistoryReader(Protocol):
    """Read persisted historical state in deterministic chronological order."""

    def list_simulation_ids(self) -> tuple[str, ...]: ...

    def get_latest_world_snapshot(self, simulation_id: str): ...

    def list_world_snapshots_for(self, simulation_id: str, *, tick=None): ...

    def list_citizen_archives_for(self, simulation_id: str, *, citizen_id=None): ...

    def list_events_for(
        self, simulation_id: str, *, source_tick=None, observed_tick=None
    ): ...

    def list_governor_reports_for(self, simulation_id: str, *, tick=None): ...

    def list_governor_findings_for(self, simulation_id: str, *, tick=None): ...
