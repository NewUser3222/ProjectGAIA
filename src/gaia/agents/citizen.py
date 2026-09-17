# Step 1: Define the Citizen entity
class Citizen:
    def __init__(self, citizen_id, name):
        self.citizen_id = citizen_id
        self.name = name


# Step 2: Run a basic citizen test
if __name__ == "__main__":
    citizen = Citizen("CIT-001", "Alex")

    print(f"Citizen ID: {citizen.citizen_id}")
    print(f"Citizen name: {citizen.name}")