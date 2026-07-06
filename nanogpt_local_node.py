"""
NanoGPT + Local LLM Chat Completion Node
──────────────────────────────────────────
Same chat-completion functionality as NanoGPT_ChatCompletion, plus the option
to route the request to a local Ollama or LM Studio server instead of the
NanoGPT cloud API. Also adds optional vision (IMAGE) input and batch prompt
processing (connect a list of strings to user_prompt to run several prompts
in one execution, keeping a local model loaded between them).
"""

import base64
import json
import urllib.request
import urllib.error
from io import BytesIO

import numpy as np
from PIL import Image as PILImage

from server import PromptServer
from aiohttp import web
from comfy_api.latest import io

from .nanogpt_node import _get_api_key, _get_api_base, DEFAULT_API_BASE

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

PROVIDER_NANOGPT = "NanoGPT (Cloud)"
PROVIDER_OLLAMA = "Ollama (Local)"
PROVIDER_LMSTUDIO = "LM Studio (Local)"
PROVIDERS = [PROVIDER_NANOGPT, PROVIDER_OLLAMA, PROVIDER_LMSTUDIO]

OLLAMA_DEFAULT_SERVER = "http://127.0.0.1:11434"
LM_STUDIO_DEFAULT_SERVER = "http://127.0.0.1:1234/v1"

IMAGE_MAX_SIDE = 2048
IMAGE_MAX_PIXELS = 2 * 1024 * 1024
IMAGE_JPEG_QUALITY = 90

_model_cache = ["(click 🔄 Refresh Models)"]

# ──────────────────────────────────────────────
# Small helpers for is_input_list-style batch handling
# ──────────────────────────────────────────────

def _first(value, default=None):
    if isinstance(value, list):
        return value[0] if value else default
    return value if value is not None else default

def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if v is not None]
    return [value]

# ──────────────────────────────────────────────
# Model fetching
# ──────────────────────────────────────────────

def _fetch_openai_models(base_url, api_key=""):
    url = f"{base_url.rstrip('/')}/models"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = []
        if isinstance(data, dict) and "data" in data:
            for entry in data["data"]:
                model_id = entry.get("id") or entry.get("name", "")
                if model_id:
                    models.append(model_id)
        return sorted(set(models))
    except Exception as e:
        print(f"[NanoGPT-Local] Error fetching models from {url}: {e}")
        return []

def _fetch_ollama_models(base_url):
    url = f"{base_url.rstrip('/')}/api/tags"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = [
            m.get("name") or m.get("model")
            for m in data.get("models", [])
            if m.get("name") or m.get("model")
        ]
        return sorted(set(models))
    except Exception as e:
        print(f"[NanoGPT-Local] Error fetching Ollama models from {url}: {e}")
        return []

# ──────────────────────────────────────────────
# Server routes
# ──────────────────────────────────────────────

@PromptServer.instance.routes.get("/nanogpt/local_models")
async def _route_local_models(request):
    provider = request.query.get("provider", PROVIDER_OLLAMA)
    server_url = request.query.get("server_url", "").strip()

    if provider == PROVIDER_LMSTUDIO:
        base = server_url or LM_STUDIO_DEFAULT_SERVER
        models = _fetch_openai_models(base)
    else:
        base = server_url or OLLAMA_DEFAULT_SERVER
        models = _fetch_ollama_models(base)

    return web.json_response({
        "models": models,
        "error": "" if models else "No models returned. Is the local server running?",
    })

# ──────────────────────────────────────────────
# Vision helpers
# ──────────────────────────────────────────────

