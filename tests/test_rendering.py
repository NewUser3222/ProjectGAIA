import sys
import subprocess
import unittest

from src.gaia.rendering import TkCanvasRenderer, build_render_plan
from src.gaia.visualization import Camera, build_scene_frame
from src.gaia.visualization_demo import build_demo_world_scene


class RecordingCanvas:
    def __init__(self):
        self.operations = []

    def delete(self, *args):
        self.operations.append(("delete", args, {}))

    def configure(self, **kwargs):
        self.operations.append(("configure", (), kwargs))

    def create_line(self, *args, **kwargs):
        self.operations.append(("line", args, kwargs))

    def create_rectangle(self, *args, **kwargs):
        self.operations.append(("rectangle", args, kwargs))

    def create_oval(self, *args, **kwargs):
        self.operations.append(("oval", args, kwargs))

    def create_text(self, *args, **kwargs):
        self.operations.append(("text", args, kwargs))


class TestRenderPlan(unittest.TestCase):
    def make_frame(self, camera=None):
        scene = build_demo_world_scene()
        camera = camera or Camera((0, 0), 800, 540, 24)
        return scene, build_scene_frame(scene, camera)

    def test_synthetic_town_produces_all_supported_drawable_entity_kinds(self):
        _, frame = self.make_frame()
        plan = build_render_plan(frame)
        kinds = {command.kind for command in plan.commands}
        self.assertEqual(kinds, {"building", "business", "vehicle", "citizen", "construction"})
        self.assertTrue(any(command.kind == "construction" and command.style == "construction"
                            for command in plan.commands))
        self.assertEqual(tuple(command.layer for command in plan.commands),
                         tuple(sorted(command.layer for command in plan.commands)))

    def test_plan_is_deterministic_and_preserves_frame_geometry_and_labels(self):
        _, frame = self.make_frame()
        first = build_render_plan(frame)
        second = build_render_plan(frame)
        self.assertEqual(first, second)
        by_id = {command.entity_id: command for command in first.commands}
        for entity in frame.render_entities:
            self.assertEqual(by_id[entity.entity_id].rectangle, entity.screen_footprint)
        self.assertEqual(by_id["market-1"].label, "Market Co-op")

    def test_outside_and_unplaced_entities_are_not_drawn(self):
        scene, frame = self.make_frame(Camera((50, 50), 800, 540, 24))
        plan = build_render_plan(frame)
        drawn_ids = {command.entity_id for command in plan.commands}
        self.assertNotIn("future-business", drawn_ids)
        self.assertNotIn("large-storehouse", drawn_ids)
        self.assertEqual(drawn_ids, set())
        self.assertTrue(any(item.entity_id == "future-business" for item in frame.culled_entities))
        self.assertTrue(any(item.entity_id == "large-storehouse" for item in frame.culled_entities))

    def test_empty_frame_has_background_and_no_entity_commands(self):
        scene = build_demo_world_scene()
        from dataclasses import replace
        scene = replace(scene, entities=())
        frame = build_scene_frame(scene, Camera((0, 0), 640, 480, 10))
        plan = build_render_plan(frame)
        self.assertEqual(plan.commands, ())
        self.assertEqual(plan.background_style, "world")

    def test_canvas_backend_consumes_detached_frame_and_is_repeatable(self):
        _, frame = self.make_frame()
        camera = frame.camera
        canvas = RecordingCanvas()
        renderer = TkCanvasRenderer(canvas)
        plan = renderer.draw_frame(frame)
        self.assertEqual(frame.camera, camera)
        self.assertEqual(frame, build_scene_frame(build_demo_world_scene(), camera))
        first_operations = tuple(canvas.operations)
        canvas.operations.clear()
        self.assertEqual(renderer.draw_frame(frame), plan)
        self.assertEqual(tuple(canvas.operations), first_operations)
        self.assertTrue(any(operation[0] == "oval" for operation in canvas.operations))
        self.assertTrue(any(operation[0] == "rectangle" for operation in canvas.operations))
        self.assertTrue(any(
            operation[0] == "rectangle" and operation[2].get("fill") == "#ffd166"
            for operation in canvas.operations
        ))
        self.assertTrue(any(operation[0] == "text" for operation in canvas.operations))

    def test_camera_changes_screen_geometry_not_world_scene_data(self):
        scene = build_demo_world_scene()
        source = next(entity for entity in scene.entities if entity.entity_id == "home-1")
        original_position, original_footprint = source.position, source.footprint
        first = build_render_plan(build_scene_frame(scene, Camera((0, 0), 800, 540, 20)))
        second = build_render_plan(build_scene_frame(scene, Camera((1, 1), 800, 540, 30)))
        first_rect = next(item.rectangle for item in first.commands if item.entity_id == "home-1")
        second_rect = next(item.rectangle for item in second.commands if item.entity_id == "home-1")
        self.assertNotEqual(first_rect, second_rect)
        self.assertEqual((source.position, source.footprint), (original_position, original_footprint))

    def test_renderer_modules_do_not_import_simulation_authority_or_storage(self):
        check = (
            "import sys; import src.gaia.rendering, src.gaia.visualization_demo; "
            "blocked={'src.gaia.core.simulation','src.gaia.governor',"
            "'src.gaia.observer','src.gaia.persistence','sqlite3'}; "
            "assert not (blocked & sys.modules.keys()), blocked & sys.modules.keys()"
        )
        result = subprocess.run(
            [sys.executable, "-c", check], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
