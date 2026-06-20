import os
import folder_paths

PROMPT_DIR = os.path.join(folder_paths.base_path, "system_prompts")

class SystemPromptPreset:
    @classmethod
    def INPUT_TYPES(cls):
        os.makedirs(PROMPT_DIR, exist_ok=True)
        files = [f for f in os.listdir(PROMPT_DIR)
                 if f.endswith((".md", ".txt"))]
        # sort by leading number if present ("0_CharGen.md"), else alpha
        def key(f):
            head = f.split("_", 1)[0]
            return (int(head), f) if head.isdigit() else (9999, f)
        return {"required": {"preset": (sorted(files, key=key),)}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("system_prompt",)
    FUNCTION = "load"
    CATEGORY = "NimhNodes"

    def load(self, preset):
        with open(os.path.join(PROMPT_DIR, preset), "r", encoding="utf-8") as f:
            return (f.read(),)

    @classmethod
    def IS_CHANGED(cls, preset):
        return os.path.getmtime(os.path.join(PROMPT_DIR, preset))

NODE_CLASS_MAPPINGS = {"SystemPromptPreset": SystemPromptPreset}
NODE_DISPLAY_NAME_MAPPINGS = {"SystemPromptPreset": "System Prompt Preset"}