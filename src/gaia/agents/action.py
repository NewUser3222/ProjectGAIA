# Step 1: Define the Action Option
class ActionOption:
    """Represents a potential action a citizen can evaluate and execute."""

    def __init__(self, action_id, name, urgency_score=0.0, requirements=None):
        if not action_id:
            raise ValueError("Action ID cannot be empty.")
        if not name:
            raise ValueError("Action Name cannot be empty.")

        self.action_id = action_id
        self.name = name
        self.urgency_score = urgency_score
        self.requirements = requirements or {}

    # Step 2: Convert the action option to a dictionary
    def to_dict(self):
        return {
            "action_id": self.action_id,
            "name": self.name,
            "urgency_score": self.urgency_score,
            "requirements": self.requirements
        }


# Step 3: Define the Action Executor
class ActionExecutor:
    """Executes selected actions and applies their state changes."""

    # Step 4: Execute a selected action
    def execute(self, citizen, action, world_context=None):
        if not action or not isinstance(action, ActionOption):
            return {"success": False, "reason": "Invalid action option."}

        current_tick = 0
        world = None

        if world_context and isinstance(world_context, dict):
            current_tick = world_context.get("tick", 0)
            world = world_context.get("world")

        # Step 43: Eat only from actual citizen inventory when world context exists.
        if action.action_id == "eat":
            if world is not None:
                if citizen.get_item_quantity("food") <= 0:
                    return {
                        "success": False,
                        "action": "eat",
                        "reason": "No food available in citizen inventory."
                    }

                try:
                    world.consume_resource_for_need(
                        citizen,
                        "food",
                        1
                    )
                except ValueError as error:
                    return {
                        "success": False,
                        "action": "eat",
                        "reason": str(error)
                    }

            current_hunger = citizen.needs.get("hunger", citizen.hunger)
            citizen.hunger = max(0.0, current_hunger - 40)
            citizen.needs["hunger"] = citizen.hunger

            if hasattr(citizen, "add_memory"):
                citizen.add_memory(
                    "Ate food to satisfy hunger",
                    current_tick
                )

            return {
                "success": True,
                "action": "eat",
                "message": "Citizen ate food."
            }

        # Step 41: Gather a resource directly into citizen inventory.
        if action.action_id == "gather":
            if world is None:
                return {
                    "success": False,
                    "action": "gather",
                    "reason": "World context is required for gathering."
                }

            resource_name = action.requirements.get("resource", "food")
            quantity = action.requirements.get("quantity", 1)

            try:
                world.gather_resource(
                    citizen,
                    resource_name,
                    quantity
                )
            except (TypeError, ValueError) as error:
                return {
                    "success": False,
                    "action": "gather",
                    "reason": str(error)
                }

            if hasattr(citizen, "add_memory"):
                citizen.add_memory(
                    f"Gathered {quantity} {resource_name}.",
                    current_tick
                )

            return {
                "success": True,
                "action": "gather",
                "resource": resource_name,
                "quantity": quantity,
                "message": f"Citizen gathered {quantity} {resource_name}."
            }

        # Step 49: Purchase a resource directly from another citizen.
        if action.action_id == "buy_resource":
            if world is None:
                return {
                    "success": False,
                    "action": "buy_resource",
                    "reason": "World context is required for purchasing."
                }

            seller = action.requirements.get("seller")
            resource_name = action.requirements.get("resource", "food")
            quantity = action.requirements.get("quantity", 1)
            unit_price = action.requirements.get("unit_price")

            if unit_price is None:
                from src.gaia.economy import get_resource_value
                unit_price = get_resource_value(resource_name)

            from src.gaia.economy_transactions import EconomicTransaction

            result = EconomicTransaction.purchase_resource(
                citizen,
                seller,
                resource_name,
                quantity,
                unit_price
            )

            if result.success and hasattr(citizen, "add_memory"):
                citizen.add_memory(
                    f"Purchased {quantity} {resource_name}.",
                    current_tick
                )

            return result.to_dict()

        # Step 6: Execute the rest action
        if action.action_id == "rest":
            current_energy = citizen.needs.get("energy", citizen.energy)
            citizen.energy = min(100.0, current_energy + 50)
            citizen.needs["energy"] = citizen.energy

            if hasattr(citizen, "add_memory"):
                citizen.add_memory(
                    "Rested to restore energy",
                    current_tick
                )

            return {
                "success": True,
                "action": "rest",
                "message": "Citizen rested."
            }

        # Step 7: Reject unknown actions
        return {
            "success": False,
            "reason": f"Unknown action_id: {action.action_id}"
        }
