import json
import sys
import urllib.request

URL = "http://127.0.0.1:8765"


def invoke(action, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode()
    req = urllib.request.Request(URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.load(resp)
    if body.get("error"):
        raise RuntimeError(f"{action}: {body['error']}")
    return body["result"]


if __name__ == "__main__":
    action = sys.argv[1]
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(json.dumps(invoke(action, **params), indent=1))
