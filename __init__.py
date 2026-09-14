"""ComfyUI-FrameSelector: extract every frame of a video, pause the workflow
and let the user select which images continue to the next step."""

from . import server  # noqa: F401  (side effect: registers HTTP routes)
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]