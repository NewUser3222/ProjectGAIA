# Step 62: Construction materials and building costs

class BuildingDefinition:
    """Configuration for the materials and cost required to construct a building."""

    def __init__(
        self,
        building_type,
        required_materials=None,
        construction_cost=0.0,
    ):
        if not building_type:
            raise ValueError("Building type cannot be empty.")

        if construction_cost < 0:
            raise ValueError("Construction cost cannot be negative.")

        self.building_type = building_type
        self.required_materials = dict(required_materials or {})
        self.construction_cost = float(construction_cost)

        self._validate_materials()

    def _validate_materials(self):
        for resource_name, quantity in self.required_materials.items():
            if not resource_name:
                raise ValueError("Material resource name cannot be empty.")

            if quantity <= 0:
                raise ValueError(
                    "Required material quantities must be greater than zero."
                )

    def get_required_materials(self):
        return dict(self.required_materials)

    def get_construction_cost(self):
        return self.construction_cost


class ConstructionCostSystem:
    """Validates and atomically consumes configured construction costs."""

    @staticmethod
    def can_afford(world, definition, payer=None):
        if world is None:
            raise ValueError("World cannot be None.")

        if not isinstance(definition, BuildingDefinition):
            raise ValueError(
                "Definition must be a BuildingDefinition instance."
            )

        # Step 62: Validate every material before mutation.
        for resource_name, quantity in definition.required_materials.items():
            if resource_name not in world.resources:
                return False

            if world.get_resource(resource_name) < quantity:
                return False

        # Step 62: Validate optional money requirement.
        if definition.construction_cost > 0:
            if payer is None:
                return False

            if not hasattr(payer, "get_money"):
                return False

            if payer.get_money() < definition.construction_cost:
                return False

        return True

    @staticmethod
    def consume(world, definition, payer=None):
        if world is None:
            raise ValueError("World cannot be None.")

        if not isinstance(definition, BuildingDefinition):
            raise ValueError(
                "Definition must be a BuildingDefinition instance."
            )

        # Step 62: Perform every validation before changing state.
        if not ConstructionCostSystem.can_afford(
            world,
            definition,
            payer,
        ):
            return {
                "success": False,
                "building_type": definition.building_type,
                "materials": {},
                "cost": definition.construction_cost,
                "reason": "Insufficient construction resources or money.",
            }

        # Step 62: Consume all configured materials.
        consumed_materials = {}

        for resource_name, quantity in definition.required_materials.items():
            world.change_resource(resource_name, -quantity)
            consumed_materials[resource_name] = quantity

        # Step 62: Consume optional construction money.
        if definition.construction_cost > 0:
            payer.change_money(-definition.construction_cost)

        return {
            "success": True,
            "building_type": definition.building_type,
            "materials": consumed_materials,
            "cost": definition.construction_cost,
        }
