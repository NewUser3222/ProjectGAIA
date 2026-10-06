import unittest
from unittest import mock

from src.gaia.live_visualization import (
    LiveVisualizationController,
    create_live_demo_simulation,
)
from src.gaia.rendering import build_render_plan
from src.gaia.visualization import Camera, build_scene_frame, snapshot_simulation
from src.gaia.building import Building


class TestLiveVisualization(unittest.TestCase):
    def setUp(self):
        self.simulation = create_live_demo_simulation()
        self.camera = Camera((0, 0), 960, 600, 20)
        self.controller = LiveVisualizationController(
            self.simulation, self.camera,
            simulation_factory=create_live_demo_simulation,
        )

    def test_live_demo_uses_real_engine_models_and_has_drawable_entities(self):
        scene = snapshot_simulation(self.simulation)
        self.assertEqual(scene.bounds, (40, 24))
        self.assertEqual(scene.population, 4)
        indexed = {(item.kind, item.entity_id): item for item in scene.entities}
        self.assertIn(("business", "town-market"), indexed)
        self.assertEqual(dict(indexed[("business", "town-market")].details)["building_id"], "market")
        self.assertIn(("construction", "clinic-project"), indexed)
        self.assertEqual(indexed[("construction", "clinic-project")].state, "under_construction")
        self.assertIn(("vehicle", "wagon"), indexed)
        self.assertEqual(dict(scene.environment)["day"], 1)

        frame = self.controller.current_frame()
        plan = build_render_plan(frame)
        self.assertGreater(len(plan.commands), 0)
        self.assertEqual(
            {command.kind for command in plan.commands},
            {"building", "business", "vehicle", "citizen", "construction"},
        )

    def test_end_to_end_tick_snapshot_frame_plan_is_detached_and_current(self):
        first_frame = self.controller.current_frame()
        first_plan = build_render_plan(first_frame)
        first_vehicle_rect = next(
            command.rectangle for command in first_plan.commands
            if command.entity_id == "handcart"
        )
        initial_tick = self.simulation.tick
        initial_camera = self.controller.camera
        original_citizen_position = self.simulation.citizens[0].location
        initial_vehicle_position = next(
            entity.position for entity in first_frame.entities if entity.entity_id == "handcart"
        )

        self.controller.resume()
        second_frame = self.controller.advance_frame()
        second_plan = build_render_plan(second_frame)
        second_vehicle_rect = next(
            command.rectangle for command in second_plan.commands
            if command.entity_id == "handcart"
        )

        self.assertEqual(self.simulation.tick, initial_tick + 1)
        self.assertEqual(second_frame.simulation_tick, self.simulation.tick)
        self.assertEqual(second_frame.world_tick, self.simulation.world.current_tick)
        self.assertEqual(dict(second_frame.environment)["day"], 2)
        self.assertEqual(second_frame.camera, initial_camera)
        moved_vehicle_position = next(
            entity.position for entity in second_frame.entities
            if entity.entity_id == "handcart"
        )
        self.assertAlmostEqual(moved_vehicle_position[0], 11.4422859)
        self.assertAlmostEqual(moved_vehicle_position[1], 7.4120817)
        self.assertNotEqual(initial_vehicle_position, moved_vehicle_position)
        self.assertNotEqual(first_vehicle_rect, second_vehicle_rect)
        construction_record = next(
            entity for entity in second_frame.entities
            if entity.kind == "construction" and entity.entity_id == "clinic-project"
        )
        self.assertEqual(dict(construction_record.details)["work_completed"], 0.0)
        worker_record = next(
            entity for entity in second_frame.entities
            if entity.kind == "citizen" and entity.entity_id == "citizen-mira"
        )
        self.assertEqual(dict(worker_record.details)["movement_status"], "moving")
        self.assertEqual(first_frame.simulation_tick, 0)
        self.assertNotEqual(first_plan.overlay_text, second_plan.overlay_text)
        self.assertIn("Day 2", second_plan.overlay_text)
        self.assertIn("Resources:", second_plan.overlay_text)
        self.assertTrue(second_plan.commands)
        self.assertEqual(self.simulation.citizens[0].location, original_citizen_position)
        self.assertFalse(any(type(entity).__name__ == "Citizen" for entity in second_frame.entities))

        detached_position = next(
            entity.position for entity in second_frame.entities
            if entity.kind == "citizen" and entity.entity_id == "citizen-ada"
        )
        self.simulation.citizens[0].location = (7, 9)
        self.assertEqual(
            next(entity.position for entity in second_frame.entities
                 if entity.kind == "citizen" and entity.entity_id == "citizen-ada"),
            detached_position,
        )

    def test_pause_resume_and_single_step_control_exact_tick_count(self):
        self.assertTrue(self.controller.paused)
        paused_frame = self.controller.advance_frame()
        self.assertEqual(paused_frame.simulation_tick, 0)
        self.assertEqual(self.simulation.tick, 0)

        stepped = self.controller.step_once()
        self.assertEqual(stepped.simulation_tick, 1)
        self.assertEqual(self.simulation.tick, 1)
        self.assertTrue(self.controller.paused)

        self.controller.resume()
        running_frame = self.controller.advance_frame()
        self.assertEqual(running_frame.simulation_tick, 2)
        self.assertFalse(self.controller.paused)

        self.controller.pause()
        frozen = self.controller.advance_frame()
        self.assertEqual(frozen.simulation_tick, 2)
        self.assertEqual(self.simulation.tick, 2)
        self.assertTrue(self.controller.paused)

    def test_camera_controls_survive_frame_replacement_and_do_not_change_world(self):
        citizen_locations = tuple(citizen.location for citizen in self.simulation.citizens)
        self.controller.pan(3, 2)
        self.controller.zoom(1.5)
        self.assertEqual(
            tuple(citizen.location for citizen in self.simulation.citizens),
            citizen_locations,
        )
        camera_before = self.controller.camera
        self.controller.resume()
        frame = self.controller.advance_frame()
        self.assertEqual(frame.camera, camera_before)
        self.assertNotEqual(self.simulation.citizens[2].location, citizen_locations[2])
        self.assertEqual(self.simulation.citizens[0].location, citizen_locations[0])
        self.assertEqual(self.controller.camera, camera_before)

        self.controller.set_viewport(800, 500)
        self.assertEqual(self.controller.camera.position, camera_before.position)
        self.assertEqual(self.controller.camera.zoom, camera_before.zoom)

    def test_reset_replaces_engine_and_keeps_camera_presentation_state(self):
        self.controller.pan(4, 5)
        self.controller.resume()
        self.controller.advance_frame()
        camera = self.controller.camera
        reset_frame = self.controller.reset()
        self.assertEqual(reset_frame.simulation_tick, 0)
        self.assertEqual(reset_frame.camera, camera)
        self.assertTrue(self.controller.paused)
        self.assertIsNot(self.simulation, self.controller._simulation)

    def test_frame_generation_and_render_plan_do_not_advance_engine(self):
        before = (self.simulation.tick, self.simulation.world.current_tick)
        frame = self.controller.current_frame()
        build_scene_frame(snapshot_simulation(self.simulation), self.camera)
        build_render_plan(frame)
        self.assertEqual((self.simulation.tick, self.simulation.world.current_tick), before)

    def test_step_error_stops_a_running_engine_and_reports_failure(self):
        self.controller.resume()
        with mock.patch.object(self.simulation, "step", side_effect=RuntimeError("tick failed")):
            with self.assertRaisesRegex(RuntimeError, "tick failed"):
                self.controller.advance_frame()
        self.assertTrue(self.controller.paused)

    def test_reset_requires_an_explicit_simulation_factory(self):
        controller = LiveVisualizationController(self.simulation, self.camera)
        with self.assertRaisesRegex(RuntimeError, "simulation factory"):
            controller.reset()

    def test_new_and_changed_engine_entities_appear_in_the_next_live_frame(self):
        market_site = self.simulation.world.get_building("market")
        vehicle = self.simulation.world.transportation.get_vehicle("wagon")

        before = self.controller.current_frame()
        vehicle.move_to((30, 16))
        self.simulation.citizens[0].die()
        self.simulation.world.add_building(
            Building("new-building", "new_building", (8, 16), dimensions=(3, 2),
                     construction_status="completed"),
        )
        after = self.controller.current_frame()
        entities = {(entity.kind, entity.entity_id): entity for entity in after.entities}

        self.assertEqual(entities[("vehicle", "wagon")].position, (30.0, 16.0))
        self.assertEqual(entities[("citizen", "citizen-ada")].state, "dead")
        self.assertEqual(entities[("construction", "clinic-project")].state, "under_construction")
        self.assertIn(("building", "new-building"), entities)
        self.assertEqual(
            dict(entities[("business", "town-market")].details)["building_id"],
            market_site.building_id,
        )
        self.assertNotIn("citizen-ada", {
            command.entity_id for command in build_render_plan(after).commands
        })
        self.simulation.world.transportation.remove_vehicle(vehicle)
        removed = self.controller.current_frame()
        self.assertNotIn(("vehicle", "wagon"), {
            (entity.kind, entity.entity_id) for entity in removed.entities
        })
        self.assertNotIn("wagon", {
            command.entity_id for command in build_render_plan(removed).commands
        })
        self.assertNotEqual(before.entities, after.entities)

    def test_construction_advances_and_completes_once_through_ticks(self):
        project = self.simulation.construction_projects[0]
        worker = self.simulation.citizens[2]
        self.assertEqual(self.simulation.world.get_resource("wood"), 82)
        self.assertEqual(self.simulation.world.get_resource("stone"), 45)
        self.assertEqual(project.work_completed, 0)

        self.controller.resume()
        one = self.controller.advance_frame()
        self.assertEqual(project.work_completed, 0)
        self.assertEqual(self.simulation.world.get_resource("wood"), 84)
        self.assertEqual(worker.location, (19.8358289998256, 11.2910427500436))
        one_plan = build_render_plan(one)
        construction_command = next(
            command for command in one_plan.commands
            if command.entity_id == "clinic-project"
        )
        self.assertEqual(dict(construction_command.details)["work_completed"], 0.0)
        self.assertNotIn("clinic", {command.entity_id for command in one_plan.commands})

        for _ in range(3):
            frame = self.controller.advance_frame()
        self.assertEqual(worker.location, (17.0, 12.0))
        self.assertEqual(project.work_completed, 0)

        one = self.controller.advance_frame()
        self.assertEqual(project.work_completed, 10)
        self.controller.advance_frame()
        self.assertEqual(project.work_completed, 20)
        three = self.controller.advance_frame()
        self.assertEqual(project.work_completed, project.work_required)
        self.assertEqual(project.status, "completed")
        self.assertEqual(project.building.construction_status, "completed")
        self.assertEqual(self.simulation.world.get_resource("wood"), 96)

        completed_plan = build_render_plan(three)
        self.assertNotIn("clinic-project", {
            command.entity_id for command in completed_plan.commands
        })
        self.assertIn("clinic", {
            command.entity_id for command in completed_plan.commands
        })
        self.controller.advance_frame()
        self.assertEqual(project.work_completed, project.work_required)
        self.assertEqual(worker.is_alive(), True)


if __name__ == "__main__":
    unittest.main()
