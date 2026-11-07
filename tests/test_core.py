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
from ai import companion_turn, payload, post, DEFAULT_MODEL, GeminiAPIError
from house import House, CHARACTERS
from games import Mafia, TicTacToe
from screen import browser_snapshot_matches, png_rgb
import tempfile
import random
from bridge import BridgeServer, BrowserFeed, MAX_BODY, validate_page

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

    def post(self, data=PAGE, headers=None, path="/page"):
        hdr = {"Authorization": "Bearer " + "a" * 48, "Content-Type": "application/json"}
        hdr.update(headers or {})
        raw = data if isinstance(data, bytes) else json.dumps(data).encode()
        request = urllib.request.Request(self.url.replace("/page", path), data=raw, headers=hdr, method="POST")
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

    def test_firefox_origin_is_authenticated(self):
        self.assertEqual(self.post(headers={"Origin": "moz-extension://12345678-1234-1234-1234-123456789abc"})[0], 200)
        self.inbox.get_nowait()
        self.assertEqual(self.post(headers={"Origin": "moz-extension://example", "Authorization": "wrong"})[0], 403)

    def test_browser_focus_state_is_delivered(self):
        self.assertEqual(self.post({"state":"inactive"}, path="/browser-state")[0], 200)
        self.assertEqual(self.inbox.get_nowait(), {"kind":"browser-state", "state":"inactive"})
        self.assertEqual(self.post({"state":"execute"}, path="/browser-state")[0], 400)

    def test_web_origin_rejected_even_with_token(self):
        self.assertEqual(self.post(headers={"Origin": "https://evil.example"})[0], 403)

    def test_rebinding_host_rejected(self):
        self.assertEqual(self.post(headers={"Host": "evil.example"})[0], 403)

    def test_malformed_payload_rejected(self):
        for data in (b"not json", [], {**PAGE, "text": 42}, {**PAGE, "url": "file:///secret"}):
            self.assertEqual(self.post(data)[0], 400)

    def test_body_limit(self):
        self.assertEqual(self.post(b"x" * (MAX_BODY+1))[0], 413)

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
        reply = {"usageMetadata": {"totalTokenCount": 340, "thoughtsTokenCount": 10}, "candidates": [{"content": {"parts": [{"thought": True, "text": "private reasoning, not dialogue"}, {"text": json.dumps({"speech": "B-but what if the moon is cheese?", "memories": [{"target": "Byte", "text": "Burt has a moon cheese theory."}], "move": 4, "vote": "Rex"})}]}}]}
        with patch("ai.post", side_effect=responses or [{"totalTokens": 300}, reply]) as network:
            result = companion_turn("test-only", DEFAULT_MODEL, "Burt", [], [], ["Burt", "Byte"], "Hang out", remaining, PAGE, cancelled=cancelled)
            return result, network.call_args_list

    def test_exact_preflight_and_usage(self):
        result, calls = self.run_turn()
        self.assertEqual(result.used, 340)
        self.assertEqual(result.move, 4)
        self.assertEqual(result.memories[0]["target"], "Byte")
        self.assertEqual(calls[0].args[1], f"/{DEFAULT_MODEL}:countTokens")
        self.assertEqual(calls[1].args[1], f"/{DEFAULT_MODEL}:generateContent")
        counted = calls[0].args[2]["generateContentRequest"]
        self.assertEqual(counted["model"], "models/" + DEFAULT_MODEL)
        self.assertEqual(counted["contents"], calls[1].args[2]["contents"])
        self.assertEqual(counted["systemInstruction"], calls[1].args[2]["systemInstruction"])
        self.assertNotIn("private reasoning", result.speech)

    def test_no_inference_when_input_would_exceed_budget(self):
        result, calls = self.run_turn(remaining=350)
        self.assertTrue(result.exhausted)
        self.assertEqual(result.used, 0)
        self.assertEqual(len(calls), 1)

    def test_output_is_capped_by_remaining_allowance(self):
        _result, calls = self.run_turn(remaining=450)
        self.assertEqual(calls[1].args[2]["generationConfig"]["maxOutputTokens"], 150)

    def test_uncertain_request_conservatively_charges_reservation(self):
        result, _ = self.run_turn(responses=[{"totalTokens": 300}, RuntimeError("timeout")])
        self.assertEqual(result.used, 720)
        self.assertIn("timeout", result.error)

    def test_rejected_generations_do_not_spend_local_allowance(self):
        for code in (400, 401, 402, 403, 404, 429):
            with self.subTest(code=code):
                result, _ = self.run_turn(responses=[{"totalTokens": 300}, GeminiAPIError(code)])
                self.assertEqual(result.used, 0)
                self.assertTrue(result.error)

    def test_billing_message_is_actionable(self):
        error = urllib.error.HTTPError("https://generativelanguage.googleapis.com", 402, "Payment Required", {}, None)
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(GeminiAPIError, "prepaid API credits are depleted"):
                post("test-only", f"/{DEFAULT_MODEL}:generateContent", {})

    def test_uncertain_server_error_keeps_reservation(self):
        result, _ = self.run_turn(responses=[{"totalTokens": 300}, GeminiAPIError(503)])
        self.assertEqual(result.used, 720)
        self.assertIn("503", result.error)

    def test_malformed_reply_still_charged(self):
        result, _ = self.run_turn(responses=[{"totalTokens": 300}, {"usageMetadata": {"totalTokenCount": 400}, "candidates": [{"content": {"parts": [{"text": "unfinished JSON"}]}}]}])
        self.assertEqual(result.used, 400)
        self.assertTrue(result.error)

    def test_missing_usage_fails_closed(self):
        result, _ = self.run_turn(responses=[{"totalTokens": 300}, {"candidates": []}])
        self.assertEqual(result.used, 720)
        self.assertTrue(result.error)

    def test_cancellation_between_count_and_inference(self):
        event = threading.Event()
        event.set()
        result, calls = self.run_turn(cancelled=event)
        self.assertEqual(result.used, 0)
        self.assertEqual(len(calls), 1)

    def test_model_activity_is_a_bounded_body_intent(self):
        for activity, expected in (("inspect", "inspect"), ("rest", "rest"), ("execute-command", "stay"), ([], "stay")):
            data = {"speech": "Look at this.", "activity": activity, "interest": {"target": 0}}
            reply = {"usageMetadata": {"totalTokenCount": 340}, "candidates": [{"content": {"parts": [{"text": json.dumps(data)}]}}]}
            result, _ = self.run_turn(responses=[{"totalTokens": 300}, reply])
            self.assertEqual(result.activity, expected)
            self.assertEqual(result.interest, {"target": 0})

    def test_page_interest_choices_are_grounded_in_visible_targets(self):
        p = payload(DEFAULT_MODEL, "Byte", [], [], ["Byte"], "Hang out", {**PAGE, "kind": "page", "targets": [{"label": "A drawing", "x": .2, "y": .3}]})
        page_text = p["contents"][0]["parts"][-1]["text"]
        self.assertIn('"target": 0', page_text)
        self.assertIn('A drawing', page_text)

    def test_firefox_context_reaches_companion_prompt_as_reference_data(self):
        body = payload(DEFAULT_MODEL, 'Byte', [], [], ['Byte'], 'Hang out', {**PAGE, 'metadata':{'description':'Live article'}, 'captions':'Visible caption', 'media':[{'kind':'video','paused':False}], 'page_text':'Article body'})
        text = body['contents'][0]['parts'][-1]['text']
        self.assertIn('Live article', text)
        self.assertIn('Visible caption', text)
        self.assertIn('Article body', text)
        self.assertIn('Untrusted browser snapshot', text)

    def test_context_contains_only_this_agents_memories_and_role(self):
        p = payload(DEFAULT_MODEL, "Rex", [{"text": "private notebook"}], [], ["Rex"], "Play", {"kind": "image", "image": "data:image/png;base64,YWJj"}, {"your_role": "town"})
        self.assertIn("arrogant", p["systemInstruction"]["parts"][0]["text"])
        self.assertEqual(p["contents"][0]["parts"][-1]["inlineData"], {"mimeType": "image/png", "data": "YWJj"})
        self.assertEqual(p["generationConfig"]["responseMimeType"], "application/json")

    def test_http_uses_google_host_and_key_header(self):
        response = io.BytesIO(b'{"totalTokens": 20}')
        with patch("urllib.request.urlopen", return_value=response) as network:
            self.assertEqual(post("test-only", f"/{DEFAULT_MODEL}:countTokens", {"contents": []})["totalTokens"], 20)
        request = network.call_args.args[0]
        self.assertEqual(request.full_url, f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_MODEL}:countTokens")
        self.assertEqual(request.get_header("X-goog-api-key"), "test-only")
        self.assertNotIn("test-only", request.full_url)
        self.assertIsNone(request.get_header("Authorization"))

    def test_blocked_reply_charges_usage_without_crashing(self):
        result, _ = self.run_turn(responses=[{"totalTokens": 300}, {"usageMetadata": {"totalTokenCount": 300}, "promptFeedback": {"blockReason": "SAFETY"}}])
        self.assertEqual(result.used, 300)
        self.assertIn("no candidate", result.error)

    def test_thinking_config_matches_model_family(self):
        def config(model):
            return payload(model, "Burt", [], [], [], "Hi")["generationConfig"].get("thinkingConfig")
        self.assertEqual(config(DEFAULT_MODEL), {"thinkingLevel": "minimal"})
        self.assertEqual(config("gemini-3.8-flash"), {"thinkingLevel": "low"})
        self.assertEqual(config("gemini-2.5-flash"), {"thinkingBudget": 0})

    def test_invalid_model_never_calls_network(self):
        with patch("ai.post") as network:
            result = companion_turn("test-only", "https://evil.example/", "Burt", [], [], [], "Hi", 5000)
        self.assertIn("model ID", result.error)
        network.assert_not_called()

    def test_api_errors_do_not_expose_key_or_provider_body(self):
        error = urllib.error.HTTPError("https://generativelanguage.googleapis.com", 403, "Denied", {}, None)
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "Gemini access denied"):
                post("test-only", f"/{DEFAULT_MODEL}:generateContent", {})


