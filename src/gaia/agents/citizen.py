# Step 1: Define the Citizen lifecycle states
ALIVE = "alive"
DEAD = "dead"


# Step 2: Define the Citizen entity
class Citizen:
    def __init__(self, citizen_id, name, age=0, location=(0, 0)):
        self.citizen_id = citizen_id
        self.name = name
        self.age = age
        self.location = location
        self.lifecycle_state = ALIVE
        self.history = []

        # Step 3: Define the citizen's basic needs
        self.needs = {
            "food": 100,
            "water": 100,
            "shelter": 100,
            "energy": 100,
            "hunger": 0.0
        }

        # Step 4: Define the citizen's health
        self.health = 100

        # Step 5: Define the citizen's personality
        self.personality = {
            "sociability": 50,
            "curiosity": 50,
            "ambition": 50,
            "cooperation": 50,
            "risk_tolerance": 50
        }

        # Step 5: Define the citizen's goals
        self.goals = []

        # Step 6: Define the citizen's skills
        self.skills = {}

        # Step 7: Define the citizen's knowledge
        self.knowledge = []

        # Step 8: Define the citizen's occupation
        self.occupation = None

        # Step 51: Define the citizen's active job
        self.job = None

        # Step 22: Store citizen relationships
        self.relationships = []
        # Step 8: Define the citizen's memories
        self.memories = []

        # Step 8: Define the citizen's inventory
        self.inventory = {}

        # Step 9: Define the citizen's money
        self.money = 0

        # Step 30: Define biological aging state
        self.life_stage = self._calculate_life_stage(age)
        self.energy = 100.0
        self.hunger = 0.0
        self.speed = 1.0
        self.energy_decay_rate = 1.0
        self._apply_life_stage_modifiers()

        self.record_history("Citizen created.")

    # Step 31: Determine life stage from age
    def _calculate_life_stage(self, age):
        if age < 13:
            return "Child"
        elif age < 25:
            return "Young Adult"
        elif age < 60:
            return "Adult"
        else:
            return "Elder"

    # Step 32: Apply physical effects of the current life stage
    def _apply_life_stage_modifiers(self):
        if self.life_stage == "Child":
            self.speed = 0.8
            self.energy_decay_rate = 1.2
        elif self.life_stage == "Young Adult":
            self.speed = 1.2
            self.energy_decay_rate = 0.9
        elif self.life_stage == "Adult":
            self.speed = 1.0
            self.energy_decay_rate = 1.0
        elif self.life_stage == "Elder":
            self.speed = 0.7
            self.energy_decay_rate = 1.3

    # Step 33: Advance the citizen's age
    def age_up(self, years=1):
        if not self.is_alive():
            return

        self.age += years
        old_stage = self.life_stage
        self.life_stage = self._calculate_life_stage(self.age)

        if old_stage != self.life_stage:
            self._apply_life_stage_modifiers()

    # Step 34: Update biological vitals affected by aging
    def update_vitals(self, hunger_inc=1.0, energy_dec=0.5):
        if not self.is_alive():
            return

        adjusted_energy_dec = energy_dec * self.energy_decay_rate
        self.hunger = min(100.0, self.hunger + hunger_inc)
        self.energy = max(0.0, self.energy - adjusted_energy_dec)

        if self.hunger >= 100.0 or self.energy <= 0.0:
            self.change_health(-5.0)

    # Step 37: Centrally process all citizen needs for one simulation tick
    def update_needs(self):
        """Advance citizen needs once and apply survival consequences."""
        if not self.is_alive():
            return

        # Biological vitals are updated exactly once through this method.
        self.update_vitals()

        # World-relevant resource needs decline predictably with time.
        self.change_need("food", -1.0)
        self.change_need("water", -1.0)
        self.change_need("shelter", -0.25)

        # Hunger and energy remain synchronized with their biological values.
        self.needs["hunger"] = self.hunger
        self.needs["energy"] = self.energy

        # Step 38: Apply health consequences from sustained critical needs.
        self.apply_survival_consequences()

    # Step 38: Apply health consequences from critical unmet needs
    def apply_survival_consequences(self):
        """Apply predictable health consequences for severe unmet needs."""
        if not self.is_alive():
            return

        critical_damage = 0.0

        if self.hunger >= 90.0:
            critical_damage += 2.0

        if self.energy <= 10.0:
            critical_damage += 2.0

        if self.needs.get("food", 100) <= 10:
            critical_damage += 1.0

        if self.needs.get("water", 100) <= 10:
            critical_damage += 1.0

        if self.needs.get("shelter", 100) <= 10:
            critical_damage += 1.0

        if critical_damage > 0:
            self.change_health(-critical_damage)

            if self.health <= 0:
                self.die()

    # Step 35: Change a citizen's health level
    def change_health(self, amount):
        new_value = self.health + amount
        self.health = max(0, min(100, new_value))

    # Step 11: Get a citizen's current health level
    def get_health(self):
        return self.health
    # Step 12: Set the citizen's occupation
    def set_occupation(self, occupation):
        if occupation == "":
            raise ValueError("Occupation cannot be empty.")

        self.occupation = occupation

    # Step 13: Get the citizen's current occupation
    # Step 51: Assign a configured job to this citizen
    def set_job(self, job):
        from src.gaia.agents.job import Job

        if not isinstance(job, Job):
            raise ValueError("Job must be a Job instance.")

        if not self.is_alive():
            raise ValueError("Dead citizens cannot be assigned active jobs.")

        if not job.active:
            raise ValueError("Cannot assign an inactive job.")

        if not job.is_citizen_eligible(self):
            raise ValueError("Citizen does not meet the job requirements.")

        self.job = job
        self.occupation = job.name

    # Step 51: Get the citizen's active job
    def get_job(self):
        return self.job

    # Step 51: Check whether the citizen has an active job
    def has_active_job(self):
        return (
            self.is_alive()
            and self.job is not None
            and self.job.active
        )

    # Step 51: Check whether the citizen can perform a job
    def can_perform_job(self, job):
        from src.gaia.agents.job import Job

        if not isinstance(job, Job):
            return False

        return job.active and job.is_citizen_eligible(self)

    # Step 51: Clear the citizen's active job
    def clear_job(self):
        self.job = None
        self.occupation = None
    def get_occupation(self):
        return self.occupation
    # Step 10: Change a citizen's need level
    def change_need(self, need_name, amount):
        if need_name not in self.needs:
            raise ValueError(f"Unknown need: {need_name}")

        new_value = self.needs[need_name] + amount
        self.needs[need_name] = max(0, min(100, new_value))

    # Step 11: Get a citizen's current need level
    def get_need(self, need_name):
        if need_name not in self.needs:
            raise ValueError(f"Unknown need: {need_name}")

        return self.needs[need_name]

    # Step 12: Change a citizen's personality trait
    def change_personality(self, trait_name, amount):
        if trait_name not in self.personality:
            raise ValueError(f"Unknown personality trait: {trait_name}")

        new_value = self.personality[trait_name] + amount
        self.personality[trait_name] = max(0, min(100, new_value))

    # Step 13: Get a citizen's personality trait
    def get_personality(self, trait_name):
        if trait_name not in self.personality:
            raise ValueError(f"Unknown personality trait: {trait_name}")

        return self.personality[trait_name]

    # Step 14: Add a goal to the citizen
    def add_goal(self, description, priority=50):
        if not description:
            raise ValueError("Goal description cannot be empty.")

        if priority < 0 or priority > 100:
            raise ValueError("Goal priority must be between 0 and 100.")

        self.goals.append({
            "description": description,
            "priority": priority,
            "status": "active"
        })

    # Step 15: Complete a citizen goal
    def complete_goal(self, goal_index):
        if goal_index < 0 or goal_index >= len(self.goals):
            raise IndexError("Invalid goal index.")

        self.goals[goal_index]["status"] = "completed"

    # Step 16: Abandon a citizen goal
    def abandon_goal(self, goal_index):
        if goal_index < 0 or goal_index >= len(self.goals):
            raise IndexError("Invalid goal index.")

        self.goals[goal_index]["status"] = "abandoned"

    # Step 17: Add or update a citizen skill
    def change_skill(self, skill_name, amount):
        if not skill_name:
            raise ValueError("Skill name cannot be empty.")

        current_level = self.skills.get(skill_name, 0)
        new_level = current_level + amount

        self.skills[skill_name] = max(0, min(100, new_level))

    # Step 18: Get a citizen's skill level
    def get_skill(self, skill_name):
        if not skill_name:
            raise ValueError("Skill name cannot be empty.")

        return self.skills.get(skill_name, 0)

    # Step 19: Add knowledge to the citizen
    def add_knowledge(self, knowledge):
        if not knowledge:
            raise ValueError("Knowledge cannot be empty.")

        if knowledge not in self.knowledge:
            self.knowledge.append(knowledge)

    # Step 20: Check whether the citizen has specific knowledge
    def has_knowledge(self, knowledge):
        if not knowledge:
            raise ValueError("Knowledge cannot be empty.")

        return knowledge in self.knowledge

    # Step 21: End the citizen's life
    def die(self):
        if self.lifecycle_state == DEAD:
            return

        self.lifecycle_state = DEAD
        self.record_history("Citizen died.")

    # Step 22: Check whether the citizen is alive
    def is_alive(self):
        return self.lifecycle_state == ALIVE

        # Step 23: Add items to the citizen's inventory
    def add_item(self, item, quantity):
        if not item:
            raise ValueError("Item name cannot be empty.")

        if quantity < 0:
            raise ValueError("Quantity cannot be negative.")

        self.inventory[item] = self.inventory.get(item, 0) + quantity

    # Step 24: Remove items from the citizen's inventory
    def remove_item(self, item, quantity):
        if not item:
            raise ValueError("Item name cannot be empty.")

        if quantity < 0:
            raise ValueError("Quantity cannot be negative.")

        current_quantity = self.inventory.get(item, 0)

        if quantity > current_quantity:
            raise ValueError("Not enough items in inventory.")

        new_quantity = current_quantity - quantity

        if new_quantity == 0:
            self.inventory.pop(item, None)
        else:
            self.inventory[item] = new_quantity

    # Step 25: Get an item's quantity
    def get_item_quantity(self, item):
        if not item:
            raise ValueError("Item name cannot be empty.")

        return self.inventory.get(item, 0)

    # Step 26: Check whether the citizen has an item
    def has_item(self, item):
        if not item:
            raise ValueError("Item name cannot be empty.")

        return self.get_item_quantity(item) > 0

    # Step 27: Change the citizen's money
    def change_money(self, amount):
        new_amount = self.money + amount

        if new_amount < 0:
            raise ValueError("Citizen cannot have negative money.")

        self.money = new_amount

    # Step 28: Get the citizen's current money
    def get_money(self):
        return self.money

    # Step 46: Calculate the economic value of one resource quantity
    def get_resource_value(self, resource_name, quantity=1):
        from src.gaia.economy import calculate_resource_value

        return calculate_resource_value(resource_name, quantity)

    # Step 46: Calculate the total configured economic value of inventory
    def get_inventory_value(self):
        from src.gaia.economy import calculate_inventory_value

        return calculate_inventory_value(self.inventory)


    # Step 29: Record an event in the citizen's history
    # Step 29: Add a memory to the citizen
    def add_memory(self, event, tick):
        if not event:
            raise ValueError("Memory event cannot be empty.")

        if tick < 0:
            raise ValueError("Memory tick cannot be negative.")

        self.memories.append({
            "event": event,
            "tick": tick
        })
    def record_history(self, event):
        if not event:
            raise ValueError("History event cannot be empty.")

        self.history.append(event)

