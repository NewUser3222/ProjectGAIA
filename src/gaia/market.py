import math
from collections import deque

from src.gaia.economy import RESOURCE_VALUES


class MarketPricing:
    """Deterministic resource pricing based on observed market conditions."""

    MIN_MULTIPLIER = 0.5
    MAX_MULTIPLIER = 2.0

    @staticmethod
    def calculate_price(
        resource_name,
        supply,
        recent_consumption=0,
        recent_production=0,
        recent_trade=0,
    ):
        if resource_name not in RESOURCE_VALUES:
            raise ValueError(f"Unknown resource: {resource_name}")

        observations = (
            supply,
            recent_consumption,
            recent_production,
            recent_trade,
        )
        try:
            observations = tuple(float(value) for value in observations)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Market observations must be finite numbers.")

        if any(not math.isfinite(value) for value in observations):
            raise ValueError("Market observations must be finite numbers.")

        supply, recent_consumption, recent_production, recent_trade = observations
        if supply < 0:
            raise ValueError("Supply cannot be negative.")

        if recent_consumption < 0:
            raise ValueError("Recent consumption cannot be negative.")

        if recent_production < 0:
            raise ValueError("Recent production cannot be negative.")

        if recent_trade < 0:
            raise ValueError("Recent trade cannot be negative.")

        baseline = RESOURCE_VALUES[resource_name]

        # Step 54: Compare actual consumption and trades with available supply.
        # Higher observed demand relative to supply increases price.
        demand_pressure = 0.0
        if supply > 0:
            demand_pressure = (recent_consumption + recent_trade) / supply
        elif recent_consumption > 0 or recent_trade > 0:
            demand_pressure = 1.0

        # Step 54: Recent production provides downward pressure on price.
        production_pressure = 0.0
        if supply > 0:
            production_pressure = recent_production / supply

        multiplier = 1.0 + demand_pressure - production_pressure

        # Step 54: Keep prices deterministic, nonnegative, and bounded.
        multiplier = max(
            MarketPricing.MIN_MULTIPLIER,
            min(MarketPricing.MAX_MULTIPLIER, multiplier)
        )

        return baseline * multiplier


class MarketObservations:
    """Seven-tick rolling totals for completed economic activity."""

    WINDOW_TICKS = 7
    ACTIVITY_TYPES = ("production", "consumption", "trade")

    def __init__(self):
        self._current = {activity: {} for activity in self.ACTIVITY_TYPES}
        self._history = deque(maxlen=self.WINDOW_TICKS)

    def _record(self, activity, resource_name, quantity):
        if activity not in self.ACTIVITY_TYPES:
            raise ValueError("Unknown market activity type.")
        if not resource_name:
            raise ValueError("Resource name cannot be empty.")
        try:
            quantity = float(quantity)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(
                "Market activity quantity must be finite and positive."
            )
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError(
                "Market activity quantity must be finite and positive."
            )

        updated_total = self._current[activity].get(resource_name, 0.0) + quantity
        if not math.isfinite(updated_total):
            raise ValueError("Market activity total must remain finite.")
        self._current[activity][resource_name] = updated_total

    def record_production(self, resource_name, quantity):
        self._record("production", resource_name, quantity)

    def record_consumption(self, resource_name, quantity):
        self._record("consumption", resource_name, quantity)

    def record_trade(self, resource_name, quantity):
        self._record("trade", resource_name, quantity)

    def advance_tick(self):
        """Close the current activity bucket and begin a new simulation tick."""
        self._history.append({
            activity: dict(values)
            for activity, values in self._current.items()
        })
        self._current = {activity: {} for activity in self.ACTIVITY_TYPES}

    def get_recent(self, resource_name):
        """Return a copy of the rolling completed-tick totals for a resource."""
        totals = {activity: 0.0 for activity in self.ACTIVITY_TYPES}
        for tick in self._history:
            for activity in self.ACTIVITY_TYPES:
                totals[activity] += tick[activity].get(resource_name, 0.0)
        return totals

    def to_dict(self):
        return {
            "window_ticks": self.WINDOW_TICKS,
            "completed_ticks": len(self._history),
            "current": {
                activity: dict(values)
                for activity, values in self._current.items()
            },
            "recent": {
                resource_name: self.get_recent(resource_name)
                for resource_name in sorted({
                    resource
                    for tick in self._history
                    for activity in self.ACTIVITY_TYPES
                    for resource in tick[activity]
                })
            },
        }
