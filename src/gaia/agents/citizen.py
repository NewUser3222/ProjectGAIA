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

        # Step 4: Record the citizen's creation
        self.record_history("Citizen created.")

    # Step 5: Record a citizen history event
    def record_history(self, event):
        self.history.append(event)

    # Step 6: Change a citizen's need level
    def change_need(self, need_name, amount):
        if need_name not in self.needs:
            raise ValueError(f"Unknown need: {need_name}")

        new_value = self.needs[need_name] + amount

        self.needs[need_name] = max(0, min(100, new_value))

    # Step 7: Get a citizen's current need level
    def get_need(self, need_name):
        if need_name not in self.needs:
            raise ValueError(f"Unknown need: {need_name}")

        return self.needs[need_name]

    # Step 8: Mark the citizen as deceased
    def die(self):
        self.lifecycle_state = DEAD
        self.record_history("Citizen died.")

    # Step 9: Check whether the citizen is alive
    def is_alive(self):
        return self.lifecycle_state == ALIVE


# Step 10: Run a basic citizen test
if __name__ == "__main__":
    citizen = Citizen(
        "CIT-001",
        "Alex",
        age=25,
        location=(10, 15)
    )

    citizen.record_history("Moved to (10, 15).")

    citizen.change_need("food", -25)

    print(f"Citizen ID: {citizen.citizen_id}")
    print(f"Citizen name: {citizen.name}")
    print(f"Citizen age: {citizen.age}")
    print(f"Citizen location: {citizen.location}")
    print(f"Lifecycle state: {citizen.lifecycle_state}")
    print(f"Needs: {citizen.needs}")
    print(f"Food need: {citizen.get_need('food')}")
    print(f"History: {citizen.history}")