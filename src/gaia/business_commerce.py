from src.gaia.economy import get_resource_value
from src.gaia.economy_transactions import EconomicTransaction
from src.gaia.market import MarketPricing


class BusinessCommerce:
    """Explicit commerce operations for businesses."""

    @staticmethod
    def calculate_price(resource_name, seller, quantity=1):
        if seller is None:
            raise ValueError("Seller cannot be None.")
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")

        supply = seller.get_item_quantity(resource_name)

        return MarketPricing.calculate_price(
            resource_name,
            supply=supply,
            recent_consumption=0,
            recent_production=0,
        ) * quantity

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

        if quantity <= 0:
            raise ValueError("Quantity must be positive.")

        # Validate the resource before any state mutation.
        unit_price = MarketPricing.calculate_price(
            resource_name,
            supply=seller.get_item_quantity(resource_name),
            recent_consumption=0,
            recent_production=0,
        )

        total_price = unit_price * quantity

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

        # Step 59: No mutation until every validation succeeds.
        seller.remove_item(resource_name, quantity)
        buyer.add_item(resource_name, quantity)

        buyer.change_money(-total_price)
        seller.change_money(total_price)

        return {
            "success": True,
            "resource": resource_name,
            "quantity": quantity,
            "unit_price": unit_price,
            "amount": total_price,
        }
