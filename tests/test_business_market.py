from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.business import Business
from src.gaia.business_commerce import BusinessCommerce
from src.gaia.core.simulation import Simulation
from src.gaia.production import ProductionRecipe


def test_market_cycle_procures_profitable_inputs_and_employees_produce_output():
    simulation = Simulation()
    business = Business("bakery", "Bakery")
    worker = Citizen("worker", "Worker", age=30)
    supplier = Citizen("supplier", "Supplier", age=30)
    supplier.add_item("wood", 2)
    business.change_money(100)

    recipe = ProductionRecipe(
        "food", "Bake Food", inputs={"wood": 2}, outputs={"food": 3}
    )
    job = Job("baker", "Baker", recipe_id="food")
    business.add_recipe(recipe)
    business.add_job(job)
    business.employ(worker, job)
    simulation.add_citizen(worker)
    simulation.add_citizen(supplier)
    simulation.add_business(business)
    simulation.world.environment.day = 270
    simulation.start()

    simulation.step()

    assert supplier.get_item_quantity("wood") == 0
    assert supplier.get_money() == 10
    assert business.get_money() == 90
    assert business.get_item_quantity("wood") == 0
    assert business.get_item_quantity("food") == 3
    activity = simulation.world.market_observations.to_dict()["current"]
    assert activity["trade"]["wood"] == 2
    assert activity["consumption"]["wood"] == 2
    assert activity["production"]["food"] == 3


def test_business_selects_the_recipe_with_the_best_current_market_margin():
    simulation = Simulation()
    business = Business("works", "Works")
    business.add_item("wood", 2)
    simulation.add_business(business)

    food_worker = Citizen("worker-food", "Food Worker", age=30)
    metal_worker = Citizen("worker-metal", "Metal Worker", age=30)
    food_recipe = ProductionRecipe(
        "food", "Make Food", inputs={"wood": 1}, outputs={"food": 1}
    )
    metal_recipe = ProductionRecipe(
        "metal", "Make Metal", inputs={"wood": 1}, outputs={"metal": 1}
    )
    food_job = Job("food-job", "Food Worker", recipe_id="food")
    metal_job = Job("metal-job", "Metal Worker", recipe_id="metal")
    for recipe, job, worker in (
        (food_recipe, food_job, food_worker),
        (metal_recipe, metal_job, metal_worker),
    ):
        business.add_recipe(recipe)
        business.add_job(job)
        business.employ(worker, job)
        simulation.add_citizen(worker)

    first_plan = business.evaluate_production_plan(simulation.world)
    assert first_plan["recipe_id"] == "metal"

    simulation.world.market_observations.record_trade("food", 100)
    simulation.world.market_observations.record_sale("food", 100)
    simulation.world.market_observations.record_production("metal", 1000)
    simulation.world.advance_tick()

    changed_plan = business.evaluate_production_plan(simulation.world)
    assert changed_plan["recipe_id"] == "food"


def test_unprofitable_recipe_does_not_buy_inputs_or_work():
    simulation = Simulation()
    business = Business("factory", "Factory")
    worker = Citizen("worker", "Worker", age=30)
    supplier = Citizen("supplier", "Supplier", age=30)
    supplier.add_item("wood", 10)
    business.change_money(100)
    business.add_recipe(
        ProductionRecipe(
            "food", "Make Food", inputs={"wood": 1}, outputs={"food": 1}
        )
    )
    job = Job("worker-job", "Worker", recipe_id="food")
    business.add_job(job)
    business.employ(worker, job)
    simulation.add_citizen(worker)
    simulation.add_citizen(supplier)
    simulation.add_business(business)
    simulation.world.market_observations.record_trade("wood", 100)
    simulation.world.market_observations.record_production("food", 1000)
    simulation.world.advance_tick()

    result = business.prepare_production(simulation.world)

    assert result["success"] is False
    assert business.get_item_quantity("wood") == 0
    assert business.get_item_quantity("food") == 0
    assert business.get_money() == 100
    assert supplier.get_item_quantity("wood") == 10
    assert supplier.get_money() == 0


