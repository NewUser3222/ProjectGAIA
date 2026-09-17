# Step 1: Define the Simulation Engine
class SimulationEngine:
    def __init__(self):
        self.tick = 0
        self.running = False

    # Step 2: Start the simulation
    def start(self):
        self.running = True
        print("GAIA Simulation started.")

    # Step 3: Advance simulation time
    def advance_tick(self):
        if not self.running:
            return

        self.tick += 1
        print(f"Simulation tick: {self.tick}")


# Step 4: Run a basic engine test
if __name__ == "__main__":
    engine = SimulationEngine()

    engine.start()

    for _ in range(5):
        engine.advance_tick()