import math

from src.gaia.agents.citizen import Citizen
from src.gaia.building import Building
from src.gaia.environment import EnvironmentState
from src.gaia.market import MarketObservations, MarketPricing
from src.gaia.transportation import TransportationSystem


# Step 2: Define the World State
class WorldState:
    def __init__(self, width=100, height=100):
        self.width = width
        self.height = height
        self.current_tick = 0

        # Step 3: Create world entity collections
        self.citizens = []
        self.businesses = []
        self.buildings = []

        # Step 71: Create the simulation-owned environment.
        self.environment = EnvironmentState()

        # Step 73: Create the simulation-owned transportation system.
        self.transportation = TransportationSystem(self)

        # Step 79: Store completed economic activity for market pricing.
        self.market_observations = MarketObservations()

        # Step 4: Create world resources
        self.resources = {
            "food": 0,
            "water": 0,
            "wood": 0,
            "stone": 0,
            "metal": 0,
            "energy": 0
        }

        # Step 5: Define maximum resource capacities
        self.resource_limits = {
            "food": 1000,
            "water": 1000,
            "wood": 1000,
            "stone": 1000,
            "metal": 1000,
            "energy": 1000
        }

        # Step 6: Define basic natural resource regeneration
        self.resource_regeneration = {
            "food": 1,
            "water": 2,
            "wood": 1,
            "stone": 0,
            "metal": 0,
            "energy": 1
        }

    # Step 7: Add a citizen to the world
    def add_citizen(self, citizen):
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can be added to the world.")

        self.citizens.append(citizen)
        citizen._market_observations = self.market_observations

    # Step 61: Building world management
    def add_building(self, building):
        if not isinstance(building, Building):
            raise TypeError("Only Building objects can be added to the world.")

        if any(
            existing.building_id == building.building_id
            for existing in self.buildings
        ):
            raise ValueError("A building with this ID already exists in the world.")

        self.buildings.append(building)

    def remove_building(self, building):
        if building in self.buildings:
            self.buildings.remove(building)

    def get_building(self, building_id):
        for building in self.buildings:
            if building.building_id == building_id:
                return building
        return None

    def get_buildings(self):
        return list(self.buildings)

    # Step 60: Add a business to the world
    def add_business(self, business):
        from src.gaia.business import Business

        if not isinstance(business, Business):
            raise TypeError("Only Business objects can be added to the world.")

        if business not in self.businesses:
            self.businesses.append(business)
            business._market_observations = self.market_observations

    # Step 79: Quote resources from current supply and completed market activity.
    def get_market_price(self, resource_name, supply):
        recent = self.market_observations.get_recent(resource_name)
        return MarketPricing.calculate_price(
            resource_name,
            supply=supply,
            recent_consumption=recent["consumption"],
            recent_production=recent["production"],
            recent_trade=recent["trade"],
        )

    # Step 80: Measure active supply for production feasibility and valuation.
    def get_market_supply(self, resource_name):
        supply = self.resources.get(resource_name, 0)
        for citizen in self.citizens:
            if citizen.is_alive():
                supply += citizen.get_item_quantity(resource_name)
        for business in self.businesses:
            if business.is_active():
                supply += business.get_item_quantity(resource_name)
        return supply

    # Step 60: Remove a business from the world
    def remove_business(self, business):
        if business in self.businesses:
            self.businesses.remove(business)
            if (
                getattr(business, "_market_observations", None)
                is self.market_observations
            ):
                business._market_observations = None

    # Step 60: Get active businesses
    def get_active_businesses(self):
        return [
            business
            for business in self.businesses
            if business.is_active()
        ]

    # Step 8: Change a world resource amount
    def change_resource(self, resource_name, amount):
        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        new_amount = self.resources[resource_name] + amount
        maximum = self.resource_limits[resource_name]

        self.resources[resource_name] = max(0, min(maximum, new_amount))

    # Step 9: Set a world resource amount
    def set_resource(self, resource_name, amount):
        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        if amount < 0:
            raise ValueError("Resource amount cannot be negative.")

        maximum = self.resource_limits[resource_name]
        self.resources[resource_name] = min(maximum, amount)

    # Step 10: Get a world resource amount
    def get_resource(self, resource_name):
        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        return self.resources[resource_name]

    # Step 11: Transfer resources from the world to a citizen
    def transfer_resource_to_citizen(self, citizen, resource_name, quantity):
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can receive resources.")

        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        available = self.get_resource(resource_name)

        if quantity > available:
            raise ValueError("Not enough resources available in the world.")

        self.change_resource(resource_name, -quantity)
        citizen.add_item(resource_name, quantity)

    # Step 41: Gather a finite world resource into a citizen inventory
    def gather_resource(self, citizen, resource_name, quantity=1):
        """Gather available world resources at the citizen's location."""
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can gather resources.")

        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        if not self._is_valid_location(citizen.location):
            raise ValueError("Citizen location is outside the world bounds.")

        available = self.get_resource(resource_name)

        if quantity > available:
            raise ValueError("Not enough resources available to gather.")

        self.change_resource(resource_name, -quantity)
        citizen.add_item(resource_name, quantity)

        return quantity

    def is_valid_location(self, location):
        """Return whether a location falls within this world's bounds."""
        return self._is_valid_location(location)

    # Step 42: Validate a citizen's world location before gathering
    def _is_valid_location(self, location):
        if not isinstance(location, (tuple, list)) or len(location) != 2:
            return False

        x, y = location

        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return False

        return 0 <= x < self.width and 0 <= y < self.height

    # Step 12: Transfer resources from a citizen back to the world
    def transfer_resource_from_citizen(self, citizen, resource_name, quantity):
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can transfer resources.")

        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        if citizen.get_item_quantity(resource_name) < quantity:
            raise ValueError("Not enough resources in citizen inventory.")

        citizen.remove_item(resource_name, quantity)
        self.change_resource(resource_name, quantity)

    # Step 13: Consume a resource from a citizen's inventory
    def consume_resource(self, citizen, resource_name, quantity):
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can consume resources.")

        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        quantity = self._validate_positive_quantity(quantity)

        if citizen.get_item_quantity(resource_name) < quantity:
            raise ValueError("Not enough resources in citizen inventory.")

        citizen.remove_item(resource_name, quantity)
        self.market_observations.record_consumption(resource_name, quantity)

    # Step 14: Consume a resource and restore a matching citizen need
    def consume_resource_for_need(self, citizen, resource_name, quantity):
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can consume resources.")

        if resource_name not in self.resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        quantity = self._validate_positive_quantity(quantity)

        need_name = resource_name

        if need_name not in citizen.needs:
            raise ValueError(
                f"Resource '{resource_name}' does not match a citizen need."
            )

        if citizen.get_item_quantity(resource_name) < quantity:
            raise ValueError("Not enough resources in citizen inventory.")

        citizen.remove_item(resource_name, quantity)
        citizen.change_need(need_name, quantity)
        self.market_observations.record_consumption(resource_name, quantity)

    @staticmethod
    def _validate_positive_quantity(quantity):
        try:
            quantity = float(quantity)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Quantity must be finite and greater than zero.")
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Quantity must be finite and greater than zero.")
        return quantity

    # Step 76: Regenerate resources using the environment for the current tick.
    def regenerate_resources(self):
        seasonal_regeneration = {
            "spring": {"food": 2, "wood": 2},
            "summer": {"food": 2, "wood": 2},
            "autumn": {"food": 1, "wood": 1},
            "winter": {"food": 0, "wood": 0},
        }
        weather_regeneration = {
            "clear": {"water": 1},
            "cloudy": {"water": 2},
            "rain": {"water": 3},
            "snow": {"water": 2},
        }

        environmental_amounts = {}
        environmental_amounts.update(
            seasonal_regeneration[self.environment.season]
        )
        environmental_amounts.update(
            weather_regeneration[self.environment.weather]
        )

        for resource_name, amount in self.resource_regeneration.items():
            if amount <= 0:
                continue

            effective_amount = environmental_amounts.get(resource_name, amount)
            self.change_resource(resource_name, effective_amount)

    # Step 77: Apply environmental exposure through world-owned conditions.
    def apply_environmental_effects(self, citizen):
        """Apply temperature exposure, reduced by an occupied active building."""
        if not isinstance(citizen, Citizen):
            raise TypeError("Environmental effects require a Citizen object.")

        if not citizen.is_alive():
            return 0

        temperature = self.environment.temperature
        if temperature <= 0:
            damage = min(5.0, 1.0 + abs(temperature) / 10.0)
        elif temperature >= 35:
            damage = min(5.0, 1.0 + (temperature - 35) / 10.0)
        else:
            return 0

        sheltered = any(
            building.is_active() and building.has_occupant(citizen)
            for building in self.buildings
        )
        if sheltered:
            damage *= 0.25

        citizen.change_health(-damage)
        if citizen.health <= 0:
            citizen.die()
        return damage

    # Step 16 / Step 72: Advance world time, environment, and resources.
    def advance_tick(self):
        self.market_observations.advance_tick()
        self.current_tick += 1
        self.environment.advance_tick()
        self.regenerate_resources()

    # Step 17: Display basic world information
    def describe(self):
        print(f"World size: {self.width} x {self.height}")
        print(f"World tick: {self.current_tick}")
        print(f"Citizens: {len(self.citizens)}")
        print(f"Buildings: {len(self.buildings)}")
        print(f"Vehicles: {len(self.transportation.get_vehicles())}")
        print(f"Season: {self.environment.season}")
        print(f"Weather: {self.environment.weather}")
        print(f"Temperature: {self.environment.temperature}")
        print(f"Resources: {self.resources}")


if __name__ == "__main__":
    world = WorldState()
    world.describe()
    world.advance_tick()
    world.describe()
