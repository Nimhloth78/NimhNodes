"""
Save Text to File Node
──────────────────────
Saves text to a uniquely-named file on every execution.
Files are never overwritten.
"""

import os
import re
import datetime
import folder_paths

# ──────────────────────────────────────────────
# Node
# ──────────────────────────────────────────────

class SaveTextToFile:
    """
    Saves text to a new file each time using counter,
    timestamp, or both for unique naming.
    """

    NAMING_MODES  = ["counter", "timestamp", "counter_and_timestamp"]
    EXTENSIONS    = [".txt", ".md", ".json", ".log", ".csv", ".html", ".xml", ".yaml"]
    ENCODINGS     = ["utf-8", "utf-16", "ascii", "latin-1"]
    NEWLINE_MODES = ["system_default", "unix_lf", "windows_crlf"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "placeholder": "Enter text or connect from another node…",
                }),
                "base_directory": ("STRING", {
                    "default": folder_paths.get_output_directory(),
                    "multiline": False,
                    "placeholder": "/path/to/output (default: ComfyUI output)",
                }),
                "subdirectory": ("STRING", {
                    "default": "text_files",
                    "multiline": False,
                    "placeholder": "subfolder (leave empty for none)",
                }),
                "filename_prefix": ("STRING", {
                    "default": "saved_text",
                    "multiline": False,
                }),
                "file_extension": (cls.EXTENSIONS, {
                    "default": ".txt",
                }),
                "naming_mode": (cls.NAMING_MODES, {
                    "default": "counter",
                }),
                "counter_digits": ("INT", {
                    "default": 4,
                    "min": 1,
                    "max": 10,
                    "step": 1,
                    "display": "slider",
                }),
                "encoding": (cls.ENCODINGS, {
                    "default": "utf-8",
                }),
                "newline_mode": (cls.NEWLINE_MODES, {
                    "default": "system_default",
                }),
            },
            "optional": {
                "prepend_text": ("STRING", {"forceInput": True}),
                "append_text":  ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING",)
    RETURN_NAMES = ("saved_text", "file_path", "filename",)
    FUNCTION     = "save_text"
    CATEGORY     = "NimhNodes"
    OUTPUT_NODE  = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Always execute so a new file is created every queue
        return float("nan")

    # ── Main logic ───────────────────────────────────────

    def save_text(
        self, text, base_directory, subdirectory, filename_prefix,
        file_extension, naming_mode, counter_digits, encoding,
        newline_mode, prepend_text="", append_text=""
    ):
        # 1. Assemble final text
        parts = []
        if prepend_text:
            parts.append(prepend_text)
        parts.append(text)
        if append_text:
            parts.append(append_text)
        final_text = "\n".join(parts)

        newline = self._resolve_newline(newline_mode)

        # 2. Resolve and create directory
        full_dir = self._resolve_directory(base_directory, subdirectory)
        os.makedirs(full_dir, exist_ok=True)

        # 3. Sanitize prefix
        safe_prefix = self._sanitize_filename(filename_prefix)
        if not safe_prefix:
            safe_prefix = "saved_text"

        # 4. Generate unique filename
        filename = self._generate_unique_filename(
            full_dir, safe_prefix, file_extension,
            naming_mode, counter_digits
        )
        full_path = os.path.join(full_dir, filename)

        # 5. Write file
        with open(full_path, "w", encoding=encoding, newline=newline) as f:
            f.write(final_text)

        file_size = os.path.getsize(full_path)
        print(f"[SaveText] ✅ Saved {file_size:,} bytes → {full_path}")

        # 6. Return
        return {
            "ui": {
                "saved_path":     [full_path],
                "saved_filename": [filename],
                "saved_size":     [f"{file_size:,} bytes"],
            },
            "result": (final_text, full_path, filename,),
        }

    # ── Helpers ──────────────────────────────────────────

    @staticmethod
    def _resolve_newline(mode):
        if mode == "unix_lf":
            return "\n"
        if mode == "windows_crlf":
            return "\r\n"
        return None

    @staticmethod
    def _resolve_directory(base, sub):
        base = base.strip()
        sub  = sub.strip().strip("/").strip("\\")

        if not base:
            base = folder_paths.get_output_directory()
        if not os.path.isabs(base):
            base = os.path.join(folder_paths.get_output_directory(), base)
        if sub:
            return os.path.join(base, sub)
        return base

    @staticmethod
    def _sanitize_filename(name):
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name.strip())

    def _generate_unique_filename(self, directory, prefix, ext, mode, padding):
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if mode == "counter":
            counter = self._next_counter(directory, prefix, ext, padding)
            return f"{prefix}_{str(counter).zfill(padding)}{ext}"

        if mode == "timestamp":
            candidate = f"{prefix}_{timestamp}{ext}"
            if os.path.exists(os.path.join(directory, candidate)):
                ms = now.strftime("%f")[:3]
                candidate = f"{prefix}_{timestamp}_{ms}{ext}"
            if os.path.exists(os.path.join(directory, candidate)):
                candidate = f"{prefix}_{timestamp}_{now.strftime('%f')}{ext}"
            return candidate

        if mode == "counter_and_timestamp":
            counter = self._next_counter(directory, prefix, ext, padding)
            return f"{prefix}_{str(counter).zfill(padding)}_{timestamp}{ext}"

        return f"{prefix}_{timestamp}{ext}"

    @staticmethod
    def _next_counter(directory, prefix, ext, padding):
        if not os.path.isdir(directory):
            return 1

        max_counter = 0
        pattern = re.compile(
            rf"^{re.escape(prefix)}_(\d+)"
            rf"(?:_\d{{8}}_\d{{6}}(?:_\d{{3,6}})?)?"
            rf"{re.escape(ext)}$"
        )

        for fname in os.listdir(directory):
            m = pattern.match(fname)
            if m:
                val = int(m.group(1))
                if val > max_counter:
                    max_counter = val

        return max_counter + 1

# ──────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────

NODE_CLASS_MAPPINGS = {
    "SaveTextToFile": SaveTextToFile,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SaveTextToFile": "💾 Save Text to File",
}