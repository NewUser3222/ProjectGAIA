import math

from src.gaia.agents.job import Job


class ProductionRecipe:
    """Configuration for a business production recipe."""

    def __init__(self, recipe_id, name, inputs=None, outputs=None):
        if not recipe_id:
            raise ValueError("Recipe ID cannot be empty.")
        if not name:
            raise ValueError("Recipe name cannot be empty.")

        self.recipe_id = recipe_id
        self.name = name
        self.inputs = self._validate_resources(dict(inputs or {}), "input")
        self.outputs = self._validate_resources(dict(outputs or {}), "output")

        if not self.outputs:
            raise ValueError("Production recipe must have at least one output.")

    @staticmethod
    def _validate_resources(resources, resource_type):
        for resource_name, quantity in resources.items():
            if not resource_name:
                raise ValueError(
                    f"Production {resource_type} resource name cannot be empty."
                )
            try:
                quantity = float(quantity)
                quantity_is_valid = math.isfinite(quantity) and quantity > 0
            except (TypeError, ValueError, OverflowError):
                quantity_is_valid = False
            if not quantity_is_valid:
                raise ValueError(
                    f"Production {resource_type} quantities must be finite and greater than zero."
                )
            resources[resource_name] = quantity
        return resources

    def can_produce(self, inventory):
        if inventory is None:
            return False

        for resource_name, quantity in self.inputs.items():
            if inventory.get(resource_name, 0) < quantity:
                return False

        return True


class ProductionSystem:
    """Executes configured production recipes atomically."""

    @staticmethod
    def produce(inventory, recipe, inventory_capacity=None):
        if inventory is None:
            raise ValueError("Inventory cannot be None.")

        if not isinstance(recipe, ProductionRecipe):
            raise ValueError("Recipe must be a ProductionRecipe instance.")

        if inventory_capacity is not None:
            try:
                inventory_capacity = float(inventory_capacity)
            except (TypeError, ValueError, OverflowError):
                raise ValueError("Inventory capacity must be finite and nonnegative.")
            if not math.isfinite(inventory_capacity) or inventory_capacity < 0:
                raise ValueError("Inventory capacity must be finite and nonnegative.")

        # Step 58: Validate every input before changing inventory.
        if not recipe.can_produce(inventory):
            return {
                "success": False,
                "recipe_id": recipe.recipe_id,
                "reason": "Missing production inputs."
            }

        # Build and validate the entire result before mutating inventory.
        next_inventory = dict(inventory)
        for resource_name, quantity in recipe.inputs.items():
            remaining = next_inventory.get(resource_name, 0) - quantity
            if remaining == 0:
                next_inventory.pop(resource_name, None)
            else:
                next_inventory[resource_name] = remaining

        # Step 58: Create only configured outputs.
        for resource_name, quantity in recipe.outputs.items():
            next_inventory[resource_name] = (
                next_inventory.get(resource_name, 0) + quantity
            )

        try:
            for resource_name, quantity in next_inventory.items():
                quantity = float(quantity)
                if not math.isfinite(quantity) or quantity < 0:
                    raise ValueError
                next_inventory[resource_name] = quantity
        except (TypeError, ValueError, OverflowError):
            return {
                "success": False,
                "recipe_id": recipe.recipe_id,
                "reason": "Production result would create invalid inventory.",
            }
        resulting_quantity = sum(next_inventory.values())
        if not math.isfinite(resulting_quantity):
            return {
                "success": False,
                "recipe_id": recipe.recipe_id,
                "reason": "Production result would create invalid inventory.",
            }
        if (
            inventory_capacity is not None
            and resulting_quantity > inventory_capacity
        ):
            return {
                "success": False,
                "recipe_id": recipe.recipe_id,
                "reason": "Production would exceed business inventory capacity.",
            }

        inventory.clear()
        inventory.update(next_inventory)

        return {
            "success": True,
            "recipe_id": recipe.recipe_id,
            "inputs": dict(recipe.inputs),
            "outputs": dict(recipe.outputs)
        }
