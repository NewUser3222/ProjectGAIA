# Step 47: Define direct citizen economic transactions

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
    def transfer_money(sender, receiver, amount):
        reason = EconomicTransaction._validate_participants(sender, receiver)

        if reason:
            return TransactionResult(False, "money_transfer", reason=reason)

        if amount <= 0:
            return TransactionResult(
                False,
                "money_transfer",
                reason="Transaction amount must be greater than zero."
            )

        if sender.get_money() < amount:
            return TransactionResult(
                False,
                "money_transfer",
                amount=amount,
                reason="Insufficient funds."
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
        EconomicTransaction._validate_participants(payer, worker)

        if amount <= 0:
            raise ValueError("Wage must be greater than zero.")

        if payer.get_money() < amount:
            raise ValueError("Payer does not have enough money.")

        payer.change_money(-amount)
        worker.change_money(amount)

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

        if quantity <= 0:
            return TransactionResult(
                False,
                "resource_purchase",
                reason="Quantity must be greater than zero."
            )

        if unit_price <= 0:
            return TransactionResult(
                False,
                "resource_purchase",
                reason="Unit price must be greater than zero."
            )

        if seller.get_item_quantity(resource_name) < quantity:
            return TransactionResult(
                False,
                "resource_purchase",
                resource=resource_name,
                quantity=quantity,
                reason="Seller does not possess enough resources."
            )

        total_cost = unit_price * quantity

        if buyer.get_money() < total_cost:
            return TransactionResult(
                False,
                "resource_purchase",
                amount=total_cost,
                resource=resource_name,
                quantity=quantity,
                reason="Insufficient funds."
            )

        # Validate everything before mutating either participant.
        seller.remove_item(resource_name, quantity)
        buyer.add_item(resource_name, quantity)

        buyer.change_money(-total_cost)
        seller.change_money(total_cost)

        return TransactionResult(
            True,
            "resource_purchase",
            amount=total_cost,
            resource=resource_name,
            quantity=quantity
        )
