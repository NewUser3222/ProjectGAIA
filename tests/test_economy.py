import unittest

from src.gaia.agents.citizen import Citizen
from src.gaia.agents.decision import DecisionEngine
from src.gaia.economy import (
    RESOURCE_VALUES,
    calculate_inventory_value,
    calculate_resource_value,
    get_resource_value
)
from src.gaia.economy_transactions import EconomicTransaction
from src.gaia.simulation.world import WorldState


class TestEconomicFoundation(unittest.TestCase):

    def test_resources_have_defined_values(self):
        self.assertEqual(set(RESOURCE_VALUES), {
            "food",
            "water",
            "wood",
            "stone",
            "metal",
            "energy"
        })
        for value in RESOURCE_VALUES.values():
            self.assertGreater(value, 0)

    def test_quantity_and_value_are_separate(self):
        citizen = Citizen("C001", "Alice")
        citizen.add_item("food", 3)

        self.assertEqual(citizen.get_item_quantity("food"), 3)
        self.assertEqual(get_resource_value("food"), 10.0)
        self.assertEqual(calculate_resource_value("food", 3), 30.0)

    def test_inventory_value(self):
        citizen = Citizen("C001", "Alice")
        citizen.add_item("food", 2)
        citizen.add_item("wood", 4)

        self.assertEqual(citizen.get_inventory_value(), 40.0)

    def test_money_transfer(self):
        alice = Citizen("C001", "Alice")
        bob = Citizen("C002", "Bob")
        alice.change_money(100)

        result = EconomicTransaction.transfer_money(alice, bob, 40)

        self.assertTrue(result.success)
        self.assertEqual(alice.get_money(), 60)
        self.assertEqual(bob.get_money(), 40)
        self.assertEqual(alice.get_money() + bob.get_money(), 100)

    def test_money_transfer_rejects_insufficient_funds(self):
        alice = Citizen("C001", "Alice")
        bob = Citizen("C002", "Bob")
        alice.change_money(20)

        result = EconomicTransaction.transfer_money(alice, bob, 30)

        self.assertFalse(result.success)
        self.assertEqual(alice.get_money(), 20)
        self.assertEqual(bob.get_money(), 0)

    def test_money_transfer_rejects_invalid_amount(self):
        alice = Citizen("C001", "Alice")
        bob = Citizen("C002", "Bob")
        alice.change_money(20)

        result = EconomicTransaction.transfer_money(alice, bob, 0)

        self.assertFalse(result.success)
        self.assertEqual(alice.get_money(), 20)
        self.assertEqual(bob.get_money(), 0)

    def test_resource_purchase(self):
        buyer = Citizen("C001", "Buyer")
        seller = Citizen("C002", "Seller")

        buyer.change_money(50)
        seller.add_item("food", 2)

        result = EconomicTransaction.purchase_resource(
            buyer,
            seller,
            "food",
            1,
            10
        )

        self.assertTrue(result.success)
        self.assertEqual(buyer.get_money(), 40)
        self.assertEqual(seller.get_money(), 10)
        self.assertEqual(buyer.get_item_quantity("food"), 1)
        self.assertEqual(seller.get_item_quantity("food"), 1)

    def test_resource_purchase_is_atomic_when_buyer_cannot_pay(self):
        buyer = Citizen("C001", "Buyer")
        seller = Citizen("C002", "Seller")

        buyer.change_money(5)
        seller.add_item("food", 1)

        result = EconomicTransaction.purchase_resource(
            buyer,
            seller,
            "food",
            1,
            10
        )

        self.assertFalse(result.success)
        self.assertEqual(buyer.get_money(), 5)
        self.assertEqual(seller.get_money(), 0)
        self.assertEqual(buyer.get_item_quantity("food"), 0)
        self.assertEqual(seller.get_item_quantity("food"), 1)

    def test_resource_purchase_is_atomic_when_seller_lacks_resource(self):
        buyer = Citizen("C001", "Buyer")
        seller = Citizen("C002", "Seller")

        buyer.change_money(50)

        result = EconomicTransaction.purchase_resource(
            buyer,
            seller,
            "food",
            1,
            10
        )

        self.assertFalse(result.success)
        self.assertEqual(buyer.get_money(), 50)
        self.assertEqual(seller.get_money(), 0)
        self.assertEqual(buyer.get_item_quantity("food"), 0)

    def test_dead_citizens_cannot_transact(self):
        buyer = Citizen("C001", "Buyer")
        seller = Citizen("C002", "Seller")

        buyer.change_money(20)
        seller.add_item("food", 1)
        seller.die()

        result = EconomicTransaction.purchase_resource(
            buyer,
            seller,
            "food",
            1,
            10
        )

        self.assertFalse(result.success)
        self.assertEqual(buyer.get_money(), 20)
        self.assertEqual(seller.get_item_quantity("food"), 1)

    def test_economic_decision_requires_real_money_and_seller(self):
        world = WorldState()
        buyer = Citizen("C001", "Buyer")
        seller = Citizen("C002", "Seller")

        buyer.hunger = 80
        buyer.needs["hunger"] = 80
        seller.add_item("food", 1)

        world.add_citizen(buyer)
        world.add_citizen(seller)

        engine = DecisionEngine()

        options = engine.evaluate_needs(buyer, world=world)
        self.assertFalse(any(option.action_id == "buy_resource" for option in options))

        buyer.change_money(10)

        options = engine.evaluate_needs(buyer, world=world)
        self.assertTrue(any(option.action_id == "buy_resource" for option in options))

    def test_gather_behavior_remains_available(self):
        world = WorldState()
        citizen = Citizen("C001", "Alice")
        citizen.hunger = 80
        citizen.needs["hunger"] = 80

        world.add_citizen(citizen)
        world.set_resource("food", 1)

        engine = DecisionEngine()
        action = engine.select_best_action(citizen, world=world)

        self.assertIsNotNone(action)
        self.assertEqual(action.action_id, "gather")

    def test_resource_and_money_conservation(self):
        buyer = Citizen("C001", "Buyer")
        seller = Citizen("C002", "Seller")

        buyer.change_money(100)
        seller.change_money(25)
        seller.add_item("food", 3)

        initial_money = buyer.get_money() + seller.get_money()
        initial_food = (
            buyer.get_item_quantity("food")
            + seller.get_item_quantity("food")
        )

        result = EconomicTransaction.purchase_resource(
            buyer,
            seller,
            "food",
            2,
            10
        )

        self.assertTrue(result.success)
        self.assertEqual(
            buyer.get_money() + seller.get_money(),
            initial_money
        )
        self.assertEqual(
            buyer.get_item_quantity("food")
            + seller.get_item_quantity("food"),
            initial_food
        )
