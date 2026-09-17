# Step 1: Import the unittest framework
import unittest


# Step 2: Import the Citizen entity and lifecycle states
from src.gaia.agents.citizen import Citizen, ALIVE, DEAD


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

    # Step 9: Test that citizens start alive
    def test_initial_lifecycle_state(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.lifecycle_state, ALIVE)
        self.assertTrue(citizen.is_alive())

    # Step 10: Test that a citizen can die
    def test_citizen_death(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.die()

        self.assertEqual(citizen.lifecycle_state, DEAD)
        self.assertFalse(citizen.is_alive())

    # Step 11: Test initial citizen history
    def test_initial_history(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(len(citizen.history), 1)
        self.assertEqual(citizen.history[0], "Citizen created.")

    # Step 12: Test recording a history event
    def test_record_history(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.record_history("Moved to (10, 15).")

        self.assertEqual(len(citizen.history), 2)
        self.assertEqual(
            citizen.history[1],
            "Moved to (10, 15)."
        )

    # Step 13: Test that death is recorded in history
    def test_death_is_recorded(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.die()

        self.assertEqual(
            citizen.history[-1],
            "Citizen died."
        )

    # Step 14: Test initial citizen needs
    def test_initial_needs(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.needs["food"], 100)
        self.assertEqual(citizen.needs["water"], 100)
        self.assertEqual(citizen.needs["shelter"], 100)
        self.assertEqual(citizen.needs["energy"], 100)

    # Step 15: Test changing a citizen's need
    def test_change_need(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_need("food", -25)

        self.assertEqual(citizen.needs["food"], 75)

    # Step 16: Test that needs cannot exceed 100
    def test_need_upper_limit(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_need("food", 50)

        self.assertEqual(citizen.needs["food"], 100)

    # Step 17: Test that needs cannot fall below 0
    def test_need_lower_limit(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_need("food", -150)

        self.assertEqual(citizen.needs["food"], 0)

    # Step 18: Test retrieving a need
    def test_get_need(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_need("water", -30)

        self.assertEqual(citizen.get_need("water"), 70)

    # Step 19: Test invalid need names
    def test_invalid_need(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.change_need("happiness", -10)

    # Step 20: Test initial personality traits
    def test_initial_personality(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.personality["sociability"], 50)
        self.assertEqual(citizen.personality["curiosity"], 50)
        self.assertEqual(citizen.personality["ambition"], 50)
        self.assertEqual(citizen.personality["cooperation"], 50)
        self.assertEqual(citizen.personality["risk_tolerance"], 50)

    # Step 21: Test changing a personality trait
    def test_change_personality(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_personality("curiosity", 20)

        self.assertEqual(citizen.personality["curiosity"], 70)

    # Step 22: Test that personality traits cannot exceed 100
    def test_personality_upper_limit(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_personality("ambition", 75)

        self.assertEqual(citizen.personality["ambition"], 100)

    # Step 23: Test that personality traits cannot fall below 0
    def test_personality_lower_limit(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_personality("risk_tolerance", -75)

        self.assertEqual(citizen.personality["risk_tolerance"], 0)

    # Step 24: Test retrieving a personality trait
    def test_get_personality(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_personality("sociability", 15)

        self.assertEqual(citizen.get_personality("sociability"), 65)

    # Step 25: Test invalid personality traits
    def test_invalid_personality(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.change_personality("kindness", 10)

    # Step 26: Test that citizens start with no goals
    def test_initial_goals(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.goals, [])

    # Step 27: Test adding a goal
    def test_add_goal(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_goal("Find employment", priority=75)

        self.assertEqual(len(citizen.goals), 1)
        self.assertEqual(
            citizen.goals[0]["description"],
            "Find employment"
        )
        self.assertEqual(citizen.goals[0]["priority"], 75)
        self.assertEqual(citizen.goals[0]["status"], "active")

    # Step 28: Test adding multiple goals
    def test_multiple_goals(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_goal("Find employment", priority=75)
        citizen.add_goal("Meet new people", priority=40)

        self.assertEqual(len(citizen.goals), 2)

    # Step 29: Test completing a goal
    def test_complete_goal(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_goal("Find employment", priority=75)
        citizen.complete_goal(0)

        self.assertEqual(
            citizen.goals[0]["status"],
            "completed"
        )

    # Step 30: Test abandoning a goal
    def test_abandon_goal(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_goal("Find employment", priority=75)
        citizen.abandon_goal(0)

        self.assertEqual(
            citizen.goals[0]["status"],
            "abandoned"
        )

    # Step 31: Test empty goal descriptions
    def test_empty_goal(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.add_goal("")

    # Step 32: Test invalid goal priority
    def test_invalid_goal_priority(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.add_goal("Find employment", priority=150)

    # Step 33: Test invalid goal index
    def test_invalid_goal_index(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(IndexError):
            citizen.complete_goal(0)


# Step 34: Run the tests
if __name__ == "__main__":
    unittest.main()