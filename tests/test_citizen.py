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


# Step 6: Run the tests
if __name__ == "__main__":
    unittest.main()