def test_citizen_can_buy_food_from_an_active_business_in_simulation():
    simulation = Simulation()
    buyer = Citizen("buyer", "Buyer", age=30)
    business = Business("market-stall", "Market Stall")
    business.add_item("food", 1)
    buyer.change_money(20)
    buyer.hunger = 80
    buyer.needs["hunger"] = 80
    simulation.add_citizen(buyer)
    simulation.add_business(business)
    simulation.world.environment.day = 270
    simulation.start()

    simulation.step()

    assert buyer.get_item_quantity("food") == 1
    assert buyer.get_money() == 10
    assert business.get_item_quantity("food") == 0
    assert business.get_money() == 10


def test_recipe_procures_partial_input_from_multiple_sellers_and_reserves_it():
    simulation = Simulation()
    business = Business("metalworks", "Metalworks")
    worker = Citizen("worker", "Worker", age=30)
    first_supplier = Citizen("supplier-a", "Supplier A", age=30)
    second_supplier = Citizen("supplier-b", "Supplier B", age=30)
    first_supplier.add_item("wood", 2)
    second_supplier.add_item("wood", 3)
    business.change_money(100)
    business.add_recipe(
        ProductionRecipe(
            "metal", "Smelt Metal", inputs={"wood": 5}, outputs={"metal": 3}
        )
    )
    job = Job("smelter", "Smelter", recipe_id="metal")
    business.add_job(job)
    business.employ(worker, job)
    for citizen in (worker, first_supplier, second_supplier):
        simulation.add_citizen(citizen)
    simulation.add_business(business)

    plan = business.prepare_production(simulation.world)

    assert plan["success"] is True
    assert len(plan["purchases"]) == 2
    assert first_supplier.get_item_quantity("wood") == 0
    assert second_supplier.get_item_quantity("wood") == 0
    assert business.get_item_quantity("wood") == 5
    assert business.get_available_quantity("wood") == 0
    assert simulation.world.market_observations.to_dict()["current"]["trade"]["wood"] == 5

    buyer = Citizen("buyer", "Buyer", age=30)
    buyer.change_money(100)
    blocked_sale = BusinessCommerce.sell_to_citizen(
        business, buyer, "wood", 1
    )
    assert blocked_sale["success"] is False
    assert business.get_item_quantity("wood") == 5
    assert buyer.get_item_quantity("wood") == 0

    production = business.produce("metal")
    assert production["success"] is True
    assert business.get_item_quantity("wood") == 0
    assert business.get_item_quantity("metal") == 3
    assert business.get_available_quantity("wood") == 0
    activity = simulation.world.market_observations.to_dict()["current"]
    assert activity["consumption"]["wood"] == 5
    assert activity["production"]["metal"] == 3


def test_multi_seller_procurement_failure_rolls_back_every_order():
    simulation = Simulation()
    buyer = Business("buyer", "Buyer")
    seller_with_wood = Citizen("wood-seller", "Wood Seller", age=30)
    seller_with_stone = Business("stone-seller", "Stone Seller")
    buyer.change_money(100)
    seller_with_wood.add_item("wood", 2)
    seller_with_stone.add_item("stone", 1)
    for citizen in (seller_with_wood,):
        simulation.add_citizen(citizen)
    for business in (buyer, seller_with_stone):
        simulation.add_business(business)

    before = (
        dict(buyer.inventory),
        dict(seller_with_wood.inventory),
        dict(seller_with_stone.inventory),
        buyer.get_money(),
        seller_with_wood.get_money(),
        seller_with_stone.get_money(),
    )
    result = BusinessCommerce.buy_bundle(
        buyer,
        [
            {"seller": seller_with_wood, "resource": "wood", "quantity": 2},
            {"seller": seller_with_stone, "resource": "stone", "quantity": 2},
        ],
    )

    assert result["success"] is False
    assert (
        buyer.inventory,
        seller_with_wood.inventory,
        seller_with_stone.inventory,
        buyer.get_money(),
        seller_with_wood.get_money(),
        seller_with_stone.get_money(),
    ) == before
    assert simulation.world.market_observations.to_dict()["current"]["trade"] == {}


