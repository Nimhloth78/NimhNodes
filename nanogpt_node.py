"""
NanoGPT Chat Completion Node
─────────────────────────────
Sends chat-completion requests to the NanoGPT API (OpenAI-compatible)
with a dynamic, refreshable model dropdown.
"""

import json
import os
import traceback
import urllib.request
import urllib.error

from server import PromptServer
from aiohttp import web

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

DEFAULT_API_BASE = "https://nano-gpt.com/api"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def _load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def _get_api_key(override=""):
    if override:
        return override
    return os.environ.get("NANOGPT_API_KEY") or _load_config().get("api_key", "")

def _get_api_base(override=""):
    if override:
        return override.rstrip("/")
    base = os.environ.get("NANOGPT_API_BASE") or _load_config().get("api_base", "")
    return base.rstrip("/") if base else DEFAULT_API_BASE

# ──────────────────────────────────────────────
# Model Fetching
# ──────────────────────────────────────────────

_model_cache = ["(click 🔄 Refresh Models)"]

def _fetch_models(api_key, api_base):
    if not api_key:
        print("[NanoGPT] No API key — cannot fetch models.")
        return []

    url = f"{api_base}/v1/models"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        models = []
        if isinstance(data, dict) and "data" in data:
            for entry in data["data"]:
                model_id = entry.get("id") or entry.get("name", "")
                if model_id:
                    models.append(model_id)
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, str):
                    models.append(entry)
                elif isinstance(entry, dict):
                    model_id = entry.get("id") or entry.get("name", "")
                    if model_id:
                        models.append(model_id)

        return sorted(set(models))

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"[NanoGPT] HTTP {e.code} fetching models: {body}")
    except Exception as e:
        print(f"[NanoGPT] Error fetching models: {e}")
        traceback.print_exc()

    return []

# ──────────────────────────────────────────────
# Server Routes
# ──────────────────────────────────────────────

@PromptServer.instance.routes.get("/nanogpt/models")
async def _route_models(request):
    global _model_cache
    api_key  = request.query.get("api_key", "")
    api_base = request.query.get("api_base", "")
    key  = _get_api_key(api_key)
    base = _get_api_base(api_base)

    models = _fetch_models(key, base)
    if models:
        _model_cache = models

    return web.json_response({
        "models": models if models else [],
        "error":  "" if models else "No models returned. Check API key / base URL.",
    })

@PromptServer.instance.routes.post("/nanogpt/save_config")
async def _route_save_config(request):
    body = await request.json()
    cfg = _load_config()
    if "api_key" in body:
        cfg["api_key"] = body["api_key"]
    if "api_base" in body:
        cfg["api_base"] = body["api_base"]
    _save_config(cfg)
    return web.json_response({"status": "saved"})

# ──────────────────────────────────────────────
# Node
# ──────────────────────────────────────────────

class NanoGPT_ChatCompletion:
    """
    Sends a chat-completion request to the NanoGPT API
    and outputs the assistant's reply as a STRING.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "sk-... (or set NANOGPT_API_KEY env var)",
                }),
                "model": (_model_cache, ),
                "system_prompt": ("STRING", {
                    "default": "You are a helpful assistant.",
                    "multiline": True,
                }),
                "user_prompt": ("STRING", {
                    "default": "",
                    "multiline": True,
                }),
                "temperature": ("FLOAT", {
                    "default": 0.7,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.05,
                    "display": "slider",
                }),
                "max_tokens": ("INT", {
                    "default": 1024,
                    "min": 1,
                    "max": 128000,
                    "step": 64,
                }),
            },
            "optional": {
                "api_base_url": ("STRING", {
                    "default": DEFAULT_API_BASE,
                    "multiline": False,
                }),
                "input_text": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES  = ("STRING",)
    RETURN_NAMES  = ("response",)
    FUNCTION      = "run"
    CATEGORY      = "NimhNodes"
    OUTPUT_NODE   = True

    def run(self, api_key, model, system_prompt, user_prompt,
            temperature, max_tokens,
            api_base_url="", input_text=""):

        key  = _get_api_key(api_key)
        base = _get_api_base(api_base_url)

        if not key:
            raise ValueError(
                "[NanoGPT] No API key found. Enter one in the node, "
                "set NANOGPT_API_KEY env var, or save via /nanogpt/save_config."
            )

        if model.startswith("("):
            raise ValueError(
                "[NanoGPT] No model selected. Click 🔄 Refresh Models first."
            )

        # Build user message
        if input_text and user_prompt:
            final_user = f"{input_text}\n\n{user_prompt}"
        elif input_text:
            final_user = input_text
        else:
            final_user = user_prompt

        if not final_user.strip():
            raise ValueError("[NanoGPT] user_prompt (and/or input_text) cannot be empty.")

        messages = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": final_user})

        payload = json.dumps({
            "model":       model,
            "messages":    messages,
            "temperature": round(temperature, 2),
            "max_tokens":  max_tokens,
        }).encode("utf-8")

        url = f"{base}/v1/chat/completions"
        req = urllib.request.Request(url, data=payload, method="POST", headers={
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
        })

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            choices = result.get("choices", [])
            if not choices:
                raise RuntimeError(f"[NanoGPT] API returned no choices: {result}")

            reply = choices[0].get("message", {}).get("content", "")
            return (reply,)

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"[NanoGPT] API HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"[NanoGPT] Connection error: {e.reason}")

# ──────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────

NODE_CLASS_MAPPINGS = {
    "NanoGPT_ChatCompletion": NanoGPT_ChatCompletion,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanoGPT_ChatCompletion": "💬 NanoGPT Chat Completion",
}