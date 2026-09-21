# Step 1: Import and re-export the action classes
from src.gaia.agents.action import ActionExecutor, ActionOption


# Step 2: Define the Decision Engine
class DecisionEngine:
    """Evaluates citizen state and selects actions."""

    def __init__(self):
        self.action_executor = ActionExecutor()

    # Step 3: Evaluate citizen needs
    def evaluate_needs(self, citizen):
        """Returns a sorted list of action options based on current citizen needs."""
        options = []

        if not hasattr(citizen, "needs"):
            return options

        # Basic need evaluations
        hunger = citizen.needs.get("hunger", 0)
        energy = citizen.needs.get("energy", 100)

        if hunger > 50:
            options.append(
                ActionOption(
                    "eat",
                    "Find Food",
                    urgency_score=float(hunger)
                )
            )

        if energy < 30:
            urgency = float(100 - energy)
            options.append(
                ActionOption(
                    "rest",
                    "Sleep / Rest",
                    urgency_score=urgency
                )
            )

        # Sort by urgency score descending
        options.sort(
            key=lambda x: x.urgency_score,
            reverse=True
        )

        return options

    # Step 4: Select the highest-priority action
    def select_best_action(self, citizen):
        """Returns the highest priority ActionOption or None."""
        options = self.evaluate_needs(citizen)
        return options[0] if options else None

    # Step 5: Preserve the existing execution interface
    def execute_action(self, citizen, action, world_context=None):
        """Delegates action execution to the ActionExecutor."""
        return self.action_executor.execute(
            citizen,
            action,
            world_context
        )
