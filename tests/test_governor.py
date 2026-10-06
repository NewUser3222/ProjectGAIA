import unittest
from dataclasses import FrozenInstanceError, replace
import math

from src.gaia.agents.citizen import Citizen
from src.gaia.building import Building
from src.gaia.business import Business
from src.gaia.construction import BuildingDefinition, ConstructionProject
from src.gaia.core.simulation import Simulation
from src.gaia.governor import GAIAGovernor, GovernorFinding
from src.gaia.vehicle import Vehicle


class TestGAIAGovernor(unittest.TestCase):
    def setUp(self):
        self.simulation = Simulation()
        self.governor = GAIAGovernor()

    def test_observation_is_deterministic_immutable_and_read_only(self):
        citizen = Citizen("c1", "Ada")
        self.simulation.add_citizen(citizen)
        before = (
            self.simulation.tick,
            self.simulation.world.current_tick,
            tuple(self.simulation.citizens),
            dict(self.simulation.world.resources),
            tuple(self.simulation.world.buildings),
            tuple(self.simulation.businesses),
        )

        first = self.governor.observe(self.simulation)
        second = self.governor.observe(self.simulation)

        self.assertEqual(first, second)
        self.assertEqual(before, (
            self.simulation.tick,
            self.simulation.world.current_tick,
            tuple(self.simulation.citizens),
            dict(self.simulation.world.resources),
            tuple(self.simulation.world.buildings),
            tuple(self.simulation.businesses),
        ))
        self.assertIsInstance(first.findings, tuple)
        with self.assertRaises(FrozenInstanceError):
            first.tick = 99
        with self.assertRaises(AttributeError):
            self.governor.change_resource("food", 1)

    def test_reports_lifecycle_resources_and_supported_world_conditions(self):
        parent = Citizen("parent", "Parent")
        child = Citizen("child", "Child")
        child.record_history("Citizen was born.")
        parent.die()
        child.needs["food"] = 5
        self.simulation.add_citizen(parent)
        self.simulation.add_citizen(child)
        self.simulation.world.set_resource("food", 0)
        business = Business("b1", "Inactive")
        business.deactivate()
        self.simulation.add_business(business)
        self.simulation.world.environment.temperature = 40
        project = ConstructionProject(
            "p1", self.simulation.world, BuildingDefinition("house"),
            "building-1", (1, 1),
        )
        project.status = "failed"
        self.simulation.add_construction_project(project)
        vehicle = Vehicle("v1", "cart")
        self.simulation.world.transportation.add_vehicle(vehicle)
        vehicle.location = (-1, 0)

        report = self.governor.observe(self.simulation)

        self.assertEqual((report.population, report.living_population), (2, 1))
        self.assertEqual((report.births, report.deaths), (1, 1))
        categories = {finding.category for finding in report.findings}
        self.assertTrue({"resource_depletion", "citizen_shortage",
                         "production_condition", "environment_condition",
                         "population_change", "construction_failure",
                         "transportation_condition"}
                        <= categories)

    def test_findings_are_structured_and_have_stable_order(self):
        self.simulation.world.set_resource("food", 1)
        report = self.governor.observe(self.simulation)
        self.assertEqual(report.findings, tuple(sorted(
            report.findings,
            key=lambda finding: (finding.category, finding.subject, finding.message),
        )))
        self.assertTrue(all(isinstance(item, GovernorFinding) for item in report.findings))

    def test_reports_current_and_rolling_market_activity_as_immutable_values(self):
        observations = self.simulation.world.market_observations
        observations.record_consumption("food", 2)
        self.simulation.world.advance_tick()
        observations.record_trade("food", 3)

        report = self.governor.observe(self.simulation)

        self.assertEqual(report.completed_market_ticks, 1)
        food = {
            activity: (current, recent)
            for resource, activity, current, recent in report.market_activity
            if resource == "food"
        }
        self.assertEqual(food["consumption"], (0.0, 2.0))
        self.assertEqual(food["trade"], (3.0, 0.0))
        self.assertEqual(report, self.governor.observe(self.simulation))

    def test_flags_corrupt_authoritative_values_without_crashing(self):
        citizen = Citizen("c1", "Ada")
        self.simulation.add_citizen(citizen)
        citizen.needs["food"] = math.nan
        self.simulation.world.resources["food"] = math.inf

        report = self.governor.observe(self.simulation)

        anomalies = [
            finding for finding in report.findings
            if finding.category in {"economic_anomaly", "abnormal_condition"}
        ]
        self.assertEqual(len(anomalies), 2)
        self.assertTrue(any(finding.subject == "food" for finding in anomalies))
        self.assertTrue(any(finding.subject == "c1" for finding in anomalies))

    def test_handles_invalid_resource_capacity_and_business_balances(self):
        self.simulation.world.resource_limits.pop("wood")
        business = Business("b1", "Broken ledger")
        business.money = "unknown"
        business.inventory["wood"] = math.inf
        self.simulation.add_business(business)

        report = self.governor.observe(self.simulation)

        self.assertTrue(any(
            finding.subject == "wood" and "capacity" in finding.message
            for finding in report.findings
        ))
        self.assertTrue(any(
            finding.category == "economic_anomaly"
            and finding.subject == "b1"
            for finding in report.findings
        ))

    def test_monitors_supported_citizen_and_environment_health_signals(self):
        citizen = Citizen("c1", "Ada")
        citizen.health = 5
        citizen.location = (-1, 0)
        self.simulation.add_citizen(citizen)
        self.simulation.world.environment.wind_speed = -1

        report = self.governor.observe(self.simulation)

        self.assertTrue(any(
            finding.category == "citizen_health" and finding.subject == "c1"
            for finding in report.findings
        ))
        self.assertTrue(any(
            finding.category == "abnormal_condition"
            and finding.subject == "c1"
            and "location" in finding.message
            for finding in report.findings
        ))
        self.assertTrue(any(
            finding.subject == "wind_speed" for finding in report.findings
        ))

    def test_world_exposes_read_only_location_validation(self):
        world = self.simulation.world
        self.assertTrue(world.is_valid_location((0, 0)))
        self.assertFalse(world.is_valid_location((-1, 0)))

    def test_findings_have_severity_context_and_stable_identifiers(self):
        self.simulation.world.set_resource("food", 0)
        report = self.governor.observe(self.simulation)
        depletion = next(
            finding for finding in report.findings
            if finding.category == "resource_depletion"
            and finding.subject == "food"
        )

        self.assertEqual(depletion.severity, "critical")
        self.assertEqual((depletion.simulation_tick, depletion.world_tick), (0, 0))
        self.assertEqual(depletion.temporal_status, "current")
        self.assertEqual(dict(depletion.evidence), {"amount": 0, "capacity": 1000})
        self.assertEqual(
            depletion.finding_id,
            replace(depletion, simulation_tick=3, world_tick=3).finding_id,
        )
        self.assertNotEqual(
            depletion.finding_id,
            replace(depletion, message="Different condition").finding_id,
        )
        self.assertEqual(len({f.finding_id for f in report.findings}), len(report.findings))

    def test_healthy_world_and_clock_context_are_reported_without_findings(self):
        for resource in self.simulation.world.resources:
            self.simulation.world.set_resource(resource, 500)
        self.simulation.tick = 4
        self.simulation.world.current_tick = 4

        report = self.governor.observe(self.simulation)

        self.assertEqual((report.tick, report.world_tick), (4, 4))
        self.assertEqual(report.findings, ())

    def test_reports_building_transport_and_construction_health(self):
        building = Building("h1", "house", (-1, 0))
        building.condition = "damaged"
        self.simulation.world.add_building(building)
        project = ConstructionProject(
            "p1", self.simulation.world, BuildingDefinition("house"), "h2", (1, 1)
        )
        self.simulation.add_construction_project(project)
        vehicle = Vehicle("v1", "cart", operational_state="disabled")
        self.simulation.world.transportation.add_vehicle(vehicle)

        report = self.governor.observe(self.simulation)

        self.assertEqual(report.construction_project_count, 1)
        self.assertEqual(report.construction_statuses, (("p1", "planned"),))
        findings = {(item.category, item.subject) for item in report.findings}
        self.assertIn(("building_condition", "h1"), findings)
        self.assertIn(("abnormal_condition", "h1"), findings)
        self.assertIn(("transportation_condition", "v1"), findings)

    def test_detects_invalid_citizen_economic_ledger(self):
        citizen = Citizen("c1", "Ada")
        citizen.money = math.nan
        citizen.inventory["food"] = -1
        self.simulation.add_citizen(citizen)

        report = self.governor.observe(self.simulation)

        self.assertTrue(any(
            item.category == "economic_anomaly" and item.subject == "c1"
            for item in report.findings
        ))

    def test_malformed_status_and_calendar_values_are_reported_deterministically(self):
        building = Building("h1", "house", (1, 1))
        building.condition = ["corrupt"]
        building.construction_status = {"corrupt": True}
        self.simulation.world.add_building(building)
        project = ConstructionProject(
            "p1", self.simulation.world, BuildingDefinition("house"), "h2", (2, 2)
        )
        project.status = ["corrupt"]
        self.simulation.add_construction_project(project)
        self.simulation.world.environment.season = ["corrupt"]
        self.simulation.world.environment.day = 0

        first = self.governor.observe(self.simulation)
        second = self.governor.observe(self.simulation)

        self.assertEqual(first, second)
        self.assertTrue(any(item.subject == "h1" for item in first.findings))
        self.assertTrue(any(item.subject == "p1" for item in first.findings))
        self.assertTrue(any(item.subject == "season" for item in first.findings))
        self.assertTrue(any(item.subject == "day" for item in first.findings))


if __name__ == "__main__":
    unittest.main()
