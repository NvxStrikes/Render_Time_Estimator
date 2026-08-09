"""
Render Time Estimator + Logger - Blender Addon
Predicts render time before you commit, tracks live ETA during render, and logs render history locally.
"""

bl_info = {
    "name": "Render Time Estimator + Logger",
    "author": "NovaStrikes (Hamayl Shahbaz)",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "Render Properties > Render Insights",
    "description": "Estimate render time before committing, track live ETA, and log render history locally",
    "warning": "",
    "doc_url": "https://novastrikes.com/",
    "category": "Render",
}

import bpy
from .history import RenderHistoryItem, sync_history_to_wm
from .preferences import RenderTimeEstimatorPreferences
from .operators import (
    RENDER_OT_estimate_render_time,
    RENDER_OT_confirm_estimate,
    RENDER_OT_clear_render_history,
    RENDER_OT_export_render_history_csv,
)
from .panels import (
    RENDER_UL_history_list,
    RENDER_PT_insights_panel,
    RENDER_PT_history_panel,
)
from .render_hooks import register_handlers, unregister_handlers

classes = (
    RenderHistoryItem,
    RenderTimeEstimatorPreferences,
    RENDER_OT_estimate_render_time,
    RENDER_OT_confirm_estimate,
    RENDER_OT_clear_render_history,
    RENDER_OT_export_render_history_csv,
    RENDER_UL_history_list,
    RENDER_PT_insights_panel,
    RENDER_PT_history_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Scene properties
    bpy.types.Scene.ste_last_estimate = bpy.props.FloatProperty(
        name="Last Estimate",
        default=0.0
    )
    bpy.types.Scene.ste_last_estimate_per_frame = bpy.props.FloatProperty(
        name="Last Estimate per Frame",
        default=0.0
    )
    bpy.types.Scene.ste_last_estimate_total = bpy.props.FloatProperty(
        name="Last Estimate Total",
        default=0.0
    )
    bpy.types.Scene.ste_last_frame_count = bpy.props.IntProperty(
        name="Last Frame Count",
        default=1
    )
    bpy.types.Scene.ste_is_adaptive_sampling = bpy.props.BoolProperty(
        name="Is Adaptive Sampling",
        default=False
    )
    bpy.types.Scene.ste_last_method = bpy.props.StringProperty(
        name="Last Estimation Method",
        default=""
    )

    # WindowManager properties
    bpy.types.WindowManager.ste_live_is_rendering = bpy.props.BoolProperty(
        name="Is Rendering",
        default=False
    )
    bpy.types.WindowManager.ste_live_elapsed = bpy.props.StringProperty(
        name="Live Elapsed",
        default="0s"
    )
    bpy.types.WindowManager.ste_live_eta = bpy.props.StringProperty(
        name="Live ETA",
        default="N/A"
    )
    bpy.types.WindowManager.render_history_items = bpy.props.CollectionProperty(
        type=RenderHistoryItem
    )
    bpy.types.WindowManager.render_history_index = bpy.props.IntProperty(
        name="History Index",
        default=0
    )

    register_handlers()

    # Deferred sync for window_manager history collection
    def deferred_sync():
        sync_history_to_wm(bpy.context)
        return None

    bpy.app.timers.register(deferred_sync, first_interval=0.1)


def unregister():
    unregister_handlers()

    # Remove Scene & WindowManager properties
    for prop in ("ste_last_estimate", "ste_last_estimate_per_frame", "ste_last_estimate_total", "ste_last_frame_count", "ste_is_adaptive_sampling", "ste_last_method"):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

    for prop in ("ste_live_is_rendering", "ste_live_elapsed", "ste_live_eta", "render_history_items", "render_history_index"):
        if hasattr(bpy.types.WindowManager, prop):
            delattr(bpy.types.WindowManager, prop)

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


if __name__ == "__main__":
    register()
