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
        self.inputs = dict(inputs or {})
        self.outputs = dict(outputs or {})

        self._validate_resources(self.inputs, "input")
        self._validate_resources(self.outputs, "output")

        if not self.outputs:
            raise ValueError("Production recipe must have at least one output.")

    @staticmethod
    def _validate_resources(resources, resource_type):
        for resource_name, quantity in resources.items():
            if not resource_name:
                raise ValueError(
                    f"Production {resource_type} resource name cannot be empty."
                )
            if quantity <= 0:
                raise ValueError(
                    f"Production {resource_type} quantities must be greater than zero."
                )

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
    def produce(inventory, recipe):
        if inventory is None:
            raise ValueError("Inventory cannot be None.")

        if not isinstance(recipe, ProductionRecipe):
            raise ValueError("Recipe must be a ProductionRecipe instance.")

        # Step 58: Validate every input before changing inventory.
        if not recipe.can_produce(inventory):
            return {
                "success": False,
                "recipe_id": recipe.recipe_id,
                "reason": "Missing production inputs."
            }

        # Step 58: Consume all configured inputs.
        for resource_name, quantity in recipe.inputs.items():
            inventory[resource_name] = inventory.get(resource_name, 0) - quantity

        # Step 58: Create only configured outputs.
        for resource_name, quantity in recipe.outputs.items():
            inventory[resource_name] = inventory.get(resource_name, 0) + quantity

        return {
            "success": True,
            "recipe_id": recipe.recipe_id,
            "inputs": dict(recipe.inputs),
            "outputs": dict(recipe.outputs)
        }
