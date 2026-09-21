import unittest
from src.gaia.agents.citizen import Citizen

class TestAgingAndLifeStages(unittest.TestCase):

    def test_initial_life_stages(self):
        child = Citizen("CIT-01", "Leo", age=8)
        young = Citizen("CIT-02", "Maya", age=20)
        adult = Citizen("CIT-03", "John", age=40)
        elder = Citizen("CIT-04", "Elena", age=70)

        self.assertEqual(child.life_stage, "Child")
        self.assertEqual(young.life_stage, "Young Adult")
        self.assertEqual(adult.life_stage, "Adult")
        self.assertEqual(elder.life_stage, "Elder")

    def test_aging_transition(self):
        child = Citizen("CIT-01", "Leo", age=12)
        self.assertEqual(child.life_stage, "Child")
        
        child.age_up(1)
        self.assertEqual(child.age, 13)
        self.assertEqual(child.life_stage, "Young Adult")
        self.assertEqual(child.speed, 1.2)

    def test_energy_decay_modifiers(self):
        elder = Citizen("CIT-04", "Elena", age=70)
        initial_energy = elder.energy
        elder.update_vitals(hunger_inc=0.0, energy_dec=10.0)
        
        # Elder decay rate is 1.3, so energy loss = 10.0 * 1.3 = 13.0
        self.assertAlmostEqual(elder.energy, initial_energy - 13.0)

if __name__ == "__main__":
    unittest.main()
