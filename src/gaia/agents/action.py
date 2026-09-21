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

        if world_context and isinstance(world_context, dict):
            current_tick = world_context.get("tick", 0)

        # Step 5: Execute the eat action
        if action.action_id == "eat":
            current_hunger = citizen.needs.get("hunger", 0)
            citizen.needs["hunger"] = max(0, current_hunger - 40)

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

        # Step 6: Execute the rest action
        if action.action_id == "rest":
            current_energy = citizen.needs.get("energy", 0)
            citizen.needs["energy"] = min(100, current_energy + 50)

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
