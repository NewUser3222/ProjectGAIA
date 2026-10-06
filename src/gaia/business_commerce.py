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
        supply = (
            seller.get_available_quantity(resource_name)
            if hasattr(seller, "get_available_quantity")
            else seller.get_item_quantity(resource_name)
        )
        observations = getattr(seller, "_market_observations", None)
        recent = (
            observations.get_recent(resource_name)
            if observations is not None
            else {"consumption": 0.0, "production": 0.0, "trade": 0.0}
        )
        return MarketPricing.calculate_price(
            resource_name,
            supply=supply,
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
    def buy_bundle(buyer, orders):
        """Buy several resource lots atomically from one or more sellers."""
        from src.gaia.agents.citizen import Citizen
        from src.gaia.business import Business

        if not isinstance(buyer, (Citizen, Business)):
            raise TypeError("Buyer must be a Citizen or Business.")
        if isinstance(buyer, Citizen) and not buyer.is_alive():
            return {
                "success": False,
                "reason": "Buyer is not active.",
                "amount": 0.0,
            }
        if isinstance(buyer, Business) and not buyer.is_active():
            return {
                "success": False,
                "reason": "Buyer is not active.",
                "amount": 0.0,
            }
        if not isinstance(orders, (list, tuple)) or not orders:
            raise ValueError("At least one purchase order is required.")

        prepared = []
        inventory_debits = {}
        seller_credits = {}
        buyer_additions = {}
        observer_trades = {}
        observer_sales = {}
        quoted_unit_prices = {}
        total_amount = 0.0

        for order in orders:
            seller = order.get("seller")
            resource_name = order.get("resource")
            if not isinstance(seller, (Citizen, Business)):
                raise TypeError("Seller must be a Citizen or Business.")
            if seller is buyer:
                raise ValueError("Buyer and seller must be different.")
            if isinstance(seller, Citizen) and not seller.is_alive():
                return {
                    "success": False,
                    "reason": "Seller is not active.",
                    "amount": 0.0,
                }
            if isinstance(seller, Business) and not seller.is_active():
                return {
                    "success": False,
                    "reason": "Seller is not active.",
                    "amount": 0.0,
                }
            if not resource_name:
                raise ValueError("Resource name cannot be empty.")
            try:
                quantity = float(order.get("quantity"))
            except (TypeError, ValueError, OverflowError):
                raise ValueError("Quantity must be finite and positive.")
            if not math.isfinite(quantity) or quantity <= 0:
                raise ValueError("Quantity must be finite and positive.")

            key = (seller, resource_name)
            inventory_debits[key] = inventory_debits.get(key, 0.0) + quantity
            buyer_additions[resource_name] = (
                buyer_additions.get(resource_name, 0.0) + quantity
            )
            prepared.append((seller, resource_name, quantity))
            observer = getattr(buyer, "_market_observations", None)
            if observer is not None and observer is getattr(
                seller, "_market_observations", None
            ):
                observer_key = (observer, resource_name)
                observer_trades[observer_key] = observer_trades.get(observer_key, 0.0) + quantity
                observer_sales[observer_key] = observer_sales.get(observer_key, 0.0) + quantity

        for (seller, resource_name), quantity in inventory_debits.items():
            available = (
                seller.get_available_quantity(resource_name)
                if hasattr(seller, "get_available_quantity")
                else seller.get_item_quantity(resource_name)
            )
            if available < quantity:
                return {
                    "success": False,
                    "reason": "Seller does not have enough available inventory.",
                    "amount": 0.0,
                }
            amount = BusinessCommerce.calculate_price(resource_name, seller, quantity)
            if not math.isfinite(amount):
                return {"success": False, "reason": "Transaction total must be finite.", "amount": 0.0}
            quoted_unit_prices[(seller, resource_name)] = amount / quantity
            total_amount += amount
            seller_credits[seller] = seller_credits.get(seller, 0.0) + amount

        if not math.isfinite(total_amount) or buyer.get_money() < total_amount:
            return {
                "success": False,
                "reason": "Buyer does not have enough money.",
                "amount": 0.0,
            }
        if not math.isfinite(buyer.get_money() - total_amount):
            return {
                "success": False,
                "reason": "Transaction would create a non-finite balance.",
                "amount": 0.0,
            }
        if any(
            not math.isfinite(seller.get_money() + amount)
            for seller, amount in seller_credits.items()
        ):
            return {
                "success": False,
                "reason": "Transaction would create a non-finite balance.",
                "amount": 0.0,
            }
        if any(
            not math.isfinite(buyer.get_item_quantity(resource) + quantity)
            for resource, quantity in buyer_additions.items()
        ):
            return {
                "success": False,
                "reason": "Transaction would create non-finite inventory.",
                "amount": 0.0,
            }
        for (observer, resource_name), quantity in observer_trades.items():
            current = observer._current["trade"].get(resource_name, 0.0)
            if not math.isfinite(current + quantity):
                return {"success": False, "reason": "Market trade total would be non-finite.", "amount": 0.0}
            current_sales = observer._current["sales"].get(resource_name, 0.0)
            if not math.isfinite(current_sales + observer_sales[(observer, resource_name)]):
                return {
                    "success": False,
                    "reason": "Market sales total would be non-finite.",
                    "amount": 0.0,
                }

        # All state and observation updates are validated before the first mutation.
        for (seller, resource_name), quantity in inventory_debits.items():
            seller.remove_item(resource_name, quantity)
        for resource_name, quantity in buyer_additions.items():
            buyer.add_item(resource_name, quantity)
        buyer.change_money(-total_amount)
        for seller, amount in seller_credits.items():
            seller.change_money(amount)
        for (observer, resource_name), quantity in observer_trades.items():
            observer.record_trade(resource_name, quantity)
            observer.record_sale(
                resource_name,
                observer_sales[(observer, resource_name)],
            )

        results = []
        for seller, resource_name, quantity in prepared:
            unit_price = quoted_unit_prices[(seller, resource_name)]
            results.append({
                "seller": seller,
                "resource": resource_name,
                "quantity": quantity,
                "unit_price": unit_price,
            })
        return {"success": True, "amount": total_amount, "purchases": results}

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

        available_quantity = (
            seller.get_available_quantity(resource_name)
            if hasattr(seller, "get_available_quantity")
            else seller.get_item_quantity(resource_name)
        )
        if available_quantity < quantity:
            return {
                "success": False,
                "reason": "Seller does not have enough available inventory.",
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

        market_observations = getattr(buyer, "_market_observations", None)
        if (
            market_observations is not None
            and market_observations
            is getattr(seller, "_market_observations", None)
        ):
            trade_total = (
                market_observations._current["trade"].get(resource_name, 0.0)
                + quantity
            )
            sales_total = (
                market_observations._current["sales"].get(resource_name, 0.0)
                + quantity
            )
            if not math.isfinite(trade_total) or not math.isfinite(sales_total):
                return {
                    "success": False,
                    "reason": "Market activity total would be non-finite.",
                    "amount": 0.0,
                }

        # Step 59: No mutation until every validation succeeds.
        seller.remove_item(resource_name, quantity)
        buyer.add_item(resource_name, quantity)

        buyer.change_money(-total_price)
        seller.change_money(total_price)

        if (
            market_observations is not None
            and market_observations
            is getattr(seller, "_market_observations", None)
        ):
            market_observations.record_trade(resource_name, quantity)
            market_observations.record_sale(resource_name, quantity)

        return {
            "success": True,
            "resource": resource_name,
            "quantity": quantity,
            "unit_price": unit_price,
            "amount": total_price,
        }
