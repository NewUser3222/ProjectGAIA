# Step 1: Define the Citizen entity
class Citizen:
    def __init__(self, citizen_id, name, age=0, location=(0, 0)):
        self.citizen_id = citizen_id
        self.name = name
        self.age = age
        self.location = location


# Step 2: Run a basic citizen test
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