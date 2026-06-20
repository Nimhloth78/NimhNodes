"""
Save Text to File Node
──────────────────────
Saves text to a uniquely-named file on every execution.
Files are never overwritten.
"""

import os
import re
import time
import datetime
import folder_paths

from comfy_api.latest import io

# ──────────────────────────────────────────────
# Node
# ──────────────────────────────────────────────

class SaveTextToFile(io.ComfyNode):
    NAMING_MODES  = ["counter", "timestamp", "counter_and_timestamp"]
    EXTENSIONS    = [".txt", ".md", ".json", ".log", ".csv", ".html", ".xml", ".yaml"]
    ENCODINGS     = ["utf-8", "utf-16", "ascii", "latin-1"]
    NEWLINE_MODES = ["system_default", "unix_lf", "windows_crlf"]

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SaveTextToFile",
            display_name="💾 Save Text to File",
            category="NimhNodes",
            is_output_node=True,
            inputs=[
                io.String.Input("text", multiline=True, default="",
                    placeholder="Enter text or connect from another node…"),
                io.String.Input("base_directory",
                    default=folder_paths.get_output_directory(),
                    placeholder="/path/to/output (default: ComfyUI output)"),
                io.String.Input("subdirectory", default="text_files",
                    placeholder="subfolder (leave empty for none)"),
                io.String.Input("filename_prefix", default="saved_text"),
                io.Combo.Input("file_extension", options=cls.EXTENSIONS, default=".txt"),
                io.Combo.Input("naming_mode", options=cls.NAMING_MODES, default="counter"),
                io.Int.Input("counter_digits", default=4, min=1, max=10, step=1,
                    display_mode=io.NumberDisplay.slider),
                io.Combo.Input("encoding", options=cls.ENCODINGS, default="utf-8"),
                io.Combo.Input("newline_mode", options=cls.NEWLINE_MODES, default="system_default"),
                io.String.Input("prepend_text", force_input=True, optional=True),
                io.String.Input("append_text", force_input=True, optional=True),
            ],
            outputs=[
                io.String.Output("saved_text"),
                io.String.Output("file_path"),
                io.String.Output("filename"),
            ],
        )

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return time.time()

    @classmethod
    def execute(
        cls, text, base_directory, subdirectory, filename_prefix,
        file_extension, naming_mode, counter_digits, encoding,
        newline_mode, prepend_text="", append_text=""
    ):
        parts = []
        if prepend_text:
            parts.append(prepend_text)
        parts.append(text)
        if append_text:
            parts.append(append_text)
        final_text = "\n".join(parts)

        newline = cls._resolve_newline(newline_mode)

        full_dir = cls._resolve_directory(base_directory, subdirectory)
        os.makedirs(full_dir, exist_ok=True)

        safe_prefix = cls._sanitize_filename(filename_prefix)
        if not safe_prefix:
            safe_prefix = "saved_text"

        filename = cls._generate_unique_filename(
            full_dir, safe_prefix, file_extension,
            naming_mode, counter_digits
        )
        full_path = os.path.join(full_dir, filename)

        with open(full_path, "w", encoding=encoding, newline=newline) as f:
            f.write(final_text)

        file_size = os.path.getsize(full_path)
        print(f"[SaveText] ✅ Saved {file_size:,} bytes → {full_path}")

        return io.NodeOutput(
            final_text, full_path, filename,
            ui={
                "saved_path":     [full_path],
                "saved_filename": [filename],
                "saved_size":     [f"{file_size:,} bytes"],
            },
        )

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

    @classmethod
    def _generate_unique_filename(cls, directory, prefix, ext, mode, padding):
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if mode == "counter":
            counter = cls._next_counter(directory, prefix, ext, padding)
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
            counter = cls._next_counter(directory, prefix, ext, padding)
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
