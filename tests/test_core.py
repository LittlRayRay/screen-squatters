import io
import json
from pathlib import Path
import queue
import sys
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai import companion_turn, payload
from house import House, CHARACTERS
from games import Mafia, TicTacToe
from screen import browser_snapshot_matches, png_rgb
import tempfile
import random
from bridge import BridgeServer, validate_page

PAGE = {"title": "Example", "url": "https://example.com/article?secret=1#private", "text": "Hello world"}


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inbox = queue.Queue(maxsize=1)
        cls.server = BridgeServer("a" * 48, cls.inbox, port=0)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/page"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def setUp(self):
        while not self.inbox.empty():
            self.inbox.get_nowait()

    def post(self, data=PAGE, headers=None):
        hdr = {"Authorization": "Bearer " + "a" * 48, "Content-Type": "application/json"}
        hdr.update(headers or {})
        raw = data if isinstance(data, bytes) else json.dumps(data).encode()
        request = urllib.request.Request(self.url, data=raw, headers=hdr, method="POST")
        # Ignore machine proxy configuration for the loopback integration test.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=3) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_extension_page_delivery_and_url_redaction(self):
        status, result = self.post(headers={"Origin": "chrome-extension://example"})
        self.assertEqual(status, 200)
        self.assertEqual(result["characters"], 11)
        self.assertEqual(self.inbox.get_nowait()["url"], "https://example.com/article")

    def test_wrong_token_rejected(self):
        self.assertEqual(self.post(headers={"Authorization": "Bearer wrong"})[0], 403)
        self.assertTrue(self.inbox.empty())

    def test_web_origin_rejected_even_with_token(self):
        self.assertEqual(self.post(headers={"Origin": "https://evil.example"})[0], 403)

    def test_rebinding_host_rejected(self):
        self.assertEqual(self.post(headers={"Host": "evil.example"})[0], 403)

    def test_malformed_payload_rejected(self):
        for data in (b"not json", [], {**PAGE, "text": 42}, {**PAGE, "url": "file:///secret"}):
            self.assertEqual(self.post(data)[0], 400)

    def test_body_limit(self):
        self.assertEqual(self.post(b"x" * 100001)[0], 413)

    def test_queue_limit(self):
        self.assertEqual(self.post()[0], 200)
        self.assertEqual(self.post()[0], 429)

    def test_snapshot_limit(self):
        self.assertEqual(len(validate_page({**PAGE, "text": "a" * 30000})["text"]), 24000)

    def test_url_credentials_are_removed(self):
        self.assertEqual(validate_page({**PAGE, "url": "https://name:password@example.com/path?q=secret"})["url"], "https://example.com/path")

    def test_status_is_authenticated_and_reports_wake_state(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request(self.url.replace('/page', '/status'), headers={"Authorization": "Bearer " + "a" * 48})
        self.server.awake = True
        with opener.open(request) as response:
            self.assertTrue(json.load(response)["awake"])
        self.server.awake = False


class AITests(unittest.TestCase):
    def run_turn(self, remaining=5000, responses=None, cancelled=None):
        reply = {"usage": {"total_tokens": 340}, "output": [{"content": [{"type": "output_text", "text": json.dumps({"speech": "B-but what if the moon is cheese?", "memories": [{"target": "Byte", "text": "Pip has a moon cheese theory."}], "move": 4, "vote": "Rex"})}]}]}
        with patch("ai.post", side_effect=responses or [{"input_tokens": 300}, reply]) as network:
            result = companion_turn("test-only", "test-model", "Pip", [], [], ["Pip", "Byte"], "Hang out", remaining, PAGE, cancelled=cancelled)
            return result, network.call_args_list

    def test_exact_preflight_and_usage(self):
        result, calls = self.run_turn()
        self.assertEqual(result.used, 340)
        self.assertEqual(result.move, 4)
        self.assertEqual(result.memories[0]["target"], "Byte")
        self.assertEqual(calls[0].args[1], "/input_tokens")
        self.assertFalse(calls[1].args[2]["store"])

    def test_no_inference_when_input_would_exceed_budget(self):
        result, calls = self.run_turn(remaining=350)
        self.assertTrue(result.exhausted)
        self.assertEqual(result.used, 0)
        self.assertEqual(len(calls), 1)

    def test_output_is_capped_by_remaining_allowance(self):
        _result, calls = self.run_turn(remaining=450)
        self.assertEqual(calls[1].args[2]["max_output_tokens"], 150)

    def test_uncertain_request_conservatively_charges_reservation(self):
        result, _ = self.run_turn(responses=[{"input_tokens": 300}, RuntimeError("timeout")])
        self.assertEqual(result.used, 720)
        self.assertIn("timeout", result.error)

    def test_malformed_reply_still_charged(self):
        result, _ = self.run_turn(responses=[{"input_tokens": 300}, {"usage": {"total_tokens": 400}, "output": []}])
        self.assertEqual(result.used, 400)
        self.assertTrue(result.error)

    def test_missing_usage_fails_closed(self):
        result, _ = self.run_turn(responses=[{"input_tokens": 300}, {"output": []}])
        self.assertEqual(result.used, 720)
        self.assertTrue(result.error)

    def test_cancellation_between_count_and_inference(self):
        event = threading.Event()
        event.set()
        result, calls = self.run_turn(cancelled=event)
        self.assertEqual(result.used, 0)
        self.assertEqual(len(calls), 1)

    def test_context_contains_only_this_agents_memories_and_role(self):
        p = payload("model", "Rex", [{"text": "private notebook"}], [], ["Rex"], "Play", {"kind": "image", "image": "data:image/png;base64,abc"}, {"your_role": "town"})
        self.assertIn("arrogant", p["instructions"])
        self.assertEqual(p["input"][0]["content"][-1]["type"], "input_image")


class HouseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "house.json"
        self.house = House(self.path)

    def test_sleep_at_exhaustion_and_explicit_refill(self):
        self.house.recharge("Pip", 1000)
        self.house.wake("Pip")
        self.house.charge("Pip", 1000)
        self.assertFalse(self.house.agents["Pip"]["awake"])
        self.assertFalse(self.house.wake("Pip"))
        self.house.recharge("Pip", 2000)
        self.assertTrue(self.house.wake("Pip"))

    def test_memories_are_cross_agent_attributed_and_bounded(self):
        for n in range(40):
            self.house.remember("Rex", [{"target": "Byte", "text": f"Game joke {n}"}])
        self.assertEqual(len(self.house.agents["Byte"]["memories"]), 30)
        self.assertEqual(self.house.agents["Byte"]["memories"][0]["from"], "Rex")
        self.assertFalse(self.house.agents["Pip"]["memories"])

    def test_memory_cannot_target_files_or_personalities(self):
        self.assertEqual(self.house.remember("Pip", [{"target": "../ai.py", "text": "overwrite"}, None]), [])
        self.assertEqual(self.house.remember("Pip", [{"target": [], "text": "invalid model output"}]), [])

    def test_sleeping_on_restart_and_crash_reservation(self):
        self.house.wake("Pip")
        amount = self.house.reserve("Pip")
        recovered = House(self.path)
        self.assertFalse(recovered.agents["Pip"]["awake"])
        self.assertEqual(recovered.agents["Pip"]["used"], amount)
        self.assertEqual(recovered.remaining("Pip"), 0)

    def test_settlement_returns_unused_reservation(self):
        self.house.reserve("Pip")
        self.house.settle("Pip", 400)
        self.assertEqual(self.house.remaining("Pip"), 19600)

    def test_factory_reset_round_trip(self):
        self.house.remember("Rex", [{"target": "Pip", "text": "We won."}])
        self.house.charge("Byte", 1500)
        self.house.reset()
        loaded = House(self.path)
        self.assertEqual(loaded.agents["Byte"]["used"], 0)
        self.assertEqual(loaded.agents["Pip"]["memories"], [])


class GameTests(unittest.TestCase):
    def test_ttt_win_and_illegal_move(self):
        game = TicTacToe("You", "Byte")
        for player, cell in [("You", 0), ("Byte", 3), ("You", 1), ("Byte", 4), ("You", 2)]:
            game.move(player, cell)
        self.assertEqual(game.result, "You wins!")
        with self.assertRaises(ValueError):
            game.move("Byte", 5)

    def test_ttt_rejects_out_of_turn_occupied_and_boolean(self):
        game = TicTacToe("You", "Pip")
        for actor, cell in [("Pip", 0), ("You", True), ("You", -1)]:
            with self.assertRaises(ValueError):
                game.move(actor, cell)
        game.move("You", 0)
        with self.assertRaises(ValueError):
            game.move("Pip", 0)

    def test_mafia_role_is_private(self):
        game = Mafia(["You", "Pip", "Byte", "Rex"], random.Random(1))
        town = next(p for p in game.players if p != game.mafia)
        view = game.view(town)
        self.assertEqual(view["your_role"], "town")
        self.assertNotIn("mafia", view.get("roles", {}))
        game.phase = "night"
        self.assertEqual(game.view(town)["turn"], "secret night action")
        self.assertEqual(game.view(game.mafia)["your_role"], "mafia")

    def test_mafia_town_can_win_and_vote_is_validated(self):
        game = Mafia(["You", "Pip", "Byte", "Rex"], random.Random(1))
        for p in game.players:
            game.act(p)
        for p in game.players:
            if p == game.actor:
                with self.assertRaises(ValueError):
                    game.act(p, p)
                game.act(p, game.mafia if p != game.mafia else "You")
        self.assertIn("town wins", game.result)

    def test_mafia_tie_night_and_mafia_victory(self):
        game = Mafia(["You", "Pip", "Byte", "Rex"], random.Random(1))
        for p in game.players:
            game.act(p)
        for i, p in enumerate(game.players):
            game.act(p, game.players[(i+1) % 4])
        self.assertEqual(game.phase, "night")
        victim = next(p for p in game.alive if p != game.mafia)
        game.act(game.mafia, victim)
        self.assertEqual(game.phase, "discussion")
        for p in list(game.alive):
            game.act(p)
        target = next(p for p in game.alive if p != game.mafia)
        for p in list(game.alive):
            game.act(p, target if p != target else game.mafia)
        self.assertIn("mafia wins", game.result)


class ScreenTests(unittest.TestCase):
    def test_png_is_valid(self):
        import struct
        import zlib
        png = png_rgb(2, 1, bytes([255, 0, 0, 0, 255, 0]))
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        position, decompressed = 8, b""
        while position < len(png):
            length = struct.unpack(">I", png[position:position+4])[0]
            kind = png[position+4:position+8]
            data = png[position+8:position+8+length]
            if kind == b"IDAT":
                decompressed += zlib.decompress(data)
            position += 12+length
        self.assertEqual(decompressed, bytes([0, 255, 0, 0, 0, 255, 0]))

    def test_browser_text_must_match_focused_window_and_be_fresh(self):
        window = {"browser": True, "title": "Example - Google Chrome"}
        self.assertTrue(browser_snapshot_matches(window, PAGE, 5))
        self.assertFalse(browser_snapshot_matches(window, PAGE, 20))
        self.assertFalse(browser_snapshot_matches({**window, "title": "Other page"}, PAGE, 5))
        self.assertFalse(browser_snapshot_matches({**window, "browser": False}, PAGE, 5))


if __name__ == "__main__":
    unittest.main()
