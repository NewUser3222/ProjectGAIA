# Step 1: Import the World State
from src.gaia.simulation.world import WorldState


# Step 2: Define the Simulation Engine
class SimulationEngine:
    def __init__(self):
        self.tick = 0
        self.running = False
        self.world = WorldState()

    # Step 3: Start the simulation
    def start(self):
        self.running = True
        print("GAIA Simulation started.")

    # Step 4: Advance the simulation
    def advance_tick(self):
        if not self.running:
            return

        self.tick += 1
        self.world.advance_tick()

        print(f"Simulation tick: {self.tick}")
        print(f"World tick: {self.world.current_tick}")


# Step 5: Run a basic engine test
if __name__ == "__main__":
    engine = SimulationEngine()

    engine.start()

    for _ in range(5):
        engine.advance_tick()