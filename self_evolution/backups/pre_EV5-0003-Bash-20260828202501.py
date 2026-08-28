
import json
import os
import time
import uuid
import requests
from flask import Flask, request, Response

app = Flask(__name__)

PORT = int(os.environ.get("SURGICAL_PROXY_PORT", "18082"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
CAPTURE_DIR = os.environ.get("SURGICAL_CAPTURE_DIR", "/content/gpt_oss_proxy_test/surgical_proxy_v2/captures")
os.makedirs(CAPTURE_DIR, exist_ok=True)

MAX_TOKENS_CAP = int(os.environ.get("SURGICAL_MAX_TOKENS_CAP", "4096"))
THINKING_BUDGET_CAP = int(os.environ.get("SURGICAL_THINKING_BUDGET_CAP", "2048"))
TEMPERATURE_OVERRIDE = os.environ.get("SURGICAL_TEMPERATURE_OVERRIDE", "")
SPEED_SUFFIX_ON = os.environ.get("SURGICAL_SPEED_SUFFIX", "0") == "1"

SPEED_SUFFIX_TEXT = (
    " Act immediately using the tool. Do not narrate your plan. "
    "Do not explain what you are about to do before doing it. "
    "Keep any internal reasoning brief."
)

request_counter = 0


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.route("/v1/messages", methods=["POST"])
def messages():
    global request_counter
    request_counter += 1
    rid = f"{request_counter:03d}_{uuid.uuid4().hex[:8]}"
    timestamp = time.time()

    try:
        incoming = request.get_json(force=True)

        original_system = incoming.get("system", "")
        original_tools = incoming.get("tools", [])

        if isinstance(original_system, list):
            original_system_text = "\n".join(
                str(x.get("text", x)) if isinstance(x, dict) else str(x)
                for x in original_system
            )
        else:
            original_system_text = str(original_system)

        allowed_names_env = os.environ.get("SURGICAL_ALLOWED_TOOLS", "Bash")
        allowed_names = [n.strip() for n in allowed_names_env.split(",") if n.strip()]

        selected_tools = [
            t for t in original_tools
            if isinstance(t, dict) and t.get("name") in allowed_names
        ]

        surgical_system = (
            "You are GPT-OSS operating through an Anthropic-compatible API. "
            "Use the provided tool(s) when the user explicitly requests it. "
            "Tool calls must use the exact tool name and schema."
        )
        if SPEED_SUFFIX_ON:
            surgical_system += SPEED_SUFFIX_TEXT

        REDUCE_TOOLS = os.environ.get("SURGICAL_REDUCE_TOOLS", "1") == "1"

        forwarded = dict(incoming)

        if REDUCE_TOOLS:
            forwarded["system"] = surgical_system
            forwarded["tools"] = selected_tools
        else:
            forwarded["system"] = original_system
            forwarded["tools"] = original_tools

        original_max_tokens = forwarded.get("max_tokens")
        forwarded["max_tokens"] = min(original_max_tokens or MAX_TOKENS_CAP, MAX_TOKENS_CAP)

        original_thinking = forwarded.get("thinking")
        if isinstance(original_thinking, dict) and original_thinking.get("type") == "enabled":
            original_budget = original_thinking.get("budget_tokens")
            forwarded["thinking"] = {
                "type": "enabled",
                "budget_tokens": min(original_budget or THINKING_BUDGET_CAP, THINKING_BUDGET_CAP),
            }

        original_temperature = forwarded.get("temperature")
        if TEMPERATURE_OVERRIDE != "":
            forwarded["temperature"] = float(TEMPERATURE_OVERRIDE)

        print(f"[CAP] max_tokens: {original_max_tokens} -> {forwarded['max_tokens']}  "
              f"thinking: {original_thinking} -> {forwarded.get('thinking')}  "
              f"temperature: {original_temperature} -> {forwarded.get('temperature')}  "
              f"speed_suffix: {SPEED_SUFFIX_ON}")

        capture = {
            "request_id": rid,
            "timestamp": timestamp,
            "model": incoming.get("model"),
            "reduce_tools": REDUCE_TOOLS,
            "allowed_tools_env": allowed_names,
            "original_tool_names": [t.get("name") for t in original_tools if isinstance(t, dict)],
            "caps_applied": {
                "max_tokens_after": forwarded.get("max_tokens"),
                "thinking_after": forwarded.get("thinking"),
                "temperature_after": forwarded.get("temperature"),
                "speed_suffix_on": SPEED_SUFFIX_ON,
            },
        }
        save_json(os.path.join(CAPTURE_DIR, f"{rid}_request.json"), capture)

        ollama_endpoint = OLLAMA_URL + "/v1/messages"
        headers = {"Content-Type": "application/json"}
        if request.headers.get("Authorization"):
            headers["Authorization"] = request.headers.get("Authorization")

        try:
            response = requests.post(ollama_endpoint, headers=headers, json=forwarded, timeout=900)
            raw_body = response.text

            def parse_sse(raw_sse):
                blocks = {}
                order = []
                stop_reason = None
                usage_info = None
                for line in raw_sse.splitlines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        evt = json.loads(line[len("data: "):])
                    except Exception:
                        continue
                    t = evt.get("type")
                    if t == "content_block_start":
                        idx = evt["index"]
                        blocks[idx] = dict(evt["content_block"])
                        blocks[idx].setdefault("_partial_json", "")
                        order.append(idx)
                    elif t == "content_block_delta":
                        idx = evt["index"]
                        d = evt["delta"]
                        if d.get("type") == "input_json_delta":
                            blocks[idx]["_partial_json"] += d.get("partial_json", "")
                    elif t == "content_block_stop":
                        idx = evt["index"]
                        b = blocks.get(idx, {})
                        if b.get("type") == "tool_use" and b.get("_partial_json"):
                            try:
                                b["input"] = json.loads(b["_partial_json"])
                            except Exception:
                                b["input"] = {}
                    elif t == "message_delta":
                        stop_reason = evt.get("delta", {}).get("stop_reason")
                        if "usage" in evt:
                            usage_info = evt["usage"]
                    elif t == "message_start":
                        msg = evt.get("message", {})
                        if "usage" in msg:
                            usage_info = msg["usage"]
                return [blocks[i] for i in order], stop_reason, usage_info

            all_blocks, stop_reason, usage_info = parse_sse(raw_body)
            tool_blocks = [b for b in all_blocks if b.get("type") == "tool_use"]

            analysis = {
                "request_id": rid,
                "http_status": response.status_code,
                "stop_reason": stop_reason,
                "usage": usage_info,
                "tool_names": [b.get("name") for b in tool_blocks],
            }
            save_json(os.path.join(CAPTURE_DIR, f"{rid}_response_analysis.json"), analysis)

            return Response(raw_body, status=response.status_code, content_type="application/json")

        except Exception as e:
            print("OLLAMA ERROR:", repr(e))
            return Response(json.dumps({"error": str(e)}), status=502, content_type="application/json")

    except Exception as e:
        print("PROXY ERROR:", repr(e))
        return Response(json.dumps({"error": str(e)}), status=500, content_type="application/json")


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    print("Surgical Proxy v5 (recovered) listening on", PORT)
    app.run(host="127.0.0.1", port=PORT, threaded=True)
