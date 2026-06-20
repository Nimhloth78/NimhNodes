import os
import folder_paths

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
    name = rel.rpartition("/")[2]          # strip folder
    name = os.path.splitext(name)[0]       # strip extension
    head, sep, tail = name.partition("_")  # strip numeric prefix
    if sep and head.isdigit():
        name = tail
    return name

def category_name(rel):
    """'Image/3_Qwen Selfie.md' -> 'Image'  (root files -> '')"""
    folder = rel.rpartition("/")[0]
    return folder

class SystemPromptPreset:
    @classmethod
    def INPUT_TYPES(cls):
        os.makedirs(PROMPT_DIR, exist_ok=True)

        def key(rel):
            folder, _, name = rel.rpartition("/")
            head = name.split("_", 1)[0]
            order = int(head) if head.isdigit() else 9999
            return (folder.lower(), order, name.lower())

        return {"required": {"preset": (sorted(list_presets(), key=key),)}}

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("system_prompt", "preset_name", "category")
    FUNCTION = "load"
    CATEGORY = "NimhNodes"

    def load(self, preset):
        path = os.path.join(PROMPT_DIR, *preset.split("/"))
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return (text, clean_name(preset), category_name(preset))

    @classmethod
    def IS_CHANGED(cls, preset):
        path = os.path.join(PROMPT_DIR, *preset.split("/"))
        return os.path.getmtime(path)

NODE_CLASS_MAPPINGS = {"SystemPromptPreset": SystemPromptPreset}
NODE_DISPLAY_NAME_MAPPINGS = {"SystemPromptPreset": "System Prompt Preset"}