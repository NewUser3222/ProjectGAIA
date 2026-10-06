import unittest
from unittest import mock
from dataclasses import replace

from src.gaia.agents.citizen import Citizen
from src.gaia.building import Building
from src.gaia.business import Business
from src.gaia.construction import BuildingDefinition, ConstructionProject
from src.gaia.core.simulation import Simulation
from src.gaia.vehicle import Vehicle
from src.gaia.visualization import (
    Camera,
    FrameEntity,
    ScreenRect,
    Footprint,
    SceneFrame,
    VisualizationSnapshot,
    VisualEntity,
    WorldScene,
    build_scene_frame,
    project_position,
    snapshot_simulation,
)


class TestVisualizationScene(unittest.TestCase):
    def make_synthetic_world(self):
        simulation = Simulation()
        simulation.world.width = 20
        simulation.world.height = 10
        simulation.tick = 4
        simulation.world.current_tick = 4
        ada = Citizen("c2", "Ada", age=30, location=(12.5, 5.0))
        lee = Citizen("c1", "Lee", age=20, location=[0, 0])
        lee.die()
        simulation.add_citizen(ada)
        simulation.add_citizen(lee)
        market = Business("biz1", "Market")
        simulation.add_business(market)
        simulation.add_business(Business("biz2", "Unplaced"))
        site = Building("b1", "shop", [3, 4], dimensions=[2, 1], construction_status="completed")
        site.set_associated_business(market)
        simulation.world.add_building(site)
        simulation.world.add_building(Building(
            "b_large", "storehouse", (5, 3), dimensions=(14, 9),
            construction_status="completed",
        ))
        simulation.world.transportation.add_vehicle(Vehicle("v1", "cart", (19.5, 9.5)))
        simulation.world.transportation.add_vehicle(Vehicle("v2", "handcart", (9.75, 0.25)))
        project = ConstructionProject(
            "p1", simulation.world,
            BuildingDefinition("home", {"wood": 2}), "b2", (8.25, 2.5),
            dimensions=(3, 2),
        )
        simulation.add_construction_project(project)
        simulation.world.set_resource("food", 17)
        simulation.world.environment.weather = "rain"
        return simulation

    def test_synthetic_world_captures_supported_entities_and_relationships(self):
        simulation = self.make_synthetic_world()
        before = (simulation.tick, simulation.world.current_tick,
                  tuple((c.age, c.location, c.lifecycle_state) for c in simulation.citizens),
                  dict(simulation.world.resources))
        scene = snapshot_simulation(simulation)

        self.assertEqual(scene.bounds, (20, 10))
        self.assertEqual((scene.population, scene.living_population), (2, 1))
        self.assertEqual(dict(scene.environment)["weather"], "rain")
        self.assertEqual(
            [(entity.kind, entity.entity_id) for entity in scene.entities],
            [("building", "b1"), ("building", "b_large"),
             ("business", "biz1"), ("business", "biz2"),
             ("citizen", "c1"), ("citizen", "c2"),
             ("construction", "p1"), ("vehicle", "v1"), ("vehicle", "v2")],
        )
        indexed = {(entity.kind, entity.entity_id): entity for entity in scene.entities}
        self.assertEqual(indexed[("citizen", "c2")].position, (12.5, 5.0))
        self.assertEqual(indexed[("building", "b1")].position, (3, 4))
        self.assertEqual(indexed[("building", "b1")].footprint.width, 2.0)
        self.assertEqual(indexed[("building", "b1")].footprint.size_source, "simulation")
        self.assertEqual(indexed[("building", "b_large")].footprint.width, 14.0)
        self.assertEqual(indexed[("vehicle", "v1")].position, (19.5, 9.5))
        self.assertEqual(indexed[("construction", "p1")].position, (8.25, 2.5))
        self.assertEqual(indexed[("construction", "p1")].footprint.height, 2.0)
        self.assertEqual(indexed[("business", "biz1")].position, (4.0, 4.5))
        self.assertEqual(dict(indexed[("business", "biz1")].details)["building_id"], "b1")
        self.assertIsNone(indexed[("business", "biz2")].position)
        resources = {item.name: item for item in scene.resources}
        self.assertEqual(resources["food"].quantity, 17)
        self.assertIsNone(resources["food"].position)
        self.assertEqual(before, (simulation.tick, simulation.world.current_tick,
                                 tuple((c.age, c.location, c.lifecycle_state) for c in simulation.citizens),
                                 simulation.world.resources))

    def test_snapshot_is_deterministic_and_stably_ordered(self):
        simulation = self.make_synthetic_world()
        first = snapshot_simulation(simulation)
        second = snapshot_simulation(simulation)
        self.assertIsInstance(first, WorldScene)
        self.assertIsInstance(second, WorldScene)
        self.assertEqual(first, second)
        self.assertEqual(first.resources, tuple(sorted(first.resources, key=lambda item: item.name)))

    def test_snapshot_is_detached_and_nested_values_are_immutable(self):
        simulation = self.make_synthetic_world()
        scene = snapshot_simulation(simulation)
        lee = next(item for item in scene.entities if item.entity_id == "c1")
        building = next(item for item in scene.entities if item.kind == "building")
        food = next(item for item in scene.resources if item.name == "food")

        simulation.citizens[1].location[0] = 7
        simulation.world.buildings[0].dimensions[0] = 9
        simulation.world.resources["food"] = 999
        self.assertEqual(lee.position, (0, 0))
        self.assertEqual(dict(building.details)["dimensions"], (2, 1))
        self.assertEqual((building.footprint.width, building.footprint.height), (2.0, 1.0))
        self.assertEqual(food.quantity, 17)
        self.assertTrue(all(type(item).__name__ == "VisualEntity" for item in scene.entities))
        self.assertFalse(any(value is simulation.citizens[0] for value in scene.entities))
        with self.assertRaises((AttributeError, TypeError)):
            scene.entities = ()
        with self.assertRaises(TypeError):
            scene.entities[0].details[0] = ("changed", True)

    def test_empty_world_and_unplaced_business_are_safe(self):
        simulation = Simulation()
        simulation.add_business(Business("b0", "Unplaced"))
        scene = snapshot_simulation(simulation)
        self.assertEqual(scene.population, 0)
        self.assertEqual(len(scene.entities), 1)
        self.assertIsNone(scene.entities[0].position)
        self.assertTrue(all(resource.position is None for resource in scene.resources))
        self.assertIs(VisualizationSnapshot, WorldScene)

    def test_snapshot_does_not_run_actions(self):
        simulation = self.make_synthetic_world()
        with mock.patch.object(simulation.decision_engine, "select_best_action", side_effect=AssertionError("action selection called")):
            before = snapshot_simulation(simulation)
            after = snapshot_simulation(simulation)
        self.assertEqual(before, after)

    def test_rejects_invalid_input(self):
        with self.assertRaises(TypeError):
            snapshot_simulation(None)