# Step 23: Add a relationship with another citizen
    def add_relationship(self, citizen_id, relationship_type):
        if not citizen_id:
            raise ValueError("Citizen ID cannot be empty.")

        if not relationship_type:
            raise ValueError("Relationship type cannot be empty.")

        if self.has_relationship(citizen_id):
            raise ValueError("Relationship already exists.")

        self.relationships.append({
            "citizen_id": citizen_id,
            "type": relationship_type
        })

    # Step 24: Get a relationship with another citizen
    def get_relationship(self, citizen_id):
        for relationship in self.relationships:
            if relationship["citizen_id"] == citizen_id:
                return relationship

        return None

    # Step 25: Check whether a relationship exists
    def has_relationship(self, citizen_id):
        return self.get_relationship(citizen_id) is not None

    # Step 26: Update a relationship
    def update_relationship(self, citizen_id, relationship_type):
        if not citizen_id:
            raise ValueError("Citizen ID cannot be empty.")

        if not relationship_type:
            raise ValueError("Relationship type cannot be empty.")

        relationship = self.get_relationship(citizen_id)

        if relationship is None:
            raise ValueError("Relationship does not exist.")

        relationship["type"] = relationship_type

    # Step 27: Remove a relationship
    def remove_relationship(self, citizen_id):
        if not citizen_id:
            raise ValueError("Citizen ID cannot be empty.")

        relationship = self.get_relationship(citizen_id)

        if relationship is None:
            raise ValueError("Relationship does not exist.")

        self.relationships.remove(relationship)
