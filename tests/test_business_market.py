from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.business import Business
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