def _array_to_jpeg_b64(arr, max_side=IMAGE_MAX_SIDE, max_pixels=IMAGE_MAX_PIXELS, quality=IMAGE_JPEG_QUALITY):
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    if arr.shape[-1] == 4:
        arr = arr[..., :3]
    elif arr.shape[-1] == 1:
        arr = np.repeat(arr, 3, axis=-1)

    pil = PILImage.fromarray(arr, "RGB")
    width, height = pil.size
    scale = 1.0
    if max(width, height) > max_side:
        scale = min(scale, max_side / float(max(width, height)))
    if width * height > max_pixels:
        scale = min(scale, (max_pixels / float(width * height)) ** 0.5)
    if scale < 1.0:
        pil = pil.resize((max(1, int(width * scale)), max(1, int(height * scale))), PILImage.Resampling.LANCZOS)

    buffer = BytesIO()
    pil.save(buffer, format="JPEG", quality=quality)
    return base64.b64encode(buffer.getvalue()).decode("ascii")

def _prepare_image_b64_list(images):
    b64_list = []
    for image in images:
        arr = image.detach().cpu().numpy() if hasattr(image, "detach") else np.asarray(image)
        if arr.ndim == 4:
            for i in range(arr.shape[0]):
                b64_list.append(_array_to_jpeg_b64(arr[i]))
        elif arr.ndim == 3:
            b64_list.append(_array_to_jpeg_b64(arr))
    return b64_list

# ──────────────────────────────────────────────
# Chat request helpers
# ──────────────────────────────────────────────

def _build_openai_messages(system_prompt, user_text, image_b64_list):
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    if image_b64_list:
        content = [{"type": "text", "text": user_text}]
        for b64 in image_b64_list:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": user_text})
    return messages

def _call_openai_chat(chat_url, api_key, model, messages, temperature, max_tokens, timeout=300):
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": round(float(temperature), 2),
        "max_tokens": int(max_tokens),
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(chat_url, data=payload, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        choices = result.get("choices", [])
        if not choices:
            raise RuntimeError(f"API returned no choices: {result}")
        reply = choices[0].get("message", {}).get("content", "")
        used_model = result.get("model", model)
        return reply, used_model
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"API HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection error: {e.reason}")

