# Step 47: Define direct citizen economic transactions

import math

from src.gaia.agents.citizen import Citizen


class TransactionResult:
    """Represents the result of a direct economic transaction."""

    def __init__(
        self,
        success,
        transaction_type,
        amount=0.0,
        resource=None,
        quantity=0,
        reason=None
    ):
        self.success = success
        self.transaction_type = transaction_type
        self.amount = amount
        self.resource = resource
        self.quantity = quantity
        self.reason = reason

    def to_dict(self):
        return {
            "success": self.success,
            "transaction_type": self.transaction_type,
            "amount": self.amount,
            "resource": self.resource,
            "quantity": self.quantity,
            "reason": self.reason
        }


class EconomicTransaction:
    """Provides atomic direct citizen-to-citizen transactions."""

    @staticmethod
    def _validate_participants(sender, receiver):
        if not isinstance(sender, Citizen) or not isinstance(receiver, Citizen):
            return "Both participants must be Citizen objects."

        if sender is receiver:
            return "Transaction participants must be different citizens."

        if not sender.is_alive() or not receiver.is_alive():
            return "Dead citizens cannot participate in transactions."

        return None

    @staticmethod
    def _is_finite_positive(value):
        try:
            return math.isfinite(float(value)) and float(value) > 0
        except (TypeError, ValueError, OverflowError):
            return False

    @staticmethod
    def _validate_wage_participants(payer, worker):
        from src.gaia.business import Business

        if not isinstance(worker, Citizen):
            return "Wage recipient must be a Citizen object."
        if not worker.is_alive():
            return "Dead citizens cannot receive wages."
        if payer is worker:
            return "Wage payer and worker must be different."
        if isinstance(payer, Citizen):
            if not payer.is_alive():
                return "Dead citizens cannot pay wages."
        elif isinstance(payer, Business):
            if not payer.is_active():
                return "Inactive businesses cannot pay wages."
        else:
            return "Wage payer must be a living Citizen or active Business."
        return None

    @staticmethod
    def transfer_money(sender, receiver, amount):
        reason = EconomicTransaction._validate_participants(sender, receiver)

        if reason:
            return TransactionResult(False, "money_transfer", reason=reason)

        if not EconomicTransaction._is_finite_positive(amount):
            return TransactionResult(
                False,
                "money_transfer",
                reason="Transaction amount must be greater than zero."
            )

        amount = float(amount)

        if sender.get_money() < amount:
            return TransactionResult(
                False,
                "money_transfer",
                amount=amount,
                reason="Insufficient funds."
            )

        if not math.isfinite(sender.get_money() - amount) or not math.isfinite(
            receiver.get_money() + amount
        ):
            return TransactionResult(
                False,
                "money_transfer",
                amount=amount,
                reason="Transaction would create a non-finite balance."
            )

        sender.change_money(-amount)
        receiver.change_money(amount)

        return TransactionResult(
            True,
            "money_transfer",
            amount=amount
        )


    @staticmethod
    def pay_wage(payer, worker, amount):
        reason = EconomicTransaction._validate_wage_participants(payer, worker)
        if reason:
            raise ValueError(reason)

        if not EconomicTransaction._is_finite_positive(amount):
            raise ValueError("Wage must be a finite number greater than zero.")

        amount = float(amount)

        available_money = (
            payer.get_available_money()
            if hasattr(payer, "get_available_money")
            else payer.get_money()
        )
        reserved_wage = (
            payer.can_pay_wage(worker, amount)
            if hasattr(payer, "can_pay_wage")
            else False
        )
        if available_money < amount and not reserved_wage:
            raise ValueError("Payer does not have enough money.")

        if not math.isfinite(payer.get_money() - amount) or not math.isfinite(
            worker.get_money() + amount
        ):
            raise ValueError("Wage would create a non-finite balance.")

        payer.change_money(-amount)
        worker.change_money(amount)
        if hasattr(payer, "release_worker_wage"):
            payer.release_worker_wage(worker, amount)

        return TransactionResult(
            success=True,
            transaction_type="wage",
            amount=float(amount)
        )

    @staticmethod
    def purchase_resource(
        buyer,
        seller,
        resource_name,
        quantity,
        unit_price
    ):
        reason = EconomicTransaction._validate_participants(buyer, seller)

        if reason:
            return TransactionResult(
                False,
                "resource_purchase",
                reason=reason
            )

        if not EconomicTransaction._is_finite_positive(quantity):
            return TransactionResult(
                False,
                "resource_purchase",
                reason="Quantity must be greater than zero."
            )

        if not EconomicTransaction._is_finite_positive(unit_price):
            return TransactionResult(
                False,
                "resource_purchase",
                reason="Unit price must be greater than zero."
            )

        unit_price = float(unit_price)
        quantity = float(quantity)

        if seller.get_item_quantity(resource_name) < quantity:
            return TransactionResult(
                False,
                "resource_purchase",
                resource=resource_name,
                quantity=quantity,
                reason="Seller does not possess enough resources."
            )
        total_cost = unit_price * quantity
        if not math.isfinite(total_cost):
            return TransactionResult(
                False,
                "resource_purchase",
                resource=resource_name,
                quantity=quantity,
                reason="Transaction total must be finite."
            )

        if buyer.get_money() < total_cost:
            return TransactionResult(
                False,
                "resource_purchase",
                amount=total_cost,
                resource=resource_name,
                quantity=quantity,
                reason="Insufficient funds."
            )

        if not math.isfinite(buyer.get_money() - total_cost) or not math.isfinite(
            seller.get_money() + total_cost
        ):
            return TransactionResult(
                False,
                "resource_purchase",
                amount=total_cost,
                resource=resource_name,
                quantity=quantity,
                reason="Transaction would create a non-finite balance."
            )

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
                return TransactionResult(
                    False,
                    "resource_purchase",
                    amount=total_cost,
                    resource=resource_name,
                    quantity=quantity,
                    reason="Market activity total would be non-finite."
                )

        # Validate everything before mutating either participant.
        seller.remove_item(resource_name, quantity)
        buyer.add_item(resource_name, quantity)

        buyer.change_money(-total_cost)
        seller.change_money(total_cost)

        if (
            market_observations is not None
            and market_observations
            is getattr(seller, "_market_observations", None)
        ):
            market_observations.record_trade(resource_name, quantity)
            market_observations.record_sale(resource_name, quantity)

        return TransactionResult(
            True,
            "resource_purchase",
            amount=total_cost,
            resource=resource_name,
            quantity=quantity
        )
