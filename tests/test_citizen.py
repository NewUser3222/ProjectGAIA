# Step 1: Import the unittest framework
import unittest


# Step 2: Import the Citizen entity
from src.gaia.agents.citizen import Citizen


# Step 3: Define Citizen tests
class TestCitizen(unittest.TestCase):

    # Step 4: Test citizen identity
    def test_citizen_identity(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.citizen_id, "CIT-001")
        self.assertEqual(citizen.name, "Alex")

    # Step 5: Test that different citizens can have different identities
    def test_multiple_citizens(self):
        citizen_one = Citizen("CIT-001", "Alex")
        citizen_two = Citizen("CIT-002", "Jordan")

        self.assertNotEqual(citizen_one.citizen_id, citizen_two.citizen_id)
        self.assertNotEqual(citizen_one.name, citizen_two.name)

    # Step 6: Test citizen age
    def test_citizen_age(self):
        citizen = Citizen("CIT-001", "Alex", age=25)

        self.assertEqual(citizen.age, 25)

    # Step 7: Test citizen location
    def test_citizen_location(self):
        citizen = Citizen("CIT-001", "Alex", location=(10, 15))

        self.assertEqual(citizen.location, (10, 15))

    # Step 8: Test default citizen values
    def test_default_values(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.age, 0)
        self.assertEqual(citizen.location, (0, 0))


# Step 9: Run the tests
if __name__ == "__main__":
    unittest.main()