class TestCoordinateProjection(unittest.TestCase):
    def setUp(self):
        self.simulation = Simulation()
        self.simulation.world.width = 20
        self.simulation.world.height = 10
        self.scene = snapshot_simulation(self.simulation)

    def test_origin_and_non_square_world_map_to_normalized_viewport(self):
        origin = project_position(self.scene, (0, 0), (200, 100))
        point = project_position(self.scene, (10, 5), (200, 100))
        self.assertEqual(origin.normalized_position, (0.0, 0.0))
        self.assertEqual(origin.viewport_position, (0.0, 0.0))
        self.assertTrue(origin.inside_world)
        self.assertEqual(point.normalized_position, (0.5, 0.5))
        self.assertEqual(point.viewport_position, (100.0, 50.0))

    def test_half_open_bounds_accept_float_edge_interior_and_reject_upper_edge(self):
        inside = project_position(self.scene, (19.999, 9.999))
        outside = project_position(self.scene, (20, 10))
        self.assertTrue(inside.inside_world)
        self.assertFalse(outside.inside_world)
        self.assertEqual(outside.normalized_position, (1.0, 1.0))

    def test_out_of_bounds_positions_are_unclamped_and_coordinates_unchanged(self):
        original = [-1.5, 3]
        projection = project_position(self.scene, original, (400, 100))
        self.assertEqual(projection.source_position, (-1.5, 3))
        self.assertEqual(projection.normalized_position, (-0.075, 0.3))
        self.assertEqual(projection.viewport_position, (-30.0, 30.0))
        self.assertFalse(projection.inside_world)
        self.assertEqual(original, [-1.5, 3])

    def test_projection_is_deterministic_and_validates_permitted_values(self):
        self.assertEqual(project_position(self.scene, (1, 2), (640, 320)),
                         project_position(self.scene, (1, 2), (640, 320)))
        for position in ((float("nan"), 1), (True, 1), ("1", 2), (1,)):
            with self.subTest(position=position), self.assertRaises(ValueError):
                project_position(self.scene, position)
        with self.assertRaises(ValueError):
            project_position(self.scene, (1, 1), (0, 100))


