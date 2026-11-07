"""Safe Gemini connectivity probe. Prompts without echo; never saves credentials."""
import argparse
import getpass
import json
import re
import urllib.error
import urllib.request

from ai import BASE, DEFAULT_MODEL, payload


def safe_error(data, key):
    error = data.get("error", {})
    message = str(error.get("message", "")).replace(key, "[REDACTED]")
    message = re.sub(r"(?:AQ\.|AIza)[A-Za-z0-9_-]+", "[REDACTED]", message)
    return {"code": error.get("code"), "status": error.get("status"), "message": message[:1000]}


def probe(key, method, suffix, body=None):
    request = urllib.request.Request(BASE + suffix, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"x-goog-api-key": key, "Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        try:
            data = json.load(error)
        except (ValueError, OSError):
            data = {}
        return error.code, data
    except (urllib.error.URLError, TimeoutError):
        return 0, {"error": {"message": "Network connection failed or timed out"}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--generate", action="store_true", help="Also generate one short test reply (uses tokens)")
    args = parser.parse_args()
    key = getpass.getpass("Gemini key (hidden, not saved): ").strip()
    if not key:
        return
    status, data = probe(key, "GET", "?pageSize=1000")
    print("models HTTP", status, flush=True)
    if status == 200:
        print(json.dumps([{"name": m.get("name"), "methods": m.get("supportedGenerationMethods", [])}
                          for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]), flush=True)
    else:
        print(json.dumps(safe_error(data, key)), flush=True)
    body = payload(args.model, "Pip", [], [], ["Pip"], "Say one very short hello in the required JSON format.")
    status, data = probe(key, "POST", f"/{args.model}:countTokens", {"generateContentRequest": {"model": "models/" + args.model, **body}})
    print("countTokens HTTP", status, flush=True)
    print(json.dumps({"totalTokens": data.get("totalTokens"), "error": safe_error(data, key) if data.get("error") else None}), flush=True)
    if args.generate and status == 200:
        status, data = probe(key, "POST", f"/{args.model}:generateContent", {**body, "generationConfig": {**body["generationConfig"], "maxOutputTokens": 420}})
        print("generateContent HTTP", status, flush=True)
        print(json.dumps({"usage": data.get("usageMetadata"), "finishes": [c.get("finishReason") for c in data.get("candidates", [])],
                          "error": safe_error(data, key) if data.get("error") else None}), flush=True)
    key = ""


if __name__ == "__main__":
    main()
