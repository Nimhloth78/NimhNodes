"""
ComfyUI-NimhNodes
─────────────────
A unified package for custom ComfyUI nodes (V3 API).

TO ADD A NEW NODE:
  1. Create a new file:  my_new_node.py
  2. Define a class inheriting from io.ComfyNode with define_schema + execute.
  3. Import the class here and add it to NimhNodesExtension.get_node_list(). Done.
"""

from typing_extensions import override
from comfy_api.latest import ComfyExtension, io

WEB_DIRECTORY = "./js"

# ──────────────────────────────────────────────
# Import node classes
# ──────────────────────────────────────────────
from .nanogpt_node import NanoGPT_ChatCompletion
from .save_text_node import SaveTextToFile
from .save_folder_node import SaveFolderString
from .nl2danbooru_node import NL2DanbooruTags
from .sysprom_preset import SystemPromptPreset

# ──────────────────────────────────────────────
# Extension registration
# ──────────────────────────────────────────────

class NimhNodesExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            NanoGPT_ChatCompletion,
            SaveTextToFile,
            SaveFolderString,
            NL2DanbooruTags,
            SystemPromptPreset,
        ]


async def comfy_entrypoint() -> NimhNodesExtension:
    return NimhNodesExtension()