class TestCameraAndSceneFrame(unittest.TestCase):
    def make_world_scene(self):
        simulation = TestVisualizationScene().make_synthetic_world()
        return simulation, snapshot_simulation(simulation)

    def test_camera_defaults_custom_projection_and_inverse(self):
        default = Camera()
        self.assertEqual(default.position, (0.0, 0.0))
        self.assertEqual(default.viewport_size, (800.0, 600.0))
        self.assertEqual(default.zoom, 1.0)
        camera = Camera((3, 4), 100, 50, 2)
        self.assertEqual(camera.world_view_size, (50.0, 25.0))
        self.assertEqual(camera.world_to_screen((4, 5)), (2.0, 2.0))
        self.assertEqual(camera.screen_to_world((2, 2)), (4.0, 5.0))
        self.assertTrue(camera.contains_screen_position((0, 0)))
        self.assertFalse(camera.contains_screen_position((100, 10)))

    def test_pan_and_zoom_are_immutable_and_do_not_touch_simulation_locations(self):
        simulation, _ = self.make_world_scene()
        locations = tuple(citizen.location for citizen in simulation.citizens)
        original = Camera((0, 0), 10, 6, 1)
        moved = original.pan_by(10, 0)
        zoomed = original.zoom_by(2)
        negative = original.pan_by(-3, -4)
        self.assertEqual(original.position, (0.0, 0.0))
        self.assertEqual(moved.position, (10.0, 0.0))
        self.assertEqual(zoomed.zoom, 2.0)
        self.assertEqual(negative.position, (-3.0, -4.0))
        self.assertEqual(locations, tuple(citizen.location for citizen in simulation.citizens))
        with self.assertRaises(AttributeError):
            original.zoom = 4

    def test_camera_rejects_invalid_position_viewport_zoom_and_pan(self):
        for args in (
            ((float("nan"), 0), 100, 100, 1),
            ((0, 0), 0, 100, 1),
            ((0, 0), 100, float("inf"), 1),
            ((0, 0), 100, 100, 0),
            ((0, 0), 100, 100, float("nan")),
            ((True, 0), 100, 100, 1),
            ((0, 0), 1e-300, 1, 1e308),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                Camera(*args)
        with self.assertRaises(ValueError):
            Camera().pan_by(float("inf"), 0)

    def test_footprint_contract_validates_and_preserves_anchor_semantics(self):
        top_left = Footprint((2, 3), 4, 2, "top_left", "simulation")
        center = Footprint((2, 3), 4, 2, "center", "visualization_default")
        self.assertEqual((top_left.left, top_left.top, top_left.right, top_left.bottom),
                         (2.0, 3.0, 6.0, 5.0))
        self.assertEqual((center.left, center.top, center.right, center.bottom),
                         (0.0, 2.0, 4.0, 4.0))
        for values in (
            ((0, 0), 0, 1, "center", "simulation"),
            ((0, 0), float("inf"), 1, "center", "simulation"),
            ((0, 0), 1, 1, "unknown", "simulation"),
            ((0, 0), 1, 1, "center", "physical_guess"),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Footprint(*values)

    def test_invalid_simulation_dimensions_produce_no_footprint(self):
        simulation, _ = self.make_world_scene()
        invalid = Building("bad", "ruin", (1, 1), dimensions=(0, 2))
        simulation.world.add_building(invalid)
        scene = snapshot_simulation(simulation)
        invalid_view = next(item for item in scene.entities if item.entity_id == "bad")
        frame = build_scene_frame(scene, Camera((0, 0), 10, 6))
        invalid_frame = next(item for item in frame.entities if item.entity_id == "bad")
        self.assertIsNone(invalid_view.footprint)
        self.assertEqual(invalid_frame.visibility, "invalid_footprint")
        self.assertFalse(invalid_frame.visible)

    def test_scene_frame_culls_projects_and_orders_synthetic_world(self):
        simulation, scene = self.make_world_scene()
        camera = Camera((0, 0), 10, 6, 1)
        before = (simulation.tick, simulation.world.current_tick,
                  tuple(citizen.location for citizen in simulation.citizens),
                  dict(simulation.world.resources))
        frame = build_scene_frame(scene, camera)
        self.assertIsInstance(frame, SceneFrame)
        self.assertEqual((frame.simulation_tick, frame.world_tick), (4, 4))
        self.assertEqual(frame.world_bounds, (20.0, 10.0))
        self.assertEqual(frame.camera, camera)
        self.assertEqual(dict(frame.environment)["weather"], "rain")
        self.assertEqual(next(r for r in frame.resources if r.name == "food").quantity, 17)
        visible = frame.render_entities
        self.assertEqual(
            [(item.kind, item.entity_id) for item in visible],
            [("construction", "p1"), ("building", "b_large"), ("building", "b1"),
             ("business", "biz1"), ("vehicle", "v2"), ("citizen", "c1")],
        )
        self.assertEqual(visible[0].screen_position, (8.25, 2.5))
        self.assertEqual(visible[0].viewport_relation, "partial")
        self.assertEqual(visible[0].screen_footprint.width, 3.0)
        large = next(item for item in visible if item.entity_id == "b_large")
        self.assertEqual(large.viewport_relation, "partial")
        self.assertEqual((large.screen_footprint.width, large.screen_footprint.height), (14.0, 9.0))
        edge_vehicle = next(item for item in visible if item.entity_id == "v2")
        self.assertEqual(edge_vehicle.viewport_relation, "partial")
        self.assertEqual(visible[-1].screen_position, (0.0, 0.0))
        self.assertEqual([layer.name for layer in frame.layers], [
            "background", "construction", "buildings", "businesses",
            "vehicles", "citizens", "foreground",
        ])
        culled = {(item.kind, item.entity_id): item for item in frame.culled_entities}
        self.assertEqual(culled[("citizen", "c2")].visibility, "outside_viewport")
        self.assertEqual(culled[("vehicle", "v1")].visibility, "outside_viewport")
        self.assertEqual(culled[("business", "biz2")].visibility, "unplaced")
        self.assertEqual(large.world_relation, "partial")
        shop = next(item for item in visible if item.entity_id == "b1")
        self.assertEqual(shop.viewport_relation, "inside")
        self.assertEqual(culled[("citizen", "c2")].viewport_relation, "outside")
        self.assertEqual(before, (simulation.tick, simulation.world.current_tick,
                                 tuple(citizen.location for citizen in simulation.citizens),
                                 simulation.world.resources))

    def test_camera_pan_and_zoom_change_visibility_without_changing_scene(self):
        _, scene = self.make_world_scene()
        original_positions = tuple(item.position for item in scene.entities)
        small = Camera((0, 0), 10, 6, 1)
        moved = build_scene_frame(scene, small.pan_by(10, 0))
        zoomed_out = build_scene_frame(scene, small.with_zoom(0.5))
        zoomed_in = build_scene_frame(scene, small.with_zoom(2))
        baseline = build_scene_frame(scene, small)
        self.assertIn(("citizen", "c2"), {(item.kind, item.entity_id) for item in moved.render_entities})
        ada = next(item for item in moved.render_entities if item.entity_id == "c2")
        self.assertEqual(ada.world_position, (12.5, 5.0))
        self.assertEqual(ada.screen_position, (2.5, 5.0))
        self.assertIn(("vehicle", "v1"), {(item.kind, item.entity_id) for item in zoomed_out.render_entities})
        zoomed_vehicle = next(item for item in zoomed_out.render_entities if item.entity_id == "v1")
        self.assertEqual(zoomed_vehicle.screen_footprint.width, 0.5)
        self.assertNotIn(("building", "b1"), {(item.kind, item.entity_id) for item in zoomed_in.render_entities})
        for variant in (moved, zoomed_out, zoomed_in):
            self.assertEqual(
                [item.layer for item in variant.render_entities],
                sorted(item.layer for item in variant.render_entities),
            )
            baseline_ids = [(item.kind, item.entity_id) for item in baseline.render_entities]
            variant_ids = [(item.kind, item.entity_id) for item in variant.render_entities]
            shared = set(baseline_ids) & set(variant_ids)
            self.assertEqual([item for item in baseline_ids if item in shared],
                             [item for item in variant_ids if item in shared])
        self.assertEqual(original_positions, tuple(item.position for item in scene.entities))

    def test_viewport_edges_negative_and_out_of_world_positions(self):
        _, scene = self.make_world_scene()
        boundary = VisualEntity(
            "edge", "citizen", "Edge", (10, 6), "alive", (),
            Footprint((10, 6), 1, 1, "top_left", "visualization_default"), "available",
        )
        right_edge = VisualEntity(
            "right", "citizen", "Right edge", (10, 2), "alive", (),
            Footprint((10, 2), 1, 1, "center", "visualization_default"), "available",
        )
        bottom_edge = VisualEntity(
            "bottom", "citizen", "Bottom edge", (2, 6), "alive", (),
            Footprint((2, 6), 1, 1, "center", "visualization_default"), "available",
        )
        outside_world = VisualEntity(
            "negative", "citizen", "Negative", (-0.25, -0.25), "alive", (),
            Footprint((-0.25, -0.25), 1, 1, "center", "visualization_default"), "available",
        )
        fully_outside_world = VisualEntity(
            "offworld", "building", "Offworld", (-3, -3), "planned", (),
            Footprint((-3, -3), 1, 1, "top_left", "visualization_default"), "available",
        )
        malformed = VisualEntity("malformed", "citizen", "Malformed", ("x", 2), "alive")
        scene = replace(scene, entities=scene.entities + (
            boundary, right_edge, bottom_edge, outside_world,
            fully_outside_world, malformed,
        ))
        camera = Camera((0, 0), 10, 6, 1)
        frame = build_scene_frame(scene, camera)
        indexed = {(item.kind, item.entity_id): item for item in frame.entities}
        self.assertEqual(indexed[("citizen", "negative")].screen_position, (-0.25, -0.25))
        self.assertTrue(indexed[("citizen", "negative")].visible)
        self.assertFalse(indexed[("citizen", "negative")].inside_world)
        self.assertEqual(indexed[("citizen", "negative")].world_relation, "partial")
        self.assertFalse(indexed[("citizen", "edge")].visible)
        self.assertEqual(indexed[("citizen", "edge")].visibility, "outside_viewport")
        self.assertEqual(indexed[("citizen", "edge")].position, (10, 6))
        self.assertEqual(indexed[("citizen", "right")].viewport_relation, "partial")
        self.assertEqual(indexed[("citizen", "bottom")].viewport_relation, "partial")
        self.assertEqual(indexed[("building", "offworld")].world_relation, "outside")
        self.assertEqual(indexed[("citizen", "malformed")].visibility, "invalid_position")

    def test_empty_scene_frame_and_frame_determinism(self):
        empty = snapshot_simulation(Simulation())
        camera = Camera((0, 0), 12, 8, 1.25)
        first = build_scene_frame(empty, camera)
        second = build_scene_frame(empty, camera)
        self.assertEqual(first, second)
        self.assertEqual(first.entities, ())
        self.assertEqual(first.render_entities, ())

    def test_frame_generation_does_not_select_actions_or_expose_engine_dependencies(self):
        simulation, scene = self.make_world_scene()
        camera = Camera((0, 0), 10, 6)
        import src.gaia.visualization as visualization_module
        for forbidden in ("Simulation", "GAIAGovernor", "GAIAObserver", "SQLiteHistoryStore", "sqlite3"):
            self.assertNotIn(forbidden, vars(visualization_module))
        with mock.patch.object(simulation.decision_engine, "select_best_action", side_effect=AssertionError("action selection called")):
            first = build_scene_frame(scene, camera)
            second = build_scene_frame(scene, camera)
        self.assertEqual(first, second)
        self.assertEqual((simulation.tick, simulation.world.current_tick), (4, 4))
        self.assertTrue(all(isinstance(item, FrameEntity) for item in first.entities))
        self.assertIsInstance(first.render_entities[0].screen_footprint, ScreenRect)
        with self.assertRaises((AttributeError, TypeError)):
            first.render_entities[0].screen_footprint.x = 99


if __name__ == "__main__":
    unittest.main()
