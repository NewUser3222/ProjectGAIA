import unittest
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.social import SocialInteraction

class TestSocialInteraction(unittest.TestCase):

    def setUp(self):
        self.alice = Citizen("CIT-001", "Alice")
        self.bob = Citizen("CIT-002", "Bob")
        
        if hasattr(self.alice, "add_relationship"):
            self.alice.add_relationship("CIT-002", "Bob")
        if hasattr(self.bob, "add_relationship"):
            self.bob.add_relationship("CIT-001", "Alice")

    def test_validation_self_interaction(self):
        with self.assertRaises(ValueError):
            SocialInteraction("talk", self.alice, self.alice)

    def test_validation_invalid_type(self):
        with self.assertRaises(ValueError):
            SocialInteraction("hug", self.alice, self.bob)

    def test_talk_interaction(self):
        interaction = SocialInteraction("talk", self.alice, self.bob)
        res = interaction.execute(current_tick=10)

        self.assertTrue(res["success"])
        self.assertTrue(len(self.alice.memories) > 0)
        self.assertTrue(len(self.bob.memories) > 0)

    def test_share_interaction(self):
        interaction = SocialInteraction("share", self.alice, self.bob)
        res = interaction.execute(current_tick=12)

        self.assertTrue(res["success"])

    def test_dispute_interaction(self):
        interaction = SocialInteraction("dispute", self.alice, self.bob)
        res = interaction.execute(current_tick=15)

        self.assertTrue(res["success"])

if __name__ == "__main__":
    unittest.main()
