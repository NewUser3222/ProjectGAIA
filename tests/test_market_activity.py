import math

import pytest

from src.gaia.agents.action import ActionExecutor, ActionOption
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.business import Business
from src.gaia.business_commerce import BusinessCommerce
from src.gaia.core.simulation import Simulation
from src.gaia.economy_transactions import EconomicTransaction
from src.gaia.production import ProductionRecipe


def test_world_market_observations_roll_completed_tick_activity():
    simulation = Simulation()
    observations = simulation.world.market_observations

    observations.record_production("food", 4)
    observations.record_consumption("food", 2)
    observations.record_trade("food", 3)
    observations.record_sale("food", 1)

    assert observations.get_recent("food") == {
        "production": 0.0,
        "consumption": 0.0,
        "trade": 0.0,
        "sales": 0.0,
    }

    simulation.world.advance_tick()

    recent = observations.get_recent("food")
    assert recent == {
        "production": 4.0,
        "consumption": 2.0,
        "trade": 3.0,
        "sales": 1.0,
    }
    recent["trade"] = 1000
    assert observations.get_recent("food")["trade"] == 3.0


def test_market_demand_rate_uses_completed_sales_and_consumption_only():
    observations = Simulation().world.market_observations
    observations.record_sale("food", 4)
    assert observations.get_demand_rate("food") == 0

    observations.advance_tick()
    assert observations.get_demand_rate("food") == 4

    observations.record_trade("food", 6)
    assert observations.get_demand_rate("food") == 4
    observations.advance_tick()
    assert observations.get_demand_rate("food") == 2


def test_market_observation_window_expires_old_activity():
    simulation = Simulation()
    observations = simulation.world.market_observations

    for _ in range(observations.WINDOW_TICKS + 1):
        observations.record_trade("wood", 1)
        observations.advance_tick()

    assert observations.get_recent("wood")["trade"] == observations.WINDOW_TICKS


def test_business_recipe_records_consumed_inputs_and_produced_outputs():
    simulation = Simulation()
    business = Business("mill", "Mill")
    business.add_item("wood", 5)
    business.add_recipe(
        ProductionRecipe(
            "food",
            "Make Food",
            inputs={"wood": 2},
            outputs={"food": 3},
        )
    )
    simulation.add_business(business)

    result = business.produce("food")
    assert result["success"]
    assert simulation.world.get_market_price("food", supply=100) == 10
    assert (
        simulation.world.market_observations.get_recent("food")["production"]
        == 0
    )

    simulation.world.advance_tick()

    assert simulation.world.market_observations.get_recent("wood")["consumption"] == 2
    assert simulation.world.market_observations.get_recent("food")["production"] == 3
    assert simulation.world.get_market_price("food", supply=100) == 9.7


def test_completed_citizen_work_records_production():
    simulation = Simulation()
    worker = Citizen("worker", "Worker")
    worker.set_job(Job("grower", "Grower", production={"food": 2}))
    simulation.add_citizen(worker)

    result = ActionExecutor().execute(
        worker,
        ActionOption("work", "Work"),
        {"world": simulation.world, "tick": 1},
    )

    assert result["success"]
    current = simulation.world.market_observations.to_dict()["current"]
    assert current["production"] == {"food": 2.0}


def test_simulation_work_and_eating_feed_the_next_ticks_market_snapshot():
    simulation = Simulation()
    worker = Citizen("worker", "Worker")
    worker.set_job(Job("grower", "Grower", production={"food": 2}))
    consumer = Citizen("consumer", "Consumer")
    consumer.add_item("food", 1)
    consumer.hunger = 70
    consumer.needs["hunger"] = 70
    simulation.add_citizen(worker)
    simulation.add_citizen(consumer)
    simulation.start()

    simulation.step()
    current = simulation.world.market_observations.to_dict()["current"]
    assert current["production"]["food"] == 2
    assert current["consumption"]["food"] == 1

    simulation.step()
    recent = simulation.world.market_observations.get_recent("food")
    assert recent["production"] == 2
    assert recent["consumption"] == 1


def test_successful_citizen_trade_and_consumption_change_world_quote():
    simulation = Simulation()
    buyer = Citizen("buyer", "Buyer")
    seller = Citizen("seller", "Seller")
    buyer.change_money(100)
    seller.add_item("food", 5)
    simulation.add_citizen(buyer)
    simulation.add_citizen(seller)

    trade = EconomicTransaction.purchase_resource(
        buyer, seller, "food", 1, 10
    )
    assert trade.success
    simulation.world.consume_resource_for_need(buyer, "food", 1)

    simulation.world.advance_tick()

    recent = simulation.world.market_observations.get_recent("food")
    assert recent["trade"] == 1
    assert recent["consumption"] == 1
    assert recent["sales"] == 1
    assert simulation.world.get_market_price("food", supply=4) == 12.5


def test_business_commerce_records_trades_used_by_later_quotes():
    simulation = Simulation()
    buyer = Business("buyer", "Buyer")
    seller = Business("seller", "Seller")
    buyer.change_money(100)
    seller.add_item("wood", 10)
    simulation.add_business(buyer)
    simulation.add_business(seller)

    result = buyer.buy_resource(seller, "wood", 2)
    assert result["success"]
    assert simulation.world.market_observations.get_demand_rate("wood") == 0

    simulation.world.advance_tick()

    assert simulation.world.market_observations.get_recent("wood")["trade"] == 2
    assert simulation.world.market_observations.get_recent("wood")["sales"] == 2
    assert BusinessCommerce.calculate_price("wood", seller) == 6.25


def test_failed_production_and_trade_do_not_create_market_activity():
    simulation = Simulation()
    buyer = Business("buyer", "Buyer")
    seller = Business("seller", "Seller")
    seller.add_item("wood", 1)
    seller.add_recipe(
        ProductionRecipe(
            "planks", "Make Planks", inputs={"wood": 2}, outputs={"food": 1}
        )
    )
    simulation.add_business(buyer)
    simulation.add_business(seller)

    production = seller.produce("planks")
    trade = buyer.buy_resource(seller, "wood", 1)

    assert not production["success"]
    assert not trade["success"]
    assert simulation.world.market_observations.to_dict()["current"] == {
        "production": {},
        "consumption": {},
        "trade": {},
        "sales": {},
    }


def test_citizen_food_decision_uses_recent_market_price():
    simulation = Simulation()
    buyer = Citizen("buyer", "Buyer")
    seller = Citizen("seller", "Seller")
    buyer.change_money(10)
    buyer.needs["hunger"] = 80
    buyer.hunger = 80
    seller.add_item("food", 10)
    simulation.add_citizen(buyer)
    simulation.add_citizen(seller)
    simulation.world.market_observations.record_trade("food", 10)
    simulation.world.advance_tick()

    options = simulation.decision_engine.evaluate_needs(
        buyer, world=simulation.world
    )

    assert not any(option.action_id == "buy_resource" for option in options)


def test_market_consumption_rejects_non_finite_quantity_before_mutation():
    simulation = Simulation()
    citizen = Citizen("consumer", "Consumer")
    citizen.add_item("food", 2)
    simulation.add_citizen(citizen)

    with pytest.raises(ValueError):
        simulation.world.consume_resource_for_need(
            citizen, "food", math.nan
        )

    assert citizen.get_item_quantity("food") == 2
    assert (
        simulation.world.market_observations.to_dict()["current"]["consumption"]
        == {}
    )
