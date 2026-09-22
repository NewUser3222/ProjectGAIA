from src.gaia.agents.decision import DecisionEngine
from src.gaia.agents.social import SocialInteraction
from src.gaia.simulation.world import WorldState


class Simulation:
    """Core simulation orchestrator managing world ticks, citizens, and environmental loop."""

    def __init__(self):
        self.tick = 0
        self.is_running = False
        self.citizens = []
        self.world = WorldState()
        self.decision_engine = DecisionEngine()

    def add_citizen(self, citizen):
        """Adds a citizen to the simulation and its world state."""
        if citizen and citizen not in self.citizens:
            self.citizens.append(citizen)
            self.world.add_citizen(citizen)

    def start(self):
        """Starts the simulation process."""
        self.is_running = True
        print("GAIA Simulation started.")

    def stop(self):
        """Stops the simulation process."""
        self.is_running = False
        print("GAIA Simulation stopped.")

    def step(self):
        """Advances one simulation tick across world and citizen state."""
        if not self.is_running:
            return

        self.tick += 1
        print(f"Simulation tick: {self.tick}")

        # Step 36: Advance shared world state once per simulation tick.
        self.world.advance_tick()

        world_context = {
            "tick": self.tick,
            "world": self.world
        }

        # Step 36: Evaluate individual needs and actions for each citizen.
        for citizen in self.citizens:
            if not citizen.is_alive():
                continue

            citizen.update_needs()

            action = self.decision_engine.select_best_action(citizen)
            if action:
                self.decision_engine.execute_action(
                    citizen,
                    action,
                    world_context=world_context
                )

        # Trigger social interactions between citizens when multiple exist.
        if len(self.citizens) >= 2:
            for i in range(len(self.citizens) - 1):
                c1 = self.citizens[i]
                c2 = self.citizens[i + 1]

                interaction = SocialInteraction("talk", c1, c2)
                interaction.execute(current_tick=self.tick)
