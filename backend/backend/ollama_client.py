import json
import urllib.request

from backend.config import settings

MODEL = "gemma4:e4b"


def generate_json(
    system: str,
    prompt: str,
    seed: int = 42,
    temperature: float = 0.0,
    num_predict: int = 512,
    timeout: float = 120.0,
) -> dict:
    body = {
        "model": MODEL,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "keep_alive": -1,
        "options": {"temperature": temperature, "seed": seed, "num_predict": num_predict},
    }
    request = urllib.request.Request(
        settings.ollama_url + "/api/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.loads(response.read().decode("utf-8"))
    text = raw.get("response", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ollama returned non-JSON response: {text[:200]!r}") from exc


def health(timeout: float = 3.0) -> bool:
    try:
        request = urllib.request.Request(settings.ollama_url + "/api/tags")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False
