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
            "energy": 100
        }

        # Step 4: Define the citizen's personality
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

        # Step 8: Record the citizen's creation
        self.record_history("Citizen created.")

    # Step 9: Record a citizen history event
    def record_history(self, event):
        self.history.append(event)

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

        if not 0 <= priority <= 100:
            raise ValueError("Goal priority must be between 0 and 100.")

        goal = {
            "description": description,
            "priority": priority,
            "status": "active"
        }

        self.goals.append(goal)

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
        if self.lifecycle_state == "dead":
            return

        self.lifecycle_state = "dead"
        self.record_history("Citizen died.")

    # Step 22: Check whether the citizen is alive
    def is_alive(self):
        return self.lifecycle_state == ALIVE


# Step 23: Run a basic citizen test
if __name__ == "__main__":
    citizen = Citizen(
        "CIT-001",
        "Alex",
        age=25,
        location=(10, 15)
    )

    citizen.record_history("Moved to (10, 15).")

    citizen.change_need("food", -25)

    citizen.change_personality("curiosity", 20)

    citizen.add_goal("Find a place to live", priority=90)
    citizen.add_goal("Learn about the surrounding area", priority=60)

    citizen.change_skill("gathering", 25)
    citizen.change_skill("gathering", 10)

    citizen.add_knowledge("Basic wilderness survival")

    citizen.complete_goal(0)

    print(f"Citizen ID: {citizen.citizen_id}")
    print(f"Citizen name: {citizen.name}")
    print(f"Citizen age: {citizen.age}")
    print(f"Citizen location: {citizen.location}")
    print(f"Lifecycle state: {citizen.lifecycle_state}")
    print(f"Needs: {citizen.needs}")
    print(f"Food need: {citizen.get_need('food')}")
    print(f"Personality: {citizen.personality}")
    print(f"Curiosity: {citizen.get_personality('curiosity')}")
    print(f"Goals: {citizen.goals}")
    print(f"Skills: {citizen.skills}")
    print(f"Gathering skill: {citizen.get_skill('gathering')}")
    print(f"Knowledge: {citizen.knowledge}")
    print(
        f"Knows wilderness survival: "
        f"{citizen.has_knowledge('Basic wilderness survival')}"
    )
    print(f"History: {citizen.history}")