"""
ComfyUI-CustomNodes
───────────────────
A unified package for custom ComfyUI nodes.

TO ADD A NEW NODE:
  1. Create a new file:  my_new_node.py
  2. Define NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS in it.
  3. Add one import line below and one register_nodes() call. Done.
"""

WEB_DIRECTORY = "./js"

# ──────────────────────────────────────────────
# Master registries
# ──────────────────────────────────────────────
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

def _register_nodes(module):
    """Merge a node module's mappings into the master registries."""
    if hasattr(module, "NODE_CLASS_MAPPINGS"):
        NODE_CLASS_MAPPINGS.update(module.NODE_CLASS_MAPPINGS)
    if hasattr(module, "NODE_DISPLAY_NAME_MAPPINGS"):
        NODE_DISPLAY_NAME_MAPPINGS.update(module.NODE_DISPLAY_NAME_MAPPINGS)

# ──────────────────────────────────────────────
# Register each node module
# ──────────────────────────────────────────────
# ➊ NanoGPT Chat Completion
from . import nanogpt_node
_register_nodes(nanogpt_node)

# ➋ Save Text to File
from . import save_text_node
_register_nodes(save_text_node)

# ➌ Save Folder String
from . import save_folder_node
_register_nodes(save_folder_node)

# ➍ Natural Language to Danbooru Tags
from . import nl2danbooru_node
_register_nodes(nl2danbooru_node)

# ➌ Add future nodes here:
# from . import my_new_node
# _register_nodes(my_new_node)

# ──────────────────────────────────────────────
print(f"[CustomNodes] ✅ Loaded {len(NODE_CLASS_MAPPINGS)} node(s): "
      f"{', '.join(NODE_DISPLAY_NAME_MAPPINGS.values())}")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]