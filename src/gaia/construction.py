from src.gaia.building import Building
from src.gaia.agents.job import Job

# Step 62: Construction materials and building costs

class BuildingDefinition:
    """Configuration for the materials and cost required to construct a building."""

    def __init__(
        self,
        building_type,
        required_materials=None,
        construction_cost=0.0,
    ):
        if not building_type:
            raise ValueError("Building type cannot be empty.")

        if construction_cost < 0:
            raise ValueError("Construction cost cannot be negative.")

        self.building_type = building_type
        self.required_materials = dict(required_materials or {})
        self.construction_cost = float(construction_cost)

        self._validate_materials()

    def _validate_materials(self):
        for resource_name, quantity in self.required_materials.items():
            if not resource_name:
                raise ValueError("Material resource name cannot be empty.")

            if quantity <= 0:
                raise ValueError(
                    "Required material quantities must be greater than zero."
                )

    def get_required_materials(self):
        return dict(self.required_materials)

    def get_construction_cost(self):
        return self.construction_cost


class ConstructionCostSystem:
    """Validates and atomically consumes configured construction costs."""

    @staticmethod
    def can_afford(world, definition, payer=None):
        if world is None:
            raise ValueError("World cannot be None.")

        if not isinstance(definition, BuildingDefinition):
            raise ValueError(
                "Definition must be a BuildingDefinition instance."
            )

        # Step 62: Validate every material before mutation.
        for resource_name, quantity in definition.required_materials.items():
            if resource_name not in world.resources:
                return False

            if world.get_resource(resource_name) < quantity:
                return False

        # Step 62: Validate optional money requirement.
        if definition.construction_cost > 0:
            if payer is None:
                return False

            if not hasattr(payer, "get_money"):
                return False

            if payer.get_money() < definition.construction_cost:
                return False

        return True

    @staticmethod
    def consume(world, definition, payer=None):
        if world is None:
            raise ValueError("World cannot be None.")

        if not isinstance(definition, BuildingDefinition):
            raise ValueError(
                "Definition must be a BuildingDefinition instance."
            )

        # Step 62: Perform every validation before changing state.
        if not ConstructionCostSystem.can_afford(
            world,
            definition,
            payer,
        ):
            return {
                "success": False,
                "building_type": definition.building_type,
                "materials": {},
                "cost": definition.construction_cost,
                "reason": "Insufficient construction resources or money.",
            }

        # Step 62: Consume all configured materials.
        consumed_materials = {}

        for resource_name, quantity in definition.required_materials.items():
            world.change_resource(resource_name, -quantity)
            consumed_materials[resource_name] = quantity

        # Step 62: Consume optional construction money.
        if definition.construction_cost > 0:
            payer.change_money(-definition.construction_cost)

        return {
            "success": True,
            "building_type": definition.building_type,
            "materials": consumed_materials,
            "cost": definition.construction_cost,
        }
# Step 63: Construction projects and worker progress

from src.gaia.building import Building
from src.gaia.construction import BuildingDefinition, ConstructionCostSystem
from src.gaia.agents.job import Job


class ConstructionProject:
    """Tracks one construction project from required materials to completion."""

    def __init__(
        self,
        project_id,
        world,
        definition,
        building_id,
        location,
        dimensions=None,
        owner=None,
        work_required=100.0,
    ):
        if not project_id:
            raise ValueError("Construction project ID cannot be empty.")

        if world is None:
            raise ValueError("World cannot be None.")

        if not isinstance(definition, BuildingDefinition):
            raise ValueError(
                "Definition must be a BuildingDefinition instance."
            )

        if work_required <= 0:
            raise ValueError("Required work must be greater than zero.")

        self.project_id = project_id
        self.world = world
        self.definition = definition
        self.building_id = building_id
        self.location = location
        self.dimensions = dimensions
        self.owner = owner

        self.work_required = float(work_required)
        self.work_completed = 0.0
        self.status = "planned"

        self.required_materials = definition.get_required_materials()
        self.materials_consumed = False

        self.workers = []
        self.worker_job = None
        self.building = None

    # Step 63: Start the project after atomically validating and consuming costs.
    def start(self, payer=None):
        if self.status != "planned":
            return {
                "success": False,
                "reason": "Construction project has already started."
            }

        if self.world.get_building(self.building_id) is not None:
            return {
                "success": False,
                "reason": "Building ID already exists."
            }

        result = ConstructionCostSystem.consume(
            self.world,
            self.definition,
            payer,
        )

        if not result["success"]:
            return result

        self.materials_consumed = True
        self.status = "under_construction"

        self.building = Building(
            self.building_id,
            self.definition.building_type,
            self.location,
            dimensions=self.dimensions,
            owner=self.owner,
            construction_status="under_construction",
        )

        self.world.add_building(self.building)

        return {
            "success": True,
            "project_id": self.project_id,
            "building_id": self.building_id,
            "status": self.status,
        }

    # Step 63: Assign the configured construction job.
    def set_worker_job(self, job):
        if not isinstance(job, Job):
            raise ValueError("Construction worker job must be a Job instance.")

        if not job.active:
            raise ValueError("Construction worker job must be active.")

        self.worker_job = job

    # Step 63: Add a living eligible worker to this project.
    def add_worker(self, worker):
        if self.status != "under_construction":
            return False

        if worker is None or not worker.is_alive():
            return False

        if self.worker_job is not None:
            if not self.worker_job.is_citizen_eligible(worker):
                return False

        if worker not in self.workers:
            self.workers.append(worker)

        return True

    # Step 63: Remove a worker from the project.
    def remove_worker(self, worker):
        if worker in self.workers:
            self.workers.remove(worker)

    # Step 63: Perform one unit of construction work.
    def perform_work(self, worker, work_amount=10.0):
        if self.status != "under_construction":
            return {
                "success": False,
                "reason": "Construction project is not under construction."
            }

        if worker is None or not worker.is_alive():
            self.remove_worker(worker)
            return {
                "success": False,
                "reason": "Dead workers cannot perform construction work."
            }

        if worker not in self.workers:
            return {
                "success": False,
                "reason": "Worker is not assigned to this project."
            }

        if work_amount <= 0:
            return {
                "success": False,
                "reason": "Work amount must be greater than zero."
            }

        remaining_work = self.work_required - self.work_completed
        applied_work = min(float(work_amount), remaining_work)

        self.work_completed += applied_work

        if self.work_completed >= self.work_required:
            self.work_completed = self.work_required
            self.status = "completed"

            if self.building is not None:
                self.building.construction_status = "completed"

        return {
            "success": True,
            "project_id": self.project_id,
            "work_completed": self.work_completed,
            "work_required": self.work_required,
            "status": self.status,
            "building_id": self.building_id,
        }

    # Step 63: Remove dead workers from active participation.
    def remove_dead_workers(self):
        self.workers = [
            worker for worker in self.workers
            if worker.is_alive()
        ]

    def get_progress(self):
        return self.work_completed / self.work_required

    def is_complete(self):
        return self.status == "completed"
