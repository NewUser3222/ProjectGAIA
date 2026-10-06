"""Read-only, deterministic observation and reporting for a GAIA simulation."""

from dataclasses import dataclass
import hashlib
import json
import math


@dataclass(frozen=True)
class GovernorFinding:
    """One deterministic observation; findings never prescribe an action."""

    category: str
    subject: str
    message: str
    severity: str = "info"
    simulation_tick: int = 0
    world_tick: int = 0
    temporal_status: str = "current"
    evidence: tuple = ()

    @property
    def finding_id(self):
        """Stable identifier for tracking this condition across observation ticks."""
        identity = json.dumps((
            self.category,
            self.subject,
            self.message,
            self.severity,
            self.temporal_status,
        ), ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        return f"gov-{self.category}-{digest}"


@dataclass(frozen=True)
class GovernorReport:
    """Immutable summary of simulation state at one observation point."""

    tick: int
    population: int
    living_population: int
    births: int
    deaths: int
    resources: tuple
    building_count: int
    business_count: int
    vehicle_count: int
    environment: tuple
    findings: tuple
    market_activity: tuple = ()
    completed_market_ticks: int = 0
    construction_project_count: int = 0
    construction_statuses: tuple = ()
    world_tick: int = 0


class GAIAGovernor:
    """Observe a Simulation without acquiring authority to change it."""

    def observe(self, simulation):
        """Return a stable snapshot and current findings; never mutate inputs."""
        if simulation is None or not hasattr(simulation, "world"):
            raise TypeError("A simulation with a world is required.")

        world = simulation.world
        citizens = tuple(simulation.citizens)
        businesses = tuple(simulation.businesses)
        projects = tuple(simulation.get_construction_projects())
        vehicles = tuple(world.transportation.get_vehicles())
        living = tuple(citizen for citizen in citizens if citizen.is_alive())
        births = sum(
            event == "Citizen was born."
            for citizen in citizens
            for event in tuple(citizen.history)
        )
        deaths = sum(
            event == "Citizen died."
            for citizen in citizens
            for event in tuple(citizen.history)
        )
        resources = tuple(sorted(
            (name, _snapshot_value(amount))
            for name, amount in world.resources.items()
        ))
        environment = tuple(sorted(
            (name, _snapshot_value(value))
            for name, value in world.environment.to_dict().items()
        ))
        market_observations = world.market_observations
        market_data = market_observations.to_dict()
        market_resources = sorted(
            set(market_data["recent"]) | {
                resource
                for values in market_data["current"].values()
                for resource in values
            }
        )
        market_activity = tuple(
            (
                resource,
                activity,
                _snapshot_value(market_data["current"][activity].get(resource, 0.0)),
                _snapshot_value(market_data["recent"].get(resource, {}).get(activity, 0.0)),
            )
            for resource in market_resources
            for activity in market_observations.ACTIVITY_TYPES
        )
        findings = []

        if births:
            findings.append(GovernorFinding(
                "population_change", "births", f"Recorded births: {births}."
            ))
        if deaths:
            findings.append(GovernorFinding(
                "population_change", "deaths", f"Recorded deaths: {deaths}."
            ))

        for name, amount in resources:
            limit = world.resource_limits.get(name)
            invalid_limit = (
                not _is_finite_number(limit) or limit < 0
            )
            if invalid_limit:
                findings.append(GovernorFinding(
                    "economic_anomaly", name,
                    "World resource capacity is missing or invalid.",
                    evidence=(("capacity", _snapshot_value(limit)),),
                ))
            if not _is_finite_number(amount) or amount < 0 or (
                _is_finite_number(limit) and amount > limit
            ):
                findings.append(GovernorFinding(
                    "economic_anomaly", name,
                    "World stock is non-finite or outside its configured capacity.",
                    evidence=(
                        ("amount", _snapshot_value(amount)),
                        ("capacity", _snapshot_value(limit)),
                    ),
                ))
            elif amount <= 0:
                findings.append(GovernorFinding(
                    "resource_depletion", name, "World stock is depleted.",
                    evidence=(("amount", amount), ("capacity", limit)),
                ))
            elif _is_finite_number(limit) and limit > 0 and amount <= limit * 0.1:
                findings.append(GovernorFinding(
                    "resource_shortage", name, "World stock is at or below 10% of capacity.",
                    evidence=(("amount", amount), ("capacity", limit)),
                ))

        for citizen in living:
            if not world.is_valid_location(citizen.location):
                findings.append(GovernorFinding(
                    "abnormal_condition", citizen.citizen_id,
                    "Citizen location is outside world bounds.",
                    evidence=(("location", _snapshot_value(citizen.location)),),
                ))
            movement = (
                simulation.get_movement_state(citizen)
                if hasattr(simulation, "get_movement_state")
                else None
            )
            if movement is not None:
                intent = movement.intent
                invalid_state = movement.status not in {
                    "stationary", "moving", "arrived", "cancelled",
                }
                missing_intent = movement.status == "moving" and intent is None
                invalid_destination = (
                    intent is not None
                    and not world.is_valid_location(intent.destination)
                )
                if invalid_state or missing_intent or invalid_destination:
                    findings.append(GovernorFinding(
                        "abnormal_condition", citizen.citizen_id,
                        "Citizen movement state is inconsistent or out of bounds.",
                        evidence=(
                            ("movement_status", _snapshot_value(movement.status)),
                            ("destination", _snapshot_value(
                                intent.destination if intent is not None else None
                            )),
                        ),
                    ))
            health = citizen.health
            if not _is_finite_number(health) or not 0 <= health <= 100:
                findings.append(GovernorFinding(
                    "abnormal_condition", citizen.citizen_id,
                    "Health is non-finite or outside its 0-100 range.",
                    evidence=(("health", _snapshot_value(health)),),
                ))
            elif health <= 10:
                findings.append(GovernorFinding(
                    "citizen_health", citizen.citizen_id,
                    "Health is critically low.",
                    evidence=(("health", health),),
                ))
            invalid_needs = tuple(sorted(
                need for need, value in citizen.needs.items()
                if not _is_finite_number(value) or not 0 <= value <= 100
            ))
            for need in invalid_needs:
                findings.append(GovernorFinding(
                    "abnormal_condition", citizen.citizen_id,
                    f"{need} need is non-finite or outside its 0-100 range.",
                    evidence=(("need", need), ("value", _snapshot_value(citizen.needs[need]))),
                ))
            critical = tuple(sorted(
                need for need, value in citizen.needs.items()
                if need != "hunger" and _is_finite_number(value) and value <= 10
            ))
            for need in critical:
                findings.append(GovernorFinding(
                    "citizen_shortage", citizen.citizen_id,
                    f"{need} need is critically low.",
                    evidence=(("need", need), ("value", citizen.needs[need])),
                ))

        for citizen in citizens:
            balances = (citizen.get_money(), *citizen.inventory.values())
            if any(not _is_finite_number(value) or value < 0 for value in balances):
                findings.append(GovernorFinding(
                    "economic_anomaly", citizen.citizen_id,
                    "Citizen balance or inventory is negative or non-finite."
                ))

        for building in world.buildings:
            if not world.is_valid_location(building.location):
                findings.append(GovernorFinding(
                    "abnormal_condition", building.building_id,
                    "Building location is outside world bounds.",
                    evidence=(("location", _snapshot_value(building.location)),),
                ))
            if building.condition != "good":
                findings.append(GovernorFinding(
                    "building_condition", building.building_id,
                    "Building condition is not good.",
                    evidence=(("condition", _snapshot_value(building.condition)),),
                ))
            if (
                not isinstance(building.condition, str)
                or building.condition not in {"good", "damaged", "destroyed", "abandoned"}
            ):
                findings.append(GovernorFinding(
                    "abnormal_condition", building.building_id,
                    "Building has an unrecognized condition."
                ))
            if (
                not isinstance(building.construction_status, str)
                or building.construction_status not in {
                    "planned", "under_construction", "completed", "abandoned"
                }
            ):
                findings.append(GovernorFinding(
                    "abnormal_condition", building.building_id,
                    "Unrecognized building construction status."
                ))

        for project in projects:
            status = project.status
            if status == "failed":
                findings.append(GovernorFinding(
                    "construction_failure", project.project_id,
                    "Construction project is marked failed.",
                    evidence=(("status", "failed"),),
                ))
            elif (
                not isinstance(status, str)
                or status not in {"planned", "under_construction", "completed"}
            ):
                findings.append(GovernorFinding(
                    "abnormal_condition", project.project_id,
                    "Construction project has an unrecognized status."
                ))

        for business in businesses:
            if not business.is_active():
                findings.append(GovernorFinding(
                    "production_condition", business.business_id,
                    "Business is inactive."
                ))
            balances = (business.get_money(), *business.inventory.values())
            if any(not _is_finite_number(value) or value < 0 for value in balances):
                findings.append(GovernorFinding(
                    "economic_anomaly", business.business_id,
                    "Business balance or inventory is negative or non-finite."
                ))

        for vehicle in vehicles:
            if not world.is_valid_location(vehicle.location):
                findings.append(GovernorFinding(
                    "transportation_condition", vehicle.vehicle_id,
                    "Vehicle location is outside world bounds.",
                    evidence=(("location", _snapshot_value(vehicle.location)),),
                ))
            if vehicle.operational_state != "operational":
                findings.append(GovernorFinding(
                    "transportation_condition", vehicle.vehicle_id,
                    "Vehicle is not operational.",
                    evidence=(("state", _snapshot_value(vehicle.operational_state)),),
                ))

        temperature = world.environment.temperature
        if not _is_finite_number(temperature):
            findings.append(GovernorFinding(
                "abnormal_condition", "temperature",
                "Temperature is non-finite.",
                evidence=(("value", _snapshot_value(temperature)),),
            ))
        elif temperature <= 0 or temperature >= 35:
            findings.append(GovernorFinding(
                "environment_condition", "temperature",
                f"Temperature is at an exposure threshold: {temperature}.",
                evidence=(("temperature", temperature),),
            ))

        for condition in ("precipitation", "wind_speed"):
            value = getattr(world.environment, condition)
            if not _is_finite_number(value) or value < 0:
                findings.append(GovernorFinding(
                    "abnormal_condition", condition,
                    "Environmental measurement is non-finite or negative.",
                    evidence=(("value", _snapshot_value(value)),),
                ))

        if world.environment.season not in world.environment.SEASONS:
            findings.append(GovernorFinding(
                "abnormal_condition", "season",
                "Season is not a recognized world season."
            ))
        if world.environment.weather not in world.environment.WEATHER_TYPES:
            findings.append(GovernorFinding(
                "abnormal_condition", "weather",
                "Weather is not a recognized world condition."
            ))
        if (
            not isinstance(world.environment.day, int)
            or isinstance(world.environment.day, bool)
            or world.environment.day < 1
        ):
            findings.append(GovernorFinding(
                "abnormal_condition", "day",
                "Environmental day is outside its positive integer range."
            ))

        if simulation.tick != world.current_tick:
            findings.append(GovernorFinding(
                "abnormal_condition", "simulation_clock",
                "Simulation and world ticks do not match."
            ))

        historical_categories = {"population_change"}
        findings = [
            GovernorFinding(
                category=finding.category,
                subject=finding.subject,
                message=finding.message,
                severity=_finding_severity(finding.category),
                simulation_tick=simulation.tick,
                world_tick=world.current_tick,
                temporal_status=(
                    "historical" if finding.category in historical_categories
                    else "current"
                ),
                evidence=tuple(
                    (key, _snapshot_value(value)) for key, value in finding.evidence
                ),
            )
            for finding in findings
        ]
        findings = sorted(
            {finding.finding_id: finding for finding in findings}.values(),
            key=lambda finding: (
                finding.category,
                finding.subject,
                finding.severity,
                finding.message,
                finding.finding_id,
            ),
        )
        return GovernorReport(
            tick=simulation.tick,
            world_tick=world.current_tick,
            population=len(citizens),
            living_population=len(living),
            births=births,
            deaths=deaths,
            resources=resources,
            building_count=len(world.buildings),
            business_count=len(businesses),
            vehicle_count=len(vehicles),
            environment=environment,
            findings=tuple(findings),
            market_activity=market_activity,
            completed_market_ticks=market_data["completed_ticks"],
            construction_project_count=len(projects),
            construction_statuses=tuple(sorted(
                (project.project_id, _snapshot_value(project.status))
                for project in projects
            )),
        )


def _is_finite_number(value):
    """Return whether a world value can safely participate in numeric checks."""
    if isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except (TypeError, ValueError, OverflowError):
        return False


def _finding_severity(category):
    """Map established finding categories to stable report severity levels."""
    if category in {"abnormal_condition", "economic_anomaly", "resource_depletion"}:
        return "critical"
    if category in {
        "building_condition", "citizen_health", "citizen_shortage", "construction_failure",
        "environment_condition", "transportation_condition",
        "production_condition", "resource_shortage",
    }:
        return "warning"
    return "info"


def _snapshot_value(value):
    """Freeze finding evidence and normalize malformed non-scalar values."""
    if isinstance(value, dict):
        return tuple(sorted(
            (str(key), _snapshot_value(item)) for key, item in value.items()
        ))
    if isinstance(value, (tuple, list)):
        return tuple(_snapshot_value(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((_snapshot_value(item) for item in value), key=repr))
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    value_type = type(value)
    return f"<{value_type.__module__}.{value_type.__qualname__}>"