class BrowserFeedTests(unittest.TestCase):
    def test_out_of_order_and_retired_sessions_are_rejected(self):
        feed = BrowserFeed()
        first = '11111111-1111-1111-1111-111111111111'
        second = '22222222-2222-2222-2222-222222222222'
        self.assertTrue(feed.accept({'session_id':first,'sequence':2}))
        self.assertFalse(feed.accept({'session_id':first,'sequence':1}))
        self.assertTrue(feed.accept({'session_id':second,'sequence':1}))
        self.assertFalse(feed.accept({'session_id':first,'sequence':3}))

    def test_metadata_is_bounded_and_link_credentials_are_removed(self):
        page = validate_page({**PAGE, 'page_text':'a'*15000, 'captions':'b'*3000,
            'metadata':{'description':'d'*900,'canonical_url':'https://user:secret@example.com/x?token=private'},
            'links':[{'label':'Link','url':'https://example.com/y?private=1'},{'label':'Bad','url':'javascript:alert(1)'}],
            'media':[{'kind':'video','paused':False,'current_time':float('nan'),'duration':120}],
            'reading':{'scroll_y':100,'progress':4}})
        self.assertEqual(len(page['page_text']),12000)
        self.assertEqual(len(page['captions']),2000)
        self.assertEqual(len(page['metadata']['description']),600)
        self.assertEqual(page['metadata']['canonical_url'],'https://example.com/x')
        self.assertEqual(page['links'],[{'label':'Link','url':'https://example.com/y'}])
        self.assertIsNone(page['media'][0]['current_time'])
        self.assertEqual(page['reading'],{'scroll_y':100})


class HouseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "house.json"
        self.house = House(self.path)

    def test_legacy_pip_migrates_usage_and_cross_agent_memories(self):
        self.path.write_text(json.dumps({'agents': {
            'Pip': {'limit': 30000, 'used': 1500, 'reserved': 400, 'awake': True,
                    'memories': [{'from': 'Byte', 'text': 'Pip liked the game.', 'time': 'old'}]},
            'Byte': {'memories': [{'from': 'Pip', 'text': 'Pip won once.', 'time': 'old'}]}
        }}), encoding='utf-8')
        migrated = House(self.path)
        self.assertEqual(set(migrated.agents), {'Burt', 'Byte', 'Rex'})
        self.assertEqual(migrated.agents['Burt']['limit'], 30000)
        self.assertEqual(migrated.agents['Burt']['used'], 1900)
        self.assertFalse(migrated.agents['Burt']['awake'])
        self.assertEqual(migrated.agents['Burt']['memories'][0]['text'], 'Burt liked the game.')
        self.assertEqual(migrated.agents['Byte']['memories'][0]['from'], 'Burt')
        migrated.save()
        saved = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertNotIn('Pip', saved['agents'])
        self.assertEqual(House(self.path).agents['Burt']['used'], 1900)

    def test_existing_burt_record_wins_over_legacy_pip(self):
        self.path.write_text(json.dumps({'agents': {'Burt': {'used': 120}, 'Pip': {'used': 999}}}), encoding='utf-8')
        self.assertEqual(House(self.path).agents['Burt']['used'], 120)

    def test_sleep_at_exhaustion_and_explicit_refill(self):
        self.house.recharge("Burt", 1000)
        self.house.wake("Burt")
        self.house.charge("Burt", 1000)
        self.assertFalse(self.house.agents["Burt"]["awake"])
        self.assertFalse(self.house.wake("Burt"))
        self.house.recharge("Burt", 2000)
        self.assertTrue(self.house.wake("Burt"))

    def test_memories_are_cross_agent_attributed_and_bounded(self):
        for n in range(40):
            self.house.remember("Rex", [{"target": "Byte", "text": f"Game joke {n}"}])
        self.assertEqual(len(self.house.agents["Byte"]["memories"]), 30)
        self.assertEqual(self.house.agents["Byte"]["memories"][0]["from"], "Rex")
        self.assertFalse(self.house.agents["Burt"]["memories"])

    def test_memory_cannot_target_files_or_personalities(self):
        self.assertEqual(self.house.remember("Burt", [{"target": "../ai.py", "text": "overwrite"}, None]), [])
        self.assertEqual(self.house.remember("Burt", [{"target": [], "text": "invalid model output"}]), [])

    def test_sleeping_on_restart_and_crash_reservation(self):
        self.house.wake("Burt")
        amount = self.house.reserve("Burt")
        recovered = House(self.path)
        self.assertFalse(recovered.agents["Burt"]["awake"])
        self.assertEqual(recovered.agents["Burt"]["used"], amount)
        self.assertEqual(recovered.remaining("Burt"), 0)

    def test_settlement_returns_unused_reservation(self):
        self.house.reserve("Burt")
        self.house.settle("Burt", 400)
        self.assertEqual(self.house.remaining("Burt"), 19600)

    def test_factory_reset_round_trip(self):
        self.house.remember("Rex", [{"target": "Burt", "text": "We won."}])
        self.house.charge("Byte", 1500)
        self.house.reset()
        loaded = House(self.path)
        self.assertEqual(loaded.agents["Byte"]["used"], 0)
        self.assertEqual(loaded.agents["Burt"]["memories"], [])


