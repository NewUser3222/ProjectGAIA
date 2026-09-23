import unittest

from src.gaia.market import MarketPricing


class TestMarketPricing(unittest.TestCase):

    # Step 1: Baseline pricing.
    def test_baseline_price(self):
        price = MarketPricing.calculate_price(
            "food",
            supply=100
        )

        self.assertEqual(price, 10.0)

    # Step 2: Higher actual consumption increases price.
    def test_consumption_increases_price(self):
        price = MarketPricing.calculate_price(
            "food",
            supply=100,
            recent_consumption=50
        )

        self.assertGreater(price, 10.0)

    # Step 3: Recent production lowers price pressure.
    def test_production_reduces_price(self):
        price = MarketPricing.calculate_price(
            "food",
            supply=100,
            recent_production=50
        )

        self.assertLess(price, 10.0)

    # Step 4: Prices never fall below the configured minimum.
    def test_price_has_lower_bound(self):
        price = MarketPricing.calculate_price(
            "food",
            supply=100,
            recent_production=500
        )

        self.assertEqual(price, 5.0)

    # Step 5: Prices never exceed the configured maximum.
    def test_price_has_upper_bound(self):
        price = MarketPricing.calculate_price(
            "food",
            supply=100,
            recent_consumption=500
        )

        self.assertEqual(price, 20.0)

    # Step 6: Zero supply with actual consumption remains bounded.
    def test_zero_supply_with_consumption(self):
        price = MarketPricing.calculate_price(
            "food",
            supply=0,
            recent_consumption=10
        )

        self.assertEqual(price, 20.0)

    # Step 7: Invalid resource names are rejected.
    def test_unknown_resource_rejected(self):
        with self.assertRaises(ValueError):
            MarketPricing.calculate_price(
                "unknown_resource",
                supply=100
            )

    # Step 8: Negative market values are rejected.
    def test_negative_values_rejected(self):
        with self.assertRaises(ValueError):
            MarketPricing.calculate_price(
                "food",
                supply=-1
            )


if __name__ == "__main__":
    unittest.main()
