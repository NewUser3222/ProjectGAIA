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
    """Evaluates citizen state and available options to select the best action."""
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
