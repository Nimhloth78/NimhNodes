"""
Folder Prompt Preset Node
─────────────────────────
Like SystemPromptPreset, but the folder is chosen per node instance, so the
same node can load emotion prompts in one place and camera/style prompts in
another. Relative folder paths are resolved against the ComfyUI base folder.
"""

import os

import folder_paths
from server import PromptServer
from aiohttp import web
from comfy_api.latest import io

from .sysprom_preset import clean_name, category_name

DEFAULT_FOLDER = os.path.join(folder_paths.base_path, "system_prompts")
EXTENSIONS = (".md", ".txt")
PLACEHOLDER = "(no prompt files found - check folder, then 🔄 Refresh)"


def _resolve_folder(folder):
    folder = (folder or "").strip().strip('"')
    if not folder:
        return DEFAULT_FOLDER
    folder = os.path.expanduser(folder)
    if not os.path.isabs(folder):
        folder = os.path.join(folder_paths.base_path, folder)
    return os.path.normpath(folder)


def _sort_key(rel):
    folder, _, name = rel.rpartition("/")
    head = name.split("_", 1)[0]
    order = int(head) if head.isdigit() else 9999
    return (folder.lower(), order, name.lower())


def _list_presets(root):
    presets = []
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith(EXTENSIONS):
                rel = os.path.relpath(os.path.join(dirpath, f), root)
                presets.append(rel.replace(os.sep, "/"))
    return sorted(presets, key=_sort_key)


def _preset_path(root, preset):
    """Join and verify the file really lives inside root with an allowed extension."""
    path = os.path.normpath(os.path.join(root, *preset.split("/")))
    if os.path.commonpath([root, path]) != root or not path.lower().endswith(EXTENSIONS):
        raise ValueError(f"[FolderPromptPreset] Invalid preset: {preset}")
    return path


@PromptServer.instance.routes.get("/nimh/folder_presets")
async def _route_folder_presets(request):
    root = _resolve_folder(request.query.get("folder", ""))
    if not os.path.isdir(root):
        return web.json_response({"presets": [], "folder": root, "error": f"Folder not found: {root}"})
    presets = _list_presets(root)
    return web.json_response({
        "presets": presets,
        "folder": root,
        "error": "" if presets else f"No .md/.txt files in {root}",
    })


class FolderPromptPreset(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        os.makedirs(DEFAULT_FOLDER, exist_ok=True)
        presets = _list_presets(DEFAULT_FOLDER) or [PLACEHOLDER]
        return io.Schema(
            node_id="FolderPromptPreset",
            display_name="Folder Prompt Preset",
            category="NimhNodes",
            description=(
                "Loads a .md/.txt prompt file from any folder you choose. Relative paths "
                "are resolved against the ComfyUI folder. Subfolders become the category. "
                "Leave the folder blank to use ComfyUI/system_prompts."
            ),
            inputs=[
                io.String.Input("folder", default="",
                    placeholder="D:/prompts/emotions  (blank = ComfyUI/system_prompts)"),
                io.Combo.Input("preset", options=presets),
            ],
            outputs=[
                io.String.Output("text"),
                io.String.Output("preset_name"),
                io.String.Output("category"),
            ],
        )

    # Naming `preset` here makes ComfyUI skip its static combo-option check,
    # since the valid options depend on the folder chosen in the UI.
    @classmethod
    def validate_inputs(cls, folder, preset):
        if preset.startswith("("):
            return "No prompt selected. Check the folder and click 🔄 Refresh."
        root = _resolve_folder(folder)
        if not os.path.isdir(root):
            return f"Folder not found: {root}"
        try:
            path = _preset_path(root, preset)
        except ValueError as e:
            return str(e)
        if not os.path.isfile(path):
            return f"Prompt file not found: {preset} (in {root})"
        return True

    @classmethod
    def fingerprint_inputs(cls, folder, preset):
        try:
            return (_resolve_folder(folder), preset,
                    os.path.getmtime(_preset_path(_resolve_folder(folder), preset)))
        except (OSError, ValueError):
            return 0

    @classmethod
    def execute(cls, folder, preset):
        path = _preset_path(_resolve_folder(folder), preset)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return io.NodeOutput(text, clean_name(preset), category_name(preset))
