import math

from src.gaia.agents.citizen import Citizen
from src.gaia.business_commerce import BusinessCommerce


class BusinessProductionPlanner:
    """Select and prepare one market-supported recipe batch per business tick."""

    @staticmethod
    def evaluate(business, world):
        if world is None:
            raise ValueError("World cannot be None.")
        if not business.is_active():
            return {"success": False, "reason": "Business is not active."}

        candidates = []
        for job_id in sorted(business.jobs):
            job = business.get_job(job_id)
            if not job.active or not job.recipe_id:
                continue

            recipe = business.get_recipe(job.recipe_id)
            if recipe is None:
                continue

            workers = sorted(
                (
                    worker for worker in business.get_employees()
                    if business.get_employee_job(worker) is job
                    and business.is_employee_eligible(worker)
                    and worker.energy >= job.energy_cost
                ),
                key=lambda worker: worker.citizen_id,
            )
            if not workers:
                continue

            candidate = BusinessProductionPlanner._evaluate_recipe(
                business, world, job, recipe, workers[0]
            )
            if candidate is not None:
                candidates.append(candidate)

        if not candidates:
            return {
                "success": False,
                "reason": "No staffed, feasible, profitable recipe is available.",
            }

        candidates.sort(
            key=lambda plan: (
                -plan["estimated_margin"],
                plan["recipe_id"],
                plan["worker"].citizen_id,
            )
        )
        return candidates[0]

    @staticmethod
    def _evaluate_recipe(business, world, job, recipe, worker):
        purchases = []
        estimated_cost = 0.0
        procurement_cost = 0.0
        seller_totals = {}

        try:
            for resource_name, quantity in recipe.inputs.items():
                market_supply = world.get_market_supply(resource_name)
                input_price = world.get_market_price(
                    resource_name,
                    supply=max(market_supply, quantity),
                )
                available_in_business = business.get_item_quantity(resource_name)
                owned_quantity = min(available_in_business, quantity)
                missing_quantity = quantity - owned_quantity
                estimated_cost += owned_quantity * input_price

                if missing_quantity > 0:
                    supplier, purchase_cost = (
                        BusinessProductionPlanner._find_supplier(
                            business, world, resource_name, missing_quantity
                        )
                    )
                    if supplier is None:
                        return None

                    purchases.append({
                        "seller": supplier,
                        "resource": resource_name,
                        "quantity": missing_quantity,
                        "amount": purchase_cost,
                    })
                    procurement_cost += purchase_cost
                    estimated_cost += purchase_cost
                    seller_totals[supplier] = (
                        seller_totals.get(supplier, 0.0) + purchase_cost
                    )

            expected_revenue = 0.0
            for resource_name, quantity in recipe.outputs.items():
                market_supply = world.get_market_supply(resource_name)
                output_price = world.get_market_price(
                    resource_name,
                    supply=max(market_supply + quantity, quantity),
                )
                expected_revenue += quantity * output_price
        except (TypeError, ValueError, OverflowError):
            return None

        estimated_margin = expected_revenue - estimated_cost
        if (
            not math.isfinite(expected_revenue)
            or not math.isfinite(estimated_cost)
            or not math.isfinite(estimated_margin)
            or estimated_margin <= 0
            or procurement_cost > business.get_money()
        ):
            return None

        if any(
            not math.isfinite(seller.get_money() + amount)
            for seller, amount in seller_totals.items()
        ):
            return None

        return {
            "success": True,
            "recipe_id": recipe.recipe_id,
            "job_id": job.job_id,
            "worker": worker,
            "job": job,
            "expected_revenue": expected_revenue,
            "estimated_cost": estimated_cost,
            "estimated_margin": estimated_margin,
            "procurement_cost": procurement_cost,
            "purchases": purchases,
            "outputs": dict(recipe.outputs),
        }

    @staticmethod
    def _find_supplier(business, world, resource_name, quantity):
        suppliers = []
        for seller in list(world.citizens) + list(world.businesses):
            if seller is business:
                continue
            if isinstance(seller, Citizen):
                if not seller.is_alive():
                    continue
            elif not seller.is_active():
                continue

            if seller.get_item_quantity(resource_name) < quantity:
                continue

            try:
                total_price = BusinessCommerce.calculate_price(
                    resource_name, seller, quantity
                )
            except (TypeError, ValueError, OverflowError):
                continue

            if not math.isfinite(seller.get_money() + total_price):
                continue

            suppliers.append((total_price / quantity, seller, total_price))

        if not suppliers:
            return None, 0.0

        suppliers.sort(
            key=lambda item: (
                item[0],
                getattr(item[1], "business_id", getattr(item[1], "citizen_id", "")),
            )
        )
        _, seller, total_price = suppliers[0]
        return seller, total_price

    @staticmethod
    def prepare(business, world):
        business._market_plan_tick = world.current_tick
        business._planned_production = None

        plan = BusinessProductionPlanner.evaluate(business, world)
        if not plan["success"]:
            return plan

        for purchase in plan["purchases"]:
            seller = purchase["seller"]
            if isinstance(seller, Citizen):
                result = BusinessCommerce.buy_from_citizen(
                    business,
                    seller,
                    purchase["resource"],
                    purchase["quantity"],
                )
            else:
                result = BusinessCommerce.buy_from_business(
                    business,
                    seller,
                    purchase["resource"],
                    purchase["quantity"],
                )

            if not result["success"]:
                return {
                    "success": False,
                    "reason": "A planned input purchase could not be completed.",
                    "recipe_id": plan["recipe_id"],
                    "purchase_result": result,
                }

        business._planned_production = plan
        return plan
