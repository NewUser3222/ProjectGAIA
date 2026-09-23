from src.gaia.agents.citizen import Citizen
from src.gaia.business import Business


def test_business_buys_resource_from_another_business():
    buyer = Business("buyer", "Buyer")
    seller = Business("seller", "Seller")

    buyer.change_money(100)
    seller.add_item("wood", 5)

    result = buyer.buy_resource(seller, "wood", 2)

    assert result["success"] is True
    assert buyer.get_item_quantity("wood") == 2
    assert seller.get_item_quantity("wood") == 3
    assert buyer.get_money() < 100
    assert seller.get_money() > 0


def test_business_sells_resource_to_another_business():
    seller = Business("seller", "Seller")
    buyer = Business("buyer", "Buyer")

    seller.add_item("wood", 5)
    buyer.change_money(100)

    result = seller.sell_resource(buyer, "wood", 2)

    assert result["success"] is True
    assert seller.get_item_quantity("wood") == 3
    assert buyer.get_item_quantity("wood") == 2


def test_business_buys_resource_from_citizen():
    business = Business("business", "Business")
    citizen = Citizen("c1", "Seller")

    business.change_money(100)
    citizen.add_item("wood", 5)

    result = business.buy_from_citizen(citizen, "wood", 2)

    assert result["success"] is True
    assert business.get_item_quantity("wood") == 2
    assert citizen.get_item_quantity("wood") == 3
    assert citizen.get_money() > 0


def test_business_sells_resource_to_citizen():
    business = Business("business", "Business")
    citizen = Citizen("c1", "Buyer")

    business.add_item("wood", 5)
    citizen.change_money(100)

    result = business.sell_to_citizen(citizen, "wood", 2)

    assert result["success"] is True
    assert business.get_item_quantity("wood") == 3
    assert citizen.get_item_quantity("wood") == 2


def test_insufficient_business_funds_prevent_purchase_without_mutation():
    buyer = Business("buyer", "Buyer")
    seller = Business("seller", "Seller")

    seller.add_item("wood", 5)

    before_buyer = dict(buyer.inventory)
    before_seller = dict(seller.inventory)

    result = buyer.buy_resource(seller, "wood", 2)

    assert result["success"] is False
    assert buyer.inventory == before_buyer
    assert seller.inventory == before_seller
    assert buyer.get_money() == 0
    assert seller.get_money() == 0


def test_insufficient_seller_inventory_prevents_sale_without_mutation():
    seller = Business("seller", "Seller")
    buyer = Business("buyer", "Buyer")

    seller.add_item("wood", 1)
    buyer.change_money(100)

    before_seller = dict(seller.inventory)
    before_buyer = dict(buyer.inventory)
    before_money = buyer.get_money()

    result = seller.sell_resource(buyer, "wood", 2)

    assert result["success"] is False
    assert seller.inventory == before_seller
    assert buyer.inventory == before_buyer
    assert buyer.get_money() == before_money


def test_business_commerce_uses_market_pricing():
    business = Business("business", "Business")
    citizen = Citizen("c1", "Seller")

    business.change_money(100)
    citizen.add_item("wood", 5)

    result = business.buy_from_citizen(citizen, "wood", 1)

    assert result["success"] is True
    assert result["unit_price"] > 0
    assert result["amount"] == result["unit_price"]


def test_businesses_have_independent_money_and_inventory():
    first = Business("first", "First")
    second = Business("second", "Second")

    first.change_money(100)
    first.add_item("wood", 5)

    assert second.get_money() == 0
    assert second.inventory == {}


def test_business_cannot_buy_from_itself():
    business = Business("business", "Business")
    business.change_money(100)
    business.add_item("wood", 5)

    try:
        business.buy_resource(business, "wood", 1)
        assert False
    except ValueError:
        pass


def test_failed_business_trade_does_not_create_money_or_resources():
    buyer = Business("buyer", "Buyer")
    seller = Business("seller", "Seller")

    buyer.change_money(5)

    before_buyer_money = buyer.get_money()
    before_seller_money = seller.get_money()

    result = buyer.buy_resource(seller, "wood", 1)

    assert result["success"] is False
    assert buyer.get_money() == before_buyer_money
    assert seller.get_money() == before_seller_money
    assert buyer.get_item_quantity("wood") == 0
    assert seller.get_item_quantity("wood") == 0
