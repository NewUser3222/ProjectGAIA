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


# Step 3: Mark the citizen as deceased
    def die(self):
        self.lifecycle_state = DEAD


# Step 4: Check whether the citizen is alive
    def is_alive(self):
        return self.lifecycle_state == ALIVE


# Step 5: Run a basic citizen test
if __name__ == "__main__":
    citizen = Citizen(
        "CIT-001",
        "Alex",
        age=25,
        location=(10, 15)
    )

    print(f"Citizen ID: {citizen.citizen_id}")
    print(f"Citizen name: {citizen.name}")
    print(f"Citizen age: {citizen.age}")
    print(f"Citizen location: {citizen.location}")
    print(f"Lifecycle state: {citizen.lifecycle_state}")