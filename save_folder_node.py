"""
Save Folder String Node (Extended)
───────────────────────────────────
Builds a folder path string with support for up to 5 levels of directory depth:
  preset_folder / custom_folder / subfolder_1 / subfolder_2 / subfolder_3

Date folder can be injected at the top or bottom of the stack.
"""

import os
from datetime import datetime
import json

class SaveFolderString:
    PRESETS_FILENAME = "save_folder_presets.json"

    @classmethod
    def _presets_path(cls) -> str:
        return os.path.join(os.path.dirname(__file__), cls.PRESETS_FILENAME)

    @classmethod
    def _load_presets(cls):
        defaults = [
            "Images",
            "Video",
            "Inpaint",
            "Controlnet",
            "Edits",
            "Faceswap",
            "Creatures",
            "Backdrops",
        ]
        try:
            with open(cls._presets_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                cleaned = []
                for x in data:
                    if isinstance(x, str):
                        s = x.strip()
                        if s and s not in cleaned:
                            cleaned.append(s)
                return cleaned or defaults
        except Exception:
            pass
        return defaults

    @classmethod
    def INPUT_TYPES(cls):
        preset_options = ["None"] + cls._load_presets()
        return {
            "required": {
                "preset_folder": (preset_options, {"default": "None"}),
                "date_folder": ("BOOLEAN", {"default": True}),
                "date_folder_position": (["first", "last"], {"default": "first"}),
                "custom_folder": ("STRING", {"default": "", "multiline": False}),
                "subfolder_1": ("STRING", {"default": "", "multiline": False}),
                "subfolder_2": ("STRING", {"default": "", "multiline": False}),
                "subfolder_3": ("STRING", {"default": "", "multiline": False}),
                "date_in_filename": (["Off", "prefix", "suffix"], {"default": "Off"}),
                "filename": ("STRING", {"default": "Image", "multiline": False}),
                "add_timestamp": ("BOOLEAN", {"default": False}),
                "separator": ("STRING", {"default": "_", "multiline": False}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING",)
    RETURN_NAMES = ("path", "dir_only", "filename",)
    FUNCTION = "build"
    CATEGORY = "NimhNodes"

    def _safe_part(self, s: str) -> str:
        """Remove characters invalid in file/dir names across OSes."""
        invalid = '<>:"/\\|?*\n\r\t'
        return "".join(c for c in s if c not in invalid).strip()

    def build(
        self,
        preset_folder: str = "None",
        date_folder: bool = True,
        date_folder_position: str = "first",
        custom_folder: str = "",
        subfolder_1: str = "",
        subfolder_2: str = "",
        subfolder_3: str = "",
        date_in_filename: str = "Off",
        filename: str = "Image",
        add_timestamp: bool = False,
        separator: str = "_",
    ):
        # Normalize and sanitize
        preset_folder = (preset_folder or "None").strip()
        custom_folder = self._safe_part(custom_folder or "")
        subfolder_1   = self._safe_part(subfolder_1 or "")
        subfolder_2   = self._safe_part(subfolder_2 or "")
        subfolder_3   = self._safe_part(subfolder_3 or "")
        filename      = self._safe_part(filename or "Image") or "Image"
        separator     = self._safe_part(separator or "_") or "_"

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H-%M-%S")

        # Build folder stack (without date)
        base_parts = []
        if preset_folder and preset_folder != "None":
            base_parts.append(self._safe_part(preset_folder))
        if custom_folder:
            base_parts.append(custom_folder)
        if subfolder_1:
            base_parts.append(subfolder_1)
        if subfolder_2:
            base_parts.append(subfolder_2)
        if subfolder_3:
            base_parts.append(subfolder_3)

        # Inject date folder at chosen position
        if date_folder:
            if (date_folder_position or "first").lower() == "first":
                parts = [date_str] + base_parts
            else:
                parts = base_parts + [date_str]
        else:
            parts = base_parts

        # Build filename with optional date and timestamp
        name = filename
        if date_in_filename == "prefix":
            name = f"{date_str}{separator}{filename}"
        elif date_in_filename == "suffix":
            name = f"{filename}{separator}{date_str}"

        if add_timestamp:
            name = f"{name}{separator}{time_str}"

        # Join with forward slashes for ComfyUI cross-platform consistency
        folder_path = "/".join(p for p in parts if p)
        path = f"{folder_path}/{name}" if folder_path else name

        dir_only = folder_path if folder_path else ""
        filename_only = name

        return (path, dir_only, filename_only,)

# ──────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────

NODE_CLASS_MAPPINGS = {
    "SaveFolderString": SaveFolderString,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SaveFolderString": "📁 Save Folder String",
}