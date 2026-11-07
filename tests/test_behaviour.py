from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from behaviour import World, interest_point
from bridge import validate_page


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.world = World(["Burt", "Cody", "Victoria"], (0, 0, 1600, 900), (1200, 600), rng=random.Random(4))

    def advance(self, seconds=50):
        arrived = []
        for i in range(int(seconds/.1)):
            arrived.extend(self.world.step(.1, i*.1))
        return arrived

    def test_wake_leaves_house_and_moves_inside_screen(self):
        self.world.wake("Burt", 0)
        start = self.world.residents["Burt"].x, self.world.residents["Burt"].y
        self.advance(2)
        resident = self.world.residents["Burt"]
        self.assertNotEqual(start, (resident.x, resident.y))
        self.assertTrue(0 <= resident.x <= 1410 and 0 <= resident.y <= 670)

    def test_return_home_eventually_hides_the_character(self):
        self.world.wake("Burt", 0)
        self.advance(2)
        self.world.rest("Burt", 2)
        self.advance(30)
        resident = self.world.residents["Burt"]
        self.assertEqual(resident.mode, "home")
        self.assertEqual((resident.x, resident.y), self.world.home)

    def test_rest_and_wake_cycles_respect_pause_budget_and_games(self):
        for resident in self.world.residents.values():
            resident.wake_at = 5
        self.world.residents["Victoria"].blocked = True
        self.assertEqual(self.world.due(6, [], ["Burt", "Victoria"]), [("wake", "Burt")])
        self.world.wake("Burt", 6)
        self.world.residents["Burt"].rest_at = 7
        self.assertIn(("sleep", "Burt"), self.world.due(8, ["Burt"], ["Burt"]))
        self.assertEqual(self.world.due(8, ["Burt"], [], busy=["Burt"]), [])
        self.assertEqual(self.world.due(8, ["Burt"], ["Burt"], playing=True), [])
        self.world.paused = True
        self.assertEqual(self.world.due(1000, [], ["Burt", "Cody"]), [])

    def test_interest_approaches_beside_target_then_points(self):
        self.world.wake("Cody", 0)
        self.world.inspect("Cody", (600, 400, "a picture"), 0, "That picture!")
        resident = self.world.residents["Cody"]
        self.assertEqual(resident.mode, "approaching")
        self.assertEqual(resident.gaze, (600, 400))
        self.assertNotEqual(resident.goal, (600, 400))
        arrived = self.advance(8)
        self.assertIn("Cody", arrived)
        self.assertEqual(resident.mode, "interested")
        self.assertEqual(resident.pending_speech, "That picture!")

    def test_autonomy_off_holds_position_but_allows_return_home(self):
        self.world.wake("Burt", 0)
        resident = self.world.residents["Burt"]
        before = resident.x, resident.y
        self.world.step(.1, 1, autonomous=False)
        self.assertEqual(before, (resident.x, resident.y))
        resident.x = 10
        self.world.rest("Burt", 2)
        self.world.step(.1, 3, autonomous=False)
        self.assertGreater(resident.x, 10)

    def test_manual_drag_hold_prevents_fighting_the_user(self):
        self.world.wake("Burt", 0)
        resident = self.world.residents["Burt"]
        resident.held_until = 30
        before = resident.x, resident.y
        self.world.step(.1, 5)
        self.assertEqual(before, (resident.x, resident.y))


class TargetTests(unittest.TestCase):
    def test_screenshot_coordinates_map_to_the_observed_window(self):
        point = interest_point({"kind": "image", "bounds": [100, 200, 900, 800]}, {"x": .5, "y": .5, "label": "a cat"})
        self.assertEqual(point, (500, 500, "a cat"))

    def test_browser_target_is_resolved_using_viewport_and_toolbar(self):
        page = {"kind": "page", "bounds": [100, 100, 1100, 900],
                "viewport": {"width": 1000, "height": 700, "outerWidth": 1000, "outerHeight": 800},
                "targets": [{"label": "Title", "x": .5, "y": .5}]}
        self.assertEqual(interest_point(page, {"target": 0}), (600, 550, "Title"))
        self.assertIsNone(interest_point(page, {"target": 10}))
        self.assertIsNone(interest_point(page, {"x": .5, "y": .5}))

    def test_invalid_and_stale_geometry_is_rejected(self):
        self.assertIsNone(interest_point({}, {"x": .5, "y": .5}))
        for value in (-1, 2, float('nan'), float('inf'), True, "0.5"):
            self.assertIsNone(interest_point({"kind": "image", "bounds": [0, 0, 800, 600]}, {"x": value, "y": .5}))

    def test_bridge_filters_untrusted_target_metadata(self):
        page = validate_page({"title": "Test", "url": "https://example.com", "text": "Hello",
                              "targets": [{"label": "Header", "x": .5, "y": .2}, {"label": "Bad", "x": float('nan'), "y": .2}],
                              "viewport": {"width": 1000, "height": 600, "outerWidth": "bad", "outerHeight": float('inf')}})
        self.assertEqual(len(page["targets"]), 1)
        self.assertEqual(page["viewport"], {"width": 1000, "height": 600})


if __name__ == "__main__":
    unittest.main()