def test_insufficient_business_funds_reject_all_procurement_orders():
    simulation = Simulation()
    business = Business("cash-limited", "Cash Limited")
    worker = Citizen("worker", "Worker", age=30)
    first_supplier = Citizen("supplier-a", "Supplier A", age=30)
    second_supplier = Citizen("supplier-b", "Supplier B", age=30)
    first_supplier.add_item("wood", 2)
    second_supplier.add_item("wood", 3)
    business.change_money(1)
    business.add_recipe(
        ProductionRecipe(
            "metal", "Smelt Metal", inputs={"wood": 5}, outputs={"metal": 3}
        )
    )
    job = Job("smelter", "Smelter", recipe_id="metal")
    business.add_job(job)
    business.employ(worker, job)
    for citizen in (worker, first_supplier, second_supplier):
        simulation.add_citizen(citizen)
    simulation.add_business(business)

    result = business.prepare_production(simulation.world)

    assert result["success"] is False
    assert business.get_money() == 1
    assert business.get_item_quantity("wood") == 0
    assert first_supplier.get_item_quantity("wood") == 2
    assert second_supplier.get_item_quantity("wood") == 3
    assert simulation.world.market_observations.to_dict()["current"]["trade"] == {}


def test_citizen_decisions_ignore_business_inventory_reserved_for_production():
    simulation = Simulation()
    buyer = Citizen("buyer", "Buyer", age=30)
    buyer.change_money(100)
    buyer.hunger = 80
    buyer.needs["hunger"] = 80
    business = Business("reserved-stall", "Reserved Stall")
    business.add_item("food", 1)
    business._reserved_inventory = {"food": 1}
    simulation.add_citizen(buyer)
    simulation.add_business(business)

    options = simulation.decision_engine.evaluate_needs(
        buyer, world=simulation.world
    )

    assert all(option.action_id != "buy_resource" for option in options)


def test_business_production_tracks_completed_demand_and_unsold_stock():
    simulation = Simulation()
    business = Business("foodworks", "Foodworks")
    business.add_item("wood", 1)
    worker = Citizen("worker", "Worker", age=30)
    business.add_recipe(
        ProductionRecipe(
            "food", "Bake Food", inputs={"wood": 1}, outputs={"food": 2}
        )
    )
    job = Job("baker", "Baker", recipe_id="food")
    business.add_job(job)
    business.employ(worker, job)
    simulation.add_citizen(worker)
    simulation.add_business(business)

    simulation.world.market_observations.record_production("food", 2)
    simulation.world.advance_tick()
    no_demand_plan = business.evaluate_production_plan(simulation.world)
    assert no_demand_plan["success"] is False

    simulation.world.market_observations.record_sale("food", 2)
    simulation.world.advance_tick()
    demand_plan = business.evaluate_production_plan(simulation.world)
    assert demand_plan["success"] is True
    assert demand_plan["expected_sales"]["food"] == 1

    business.add_item("food", 1)
    inventory_plan = business.evaluate_production_plan(simulation.world)
    assert inventory_plan["success"] is False


