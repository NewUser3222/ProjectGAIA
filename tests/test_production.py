from src.gaia.business import Business
from src.gaia.production import ProductionRecipe


def test_production_recipe_consumes_inputs_and_creates_outputs():
    business = Business("bakery", "Bakery")
    business.add_item("wood", 5)
    business.add_item("food", 2)

    recipe = ProductionRecipe(
        "bread",
        "Bake Bread",
        inputs={"food": 2, "wood": 1},
        outputs={"bread": 4},
    )

    business.add_recipe(recipe)

    result = business.produce("bread")

    assert result["success"] is True
    assert business.get_item_quantity("food") == 0
    assert business.get_item_quantity("wood") == 4
    assert business.get_item_quantity("bread") == 4


def test_missing_inputs_prevent_production_without_mutation():
    business = Business("bakery", "Bakery")
    business.add_item("food", 1)

    recipe = ProductionRecipe(
        "bread",
        "Bake Bread",
        inputs={"food": 2},
        outputs={"bread": 4},
    )

    business.add_recipe(recipe)

    before = dict(business.inventory)
    result = business.produce("bread")

    assert result["success"] is False
    assert business.inventory == before


def test_recipe_only_creates_configured_outputs():
    business = Business("mill", "Mill")
    business.add_item("wood", 10)

    recipe = ProductionRecipe(
        "planks",
        "Make Planks",
        inputs={"wood": 2},
        outputs={"wood": 1},
    )

    business.add_recipe(recipe)
    result = business.produce("planks")

    assert result["success"] is True
    assert business.get_item_quantity("wood") == 9
    assert business.get_item_quantity("planks") == 0


def test_businesses_have_independent_recipes_and_inventory():
    first = Business("first", "First Business")
    second = Business("second", "Second Business")

    first.add_item("wood", 5)

    recipe = ProductionRecipe(
        "planks",
        "Make Planks",
        inputs={"wood": 2},
        outputs={"stone": 3},
    )

    first.add_recipe(recipe)

    assert first.has_recipe("planks") is True
    assert second.has_recipe("planks") is False

    result = first.produce("planks")

    assert result["success"] is True
    assert first.get_item_quantity("wood") == 3
    assert first.get_item_quantity("stone") == 3
    assert second.inventory == {}


def test_unknown_recipe_does_not_change_inventory():
    business = Business("shop", "Shop")
    business.add_item("wood", 5)

    before = dict(business.inventory)
    result = business.produce("missing")

    assert result["success"] is False
    assert business.inventory == before


def test_inactive_business_cannot_produce():
    business = Business("shop", "Shop")
    business.add_item("wood", 5)

    recipe = ProductionRecipe(
        "planks",
        "Make Planks",
        inputs={"wood": 2},
        outputs={"stone": 3},
    )

    business.add_recipe(recipe)
    business.deactivate()

    before = dict(business.inventory)
    result = business.produce("planks")

    assert result["success"] is False
    assert business.inventory == before


def test_invalid_recipe_rejects_nonpositive_quantities():
    try:
        ProductionRecipe(
            "bad",
            "Bad Recipe",
            inputs={"wood": 0},
            outputs={"stone": 1},
        )
        assert False
    except ValueError:
        pass
