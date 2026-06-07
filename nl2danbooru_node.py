"""
Natural Language to Danbooru Tags Node
──────────────────────────────────────
Converts natural language descriptions into Danbooru-style
tag prompts via an LLM, preserving all descriptive content.
"""

import json
import re
import urllib.request
import urllib.error

from .nanogpt_node import (
    _get_api_key,
    _get_api_base,
    _model_cache,
    DEFAULT_API_BASE,
)

# ──────────────────────────────────────────────
# Prompt Engineering
# ──────────────────────────────────────────────

DETAIL_INSTRUCTIONS = {
    "concise":    "Output approximately 10–20 essential tags capturing the core elements.",
    "standard":   "Output approximately 20–35 tags with good coverage of all mentioned details.",
    "detailed":   "Output approximately 35–50 tags, breaking every compound description into granular atomic tags.",
    "exhaustive": "Output 50+ tags. Tag every possible detail, implication, and visual element including implied lighting, atmosphere, composition, perspective, and framing.",
}

SYSTEM_PROMPT = """\
You are an expert Danbooru tag converter. Convert the user's natural-language \
description into Danbooru-style tags.

ABSOLUTE RULES — NEVER BREAK THESE:
1. PRESERVE ALL CONTENT — every visual detail in the input MUST appear as one \
or more tags. Never omit, skip, merge, or summarize details.
2. Output ONLY a single comma-separated line of tags.  \
No explanations, no headers, no numbering, no bullet points, no markdown, \
no categories, no commentary before or after the tags.

TAG CONVENTIONS:
- Multi-word tags use underscores: long_hair, blue_eyes, school_uniform
- Character count comes first: 1girl, 1boy, 2girls, solo, multiple_boys
- Hair: {color}_hair, {length}_hair, {style}_hair  \
  (e.g. blonde_hair, long_hair, ponytail, hair_over_one_eye)
- Eyes: {color}_eyes  (e.g. blue_eyes, heterochromia, closed_eyes)
- Body: large_breasts, petite, muscular, tall_female, dark_skin, pointy_ears
- Face / expression: smile, blush, open_mouth, angry, crying, smirk, pout
- Gaze: looking_at_viewer, looking_away, looking_up, eye_contact
- Clothing: use specific garment tags (dress, hoodie, armor, bikini, thighhighs)
- Accessories: glasses, hairband, necklace, earrings, hat, scarf
- Pose: standing, sitting, lying, kneeling, leaning_forward, arms_up, hand_on_hip
- Action: running, fighting, reading, eating, sleeping, dancing, walking
- Background: simple_background, outdoors, indoors, forest, cityscape, sky, night
- Lighting: sunlight, backlighting, dramatic_lighting, rim_lighting, dimly_lit
- Weather / time: rain, snow, sunset, night_sky, cloudy_sky
- Composition: close-up, full_body, upper_body, portrait, from_above, from_below, \
  dutch_angle, wide_shot
- Art style: watercolor_(medium), oil_painting_(medium), pixel_art, realistic, \
  anime_coloring, sketch, lineart
- Mood / atmosphere: dark, moody, vibrant, serene, ominous, cozy

DECOMPOSITION:
Break compound phrases into atomic tags.  \
"a tall girl with long flowing red hair smiling in a dark forest at night" → \
1girl, solo, tall_female, long_hair, red_hair, flowing_hair, smile, forest, \
dark, night, outdoors, trees

{detail_instruction}"""

QUALITY_PRESETS = {
    "none":                         "",
    "masterpiece, best quality":    "masterpiece, best_quality",
    "masterpiece, absurdres":       "masterpiece, best_quality, absurdres, highres",
    "high quality, detailed":       "high_quality, very_detailed",
    "anime masterpiece":            "masterpiece, best_quality, anime_coloring, detailed",
}

# ──────────────────────────────────────────────
# Node
# ──────────────────────────────────────────────