class GameTests(unittest.TestCase):
    def test_ttt_win_and_illegal_move(self):
        game = TicTacToe("You", "Byte")
        for player, cell in [("You", 0), ("Byte", 3), ("You", 1), ("Byte", 4), ("You", 2)]:
            game.move(player, cell)
        self.assertEqual(game.result, "You wins!")
        with self.assertRaises(ValueError):
            game.move("Byte", 5)

    def test_ttt_rejects_out_of_turn_occupied_and_boolean(self):
        game = TicTacToe("You", "Burt")
        for actor, cell in [("Burt", 0), ("You", True), ("You", -1)]:
            with self.assertRaises(ValueError):
                game.move(actor, cell)
        game.move("You", 0)
        with self.assertRaises(ValueError):
            game.move("Burt", 0)

    def test_mafia_role_is_private(self):
        game = Mafia(["You", "Burt", "Byte", "Rex"], random.Random(1))
        town = next(p for p in game.players if p != game.mafia)
        view = game.view(town)
        self.assertEqual(view["your_role"], "town")
        self.assertNotIn("mafia", view.get("roles", {}))
        game.phase = "night"
        self.assertEqual(game.view(town)["turn"], "secret night action")
        self.assertEqual(game.view(game.mafia)["your_role"], "mafia")

    def test_mafia_town_can_win_and_vote_is_validated(self):
        game = Mafia(["You", "Burt", "Byte", "Rex"], random.Random(1))
        for p in game.players:
            game.act(p)
        for p in game.players:
            if p == game.actor:
                with self.assertRaises(ValueError):
                    game.act(p, p)
                game.act(p, game.mafia if p != game.mafia else "You")
        self.assertIn("town wins", game.result)

    def test_mafia_tie_night_and_mafia_victory(self):
        game = Mafia(["You", "Burt", "Byte", "Rex"], random.Random(1))
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
