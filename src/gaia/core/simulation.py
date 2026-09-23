from src.gaia.agents.decision import DecisionEngine
from src.gaia.agents.social import SocialInteraction
from src.gaia.simulation.world import WorldState


class Simulation:
    """Core simulation orchestrator managing world ticks, citizens, and environmental loop."""

    def __init__(self):
        self.tick = 0
        self.is_running = False
        self.citizens = []
        self.businesses = []
        self.construction_projects = []
        self.world = WorldState()
        self.decision_engine = DecisionEngine()

    # Step 69: Return all known ancestors through persistent parent IDs
    def get_ancestors(self, citizen):
        if citizen is None:
            raise ValueError("Citizen cannot be None.")

        ancestors = []
        visited = set()

        def collect(parent_id):
            if parent_id in visited:
                return

            visited.add(parent_id)

            parent = next(
                (
                    existing
                    for existing in self.citizens
                    if existing.citizen_id == parent_id
                ),
                None
            )

            if parent is None:
                return

            ancestors.append(parent)

            for grandparent_id in parent.get_parents():
                collect(grandparent_id)

        for parent_id in citizen.get_parents():
            collect(parent_id)

        return ancestors
    # Step 68: Create a child through the simulation engine
    def create_child(self, parent_a, parent_b, child_id, name, location=None):
        if parent_a is None or parent_b is None:
            raise ValueError("Two parents are required.")
        if parent_a is parent_b:
            raise ValueError("Two distinct parents are required.")
        if not parent_a.is_alive() or not parent_b.is_alive():
            raise ValueError("Both parents must be alive.")
        if not child_id:
            raise ValueError("Child ID cannot be empty.")
        if any(citizen.citizen_id == child_id for citizen in self.citizens):
            raise ValueError("Citizen ID already exists.")

        from src.gaia.agents.citizen import Citizen

        child_location = location if location is not None else parent_a.location
        child_generation = max(parent_a.generation, parent_b.generation) + 1
        child = Citizen(child_id, name, age=0, location=child_location, generation=child_generation)
        child.record_history("Citizen was born.")

        child.add_parent(parent_a.citizen_id)
        child.add_parent(parent_b.citizen_id)

        parent_a.add_child(child.citizen_id)
        parent_b.add_child(child.citizen_id)

        parent_a.add_relationship(child.citizen_id, "child")
        parent_b.add_relationship(child.citizen_id, "child")
        child.add_relationship(parent_a.citizen_id, "parent")
        child.add_relationship(parent_b.citizen_id, "parent")

        self.add_citizen(child)
        return child

    def add_citizen(self, citizen):
        """Adds a citizen to the simulation and its world state."""
        if citizen and citizen not in self.citizens:
            self.citizens.append(citizen)
            self.world.add_citizen(citizen)

    # Step 60: Add a business to the simulation and world
    def add_business(self, business):
        from src.gaia.business import Business

        if not isinstance(business, Business):
            raise TypeError("Only Business objects can be added to the simulation.")

        if business not in self.businesses:
            self.businesses.append(business)
            self.world.add_business(business)

    # Step 60: Remove a business from the simulation and world
    def remove_business(self, business):
        if business in self.businesses:
            self.businesses.remove(business)

        self.world.remove_business(business)

    # Step 65: Track a construction project in the simulation.
    def add_construction_project(self, project):
        from src.gaia.construction import ConstructionProject

        if not isinstance(project, ConstructionProject):
            raise TypeError(
                "Only ConstructionProject objects can be added to the simulation."
            )

        if project not in self.construction_projects:
            self.construction_projects.append(project)

    # Step 65: Remove a construction project from the simulation.
    def remove_construction_project(self, project):
        if project in self.construction_projects:
            self.construction_projects.remove(project)

    # Step 65: Return tracked construction projects.
    def get_construction_projects(self):
        return list(self.construction_projects)

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

        # Step 60: Remove dead employees before business work processing.
        for business in self.businesses:
            if business.is_active():
                business.remove_dead_employees()

        # Step 65: Remove dead workers from active construction projects.
        for project in self.construction_projects:
            if not project.is_complete():
                project.remove_dead_workers()

        # Step 36: Evaluate individual needs and actions for each citizen.
        for citizen in self.citizens:
            if not citizen.is_alive():
                continue

            # Step 66: Advance the lifecycle once per simulation tick.
            citizen.age_up(1)

            if not citizen.is_alive():
                continue
            citizen.update_needs()

            # Step 44: Decisions must observe the current shared world state.
            action = self.decision_engine.select_best_action(
                citizen,
                world=self.world
            )
            if action:
                # Step 60: Support both business and legacy citizen employers.
                if action.action_id == "work":
                    job = citizen.get_job()
                    employer = citizen.get_employer()

                    if job is not None and job.wage > 0:
                        # Step 60: Business-employed citizens use their registered employer.
                        if employer is not None:
                            if not employer.is_active():
                                continue

                            if not employer.has_employee(citizen):
                                continue

                            if employer.get_employee_job(citizen) is not job:
                                continue

                            if employer.get_money() < job.wage:
                                continue
                        else:
                            # Preserve the legacy citizen-employer economic loop.
                            for potential_employer in self.citizens:
                                if potential_employer is citizen:
                                    continue

                                if not potential_employer.is_alive():
                                    continue

                                if potential_employer.get_money() >= job.wage:
                                    employer = potential_employer
                                    break

                            if employer is None:
                                continue

                        work_context = dict(world_context)
                        work_context["employer"] = employer

                        self.decision_engine.execute_action(
                            citizen,
                            action,
                            world_context=work_context
                        )
                    else:
                        self.decision_engine.execute_action(
                            citizen,
                            action,
                            world_context=world_context
                        )
                else:
                    self.decision_engine.execute_action(
                        citizen,
                        action,
                        world_context=world_context
                    )

        # Step 40: Social interactions only occur between active citizens.
        active_citizens = [
            citizen for citizen in self.citizens
            if citizen.is_alive()
        ]

        if len(active_citizens) >= 2:
            for i in range(len(active_citizens) - 1):
                c1 = active_citizens[i]
                c2 = active_citizens[i + 1]

                interaction = SocialInteraction("talk", c1, c2)
                interaction.execute(current_tick=self.tick)


