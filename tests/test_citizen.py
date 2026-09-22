# Step 1: Import the unittest framework
import unittest

# Step 2: Import the Citizen class
from src.gaia.agents.citizen import Citizen


# Step 3: Define the Citizen test class
class TestCitizen(unittest.TestCase):

    # Step 4: Test citizen identity
    def test_citizen_identity(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.citizen_id, "CIT-001")
        self.assertEqual(citizen.name, "Alex")

    # Step 5: Test citizen age
    def test_citizen_age(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.age, 0)

    # Step 6: Test citizen location
    def test_citizen_location(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.location, (0, 0))

    # Step 7: Test default values
    def test_default_values(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.citizen_id, "CIT-001")
        self.assertEqual(citizen.name, "Alex")
        self.assertEqual(citizen.age, 0)
        self.assertEqual(citizen.location, (0, 0))
        self.assertEqual(citizen.lifecycle_state, "alive")

    # Step 8: Test multiple citizens
    def test_multiple_citizens(self):
        citizen_one = Citizen("CIT-001", "Alex")
        citizen_two = Citizen("CIT-002", "Jordan")

        self.assertNotEqual(
            citizen_one.citizen_id,
            citizen_two.citizen_id
        )

        self.assertNotEqual(
            citizen_one.name,
            citizen_two.name
        )

    # Step 9: Test initial lifecycle state
    def test_initial_lifecycle_state(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(
            citizen.lifecycle_state,
            "alive"
        )

    # Step 10: Test initial history
    def test_initial_history(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.history, ["Citizen created."])

    # Step 11: Test recording history
    def test_record_history(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.record_history("Citizen was born.")

        self.assertEqual(
            citizen.history, ["Citizen created.", "Citizen was born."]
        )

    # Step 12: Test citizen death
    def test_citizen_death(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.die()

        self.assertEqual(
            citizen.lifecycle_state, "dead"
        )

    # Step 13: Test death is recorded
    def test_death_is_recorded(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.die()

        self.assertEqual(
            citizen.history[-1],
            "Citizen died."
        )

    # Step 14: Test citizen cannot die twice
    def test_citizen_death_twice(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.die()
        citizen.die()

        self.assertEqual(
            citizen.lifecycle_state, "dead"
        )

        self.assertEqual(
            citizen.history.count("Citizen died."),
            1
        )

    # Step 15: Test citizen is alive
    def test_is_alive(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertTrue(citizen.is_alive())

    # Step 16: Test citizen is no longer alive after death
    def test_is_not_alive_after_death(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.die()

        self.assertFalse(citizen.is_alive())

    # Step 17: Test initial needs
    def test_initial_needs(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(
            citizen.needs,
            {
                "food": 100,
                "water": 100,
                "shelter": 100,
                "energy": 100,
                "hunger": 0.0
            }
        )

    # Step 18: Test changing a need
    def test_change_need(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_need("food", -25)

        self.assertEqual(
            citizen.get_need("food"),
            75
        )

    # Step 19: Test getting a need
    def test_get_need(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(
            citizen.get_need("water"),
            100
        )

    # Step 20: Test need lower limit
    def test_need_lower_limit(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_need("food", -150)

        self.assertEqual(
            citizen.get_need("food"),
            0
        )

    # Step 21: Test need upper limit
    def test_need_upper_limit(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_need("food", 150)

        self.assertEqual(
            citizen.get_need("food"),
            100
        )

    # Step 22: Test invalid need
    def test_invalid_need(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.change_need("invalid", 10)

    # Step 23: Test initial personality
    def test_initial_personality(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(
            citizen.personality,
            {
                "sociability": 50,
                "curiosity": 50,
                "ambition": 50,
                "cooperation": 50,
                "risk_tolerance": 50
            }
        )

    # Step 24: Test changing personality
    def test_change_personality(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_personality("curiosity", 20)

        self.assertEqual(
            citizen.get_personality("curiosity"),
            70
        )

    # Step 25: Test personality lower limit
    def test_personality_lower_limit(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_personality("curiosity", -150)

        self.assertEqual(
            citizen.get_personality("curiosity"),
            0
        )

    # Step 26: Test personality upper limit
    def test_personality_upper_limit(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_personality("curiosity", 150)

        self.assertEqual(
            citizen.get_personality("curiosity"),
            100
        )

    # Step 27: Test invalid personality
    def test_invalid_personality(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.change_personality("invalid", 10)

    # Step 28: Test citizens start with no goals
    def test_initial_goals(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.goals, [])

    # Step 29: Test adding a goal
    def test_add_goal(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_goal("Find employment", priority=75)

        self.assertEqual(len(citizen.goals), 1)
        self.assertEqual(
            citizen.goals[0]["description"],
            "Find employment"
        )
        self.assertEqual(
            citizen.goals[0]["priority"],
            75
        )
        self.assertEqual(
            citizen.goals[0]["status"],
            "active"
        )

    # Step 30: Test adding multiple goals
    def test_multiple_goals(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_goal("Find employment", priority=75)
        citizen.add_goal("Meet new people", priority=40)

        self.assertEqual(len(citizen.goals), 2)

    # Step 31: Test completing a goal
    def test_complete_goal(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_goal("Find employment", priority=75)
        citizen.complete_goal(0)

        self.assertEqual(
            citizen.goals[0]["status"],
            "completed"
        )

    # Step 32: Test abandoning a goal
    def test_abandon_goal(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_goal("Find employment", priority=75)
        citizen.abandon_goal(0)

        self.assertEqual(
            citizen.goals[0]["status"],
            "abandoned"
        )

    # Step 33: Test empty goal descriptions
    def test_empty_goal(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.add_goal("")

    # Step 34: Test invalid goal priority
    def test_invalid_goal_priority(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.add_goal(
                "Find employment",
                priority=150
            )

    # Step 35: Test invalid goal index
    def test_invalid_goal_index(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(IndexError):
            citizen.complete_goal(0)

    # Step 36: Test initial skills
    def test_initial_skills(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(
            citizen.skills,
            {}
        )

    # Step 37: Test changing a skill
    def test_change_skill(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_skill("gathering", 25)

        self.assertEqual(
            citizen.get_skill("gathering"),
            25
        )

    # Step 38: Test increasing an existing skill
    def test_increase_skill(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_skill("gathering", 25)
        citizen.change_skill("gathering", 15)

        self.assertEqual(
            citizen.get_skill("gathering"),
            40
        )

    # Step 39: Test skill lower limit
    def test_skill_lower_limit(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_skill("gathering", -25)

        self.assertEqual(
            citizen.get_skill("gathering"),
            0
        )

    # Step 40: Test skill upper limit
    def test_skill_upper_limit(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_skill("gathering", 150)

        self.assertEqual(
            citizen.get_skill("gathering"),
            100
        )

    # Step 41: Test empty skill name
    def test_empty_skill(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.change_skill("", 25)

    # Step 42: Test initial knowledge
    def test_initial_knowledge(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(
            citizen.knowledge,
            []
        )

    # Step 43: Test adding knowledge
    def test_add_knowledge(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_knowledge("Basic farming")

        self.assertTrue(
            citizen.has_knowledge("Basic farming")
        )

    # Step 44: Test duplicate knowledge
    def test_duplicate_knowledge(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_knowledge("Basic farming")
        citizen.add_knowledge("Basic farming")

        self.assertEqual(
            citizen.knowledge.count("Basic farming"),
            1
        )

    # Step 45: Test empty knowledge
    def test_empty_knowledge(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.add_knowledge("")



    # Step 46: Test initial inventory
    def test_initial_inventory(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(
            citizen.inventory,
            {}
        )

    # Step 47: Test adding an item
    def test_add_item(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_item("wood", 5)

        self.assertEqual(
            citizen.inventory["wood"],
            5
        )

    # Step 48: Test adding more of an existing item
    def test_add_existing_item(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_item("wood", 5)
        citizen.add_item("wood", 3)

        self.assertEqual(
            citizen.get_item_quantity("wood"),
            8
        )

    # Step 49: Test removing an item
    def test_remove_item(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_item("wood", 5)
        citizen.remove_item("wood", 2)

        self.assertEqual(
            citizen.get_item_quantity("wood"),
            3
        )

    # Step 50: Test removing an item completely
    def test_remove_item_completely(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_item("wood", 5)
        citizen.remove_item("wood", 5)

        self.assertFalse(
            citizen.has_item("wood")
        )

        self.assertNotIn(
            "wood",
            citizen.inventory
        )

    # Step 51: Test getting an item quantity
    def test_get_item_quantity(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_item("food", 10)

        self.assertEqual(
            citizen.get_item_quantity("food"),
            10
        )

        self.assertEqual(
            citizen.get_item_quantity("water"),
            0
        )

    # Step 52: Test empty item name
    def test_empty_item(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.add_item("", 5)

    # Step 53: Test removing more items than owned
    def test_remove_too_many_items(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_item("wood", 5)

        with self.assertRaises(ValueError):
            citizen.remove_item("wood", 6)




    # Step 54: Test initial money
    def test_initial_money(self):
        citizen = Citizen("CIT-001", "Alex")
        self.assertEqual(citizen.get_money(), 0)

    # Step 55: Test adding money
    def test_add_money(self):
        citizen = Citizen("CIT-001", "Alex")
        citizen.change_money(100)
        self.assertEqual(citizen.get_money(), 100)

    # Step 56: Test spending money
    def test_spend_money(self):
        citizen = Citizen("CIT-001", "Alex")
        citizen.change_money(100)
        citizen.change_money(-25)
        self.assertEqual(citizen.get_money(), 75)

    # Step 57: Test preventing negative money
    def test_negative_money(self):
        citizen = Citizen("CIT-001", "Alex")
        with self.assertRaises(ValueError):
            citizen.change_money(-1)
    # Step 59: Test initial memories
    def test_initial_memories(self):
        citizen = Citizen("CIT-001", "Alex")
        self.assertEqual(citizen.memories, [])

    # Step 60: Test adding a memory
    def test_add_memory(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_memory("Met another citizen.", 10)

        self.assertEqual(
            citizen.memories,
            [{"event": "Met another citizen.", "tick": 10}]
        )

    # Step 61: Test invalid memory input
    def test_invalid_memory(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.add_memory("", 10)

        with self.assertRaises(ValueError):
            citizen.add_memory("Met another citizen.", -1)

    # Step 62: Test initial health
    def test_initial_health(self):
        citizen = Citizen("CIT-001", "Alex")
        self.assertEqual(citizen.get_health(), 100)

    # Step 63: Test changing health
    def test_change_health(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_health(-25)

        self.assertEqual(citizen.get_health(), 75)

    # Step 64: Test health lower limit
    def test_health_lower_limit(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_health(-150)

        self.assertEqual(citizen.get_health(), 0)

    # Step 65: Test health upper limit
    def test_health_upper_limit(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.change_health(50)

        self.assertEqual(citizen.get_health(), 100)
    # Step 66: Test initial occupation
    def test_initial_occupation(self):
        citizen = Citizen("CIT-001", "Alex")
        self.assertIsNone(citizen.get_occupation())

    # Step 67: Test setting an occupation
    def test_set_occupation(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.set_occupation("Farmer")

        self.assertEqual(citizen.get_occupation(), "Farmer")

    # Step 68: Test changing an occupation
    def test_change_occupation(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.set_occupation("Farmer")
        citizen.set_occupation("Engineer")

        self.assertEqual(citizen.get_occupation(), "Engineer")

    # Step 69: Test clearing an occupation
    def test_clear_occupation(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.set_occupation("Farmer")
        citizen.set_occupation(None)

        self.assertIsNone(citizen.get_occupation())

    # Step 70: Test empty occupation
    def test_empty_occupation(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.set_occupation("")
    # Step 76: Test duplicate relationship
    def test_duplicate_relationship(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_relationship("CIT-002", "friend")

        with self.assertRaises(ValueError):
            citizen.add_relationship("CIT-002", "family")

    # Step 77: Test updating a relationship
    def test_update_relationship(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_relationship("CIT-002", "friend")
        citizen.update_relationship("CIT-002", "family")

        relationship = citizen.get_relationship("CIT-002")

        self.assertEqual(relationship["type"], "family")

    # Step 78: Test updating nonexistent relationship
    def test_update_nonexistent_relationship(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.update_relationship("CIT-002", "friend")

    # Step 79: Test removing a relationship
    def test_remove_relationship(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_relationship("CIT-002", "friend")
        citizen.remove_relationship("CIT-002")

        self.assertFalse(citizen.has_relationship("CIT-002"))

    # Step 80: Test removing nonexistent relationship
    def test_remove_nonexistent_relationship(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.remove_relationship("CIT-002")

    # Step 81: Test invalid relationship management
    def test_invalid_relationship_management(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.update_relationship("", "friend")

        with self.assertRaises(ValueError):
            citizen.update_relationship("CIT-002", "")

        with self.assertRaises(ValueError):
            citizen.remove_relationship("")


    # Step 71: Test initial relationships
    def test_initial_relationships(self):
        citizen = Citizen("CIT-001", "Alex")

        self.assertEqual(citizen.relationships, [])

    # Step 72: Test adding a relationship
    def test_add_relationship(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_relationship("CIT-002", "friend")

        self.assertEqual(len(citizen.relationships), 1)
        self.assertEqual(
            citizen.relationships[0]["citizen_id"],
            "CIT-002"
        )
        self.assertEqual(
            citizen.relationships[0]["type"],
            "friend"
        )

    # Step 73: Test retrieving a relationship
    def test_get_relationship(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_relationship("CIT-002", "friend")

        relationship = citizen.get_relationship("CIT-002")

        self.assertEqual(
            relationship["citizen_id"],
            "CIT-002"
        )
        self.assertEqual(
            relationship["type"],
            "friend"
        )

    # Step 74: Test checking a relationship
    def test_has_relationship(self):
        citizen = Citizen("CIT-001", "Alex")

        citizen.add_relationship("CIT-002", "friend")

        self.assertTrue(
            citizen.has_relationship("CIT-002")
        )
        self.assertFalse(
            citizen.has_relationship("CIT-003")
        )

    # Step 75: Test invalid relationship
    def test_invalid_relationship(self):
        citizen = Citizen("CIT-001", "Alex")

        with self.assertRaises(ValueError):
            citizen.add_relationship("", "friend")

        with self.assertRaises(ValueError):
            citizen.add_relationship("CIT-002", "")
# Step 58: Run the tests
if __name__ == "__main__":
    unittest.main()




