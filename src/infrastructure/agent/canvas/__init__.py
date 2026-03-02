"""Canvas/A2UI module for dynamic UI block management.

Public API:
    - CanvasBlockType, CanvasBlock, CanvasState  (models)
    - CanvasManager                               (state management)
    - configure_canvas                            (DI)
    - canvas_create, canvas_update, canvas_delete (tools)
    - build_canvas_event_dict                     (event helper)
"""

from src.infrastructure.agent.canvas.events import build_canvas_event_dict
from src.infrastructure.agent.canvas.manager import CanvasManager
from src.infrastructure.agent.canvas.models import (
    CanvasBlock,
    CanvasBlockType,
    CanvasState,
)
from src.infrastructure.agent.canvas.tools import configure_canvas

__all__ = [
    "CanvasBlock",
    "CanvasBlockType",
    "CanvasManager",
    "CanvasState",
    "build_canvas_event_dict",
    "configure_canvas",
]
