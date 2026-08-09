"""
App handler hooks for real-time ETA tracking and render history logging.
"""

import os
import time
import bpy

from .utils import get_render_device, get_timestamp_iso, format_time, get_addon_preferences
from .history import add_history_entry

# Module-level state for current render session
_render_state = {
    "is_rendering": False,
    "is_cancelled": False,
    "start_time": 0.0,
    "frame_start_time": 0.0,
    "frame_times": [],
    "rendered_frames": 0,
    "total_frames": 1,
    "single_frame": True,
}


def _get_prefs():
    return get_addon_preferences(bpy.context)


@bpy.app.handlers.persistent
def on_render_pre(scene, history=None):
    """Callback fired immediately before render starts."""
    global _render_state

    # Avoid tracking internal sample estimation passes
    filepath = scene.render.filepath
    if "_ste_sample_render" in filepath:
        return

    now = time.time()
    wm = bpy.context.window_manager

    # Check if rendering single frame or animation range
    frame_start = scene.frame_start
    frame_end = scene.frame_end
    frame_step = max(1, scene.frame_step)

    # Frame count calculation
    if frame_end >= frame_start:
        total_frames = max(1, ((frame_end - frame_start) // frame_step) + 1)
    else:
        total_frames = 1

    _render_state["is_rendering"] = True
    _render_state["is_cancelled"] = False
    _render_state["start_time"] = now
    _render_state["frame_start_time"] = now
    _render_state["frame_times"] = []
    _render_state["rendered_frames"] = 0
    _render_state["total_frames"] = total_frames
    # NOTE: this is only a starting guess based on the scene's configured
    # frame range. It does NOT reliably tell us whether the user pressed
    # "render single frame" (F12) vs "render animation" - Blender's frame
    # range can be 1-250 while the user still only renders one still frame
    # via F12. The real signal is how many times on_render_post actually
    # fires before on_render_complete, which is only known in hindsight -
    # see _finish_render_session, which corrects this using the real count.
    _render_state["single_frame"] = (total_frames <= 1)

    wm.ste_live_is_rendering = True
    wm.ste_live_elapsed = "0s"
    wm.ste_live_eta = "Calculating..." if total_frames > 1 else "In Progress..."


@bpy.app.handlers.persistent
def on_render_post(scene, history=None):
    """Callback fired after each frame completes."""
    global _render_state

    filepath = scene.render.filepath
    if "_ste_sample_render" in filepath or not _render_state["is_rendering"]:
        return

    now = time.time()
    frame_duration = now - _render_state["frame_start_time"]
    _render_state["frame_start_time"] = now
    _render_state["frame_times"].append(frame_duration)
    _render_state["rendered_frames"] += 1

    total_elapsed = now - _render_state["start_time"]
    wm = bpy.context.window_manager
    wm.ste_live_elapsed = format_time(total_elapsed)

    # Calculate rolling ETA for multi-frame animations
    if not _render_state["single_frame"]:
        rendered = _render_state["rendered_frames"]
        total = _render_state["total_frames"]
        remaining = max(0, total - rendered)
        
        # Rolling average frame time
        avg_frame_time = sum(_render_state["frame_times"]) / max(1, len(_render_state["frame_times"]))
        remaining_eta = avg_frame_time * remaining
        wm.ste_live_eta = format_time(remaining_eta)
    else:
        # Single-frame stills only have one frame, so there's no "next frame"
        # to learn a rate from - by the time this handler fires the one and
        # only frame is already done. Rather than guess, show real elapsed
        # time with an honest label instead of a fabricated ETA.
        wm.ste_live_eta = "Done (single frame)"


@bpy.app.handlers.persistent
def on_render_complete(scene, history=None):
    """Callback fired when full render sequence finishes successfully."""
    _finish_render_session(scene, status="completed")


@bpy.app.handlers.persistent
def on_render_cancel(scene, history=None):
    """Callback fired when render is cancelled by user."""
    _finish_render_session(scene, status="cancelled")


def _finish_render_session(scene, status="completed"):
    global _render_state

    filepath = scene.render.filepath
    if "_ste_sample_render" in filepath:
        return

    if not _render_state["is_rendering"]:
        return

    total_duration = time.time() - _render_state["start_time"]
    _render_state["is_rendering"] = False

    wm = bpy.context.window_manager
    wm.ste_live_is_rendering = False
    wm.ste_live_elapsed = format_time(total_duration)

    # Decide single-frame vs animation using the ACTUAL number of frames
    # that were rendered (render_post fire count), not the scene's
    # configured frame range. A scene with Frame Start/End = 1-250 can
    # still be rendered as a single still via F12 - in that case
    # on_render_post only fires once, regardless of what the range says.
    actually_single_frame = _render_state["rendered_frames"] <= 1

    if status == "completed":
        wm.ste_live_eta = "Done (single frame)" if actually_single_frame else "Finished"
    else:
        wm.ste_live_eta = "Cancelled"

    prefs = _get_prefs()
    if prefs and not prefs.auto_log_renders:
        return

    # Capture details for history log
    blend_path = bpy.data.filepath
    blend_filename = os.path.basename(blend_path) if blend_path else "Unsaved"
    
    res_x = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
    res_y = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

    samples = None
    if scene.render.engine == 'CYCLES':
        samples = getattr(scene.cycles, 'samples', None)

    frame_range_str = f"{scene.frame_current}" if actually_single_frame else f"{scene.frame_start}-{scene.frame_end}"

    entry = {
        "timestamp": get_timestamp_iso(),
        "blend_filename": blend_filename,
        "scene_name": scene.name,
        "render_engine": scene.render.engine,
        "resolution": f"{res_x}x{res_y}",
        "samples": samples,
        "device": get_render_device(scene),
        "frame_range": frame_range_str,
        "duration_seconds": round(total_duration, 2),
        "status": status,
        "output_path": filepath or "Default"
    }

    add_history_entry(entry)


def register_handlers():
    """Register callbacks into bpy.app.handlers."""
    if on_render_pre not in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.append(on_render_pre)
    if on_render_post not in bpy.app.handlers.render_post:
        bpy.app.handlers.render_post.append(on_render_post)
    if on_render_complete not in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.append(on_render_complete)
    if on_render_cancel not in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.append(on_render_cancel)


def unregister_handlers():
    """Unregister callbacks from bpy.app.handlers."""
    if on_render_pre in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.remove(on_render_pre)
    if on_render_post in bpy.app.handlers.render_post:
        bpy.app.handlers.render_post.remove(on_render_post)
    if on_render_complete in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.remove(on_render_complete)
    if on_render_cancel in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.remove(on_render_cancel)
