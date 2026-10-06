# Step 1: Import and re-export the action classes
from src.gaia.agents.action import ActionExecutor, ActionOption


# Step 2: Define the Decision Engine
class DecisionEngine:
    """Evaluates citizen state and selects actions."""

    def __init__(self):
        self.action_executor = ActionExecutor()
        self._action_providers = []
        self.register_action_provider(self._construction_actions)

    def register_action_provider(self, provider):
        """Register a deterministic source of available citizen actions.

        Providers receive ``(citizen, world, context)`` and return action
        options. They describe possibilities; the Simulation still owns
        validation and execution.
        """
        if not callable(provider):
            raise TypeError("Action provider must be callable.")
        if provider in self._action_providers:
            raise ValueError("Action provider is already registered.")
        self._action_providers.append(provider)

    @staticmethod
    def _construction_actions(citizen, world, context):
        options = []
        projects = context.get("construction_projects", ())
        for project in sorted(
            tuple(projects), key=lambda item: str(item.project_id)
        ):
            if project.can_worker_contribute(citizen):
                options.append(ActionOption(
                    "construct",
                    "Work on Construction",
                    urgency_score=25.0,
                    requirements={
                        "project": project,
                        "work_amount": 10.0,
                        "destination": tuple(project.location),
                        "movement_reason": "construction",
                        "target_kind": "construction",
                        "target_id": str(project.project_id),
                    },
                ))
        return options

    # Step 44: Evaluate citizen needs using actual world circumstances.
    def evaluate_needs(self, citizen, world=None, *, context=None):
        """Return valid actions based on needs, inventory, and world resources."""
        options = []

        if not hasattr(citizen, "needs") or not citizen.is_alive():
            return options

        context = context or {}

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

        # Step 49: Consider direct peer-to-peer food purchases when gathering
        # is unavailable. Economic behavior remains optional.
        if hunger > 50 and citizen.get_item_quantity("food") <= 0 and world is not None:
            sellers = list(world.citizens) + world.get_active_businesses()
            affordable_offers = []
            for seller in sellers:
                if seller is citizen:
                    continue
                if hasattr(seller, "is_alive") and not seller.is_alive():
                    continue
                if hasattr(seller, "is_active") and not seller.is_active():
                    continue
                available_food = (
                    seller.get_available_quantity("food")
                    if hasattr(seller, "get_available_quantity")
                    else seller.get_item_quantity("food")
                )
                if available_food <= 0:
                    continue

                food_price = world.get_market_price(
                    "food",
                    supply=available_food,
                )
                if citizen.get_money() >= food_price:
                    affordable_offers.append((food_price, seller))

            if affordable_offers:
                food_price, seller = min(
                    affordable_offers,
                    key=lambda offer: (
                        offer[0],
                        getattr(
                            offer[1],
                            "business_id",
                            getattr(offer[1], "citizen_id", ""),
                        ),
                    ),
                )
                options.append(
                    ActionOption(
                        "buy_resource",
                        "Buy Food",
                        urgency_score=float(hunger),
                        requirements={
                            "seller": seller,
                            "resource": "food",
                            "quantity": 1,
                            "unit_price": food_price
                        }
                    )
                )

        # Step 55: Work is an optional low-priority economic action.
        if citizen.has_active_job():
            job = citizen.get_job()

            if citizen.can_perform_job(job):
                if citizen.energy >= job.energy_cost:
                    business = citizen.get_employer()
                    recipe_work_is_planned = (
                        business is None
                        or job.recipe_id is None
                        or world is None
                        or business.can_worker_produce(
                            citizen, job, world.current_tick
                        )
                    )
                    if recipe_work_is_planned:
                        options.append(
                            ActionOption(
                                "work",
                                "Work",
                                urgency_score=20.0
                            )
                        )
        # Extend the available action set through registered providers. Stable
        # provider order and Python's stable urgency sort make ties repeatable.
        for provider in tuple(self._action_providers):
            provided = provider(citizen, world, context)
            if provided is None:
                continue
            for option in provided:
                if not isinstance(option, ActionOption):
                    raise TypeError("Action providers must return ActionOption values.")
                options.append(option)

        options.sort(
            key=lambda x: x.urgency_score,
            reverse=True
        )

        return options

    # Step 44: Select the highest-priority valid action.
    def select_best_action(self, citizen, world=None, *, context=None):
        """Return the highest-priority action valid for current circumstances."""
        options = self.evaluate_needs(citizen, world=world, context=context)
        return options[0] if options else None

    # Step 5: Preserve the existing execution interface
    def execute_action(self, citizen, action, world_context=None):
        """Delegates action execution to the ActionExecutor."""
        return self.action_executor.execute(
            citizen,
            action,
            world_context
        )
