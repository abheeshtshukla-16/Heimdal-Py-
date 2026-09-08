import json
import time
from quota import update_usage
from schemas import OpenAI

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096

STOP_REASON_MAP = {
    "end_turn": "stop",
    "max_tokens": "length",
    "stop_sequence": "stop",
    "tool_use": "tool_calls",
}


def build_anthropic_request(body: OpenAI) -> dict:
    system = None
    messages = []
    for message in body.messages:
        if message.role == "system":
            system = message.content
            continue
        messages.append({"role": message.role, "content": message.content})

    payload = {
        "model": body.model,
        "messages": messages,
        "max_tokens": body.max_tokens or DEFAULT_MAX_TOKENS,
        "stream": bool(body.stream),
    }
    if system is not None:
        payload["system"] = system
    if body.temperature is not None:
        payload["temperature"] = body.temperature
    if body.top_p is not None:
        payload["top_p"] = body.top_p

    return payload


def anthropic_to_openai_response(data: dict) -> dict:
    text = "".join(
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text"
    )
    usage = data.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    return {
        "id": data.get("id"),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": data.get("model"),
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": text},
            "finish_reason": STOP_REASON_MAP.get(data.get("stop_reason"), "stop"),
        }],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    }


async def stream_anthropic_completion(client, payload, redis_client, user_id):
    completion_id = None
    model = payload["model"]
    created = int(time.time())
    input_tokens = 0
    output_tokens = 0

    def chunk(delta=None, finish_reason=None, usage=None):
        body = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [] if usage is not None else [{
                "index": 0,
                "delta": delta or {},
                "finish_reason": finish_reason,
            }],
        }
        if usage is not None:
            body["usage"] = usage
        return f"data: {json.dumps(body)}\n\n"

    async with client.stream("POST", "/v1/messages", json=payload) as response:
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line.removeprefix("data: "))
            event_type = event.get("type")

            if event_type == "message_start":
                completion_id = event["message"]["id"]
                input_tokens = event["message"]["usage"]["input_tokens"]
                yield chunk(delta={"role": "assistant", "content": ""})

            elif event_type == "content_block_delta":
                text = event["delta"].get("text", "")
                if text:
                    yield chunk(delta={"content": text})

            elif event_type == "message_delta":
                output_tokens = event["usage"]["output_tokens"]
                stop_reason = event["delta"].get("stop_reason")
                yield chunk(finish_reason=STOP_REASON_MAP.get(stop_reason, "stop"))

            elif event_type == "message_stop":
                total_tokens = input_tokens + output_tokens
                yield chunk(usage={
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": total_tokens,
                })
                yield "data: [DONE]\n\n"
                await update_usage(redis_client, user_id, total_tokens)