def test_production_planner_respects_temporary_and_resulting_storage_capacity():
    simulation = Simulation()
    business = Business("compact", "Compact Works", inventory_capacity=2)
    business.change_money(100)
    business.add_item("stone", 1)
    worker = Citizen("worker", "Worker", age=30)
    supplier = Citizen("supplier", "Supplier", age=30)
    supplier.add_item("wood", 2)
    business.add_recipe(
        ProductionRecipe(
            "metal", "Smelt Metal", inputs={"wood": 2}, outputs={"metal": 2}
        )
    )
    job = Job("smelter", "Smelter", recipe_id="metal")
    business.add_job(job)
    business.employ(worker, job)
    simulation.add_citizen(worker)
    simulation.add_citizen(supplier)
    simulation.add_business(business)

    plan = business.prepare_production(simulation.world)

    assert plan["success"] is False
    assert business.get_money() == 100
    assert business.inventory == {"stone": 1.0}
    assert supplier.inventory == {"wood": 2}
    assert simulation.world.market_observations.to_dict()["current"]["trade"] == {}


def test_business_plan_reserves_worker_wage_after_procurement():
    simulation = Simulation()
    business = Business("wage-backed", "Wage Backed")
    worker = Citizen("worker", "Worker", age=30)
    other_worker = Citizen("a-other-worker", "Other Worker", age=30)
    supplier = Citizen("supplier", "Supplier", age=30)
    supplier.add_item("wood", 1)
    business.change_money(15)
    business.add_recipe(
        ProductionRecipe(
            "food", "Bake Food", inputs={"wood": 1}, outputs={"food": 2}
        )
    )
    job = Job("baker", "Baker", recipe_id="food", wage=10)
    business.add_job(job)
    business.employ(worker, job)
    other_job = Job("helper", "Helper", wage=5)
    business.add_job(other_job)
    business.employ(other_worker, other_job)
    simulation.add_citizen(other_worker)
    simulation.add_citizen(worker)
    simulation.add_citizen(supplier)
    simulation.add_business(business)
    simulation.start()

    simulation.step()

    assert supplier.get_item_quantity("wood") == 0
    assert worker.get_money() == 10
    assert other_worker.get_money() == 0
    assert business.get_money() == 0
    assert business.get_item_quantity("food") == 2


def test_business_does_not_procure_when_inputs_would_strand_worker_wage():
    simulation = Simulation()
    business = Business("underfunded", "Underfunded")
    worker = Citizen("worker", "Worker", age=30)
    supplier = Citizen("supplier", "Supplier", age=30)
    supplier.add_item("wood", 1)
    business.change_money(14)
    business.add_recipe(
        ProductionRecipe(
            "food", "Bake Food", inputs={"wood": 1}, outputs={"food": 2}
        )
    )
    job = Job("baker", "Baker", recipe_id="food", wage=10)
    business.add_job(job)
    business.employ(worker, job)
    simulation.add_citizen(worker)
    simulation.add_citizen(supplier)
    simulation.add_business(business)

    result = business.prepare_production(simulation.world)

    assert result["success"] is False
    assert business.get_money() == 14
    assert business.get_item_quantity("wood") == 0
    assert supplier.get_item_quantity("wood") == 1
    assert simulation.world.market_observations.to_dict()["current"]["trade"] == {}


def test_business_cannot_spend_cash_reserved_for_selected_worker_wage():
    simulation = Simulation()
    business = Business("payroll", "Payroll")
    business.change_money(10)
    business.add_item("wood", 1)
    worker = Citizen("worker", "Worker", age=30)
    supplier = Citizen("supplier", "Supplier", age=30)
    supplier.add_item("wood", 1)
    business.add_recipe(
        ProductionRecipe(
            "food", "Bake Food", inputs={"wood": 1}, outputs={"food": 4}
        )
    )
    job = Job("baker", "Baker", recipe_id="food", wage=10)
    business.add_job(job)
    business.employ(worker, job)
    simulation.add_citizen(worker)
    simulation.add_citizen(supplier)
    simulation.add_business(business)

    plan = business.prepare_production(simulation.world)
    purchase = business.buy_from_citizen(supplier, "wood", 1)

    assert plan["success"] is True
    assert business.get_money() == 10
    assert business.get_available_money() == 0
    assert purchase["success"] is False
    assert business.get_item_quantity("wood") == 1
    assert supplier.get_item_quantity("wood") == 1
