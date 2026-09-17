# Step 1: Import the unittest framework
import unittest


# Step 2: Import the Simulation Engine
from src.gaia.simulation.engine import SimulationEngine


# Step 3: Define Simulation Engine tests
class TestSimulationEngine(unittest.TestCase):

    # Step 4: Test the engine's initial state
    def test_initial_state(self):
        engine = SimulationEngine()

        self.assertEqual(engine.tick, 0)
        self.assertFalse(engine.running)

    # Step 5: Test starting the engine
    def test_start(self):
        engine = SimulationEngine()

        engine.start()

        self.assertTrue(engine.running)

    # Step 6: Test engine tick advancement
    def test_advance_tick(self):
        engine = SimulationEngine()

        engine.start()
        engine.advance_tick()

        self.assertEqual(engine.tick, 1)

    # Step 7: Test world tick advancement
    def test_world_tick_advances_with_engine(self):
        engine = SimulationEngine()

        engine.start()
        engine.advance_tick()

        self.assertEqual(engine.world.current_tick, 1)

    # Step 8: Test engine and world tick synchronization
    def test_engine_and_world_ticks_stay_synchronized(self):
        engine = SimulationEngine()

        engine.start()

        for _ in range(5):
            engine.advance_tick()

        self.assertEqual(engine.tick, 5)
        self.assertEqual(engine.world.current_tick, 5)

    # Step 9: Test stopped engine does not advance
    def test_stopped_engine_does_not_advance(self):
        engine = SimulationEngine()

        engine.advance_tick()

        self.assertEqual(engine.tick, 0)
        self.assertEqual(engine.world.current_tick, 0)


# Step 10: Run the tests
if __name__ == "__main__":
    unittest.main()