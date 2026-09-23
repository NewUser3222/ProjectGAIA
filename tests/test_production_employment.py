from src.gaia.agents.action import ActionExecutor, ActionOption
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.business import Business
from src.gaia.production import ProductionRecipe


def test_employee_recipe_job_consumes_business_inputs_and_produces_outputs():
    citizen = Citizen("c1", "Worker")
    business = Business("b1", "Factory")

    recipe = ProductionRecipe(
        "planks",
        "Make Planks",
        inputs={"wood": 2},
        outputs={"stone": 3},
    )

    business.add_recipe(recipe)
    business.add_item("wood", 5)

    job = Job(
        "worker",
        "Factory Worker",
        recipe_id="planks",
        energy_cost=10,
    )

    business.add_job(job)
    business.employ(citizen, job)

    action = ActionOption("work", "Work")
    result = ActionExecutor().execute(citizen, action)

    assert result["success"] is True
    assert business.get_item_quantity("wood") == 3
    assert business.get_item_quantity("stone") == 3


def test_employee_recipe_job_uses_business_production():
    citizen = Citizen("c1", "Worker")
    business = Business("b1", "Factory")

    recipe = ProductionRecipe(
        "planks",
        "Make Planks",
        inputs={"wood": 2},
        outputs={"stone": 3},
    )

    business.add_recipe(recipe)
    business.add_item("wood", 5)

    job = Job(
        "worker",
        "Factory Worker",
        production={},
        recipe_id="planks",
        energy_cost=10,
    )

    business.add_job(job)
    business.employ(citizen, job)

    action = ActionOption("work", "Work")
    result = ActionExecutor().execute(
        citizen,
        action,
        world_context={"employer": business},
    )

    assert result["success"] is True
    assert business.get_item_quantity("wood") == 3
    assert business.get_item_quantity("stone") == 3
    assert citizen.get_item_quantity("stone") == 0


def test_employee_recipe_job_fails_atomically_when_inputs_are_missing():
    citizen = Citizen("c1", "Worker")
    business = Business("b1", "Factory")

    recipe = ProductionRecipe(
        "planks",
        "Make Planks",
        inputs={"wood": 2},
        outputs={"stone": 3},
    )

    business.add_recipe(recipe)
    business.add_item("wood", 1)

    job = Job(
        "worker",
        "Factory Worker",
        production={},
        recipe_id="planks",
        energy_cost=10,
    )

    business.add_job(job)
    business.employ(citizen, job)

    before = dict(business.inventory)

    result = ActionExecutor().execute(
        citizen,
        ActionOption("work", "Work"),
        world_context={"employer": business},
    )

    assert result["success"] is False
    assert business.inventory == before
    assert citizen.get_item_quantity("stone") == 0
