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
    ):
        if resource_name not in RESOURCE_VALUES:
            raise ValueError(f"Unknown resource: {resource_name}")

        if supply < 0:
            raise ValueError("Supply cannot be negative.")

        if recent_consumption < 0:
            raise ValueError("Recent consumption cannot be negative.")

        if recent_production < 0:
            raise ValueError("Recent production cannot be negative.")

        baseline = RESOURCE_VALUES[resource_name]

        # Step 54: Compare actual recent consumption with actual supply.
        # Higher consumption relative to supply increases price.
        demand_pressure = 0.0
        if supply > 0:
            demand_pressure = recent_consumption / supply
        elif recent_consumption > 0:
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
