import math

from src.gaia.market import MarketPricing


class BusinessCommerce:
    """Explicit commerce operations for businesses."""

    @staticmethod
    def calculate_price(resource_name, seller, quantity=1):
        if seller is None:
            raise ValueError("Seller cannot be None.")
        try:
            quantity = float(quantity)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Quantity must be finite and positive.")
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Quantity must be finite and positive.")

        unit_price = BusinessCommerce._unit_price(resource_name, seller)
        total_price = unit_price * quantity
        if not math.isfinite(total_price):
            raise ValueError("Quoted price must remain finite.")
        return total_price

    @staticmethod
    def _unit_price(resource_name, seller):
        observations = getattr(seller, "_market_observations", None)
        recent = (
            observations.get_recent(resource_name)
            if observations is not None
            else {"consumption": 0.0, "production": 0.0, "trade": 0.0}
        )
        return MarketPricing.calculate_price(
            resource_name,
            supply=seller.get_item_quantity(resource_name),
            recent_consumption=recent["consumption"],
            recent_production=recent["production"],
            recent_trade=recent["trade"],
        )

    @staticmethod
    def buy_from_citizen(business, seller, resource_name, quantity):
        return BusinessCommerce._purchase(
            buyer=business,
            seller=seller,
            resource_name=resource_name,
            quantity=quantity,
        )

    @staticmethod
    def buy_from_business(business, seller, resource_name, quantity):
        return BusinessCommerce._purchase(
            buyer=business,
            seller=seller,
            resource_name=resource_name,
            quantity=quantity,
        )

    @staticmethod
    def sell_to_citizen(business, buyer, resource_name, quantity):
        return BusinessCommerce._purchase(
            buyer=buyer,
            seller=business,
            resource_name=resource_name,
            quantity=quantity,
        )

    @staticmethod
    def sell_to_business(business, buyer, resource_name, quantity):
        return BusinessCommerce._purchase(
            buyer=buyer,
            seller=business,
            resource_name=resource_name,
            quantity=quantity,
        )

    @staticmethod
    def _purchase(buyer, seller, resource_name, quantity):
        if buyer is None or seller is None:
            raise ValueError("Buyer and seller are required.")

        if buyer is seller:
            raise ValueError("Buyer and seller must be different.")

        from src.gaia.agents.citizen import Citizen
        from src.gaia.business import Business

        if not isinstance(buyer, (Citizen, Business)) or not isinstance(
            seller, (Citizen, Business)
        ):
            raise TypeError("Commerce participants must be Citizens or Businesses.")

        for participant in (buyer, seller):
            if isinstance(participant, Citizen) and not participant.is_alive():
                return {
                    "success": False,
                    "reason": "Dead citizens cannot participate in commerce.",
                    "amount": 0.0,
                }
            if isinstance(participant, Business) and not participant.is_active():
                return {
                    "success": False,
                    "reason": "Inactive businesses cannot participate in commerce.",
                    "amount": 0.0,
                }

        try:
            quantity = float(quantity)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Quantity must be finite and positive.")
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Quantity must be finite and positive.")

        # Validate the resource before any state mutation.
        unit_price = BusinessCommerce._unit_price(resource_name, seller)

        total_price = unit_price * quantity

        if not math.isfinite(total_price):
            return {
                "success": False,
                "reason": "Transaction total must be finite.",
                "amount": 0.0,
            }

        if seller.get_item_quantity(resource_name) < quantity:
            return {
                "success": False,
                "reason": "Seller does not have enough inventory.",
                "amount": 0.0,
            }

        if buyer.get_money() < total_price:
            return {
                "success": False,
                "reason": "Buyer does not have enough money.",
                "amount": 0.0,
            }

        if not math.isfinite(buyer.get_money() - total_price) or not math.isfinite(
            seller.get_money() + total_price
        ):
            return {
                "success": False,
                "reason": "Transaction would create a non-finite balance.",
                "amount": 0.0,
            }

        # Step 59: No mutation until every validation succeeds.
        seller.remove_item(resource_name, quantity)
        buyer.add_item(resource_name, quantity)

        buyer.change_money(-total_price)
        seller.change_money(total_price)

        market_observations = getattr(buyer, "_market_observations", None)
        if (
            market_observations is not None
            and market_observations
            is getattr(seller, "_market_observations", None)
        ):
            market_observations.record_trade(resource_name, quantity)

        return {
            "success": True,
            "resource": resource_name,
            "quantity": quantity,
            "unit_price": unit_price,
            "amount": total_price,
        }
