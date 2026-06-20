import os
import folder_paths

from comfy_api.latest import io

PROMPT_DIR = os.path.join(folder_paths.base_path, "system_prompts")

def list_presets():
    presets = []
    for root, _, files in os.walk(PROMPT_DIR):
        for f in files:
            if f.endswith((".md", ".txt")):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, PROMPT_DIR)
                presets.append(rel.replace(os.sep, "/"))
    return presets

def clean_name(rel):
    """'Image/3_Qwen Selfie.md' -> 'Qwen Selfie'"""
    name = rel.rpartition("/")[2]
    name = os.path.splitext(name)[0]
    head, sep, tail = name.partition("_")
    if sep and head.isdigit():
        name = tail
    return name

def category_name(rel):
    """'Image/3_Qwen Selfie.md' -> 'Image'  (root files -> '')"""
    return rel.rpartition("/")[0]


class SystemPromptPreset(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        os.makedirs(PROMPT_DIR, exist_ok=True)

        def key(rel):
            folder, _, name = rel.rpartition("/")
            head = name.split("_", 1)[0]
            order = int(head) if head.isdigit() else 9999
            return (folder.lower(), order, name.lower())

        presets = sorted(list_presets(), key=key)

        return io.Schema(
            node_id="SystemPromptPreset",
            display_name="System Prompt Preset",
            category="NimhNodes",
            inputs=[
                io.Combo.Input("preset", options=presets),
            ],
            outputs=[
                io.String.Output("system_prompt"),
                io.String.Output("preset_name"),
                io.String.Output("category"),
            ],
        )

    @classmethod
    def fingerprint_inputs(cls, preset):
        path = os.path.join(PROMPT_DIR, *preset.split("/"))
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0

    @classmethod
    def execute(cls, preset):
        path = os.path.join(PROMPT_DIR, *preset.split("/"))
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return io.NodeOutput(text, clean_name(preset), category_name(preset))
