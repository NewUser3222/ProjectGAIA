"""Decision/action integration contracts for citizen activity."""

import unittest

from src.gaia.agents.action import ActionOption
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.decision import DecisionEngine
from src.gaia.construction import BuildingDefinition, ConstructionProject
from src.gaia.core.simulation import Simulation


class TestExtensibleCitizenActions(unittest.TestCase):
    def test_provider_actions_are_stably_ordered_and_executed_by_registered_handler(self):
        citizen = Citizen("worker", "Worker")
        engine = DecisionEngine()
        calls = []

        def provider(subject, world, context):
            calls.append((subject, world, context["tick"]))
            return [ActionOption("learn", "Learn", 12)]

        engine.register_action_provider(provider)
        engine.action_executor.register_handler(
            "learn",
            lambda subject, action, context: {
                "success": True,
                "action": action.action_id,
            },
        )

        options = engine.evaluate_needs(citizen, context={"tick": 4})
        self.assertEqual(options[0].action_id, "learn")
        self.assertEqual(engine.select_best_action(citizen, context={"tick": 4}).action_id, "learn")
        result = engine.execute_action(citizen, options[0], {"tick": 4})
        self.assertEqual(result, {"success": True, "action": "learn"})
        self.assertEqual(len(calls), 2)

    def test_extensions_cannot_replace_built_in_accounting_handlers(self):
        engine = DecisionEngine()
        with self.assertRaisesRegex(ValueError, "cannot be replaced"):
            engine.action_executor.register_handler("buy_resource", lambda *args: {})


class TestDecisionDrivenConstruction(unittest.TestCase):
    def make_project(self, simulation, worker, *, work_required=20):
        simulation.world.set_resource("wood", 10)
        project = ConstructionProject(
            "workshop-project",
            simulation.world,
            BuildingDefinition("workshop", {"wood": 2}),
            "workshop",
            (4, 5),
            work_required=work_required,
        )
        self.assertTrue(project.start()["success"])
        self.assertTrue(project.add_worker(worker))
        simulation.add_construction_project(project)
        return project

    def test_only_assigned_eligible_project_is_offered_to_citizen(self):
        simulation = Simulation()
        worker = Citizen("builder", "Builder")
        outsider = Citizen("outsider", "Outsider")
        simulation.add_citizen(worker)
        project = self.make_project(simulation, worker)

        actions = simulation.decision_engine.evaluate_needs(
            worker,
            simulation.world,
            context={"construction_projects": (project,)},
        )
        self.assertEqual([action.action_id for action in actions], ["construct"])
        self.assertEqual(actions[0].requirements["project"], project)
        self.assertEqual(
            simulation.decision_engine.evaluate_needs(
                outsider,
                simulation.world,
                context={"construction_projects": (project,)},
            ),
            [],
        )

    def test_need_action_wins_over_construction_and_no_work_is_scheduled_behind_it(self):
        simulation = Simulation()
        worker = Citizen("builder", "Builder")
        worker.add_item("food", 1)
        worker.hunger = 70
        worker.needs["hunger"] = 70
        simulation.add_citizen(worker)
        project = self.make_project(simulation, worker)
        simulation.start()

        simulation.step()

        self.assertEqual(project.work_completed, 0)
        self.assertEqual(worker.get_item_quantity("food"), 0)
        self.assertEqual(project.status, "under_construction")

    def test_selected_construction_action_completes_once_and_is_historically_observable(self):
        simulation = Simulation()
        worker = Citizen("builder", "Builder", location=(4, 5))
        simulation.add_citizen(worker)
        project = self.make_project(simulation, worker, work_required=10)
        simulation.start()

        simulation.step()
        simulation.step()

        self.assertEqual(project.work_completed, 10)
        self.assertEqual(project.status, "completed")
        self.assertEqual(project.building.construction_status, "completed")
        completion_events = [
            event for event in simulation.event_records
            if event.event_type == "construction_completed"
        ]
        self.assertEqual(len(completion_events), 1)
        self.assertEqual(completion_events[0].source_tick, 1)
        self.assertTrue(any("construction work" in item["event"].lower() for item in worker.memories))

    def test_completed_and_ineligible_projects_are_not_action_options(self):
        simulation = Simulation()
        worker = Citizen("builder", "Builder")
        simulation.add_citizen(worker)
        project = self.make_project(simulation, worker, work_required=10)
        project.perform_work(worker, 10)
        actions = simulation.decision_engine.evaluate_needs(
            worker, simulation.world, context={"construction_projects": (project,)}
        )
        self.assertEqual(actions, [])

        inactive_worker = Citizen("other", "Other")
        inactive = self.make_project(Simulation(), inactive_worker)
        inactive.status = "planned"
        self.assertFalse(inactive.can_worker_contribute(inactive_worker))


if __name__ == "__main__":
    unittest.main()