class NL2DanbooruTags:
    """
    Converts natural language text into Danbooru-style tag prompts
    using an LLM API (NanoGPT / OpenAI-compatible).
    All descriptive content is preserved.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "placeholder": "Describe your image in natural language…",
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "sk-… (or set NANOGPT_API_KEY env var)",
                }),
                "model": (_model_cache,),
                "detail_level": (
                    ["concise", "standard", "detailed", "exhaustive"],
                    {"default": "standard"},
                ),
                "tag_format": (
                    ["underscored", "spaced"],
                    {"default": "underscored"},
                ),
                "quality_tags": (
                    list(QUALITY_PRESETS.keys()),
                    {"default": "none"},
                ),
                "temperature": ("FLOAT", {
                    "default": 0.3,
                    "min": 0.0,
                    "max": 1.5,
                    "step": 0.05,
                    "display": "slider",
                }),
                "max_tokens": ("INT", {
                    "default": 512,
                    "min": 64,
                    "max": 4096,
                    "step": 64,
                }),
            },
            "optional": {
                "api_base_url": ("STRING", {
                    "default": DEFAULT_API_BASE,
                    "multiline": False,
                }),
                "input_text": ("STRING", {"forceInput": True}),
                "additional_tags": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Tags to always include (comma-separated)",
                }),
                "exclude_tags": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "placeholder": "Tags to remove (comma or newline separated)",
                }),
            },
        }

    RETURN_TYPES  = ("STRING", "STRING",)
    RETURN_NAMES  = ("tags", "raw_response",)
    FUNCTION      = "convert"
    CATEGORY      = "NimhNodes"
    OUTPUT_NODE   = True

    # ── Entry point ──────────────────────────────────────

    def convert(
        self, text, api_key, model, detail_level, tag_format,
        quality_tags, temperature, max_tokens,
        api_base_url="", input_text="",
        additional_tags="", exclude_tags=""
    ):
        key  = _get_api_key(api_key)
        base = _get_api_base(api_base_url)

        if not key:
            raise ValueError(
                "[NL2Danbooru] No API key. Enter one in the node "
                "or set NANOGPT_API_KEY env var."
            )
        if model.startswith("("):
            raise ValueError(
                "[NL2Danbooru] No model selected. Click 🔄 Refresh Models."
            )

        # Combine text inputs
        if input_text and text:
            full_text = f"{input_text}\n\n{text}"
        elif input_text:
            full_text = input_text
        else:
            full_text = text

        if not full_text.strip():
            raise ValueError("[NL2Danbooru] No text provided to convert.")

        # Build system prompt
        detail_instruction = DETAIL_INSTRUCTIONS.get(
            detail_level, DETAIL_INSTRUCTIONS["standard"]
        )
        system_content = SYSTEM_PROMPT.format(
            detail_instruction=detail_instruction
        )

        # ── API call ─────────────────────────────────────
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user",   "content": full_text.strip()},
        ]

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
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            choices = result.get("choices", [])
            if not choices:
                raise RuntimeError(
                    f"[NL2Danbooru] API returned no choices: {result}"
                )
            raw_response = choices[0].get("message", {}).get("content", "")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"[NL2Danbooru] API HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"[NL2Danbooru] Connection error: {e.reason}")

        # ── Post-process ─────────────────────────────────
        exclude_set = self._build_exclude_set(exclude_tags)
        cleaned = self._clean_tags(raw_response, tag_format, exclude_set)

        # Prepend quality tags
        quality = QUALITY_PRESETS.get(quality_tags, "")
        if quality:
            if tag_format == "spaced":
                quality = quality.replace("_", " ")
            cleaned = f"{quality}, {cleaned}" if cleaned else quality

        # Append additional tags
        if additional_tags and additional_tags.strip():
            extra = additional_tags.strip().strip(",").strip()
            if tag_format == "underscored":
                extra = re.sub(r"(?<=\w) (?=\w)", "_", extra)
            cleaned = f"{cleaned}, {extra}" if cleaned else extra

        # Final whitespace / comma cleanup
        cleaned = re.sub(r",\s*,+", ",", cleaned)       # collapse multiple commas
        cleaned = re.sub(r"\s{2,}", " ", cleaned)        # collapse whitespace
        cleaned = cleaned.strip().strip(",").strip()

        tag_count = len([t for t in cleaned.split(",") if t.strip()])
        print(f"[NL2Danbooru] ✅ Generated {tag_count} tags")

        return (cleaned, raw_response,)

    # ── Tag cleaning / normalization ─────────────────────

    @staticmethod
    def _build_exclude_set(exclude_tags):
        """Parse the exclude string into a normalized set."""
        exclude_set = set()
        if not exclude_tags:
            return exclude_set
        for line in exclude_tags.replace(",", "\n").split("\n"):
            t = line.strip().lower().replace(" ", "_")
            if t:
                exclude_set.add(t)
        return exclude_set

    @staticmethod
    def _clean_tags(raw_text, tag_format, exclude_set):
        """
        Robust post-processing of LLM output into a clean tag string.
        Handles markdown, preambles, numbered lists, category headers, etc.
        """
        text = raw_text.strip()

        # ── Strip markdown formatting ────────────────────
        text = re.sub(r"```[\s\S]*?```", "", text)          # code blocks
        text = re.sub(r"`([^`]+)`", r"\1", text)            # inline code
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)      # bold
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)  # italic

        # ── Strip common LLM preambles ───────────────────
        preamble_patterns = [
            r"^(?:here\s+(?:are|is)\s+.*?:\s*)",
            r"^(?:(?:the\s+)?(?:danbooru\s+)?tags?\s+.*?:\s*)",
            r"^(?:(?:converted|generated|resulting)\s+tags?\s*:?\s*)",
            r"^(?:tags?\s*:\s*)",
            r"^(?:output\s*:\s*)",
            r"^(?:prompt\s*:\s*)",
            r"^(?:sure[!,.]?\s*(?:here\s+.*?:\s*)?)",
            r"^(?:certainly[!,.]?\s*(?:here\s+.*?:\s*)?)",
            r"^(?:of\s+course[!,.]?\s*(?:here\s+.*?:\s*)?)",
        ]
        for pat in preamble_patterns:
            text = re.sub(pat, "", text, count=1, flags=re.IGNORECASE)

        # ── Strip trailing LLM commentary ────────────────
        # Cut off anything after a blank line followed by a sentence
        text = re.sub(
            r"\n\s*\n(?:note|this|these|the above|i |let me|feel free|hope).*",
            "", text, flags=re.IGNORECASE | re.DOTALL
        )

        # ── Strip list / category formatting ─────────────
        text = re.sub(r"^\d+[\.\)]\s*", "", text, flags=re.MULTILINE)   # numbered lists
        text = re.sub(r"^[-•·▸►]\s*", "", text, flags=re.MULTILINE)     # bullet points
        text = re.sub(r"\*\*[^*]+\*\*:?\s*", "", text)                  # **Category**:
        text = re.sub(
            r"^[A-Za-z_/\s]{2,25}:\s*(?=\w)", "", text, flags=re.MULTILINE
        )  # "Category:" headers

        # ── Normalize separators ─────────────────────────
        text = text.replace("\n", ", ").replace(";", ",")

        # ── Split and clean individual tags ──────────────
        raw_tags = [t.strip().strip("\"'()[]{}") for t in text.split(",")]

        cleaned = []
        seen = set()

        for tag in raw_tags:
            tag = tag.strip().strip(".").strip()

            # Skip empty or too-short tokens
            if not tag or len(tag) < 2:
                continue

            # Skip if it looks like a sentence (LLM explanation leak)
            word_count = len(tag.split())
            if word_count > 6 and "_" not in tag:
                continue

            # Skip if it's just a number
            if tag.isdigit():
                continue

            # Apply format preference
            if tag_format == "underscored":
                tag = re.sub(r"\s+", "_", tag)
            elif tag_format == "spaced":
                tag = tag.replace("_", " ")

            # Normalize for dedup and exclusion checks
            tag_norm = tag.lower().replace(" ", "_").strip("_")

            if tag_norm in seen:
                continue
            seen.add(tag_norm)

            if tag_norm in exclude_set:
                continue

            cleaned.append(tag)

        return ", ".join(cleaned)

# ──────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────

NODE_CLASS_MAPPINGS = {
    "NL2DanbooruTags": NL2DanbooruTags,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NL2DanbooruTags": "🏷️ Natural Language to Danbooru Tags",
}