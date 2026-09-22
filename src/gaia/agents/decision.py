# Step 1: Import and re-export the action classes
from src.gaia.agents.action import ActionExecutor, ActionOption


# Step 2: Define the Decision Engine
class DecisionEngine:
    """Evaluates citizen state and selects actions."""

    def __init__(self):
        self.action_executor = ActionExecutor()

    # Step 44: Evaluate citizen needs using actual world circumstances.
    def evaluate_needs(self, citizen, world=None):
        """Return valid actions based on needs, inventory, and world resources."""
        options = []

        if not hasattr(citizen, "needs") or not citizen.is_alive():
            return options

        hunger = citizen.needs.get("hunger", 0)
        energy = citizen.needs.get("energy", 100)

        if hunger > 50:
            if citizen.get_item_quantity("food") > 0:
                options.append(
                    ActionOption(
                        "eat",
                        "Eat Food",
                        urgency_score=float(hunger),
                        requirements={"resource": "food"}
                    )
                )
            elif world is None:
                # Preserve the existing standalone decision API.
                options.append(
                    ActionOption(
                        "eat",
                        "Find Food",
                        urgency_score=float(hunger)
                    )
                )
            elif world.get_resource("food") > 0:
                options.append(
                    ActionOption(
                        "gather",
                        "Gather Food",
                        urgency_score=float(hunger),
                        requirements={
                            "resource": "food",
                            "quantity": 1
                        }
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

        options.sort(
            key=lambda x: x.urgency_score,
            reverse=True
        )

        return options

    # Step 44: Select the highest-priority valid action.
    def select_best_action(self, citizen, world=None):
        """Return the highest-priority action valid for current circumstances."""
        options = self.evaluate_needs(citizen, world=world)
        return options[0] if options else None

    # Step 5: Preserve the existing execution interface
    def execute_action(self, citizen, action, world_context=None):
        """Delegates action execution to the ActionExecutor."""
        return self.action_executor.execute(
            citizen,
            action,
            world_context
        )
