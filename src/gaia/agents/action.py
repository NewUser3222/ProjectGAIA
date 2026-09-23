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
        # Step 52: Execute configured job work and production
        if action.action_id == "work":
            if not citizen.is_alive():
                return {
                    "success": False,
                    "action": "work",
                    "reason": "Dead citizens cannot work."
                }

            job = citizen.get_job()

            if job is None:
                return {
                    "success": False,
                    "action": "work",
                    "reason": "Citizen has no job."
                }

            if not citizen.has_active_job():
                return {
                    "success": False,
                    "action": "work",
                    "reason": "Citizen does not have an active job."
                }

            if not job.is_citizen_eligible(citizen):
                return {
                    "success": False,
                    "action": "work",
                    "reason": "Citizen is not eligible for this job."
                }

            if citizen.energy < job.energy_cost:
                return {
                    "success": False,
                    "action": "work",
                    "reason": "Citizen does not have enough energy."
                }

            if not job.production and job.recipe_id is None:
                return {
                    "success": False,
                    "action": "work",
                    "reason": "Job has no configured production."
                }

            # Validate direct job production only.
            # Recipe-based production validates its own inputs and outputs.
            for resource_name, quantity in job.production.items():
                if not resource_name:
                    return {
                        "success": False,
                        "action": "work",
                        "reason": "Production resource cannot be empty."
                    }

                if quantity <= 0:
                    return {
                        "success": False,
                        "action": "work",
                        "reason": "Production quantity must be positive."
                    }

            # Step 53: Resolve the explicit wage payer before mutation.
            employer = None
            if world_context:
                employer = world_context.get("employer")

            # Step 53: A wage requires an explicit payer when no work context exists.
            # Legacy work calls may provide a context containing only tick; those
            # calls continue to support production without performing payroll.
            if job.wage > 0 and world_context is None:
                return {
                    "success": False,
                    "action": "work",
                    "reason": "No wage payer provided."
                }

            if job.wage > 0 and employer is not None:
                # Step 57: Citizens use is_alive(); businesses use is_active().
                if hasattr(employer, "is_alive"):
                    if not employer.is_alive():
                        return {
                            "success": False,
                            "action": "work",
                            "reason": "Wage payer is not alive."
                        }
                elif hasattr(employer, "is_active"):
                    if not employer.is_active():
                        return {
                            "success": False,
                            "action": "work",
                            "reason": "Wage payer is not active."
                        }
                else:
                    return {
                        "success": False,
                        "action": "work",
                        "reason": "Invalid wage payer."
                    }

                if employer is citizen:
                    return {
                        "success": False,
                        "action": "work",
                        "reason": "Citizen cannot pay their own wage."
                    }

                if employer.get_money() < job.wage:
                    return {
                        "success": False,
                        "action": "work",
                        "reason": "Wage payer does not have enough money."
                    }

            # Step 57: Business employment routes production into
            # the employer's inventory instead of the citizen's inventory.
            business = citizen.get_employer()

            if business is not None:
                if not business.is_active():
                    return {
                        "success": False,
                        "action": "work",
                        "reason": "Employer is not active."
                    }

                if not business.has_employee(citizen):
                    return {
                        "success": False,
                        "action": "work",
                        "reason": "Citizen is not an active employee."
                    }

                if business.get_employee_job(citizen) is not job:
                    return {
                        "success": False,
                        "action": "work",
                        "reason": "Citizen's business job does not match the assigned job."
                    }

            # Step 58: Apply production only after all checks pass.
            if business is not None and job.recipe_id is not None:
                production_result = business.produce(job.recipe_id)

                if not production_result["success"]:
                    return {
                        "success": False,
                        "action": "work",
                        "reason": production_result["reason"]
                    }

                production = dict(production_result["outputs"])

            else:
                production_target = business if business is not None else citizen
                production = dict(job.production)

                for resource_name, quantity in production.items():
                    production_target.add_item(resource_name, quantity)

            citizen.energy = max(
                0.0,
                citizen.energy - job.energy_cost
            )

            # Step 57: Businesses can pay wages through the existing
            # transaction layer.
            wage_paid = 0.0
            if job.wage > 0 and employer is not None:
                from src.gaia.economy_transactions import EconomicTransaction

                EconomicTransaction.pay_wage(
                    employer,
                    citizen,
                    job.wage
                )
                wage_paid = job.wage

            tick = 0
            if world_context:
                tick = world_context.get("tick", 0)

            citizen.add_memory(
                f"Worked as {job.name} and produced {production}.",
                tick
            )

            return {
                "success": True,
                "action": "work",
                "job_id": job.job_id,
                "production": dict(production),
                "wage": wage_paid
            }
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
