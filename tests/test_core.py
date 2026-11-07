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
from ai import ask, extract_text, make_payload
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


class AITests(unittest.TestCase):
    def test_page_is_data_and_history_is_bounded(self):
        history = [{"role": "user", "content": str(n)} for n in range(20)]
        payload = make_payload("test-model", PAGE, history, "Explain")
        self.assertFalse(payload["store"])
        self.assertEqual(len(payload["input"]), 14)
        self.assertIn("untrusted", payload["instructions"])
        self.assertEqual(payload["input"][-1]["content"], "Explain")

    def test_text_extraction(self):
        response = {"output": [{"type": "reasoning"}, {"content": [{"type": "output_text", "text": "Hello!"}]}]}
        self.assertEqual(extract_text(response), "Hello!")

    def test_request_and_reply_without_live_key(self):
        response = io.BytesIO(json.dumps({"output": [{"content": [{"type": "output_text", "text": "Hi"}]}]}).encode())
        with patch("urllib.request.urlopen", return_value=response) as network:
            self.assertEqual(ask("test-only", "test-model", PAGE, [], "Hi"), "Hi")
            request = network.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
            self.assertFalse(json.loads(request.data)["store"])

    def test_key_error_is_actionable(self):
        error = urllib.error.HTTPError("https://api.openai.com", 401, "Unauthorized", {}, None)
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "key was rejected"):
                ask("invalid", "test-model", None, [], "Hi")


if __name__ == "__main__":
    unittest.main()
