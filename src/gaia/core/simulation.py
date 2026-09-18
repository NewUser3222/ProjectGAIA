from src.gaia.agents.decision import DecisionEngine
from src.gaia.agents.social import SocialInteraction

class Simulation:
    """Core simulation orchestrator managing world ticks, citizens, and environmental loop."""
    
    def __init__(self):
        self.tick = 0
        self.is_running = False
        self.citizens = []
        self.decision_engine = DecisionEngine()

    def add_citizen(self, citizen):
        """Adds a citizen to the simulation world."""
        if citizen and citizen not in self.citizens:
            self.citizens.append(citizen)

    def start(self):
        """Starts the simulation process."""
        self.is_running = True
        print("GAIA Simulation started.")

    def stop(self):
        """Stops the simulation process."""
        self.is_running = False
        print("GAIA Simulation stopped.")

    def step(self):
        """Advances the simulation by one tick, executing agent needs, decisions, and social behavior."""
        if not self.is_running:
            return

        self.tick += 1
        print(f"Simulation tick: {self.tick}")

        world_context = {"tick": self.tick}

        # 1. Evaluate individual needs and actions for each citizen
        for citizen in self.citizens:
            if hasattr(citizen, "update_needs"):
                citizen.update_needs()

            action = self.decision_engine.select_best_action(citizen)
            if action:
                self.decision_engine.execute_action(citizen, action, world_context=world_context)

        # 2. Trigger social interactions between citizens when multiple exist
        if len(self.citizens) >= 2:
            for i in range(len(self.citizens) - 1):
                c1 = self.citizens[i]
                c2 = self.citizens[i + 1]
                # Default to friendly conversation tick-based interaction
                interaction = SocialInteraction("talk", c1, c2)
                interaction.execute(current_tick=self.tick)
