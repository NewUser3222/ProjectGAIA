import math


# Step 57: Business employment integration
class Business:
    """An economic entity with its own bounded, aggregate-unit inventory."""

    def __init__(
        self, business_id, name, owners=None, inventory_capacity=100.0
    ):
        if not business_id:
            raise ValueError("Business ID cannot be empty.")

        if not name:
            raise ValueError("Business name cannot be empty.")

        self.business_id = business_id
        self.name = name
        self.money = 0.0
        self.inventory = {}
        self.inventory_capacity = self._validate_inventory_capacity(
            inventory_capacity
        )

        self.owners = []
        self.employees = {}
        self.jobs = {}
        self.recipes = {}
        self.employee_jobs = {}
        self._planned_production = None
        self._market_plan_tick = None
        self._reserved_inventory = {}
        self._reserved_wages = {}

        self.active = True

        if owners:
            for owner in owners:
                self.add_owner(owner)

    # Step 56: Ownership
    def add_owner(self, citizen):
        from src.gaia.agents.citizen import Citizen

        if not isinstance(citizen, Citizen):
            raise ValueError("Business owners must be Citizen objects.")

        if not citizen.is_alive():
            raise ValueError("Dead citizens cannot own a business.")

        if citizen not in self.owners:
            self.owners.append(citizen)

    def remove_owner(self, citizen):
        if citizen in self.owners:
            self.owners.remove(citizen)

    def has_owner(self, citizen):
        return citizen in self.owners

    # Step 56: Business operating state
    def activate(self):
        self.active = True

    def deactivate(self):
        self.active = False

    def is_active(self):
        return self.active

    # Step 56: Money
    def change_money(self, amount):
        try:
            amount = float(amount)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Money change must be a finite number.")
        if not math.isfinite(amount):
            raise ValueError("Money change must be a finite number.")

        new_balance = self.money + amount

        if not math.isfinite(new_balance):
            raise ValueError("Business money must remain finite.")
        if new_balance < 0:
            raise ValueError("Business money cannot become negative.")

        self.money = new_balance

    def get_money(self):
        return self.money

    def get_available_money(self):
        """Return cash that is not committed to planned worker wages."""
        return self.money - sum(self._reserved_wages.values())

    def can_pay_wage(self, worker, amount):
        reserved = self._reserved_wages.get(worker.citizen_id, 0.0)
        if reserved == amount:
            return True
        return self.get_available_money() >= amount

    def reserve_worker_wage(self, worker, amount):
        if amount <= 0:
            return
        if self.get_available_money() < amount:
            raise ValueError("Business does not have enough available money.")
        self._reserved_wages[worker.citizen_id] = amount

    def release_worker_wage(self, worker, amount=None):
        if worker is not None:
            reserved = self._reserved_wages.get(worker.citizen_id)
            if amount is None or reserved == amount:
                self._reserved_wages.pop(worker.citizen_id, None)

    # Step 56: Inventory
    def add_item(self, resource_name, quantity):
        if not resource_name:
            raise ValueError("Resource name cannot be empty.")

        try:
            quantity = float(quantity)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Inventory quantity must be finite and positive.")
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Inventory quantity must be finite and positive.")

        next_quantity = self.inventory.get(resource_name, 0) + quantity
        if not math.isfinite(next_quantity):
            raise ValueError("Business inventory must remain finite.")
        projected_total = (
            self.get_inventory_quantity()
            - self.inventory.get(resource_name, 0)
            + next_quantity
        )
        if projected_total > self.inventory_capacity:
            raise ValueError("Business inventory capacity would be exceeded.")

        self.inventory[resource_name] = next_quantity

    def remove_item(self, resource_name, quantity):
        if not resource_name:
            raise ValueError("Resource name cannot be empty.")

        try:
            quantity = float(quantity)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Inventory quantity must be finite and positive.")
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Inventory quantity must be finite and positive.")

        current_quantity = self.inventory.get(resource_name, 0)

        if current_quantity < quantity:
            raise ValueError("Business does not have enough inventory.")

        remaining = current_quantity - quantity

        if remaining == 0:
            self.inventory.pop(resource_name, None)
        else:
            self.inventory[resource_name] = remaining

    def get_item_quantity(self, resource_name):
        if not resource_name:
            raise ValueError("Resource name cannot be empty.")

        return self.inventory.get(resource_name, 0)

    def get_inventory_quantity(self):
        return sum(self.inventory.values())

    def get_inventory_space(self):
        return max(0.0, self.inventory_capacity - self.get_inventory_quantity())

    def can_add_items(self, additions):
        if not isinstance(additions, dict):
            return False
        added_quantity = 0.0
        try:
            for resource_name, quantity in additions.items():
                quantity = float(quantity)
                if (
                    not resource_name
                    or not math.isfinite(quantity)
                    or quantity <= 0
                ):
                    return False
                if not math.isfinite(
                    self.get_item_quantity(resource_name) + quantity
                ):
                    return False
                added_quantity += quantity
        except (TypeError, ValueError, OverflowError):
            return False
        projected_total = self.get_inventory_quantity() + added_quantity
        return (
            math.isfinite(projected_total)
            and projected_total <= self.inventory_capacity
        )

    def get_inventory_capacity(self):
        return self.inventory_capacity

    @staticmethod
    def _validate_inventory_capacity(capacity):
        try:
            capacity = float(capacity)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Inventory capacity must be finite and nonnegative.")
        if not math.isfinite(capacity) or capacity < 0:
            raise ValueError("Inventory capacity must be finite and nonnegative.")
        return capacity

    def set_inventory_capacity(self, capacity):
        capacity = self._validate_inventory_capacity(capacity)
        if capacity < self.get_inventory_quantity():
            raise ValueError("Capacity cannot be lower than current inventory.")
        self.inventory_capacity = capacity

    def get_available_quantity(self, resource_name):
        """Return inventory not committed to the current production plan."""
        return max(
            0,
            self.get_item_quantity(resource_name)
            - self._reserved_inventory.get(resource_name, 0),
        )

    def has_item(self, resource_name, quantity=1):
        if quantity < 0:
            raise ValueError("Inventory quantity cannot be negative.")

        return self.get_item_quantity(resource_name) >= quantity

    # Step 56: Employee foundation
    def add_employee(self, citizen):
        from src.gaia.agents.citizen import Citizen

        if not isinstance(citizen, Citizen):
            raise ValueError("Employees must be Citizen objects.")

        if not citizen.is_alive():
            raise ValueError("Dead citizens cannot be employed.")

        current_business = getattr(citizen, "employer", None)

        if current_business is not None and current_business is not self:
            raise ValueError("Citizen is already employed by another business.")

        self.employees[citizen.citizen_id] = citizen
        citizen.employer = self

    def remove_employee(self, citizen):
        if citizen is None:
            return

        self.employees.pop(citizen.citizen_id, None)

        if getattr(citizen, "employer", None) is self:
            citizen.employer = None
            citizen.clear_job()

        self.employee_jobs.pop(citizen.citizen_id, None)

    def has_employee(self, citizen):
        if citizen is None:
            return False

        return citizen.citizen_id in self.employees

    def get_employees(self):
        return list(self.employees.values())

    def remove_dead_employees(self):
        dead_ids = [
            citizen_id
            for citizen_id, citizen in self.employees.items()
            if not citizen.is_alive()
        ]

        for citizen_id in dead_ids:
            citizen = self.employees[citizen_id]
            self.remove_employee(citizen)

        return len(dead_ids)

    # Step 57: Register a business-owned job
    def add_job(self, job):
        from src.gaia.agents.job import Job

        if not isinstance(job, Job):
            raise ValueError("Business jobs must be Job objects.")

        if job.job_id in self.jobs:
            raise ValueError("A job with this ID already exists in the business.")

        self.jobs[job.job_id] = job

    def get_job(self, job_id):
        return self.jobs.get(job_id)

    def has_job(self, job_id):
        return job_id in self.jobs

    # Step 58: Business production recipes
    def add_recipe(self, recipe):
        from src.gaia.production import ProductionRecipe

        if not isinstance(recipe, ProductionRecipe):
            raise ValueError("Recipe must be a ProductionRecipe instance.")

        if recipe.recipe_id in self.recipes:
            raise ValueError("Recipe ID already exists.")

        self.recipes[recipe.recipe_id] = recipe

    def get_recipe(self, recipe_id):
        return self.recipes.get(recipe_id)

    def has_recipe(self, recipe_id):
        return recipe_id in self.recipes

    def produce(self, recipe_id):
        from src.gaia.production import ProductionSystem

        recipe = self.get_recipe(recipe_id)

        if recipe is None:
            return {
                "success": False,
                "recipe_id": recipe_id,
                "reason": "Recipe does not belong to this business."
            }

        if not self.active:
            return {
                "success": False,
                "recipe_id": recipe_id,
                "reason": "Business is not active."
            }

        if (
            self._planned_production is not None
            and self._planned_production["recipe_id"] != recipe_id
        ):
            return {
                "success": False,
                "recipe_id": recipe_id,
                "reason": "Business inputs are committed to another recipe this tick."
            }

        market_observations = getattr(self, "_market_observations", None)
        if market_observations is not None:
            for activity, quantities in (
                ("consumption", recipe.inputs),
                ("production", recipe.outputs),
            ):
                if any(
                    not math.isfinite(
                        market_observations._current[activity].get(
                            resource_name, 0.0
                        ) + quantity
                    )
                    for resource_name, quantity in quantities.items()
                ):
                    return {
                        "success": False,
                        "recipe_id": recipe_id,
                        "reason": "Market activity total would be non-finite."
                    }

        result = ProductionSystem.produce(
            self.inventory,
            recipe,
            inventory_capacity=self.inventory_capacity,
        )
        if result["success"]:
            if market_observations is not None:
                for resource_name, quantity in recipe.inputs.items():
                    market_observations.record_consumption(
                        resource_name, quantity
                    )
                for resource_name, quantity in recipe.outputs.items():
                    market_observations.record_production(
                        resource_name, quantity
                    )
            self._planned_production = None
            self._reserved_inventory = {}
        return result

    # Step 80: Evaluate configured recipes against market conditions and workers.
    def evaluate_production_plan(self, world):
        from src.gaia.business_planning import BusinessProductionPlanner

        return BusinessProductionPlanner.evaluate(self, world)

    # Step 80: Procure the chosen recipe's missing inputs for the current tick.
    def prepare_production(self, world):
        from src.gaia.business_planning import BusinessProductionPlanner

        self._planned_production = None
        self._reserved_inventory = {}
        self._reserved_wages = {}
        return BusinessProductionPlanner.prepare(self, world)

    # Step 80: Restrict recipe work to the worker selected for this market plan.
    def can_worker_produce(self, worker, job, tick):
        plan = self._planned_production
        return (
            self.active
            and self._market_plan_tick == tick
            and plan is not None
            and plan["worker"] is worker
            and plan["job"] is job
            and plan["recipe_id"] == job.recipe_id
        )

    # Step 57: Employ a citizen into a specific business job
    def employ(self, citizen, job):
        if not self.active:
            raise ValueError("Inactive businesses cannot employ citizens.")

        if job is None or job.job_id not in self.jobs:
            raise ValueError("Job must belong to this business.")

        if not job.active:
            raise ValueError("Cannot assign an inactive job.")

        if not job.is_citizen_eligible(citizen):
            raise ValueError("Citizen is not eligible for this job.")

        self.add_employee(citizen)

        try:
            citizen.set_job(job)
        except Exception:
            self.remove_employee(citizen)
            raise

        self.employee_jobs[citizen.citizen_id] = job
        return job

    def get_employee_job(self, citizen):
        if citizen is None:
            return None

        return self.employee_jobs.get(citizen.citizen_id)

    def is_employee_eligible(self, citizen):
        if not self.active:
            return False

        if not self.has_employee(citizen):
            return False

        job = self.get_employee_job(citizen)

        if job is None or not job.active:
            return False

        return citizen.is_alive() and job.is_citizen_eligible(citizen)

    # Step 59: Explicit business commerce
    def buy_resource(self, seller, resource_name, quantity):
        from src.gaia.business_commerce import BusinessCommerce

        return BusinessCommerce.buy_from_business(
            self,
            seller,
            resource_name,
            quantity,
        )

    def buy_from_citizen(self, seller, resource_name, quantity):
        from src.gaia.business_commerce import BusinessCommerce

        return BusinessCommerce.buy_from_citizen(
            self,
            seller,
            resource_name,
            quantity,
        )

    def sell_resource(self, buyer, resource_name, quantity):
        from src.gaia.business_commerce import BusinessCommerce

        return BusinessCommerce.sell_to_business(
            self,
            buyer,
            resource_name,
            quantity,
        )

    def sell_to_citizen(self, buyer, resource_name, quantity):
        from src.gaia.business_commerce import BusinessCommerce

        return BusinessCommerce.sell_to_citizen(
            self,
            buyer,
            resource_name,
            quantity,
        )