def _call_ollama_chat(server_url, model, system_prompt, user_text, image_b64_list, temperature, max_tokens, timeout=300):
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    user_message = {"role": "user", "content": user_text}
    if image_b64_list:
        user_message["images"] = image_b64_list
    messages.append(user_message)

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": round(float(temperature), 2),
            "num_predict": int(max_tokens),
        },
    }).encode("utf-8")

    url = f"{server_url.rstrip('/')}/api/chat"
    req = urllib.request.Request(url, data=payload, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        reply = result.get("message", {}).get("content", "")
        used_model = result.get("model", model)
        return reply, used_model
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Ollama API HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach Ollama server: {e.reason}")

# ──────────────────────────────────────────────
# Node
# ──────────────────────────────────────────────

class NanoGPT_Local_ChatCompletion(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="NanoGPT_Local_ChatCompletion",
            display_name="💬 NanoGPT + Local LLM Chat",
            category="NimhNodes",
            is_output_node=True,
            is_input_list=True,
            description=(
                "Chat completion node that can call the NanoGPT cloud API, or a local "
                "Ollama / LM Studio server. Supports an optional vision (IMAGE) input for "
                "vision-capable models, and batch prompts: connect a list of strings to "
                "user_prompt to process them all in one run."
            ),
            inputs=[
                io.Combo.Input("provider", options=PROVIDERS, default=PROVIDER_NANOGPT),
                io.String.Input("api_key", default="",
                    placeholder="sk-... (NanoGPT cloud only; or set NANOGPT_API_KEY env var)"),
                io.Combo.Input("model", options=_model_cache),
                io.String.Input("system_prompt", multiline=True,
                    default="You are a helpful assistant."),
                io.String.Input("user_prompt", multiline=True, default=""),
                io.Float.Input("temperature", default=0.7, min=0.0, max=2.0, step=0.05,
                    display_mode=io.NumberDisplay.slider),
                io.Int.Input("max_tokens", default=1024, min=1, max=128000, step=64),
                io.String.Input("api_base_url", default=DEFAULT_API_BASE, optional=True,
                    tooltip="NanoGPT cloud API base URL. Ignored for local providers."),
                io.String.Input("local_server_url", default="", optional=True,
                    placeholder="http://127.0.0.1:11434 (Ollama) or http://127.0.0.1:1234/v1 (LM Studio)",
                    tooltip="Local server URL. Ignored for NanoGPT (Cloud). Leave blank to use the provider's default."),
                io.String.Input("input_text", force_input=True, optional=True),
                io.Image.Input("image", optional=True,
                    tooltip="Optional image(s) for vision-capable models."),
            ],
            outputs=[
                io.String.Output("response", is_output_list=True),
                io.String.Output("model_used", is_output_list=True),
            ],
        )

    @classmethod
    def validate_inputs(cls, model, **kwargs):
        if str(_first(model, "")).startswith("("):
            return "No model selected. Click 🔄 Refresh Models first."
        return True

    @classmethod
    def execute(cls, provider, api_key, model, system_prompt, user_prompt,
                temperature, max_tokens, api_base_url=None, local_server_url=None,
                input_text=None, image=None):

        provider_value = _first(provider, PROVIDER_NANOGPT)
        api_key_value = _first(api_key, "") or ""
        model_value = str(_first(model, "") or "").strip()
        system_value = str(_first(system_prompt, "") or "")
        temperature_value = float(_first(temperature, 0.7))
        max_tokens_value = int(_first(max_tokens, 1024))
        api_base_value = _first(api_base_url, "") or ""
        server_url_value = str(_first(local_server_url, "") or "").strip()

        if model_value.startswith("("):
            raise ValueError("[NanoGPT] No model selected. Click 🔄 Refresh Models first.")
        if not model_value:
            raise ValueError("[NanoGPT] No model selected. Click 🔄 Refresh Models first.")

        prompts = _as_list(user_prompt) or [""]
        input_texts = _as_list(input_text)
        image_b64_list = _prepare_image_b64_list(_as_list(image))

        responses = []
        models_used = []

        for index in range(len(prompts)):
            prompt_i = prompts[index]
            input_i = input_texts[index] if index < len(input_texts) else (input_texts[-1] if input_texts else "")

            if input_i and prompt_i:
                final_user = f"{input_i}\n\n{prompt_i}"
            elif input_i:
                final_user = input_i
            else:
                final_user = prompt_i

            if not str(final_user).strip():
                raise ValueError("[NanoGPT] user_prompt (and/or input_text) cannot be empty.")

            if provider_value == PROVIDER_OLLAMA:
                base = server_url_value or OLLAMA_DEFAULT_SERVER
                reply, used_model = _call_ollama_chat(
                    base, model_value, system_value, final_user, image_b64_list,
                    temperature_value, max_tokens_value,
                )
            elif provider_value == PROVIDER_LMSTUDIO:
                base = (server_url_value or LM_STUDIO_DEFAULT_SERVER).rstrip("/")
                messages = _build_openai_messages(system_value, final_user, image_b64_list)
                reply, used_model = _call_openai_chat(
                    f"{base}/chat/completions", "", model_value, messages,
                    temperature_value, max_tokens_value,
                )
            else:
                key = _get_api_key(api_key_value)
                base = _get_api_base(api_base_value)
                if not key:
                    raise ValueError(
                        "[NanoGPT] No API key found. Enter one in the node, "
                        "set NANOGPT_API_KEY env var, or save via /nanogpt/save_config."
                    )
                messages = _build_openai_messages(system_value, final_user, image_b64_list)
                reply, used_model = _call_openai_chat(
                    f"{base}/v1/chat/completions", key, model_value, messages,
                    temperature_value, max_tokens_value,
                )

            responses.append(reply)
            models_used.append(used_model)

        return io.NodeOutput(responses, models_used)
