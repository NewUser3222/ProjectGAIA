from dataclasses import dataclass
import math
from weakref import WeakKeyDictionary

from src.gaia.agents.decision import DecisionEngine
from src.gaia.agents.social import SocialInteraction
from src.gaia.movement import MovementIntent, MovementState
from src.gaia.simulation.world import WorldState


@dataclass(frozen=True)
class SimulationEventRecord:
    """Immutable event context the engine can timestamp authoritatively."""

    sequence: int
    event_type: str
    subject_id: str
    subject_incarnation: int
    subject_name: str
    description: str
    source_tick: int
    related_citizen_ids: tuple = ()


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
        self._event_records = []
        self._citizen_instances = WeakKeyDictionary()
        self._next_citizen_incarnation = {}
        self._movement_states = {}

    @property
    def event_records(self):
        """Return immutable engine events known with an authoritative tick."""
        return tuple(self._event_records)

    def _ensure_citizen_identity(self, citizen):
        known = self._citizen_instances.get(citizen)
        if known is not None:
            return known
        citizen_id = str(citizen.citizen_id)
        incarnation = self._next_citizen_incarnation.get(citizen_id, 0) + 1
        self._next_citizen_incarnation[citizen_id] = incarnation
        identity = (citizen_id, incarnation)
        self._citizen_instances[citizen] = identity
        return identity

    def get_citizen_incarnation(self, citizen):
        """Return the engine identity assigned when a citizen was added."""
        identity = self._citizen_instances.get(citizen)
        if identity is None:
            raise ValueError("Citizen has not been added to this simulation.")
        return identity[1]

    def _record_event(self, citizen, event_type, description, related=()):
        citizen_id, incarnation = self._ensure_citizen_identity(citizen)
        self._event_records.append(SimulationEventRecord(
            sequence=len(self._event_records),
            event_type=event_type,
            subject_id=citizen_id,
            subject_incarnation=incarnation,
            subject_name=str(citizen.name),
            description=description,
            source_tick=self.tick,
            related_citizen_ids=tuple(sorted(str(value) for value in related)),
        ))

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
        self._record_event(
            child, "birth", "Citizen was born.",
            related=(parent_a.citizen_id, parent_b.citizen_id),
        )
        return child

    def add_citizen(self, citizen):
        """Adds a citizen to the simulation and its world state."""
        if citizen and citizen not in self.citizens:
            self._ensure_citizen_identity(citizen)
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
        if project.world is not self.world:
            raise ValueError("Construction project must belong to this simulation's world.")

        if project not in self.construction_projects:
            self.construction_projects.append(project)

    # Step 65: Remove a construction project from the simulation.
    def remove_construction_project(self, project):
        if project in self.construction_projects:
            self.construction_projects.remove(project)

    # Step 65: Return tracked construction projects.
    def get_construction_projects(self):
        return list(self.construction_projects)

    def get_movement_state(self, citizen):
        """Return a detached intent/status value owned by this Simulation."""
        return self._movement_states.get(citizen, MovementState("stationary"))

    def request_movement(
        self,
        citizen,
        destination,
        *,
        reason="",
        target_kind=None,
        target_id=None,
    ):
        """Validate and accept a citizen destination without moving it."""
        if citizen not in self.citizens:
            return {"success": False, "reason": "Citizen is not registered with this simulation."}
        if not citizen.is_alive():
            return {"success": False, "reason": "Dead citizens cannot request movement."}
        try:
            intent = MovementIntent(
                destination, reason, target_kind, target_id,
            )
        except (TypeError, ValueError) as error:
            return {"success": False, "reason": str(error)}
        if not self.world.is_valid_location(intent.destination):
            return {"success": False, "reason": "Destination is outside the world bounds."}
        try:
            current = MovementIntent(citizen.location).destination
        except (TypeError, ValueError):
            return {"success": False, "reason": "Citizen position is invalid."}
        if not self.world.is_valid_location(current):
            return {"success": False, "reason": "Citizen position is outside the world bounds."}
        try:
            speed = float(citizen.speed)
        except (TypeError, ValueError, OverflowError):
            return {"success": False, "reason": "Citizen movement speed is invalid."}
        if isinstance(citizen.speed, bool) or not math.isfinite(speed) or speed <= 0:
            return {"success": False, "reason": "Citizen movement speed is invalid."}

        target_location, target_error = self._movement_target_location(intent)
        if target_error is not None:
            return {"success": False, "reason": target_error}
        if target_location != intent.destination:
            return {"success": False, "reason": "Destination does not match the target location."}

        previous = self.get_movement_state(citizen)
        if previous.intent == intent and previous.status in {"moving", "arrived"}:
            return {
                "success": True,
                "duplicate": True,
                "status": previous.status,
                "destination": intent.destination,
            }
        if previous.status == "moving":
            self._cancel_movement(citizen, "replaced by a new movement request")

        status = "arrived" if current == intent.destination else "moving"
        self._movement_states[citizen] = MovementState(status, intent)
        related = (intent.target_id,) if intent.target_kind == "citizen" else ()
        self._record_event(
            citizen,
            "movement_intent_accepted",
            f"Movement requested from {current} to {intent.destination} ({intent.reason or 'unspecified'}).",
            related=related,
        )
        if status == "arrived":
            self._record_event(
                citizen,
                "movement_arrived",
                f"Arrived at destination {intent.destination}.",
                related=related,
            )
        return {
            "success": True,
            "duplicate": False,
            "status": status,
            "destination": intent.destination,
        }

    def cancel_movement(self, citizen, reason="cancelled by simulation"):
        """Cancel a pending route through the Simulation authority."""
        if citizen not in self.citizens:
            return {"success": False, "reason": "Citizen is not registered with this simulation."}
        if not isinstance(reason, str) or not reason:
            return {"success": False, "reason": "Cancellation reason cannot be empty."}
        if self.get_movement_state(citizen).status != "moving":
            return {"success": False, "reason": "Citizen has no active movement intent."}
        self._cancel_movement(citizen, reason)
        return {"success": True, "status": "cancelled"}

    def _movement_target_location(self, intent):
        """Resolve optional target identity to a currently valid world point."""
        kind, target_id = intent.target_kind, intent.target_id
        if kind is None:
            return intent.destination, None
        if kind == "building":
            target = self.world.get_building(target_id)
            if target is None or not target.is_active():
                return None, "Movement target building is missing or inactive."
            return self._validated_target_location(target.location)
        if kind == "construction":
            target = next((
                project for project in self.construction_projects
                if str(project.project_id) == target_id
            ), None)
            if target is None or target.status != "under_construction":
                return None, "Movement target construction project is missing or inactive."
            return self._validated_target_location(target.location)
        if kind == "business":
            target = next((
                business for business in self.businesses
                if str(business.business_id) == target_id
            ), None)
            if target is None or not target.is_active():
                return None, "Movement target business is missing or inactive."
            sites = sorted(
                (building for building in self.world.buildings
                 if building.get_associated_business() is target),
                key=lambda building: str(building.building_id),
            )
            site = next((building for building in sites if building.is_active()), None)
            if site is None:
                return None, "Movement target business has no active associated building."
            return self._validated_target_location(site.location)
        if kind == "citizen":
            target = next((
                subject for subject in self.citizens
                if str(subject.citizen_id) == target_id and subject.is_alive()
            ), None)
            if target is None:
                return None, "Movement target citizen is missing or inactive."
            return self._validated_target_location(target.location)
        return None, f"Unsupported movement target kind: {kind}."

    def _validated_target_location(self, location):
        try:
            location = MovementIntent(location).destination
        except (TypeError, ValueError):
            return None, "Movement target location is invalid."
        if not self.world.is_valid_location(location):
            return None, "Movement target location is outside the world bounds."
        return location, None

    def _cancel_movement(self, citizen, reason):
        state = self.get_movement_state(citizen)
        intent = state.intent
        if intent is None:
            self._movement_states[citizen] = MovementState("cancelled")
            return
        self._movement_states[citizen] = MovementState("cancelled")
        related = (intent.target_id,) if intent.target_kind == "citizen" else ()
        self._record_event(
            citizen,
            "movement_cancelled",
            f"Movement toward {intent.destination} was cancelled: {reason}.",
            related=related,
        )

    def _advance_citizen_movement(self):
        """Apply one bounded, deterministic movement update per active intent."""
        ordered = sorted(self.citizens, key=lambda citizen: str(citizen.citizen_id))
        for citizen in ordered:
            state = self.get_movement_state(citizen)
            intent = state.intent
            if state.status != "moving" or intent is None:
                continue
            if not citizen.is_alive():
                self._cancel_movement(citizen, "citizen is no longer alive")
                continue

            destination, error = self._movement_target_location(intent)
            if error is not None or not self.world.is_valid_location(destination):
                self._cancel_movement(citizen, error or "destination is outside world bounds")
                continue
            if destination != intent.destination:
                intent = MovementIntent(
                    destination, intent.reason, intent.target_kind, intent.target_id,
                )
                self._movement_states[citizen] = MovementState("moving", intent)

            try:
                current = MovementIntent(citizen.location).destination
                speed = float(citizen.speed)
            except (TypeError, ValueError, OverflowError):
                self._cancel_movement(citizen, "citizen position or speed is invalid")
                continue
            if (
                not self.world.is_valid_location(current)
                or isinstance(citizen.speed, bool)
                or not math.isfinite(speed)
                or speed <= 0
            ):
                self._cancel_movement(citizen, "citizen position or speed is invalid")
                continue

            dx = destination[0] - current[0]
            dy = destination[1] - current[1]
            distance = math.hypot(dx, dy)
            if not math.isfinite(distance):
                self._cancel_movement(citizen, "movement distance is non-finite")
                continue
            if distance <= speed:
                citizen.location = destination
                self._movement_states[citizen] = MovementState("arrived", intent)
                related = (intent.target_id,) if intent.target_kind == "citizen" else ()
                self._record_event(
                    citizen,
                    "movement_arrived",
                    f"Arrived at destination {destination}.",
                    related=related,
                )
            else:
                scale = speed / distance
                next_location = (
                    current[0] + dx * scale,
                    current[1] + dy * scale,
                )
                if next_location == current:
                    self._cancel_movement(citizen, "movement speed is below coordinate precision")
                    continue
                if not self.world.is_valid_location(next_location):
                    self._cancel_movement(citizen, "movement would leave world bounds")
                    continue
                citizen.location = next_location

    def _action_movement_requirement(self, citizen, action, employer=None):
        requirements = action.requirements
        if action.action_id == "construct":
            project = requirements.get("project")
            if project is None:
                return None
            return (
                project.location,
                "construction",
                "construction",
                str(project.project_id),
            )
        if action.action_id == "work" and employer is not None and hasattr(employer, "business_id"):
            sites = sorted(
                (building for building in self.world.buildings
                 if building.get_associated_business() is employer),
                key=lambda building: str(building.building_id),
            )
            if sites:
                site = next((building for building in sites if building.is_active()), None)
                if site is None:
                    return None, "work", "business", str(employer.business_id)
                return (
                    site.location, "work", "business", str(employer.business_id),
                )
        destination = requirements.get("destination")
        if destination is None:
            return None
        return (
            destination,
            requirements.get("movement_reason", action.action_id),
            requirements.get("target_kind"),
            requirements.get("target_id"),
        )

    def _defer_action_for_movement(self, citizen, action, employer=None):
        requirement = self._action_movement_requirement(citizen, action, employer)
        if requirement is None:
            return False
        destination, reason, target_kind, target_id = requirement
        if destination is None:
            # An associated workplace exists but is not currently usable.
            return True
        try:
            target = MovementIntent(destination).destination
            current = MovementIntent(citizen.location).destination
        except (TypeError, ValueError):
            return True
        if not self.world.is_valid_location(target):
            return True
        if current == target:
            state = self.get_movement_state(citizen)
            if state.status == "moving":
                self._cancel_movement(citizen, "activity destination already reached")
            return False
        self.request_movement(
            citizen,
            target,
            reason=reason,
            target_kind=target_kind,
            target_id=target_id,
        )
        return True

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

        before_states = {
            id(citizen): (citizen, citizen.life_stage, citizen.lifecycle_state)
            for citizen in tuple(self.citizens)
        }
        self.tick += 1
        print(f"Simulation tick: {self.tick}")

        # Step 36: Advance shared world state once per simulation tick.
        self.world.advance_tick()

        # Step 73: Move registered vehicles along their assigned routes.
        self.world.transportation.advance_tick()

        world_context = {
            "tick": self.tick,
            "world": self.world
        }
        decision_context = {
            "construction_projects": tuple(self.construction_projects),
        }

        # Step 60: Remove dead employees before business work processing.
        for business in self.businesses:
            if business.is_active():
                business.remove_dead_employees()

        # Step 80: Businesses evaluate market conditions and procure inputs.
        for business in self.businesses:
            if business.is_active():
                business.prepare_production(self.world)

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
            # Step 77: World conditions affect exposed citizens independently.
            self.world.apply_environmental_effects(citizen)
            if not citizen.is_alive():
                continue
            citizen.update_needs()

            # Step 44: Decisions must observe the current shared world state.
            action = self.decision_engine.select_best_action(
                citizen,
                world=self.world,
                context=decision_context,
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

                            can_pay_worker = (
                                employer.can_pay_wage(citizen, job.wage)
                                if hasattr(employer, "can_pay_wage")
                                else employer.get_money() >= job.wage
                            )
                            if not can_pay_worker:
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

                        if self._defer_action_for_movement(
                            citizen, action, employer=employer
                        ):
                            continue

                        self.decision_engine.execute_action(
                            citizen,
                            action,
                            world_context=work_context
                        )
                    else:
                        if self._defer_action_for_movement(
                            citizen, action, employer=employer
                        ):
                            continue
                        self.decision_engine.execute_action(
                            citizen,
                            action,
                            world_context=world_context
                        )
                else:
                    if self._defer_action_for_movement(citizen, action):
                        continue
                    result = self.decision_engine.execute_action(
                        citizen,
                        action,
                        world_context=world_context
                    )
                    if (
                        action.action_id == "construct"
                        and result.get("success")
                        and result.get("status") == "completed"
                    ):
                        self._record_event(
                            citizen,
                            "construction_completed",
                            f"Completed construction project {result['project_id']}.",
                        )

        # Movement is applied only by the Simulation and after citizen choices,
        # so a newly requested trip cannot also perform its destination action.
        self._advance_citizen_movement()

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

        for citizen in tuple(self.citizens):
            previous = before_states.get(id(citizen))
            if previous is None or previous[0] is not citizen:
                continue
            _, old_stage, old_lifecycle = previous
            if old_stage != citizen.life_stage:
                self._record_event(
                    citizen,
                    "life_stage_transition",
                    f"Life stage changed from {old_stage} to {citizen.life_stage}.",
                )
            if old_lifecycle != "dead" and citizen.lifecycle_state == "dead":
                self._record_event(citizen, "death", "Citizen died.")


