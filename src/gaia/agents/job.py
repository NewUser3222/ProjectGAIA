# Step 1: Define the Job configuration
class Job:
    """Configuration for a citizen job."""

    def __init__(
        self,
        job_id,
        name,
        required_skills=None,
        production=None,
        wage=0.0,
        energy_cost=0.0,
    ):
        if not job_id:
            raise ValueError("Job ID cannot be empty.")

        if not name:
            raise ValueError("Job name cannot be empty.")

        if wage < 0:
            raise ValueError("Wage cannot be negative.")

        if energy_cost < 0:
            raise ValueError("Energy cost cannot be negative.")

        self.job_id = job_id
        self.name = name
        self.required_skills = dict(required_skills or {})
        self.production = dict(production or {})
        self.wage = float(wage)
        self.energy_cost = float(energy_cost)
        self.active = True

    # Step 2: Deactivate this job
    def deactivate(self):
        self.active = False

    # Step 3: Activate this job
    def activate(self):
        self.active = True

    # Step 4: Determine whether a citizen meets the job skill requirements
    def is_citizen_eligible(self, citizen):
        if citizen is None or not citizen.is_alive():
            return False

        for skill_name, required_level in self.required_skills.items():
            if citizen.get_skill(skill_name) < required_level:
                return False

        return True
