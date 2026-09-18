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

    def to_dict(self):
        return {
            "action_id": self.action_id,
            "name": self.name,
            "urgency_score": self.urgency_score,
            "requirements": self.requirements
        }


class DecisionEngine:
    """Evaluates citizen state and available options to select and execute actions."""
    def __init__(self):
        pass

    def evaluate_needs(self, citizen):
        """Returns a sorted list of action options based on current citizen needs."""
        options = []
        if not hasattr(citizen, "needs"):
            return options

        # Basic need evaluations
        hunger = citizen.needs.get("hunger", 0)
        energy = citizen.needs.get("energy", 100)

        if hunger > 50:
            options.append(ActionOption("eat", "Find Food", urgency_score=float(hunger)))
        if energy < 30:
            urgency = float(100 - energy)
            options.append(ActionOption("rest", "Sleep / Rest", urgency_score=urgency))

        # Sort by urgency score descending
        options.sort(key=lambda x: x.urgency_score, reverse=True)
        return options

    def select_best_action(self, citizen):
        """Returns the highest priority ActionOption or None."""
        options = self.evaluate_needs(citizen)
        return options[0] if options else None

    def execute_action(self, citizen, action, world_context=None):
        """Executes a selected ActionOption, modifying citizen state and adding memory."""
        if not action or not isinstance(action, ActionOption):
            return {"success": False, "reason": "Invalid action option."}

        current_tick = 0
        if world_context and isinstance(world_context, dict):
            current_tick = world_context.get("tick", 0)

        if action.action_id == "eat":
            current_hunger = citizen.needs.get("hunger", 0)
            citizen.needs["hunger"] = max(0, current_hunger - 40)
            if hasattr(citizen, "add_memory"):
                citizen.add_memory("Ate food to satisfy hunger", current_tick)
            return {"success": True, "action": "eat", "message": "Citizen ate food."}

        elif action.action_id == "rest":
            current_energy = citizen.needs.get("energy", 0)
            citizen.needs["energy"] = min(100, current_energy + 50)
            if hasattr(citizen, "add_memory"):
                citizen.add_memory("Rested to restore energy", current_tick)
            return {"success": True, "action": "rest", "message": "Citizen rested."}

        return {"success": False, "reason": f"Unknown action_id: {action.action_id}"}
