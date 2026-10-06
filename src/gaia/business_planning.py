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
                available_in_business = business.get_available_quantity(
                    resource_name
                )
                owned_quantity = min(available_in_business, quantity)
                missing_quantity = quantity - owned_quantity
                estimated_cost += owned_quantity * input_price

                if missing_quantity > 0:
                    supplier_orders, purchase_cost = (
                        BusinessProductionPlanner._find_suppliers(
                            business, world, resource_name, missing_quantity
                        )
                    )
                    if not supplier_orders:
                        return None

                    for supplier, supplied_quantity, amount in supplier_orders:
                        purchases.append({
                            "seller": supplier,
                            "resource": resource_name,
                            "quantity": supplied_quantity,
                            "amount": amount,
                        })
                    procurement_cost += purchase_cost
                    estimated_cost += purchase_cost
                    for supplier, _, amount in supplier_orders:
                        seller_totals[supplier] = (
                            seller_totals.get(supplier, 0.0) + amount
                        )

            expected_revenue = 0.0
            expected_sales = {}
            for resource_name, quantity in recipe.outputs.items():
                market_supply = world.get_market_supply(resource_name)
                output_price = world.get_market_price(
                    resource_name,
                    supply=max(market_supply + quantity, quantity),
                )
                demand_rate = world.market_observations.get_demand_rate(
                    resource_name
                )
                existing_stock = max(
                    0.0,
                    business.get_item_quantity(resource_name)
                    - recipe.inputs.get(resource_name, 0.0),
                )
                if demand_rate is None:
                    # Let a business with no stock establish its first supply.
                    demand_rate = quantity if existing_stock <= 0 else 0.0
                expected_sold = max(
                    0.0,
                    min(existing_stock + quantity, demand_rate)
                    - min(existing_stock, demand_rate),
                )
                expected_sales[resource_name] = expected_sold
                expected_revenue += expected_sold * output_price
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
            "inputs": dict(recipe.inputs),
            "outputs": dict(recipe.outputs),
            "expected_sales": expected_sales,
        }

    @staticmethod
    def _find_suppliers(business, world, resource_name, quantity):
        suppliers = []
        seen = set()
        for seller in list(world.citizens) + list(world.businesses):
            if seller is business or id(seller) in seen:
                continue
            seen.add(id(seller))
            if isinstance(seller, Citizen):
                if not seller.is_alive():
                    continue
            elif not seller.is_active():
                continue

            available = (
                seller.get_available_quantity(resource_name)
                if hasattr(seller, "get_available_quantity")
                else seller.get_item_quantity(resource_name)
            )
            if available <= 0:
                continue

            try:
                unit_price = BusinessCommerce.calculate_price(
                    resource_name, seller, 1
                )
            except (TypeError, ValueError, OverflowError):
                continue

            if not math.isfinite(unit_price) or unit_price < 0:
                continue

            suppliers.append((
                unit_price,
                getattr(seller, "business_id", getattr(seller, "citizen_id", "")),
                seller,
                available,
            ))

        suppliers.sort(key=lambda item: (item[0], item[1]))
        remaining = quantity
        orders = []
        total_cost = 0.0
        for unit_price, _, seller, available in suppliers:
            supplied_quantity = min(available, remaining)
            amount = unit_price * supplied_quantity
            if not math.isfinite(amount) or not math.isfinite(
                seller.get_money() + amount
            ):
                continue
            orders.append((seller, supplied_quantity, amount))
            total_cost += amount
            remaining -= supplied_quantity
            if remaining <= 0:
                break

        if remaining > 0 or not math.isfinite(total_cost):
            return [], 0.0
        return orders, total_cost

    @staticmethod
    def prepare(business, world):
        business._market_plan_tick = world.current_tick
        business._planned_production = None

        plan = BusinessProductionPlanner.evaluate(business, world)
        if not plan["success"]:
            return plan

        if plan["purchases"]:
            result = BusinessCommerce.buy_bundle(business, plan["purchases"])
            if not result["success"]:
                return {
                    "success": False,
                    "reason": "Planned input procurement could not be completed.",
                    "recipe_id": plan["recipe_id"],
                    "purchase_result": result,
                }

        business._reserved_inventory = dict(plan["inputs"])
        business._planned_production = plan
        return plan
