"""OpenAI-compatible mock upstream. Logs every request; fails for keys listed in argv[3]."""
import json, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]); LOG = sys.argv[2]
FAIL_KEYS = set((sys.argv[3] if len(sys.argv) > 3 else "").split(",")) - {""}
FAIL_MODE = sys.argv[4] if len(sys.argv) > 4 else "401"   # 401 | 402(no credit) | 429
lock = threading.Lock()

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            return self._send(200, {"object": "list", "data": [
                {"id": "mock-model", "object": "model", "created": 0, "owned_by": "mock"}]})
        return self._send(404, {"error": "nope"})
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        auth = (self.headers.get("Authorization") or "").replace("Bearer ", "")
        body = json.loads(raw or b"{}")
        with lock, open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"port": PORT, "path": self.path, "auth": auth, "body": body}) + "\n")
        if auth in FAIL_KEYS:
            code = {"401": 401, "402": 402, "429": 429}.get(FAIL_MODE, 401)
            msg = {"401": "invalid api key", "402": "insufficient credits", "429": "rate limited"}.get(FAIL_MODE)
            return self._send(code, {"error": {"message": f"{msg} ({auth})", "type": "invalid_request_error", "code": "insufficient_quota" if code == 402 else "invalid_api_key"}})
        if self.path.rstrip("/").endswith("/responses"):
            return self._send(200, {"id": "resp_mock", "object": "response", "created_at": 0, "status": "completed",
                "model": body.get("model", "m"),
                "output": [{"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
                            "content": [{"type": "output_text", "text": "ok", "annotations": []}]}],
                "usage": {"input_tokens": 5, "output_tokens": 1, "total_tokens": 6}})
        return self._send(200, {"id": "chatcmpl-mock", "object": "chat.completion", "created": 0,
            "model": body.get("model", "m"),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}})

ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
