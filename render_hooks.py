"""
Copyright (C) 2026 NovaStrikes
https://novastrikes.com
contact@novastrikes.com

Created by NovaStrikes (Hamayl Shahbaz)

This file is part of Render Time Estimator + Logger.

Render Time Estimator + Logger is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 3
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, see https://www.gnu.org/licenses/gpl-3.0.txt.
"""

import os
import time
import bpy

from .utils import (
    get_render_device,
    get_timestamp_iso,
    format_time,
    get_addon_preferences,
    compute_settings_signature,
    get_window_manager,
)
from .history import add_history_entry, sync_history_to_wm

# Number of most-recent frame times used in the rolling ETA average.
ROLLING_AVG_WINDOW = 10

# Per-frame times are stored in the history JSON/CSV up to this many frames.
MAX_STORED_FRAME_TIMES = 2000

# How often (seconds) the main-thread UI timer refreshes the panel/status bar.
UI_TICK_SECONDS = 0.5

# ---------------------------------------------------------------------------
# v1.1.0 design notes
#
# 1) Session start moved to render_init. Blender fires render_pre / render_post
#    once PER FRAME during an animation render, but render_init and
#    render_complete only once per job. The old code reset all tracking state
#    in render_pre, so every frame wiped the elapsed time, frame list and ETA
#    back to "0s / Calculating..." and the job was logged as a single frame.
#
# 2) Render handlers can run on Blender's render thread, where bpy.context is
#    not safe to touch (this is what produces "Python context internal state
#    bug"). Handlers now ONLY update the plain-Python _render_state dict and
#    read the scene they are given. Everything that touches the UI (window
#    manager props, status bar, redraws, prefs) happens in _ui_tick, a
#    bpy.app.timers callback that runs on the main thread.
# ---------------------------------------------------------------------------

_render_state = {
    "is_rendering": False,
    "start_time": 0.0,
    "frame_start_time": 0.0,
    "frame_times": [],
    "rendered_frames": 0,
    "total_frames": 1,
    # Consumed estimate timestamp, so one estimate is never reused
    # (replaces writing back to the scene from the render thread).
    "consumed_estimate_ts": 0.0,
    # Handoff from handlers -> UI timer
    "ui_final": None,
    "pending_history_sync": False,
}

# Prefs cache, refreshed on the main thread by _ui_tick (and once in
# background mode). Handlers read this instead of touching bpy.context.
_prefs_cache = {
    "auto_log_renders": True,
    "live_eta_enabled": True,
    "show_status_bar_eta": True,
}

_logged_errors = set()


def _log_error_once(where, exc):
    key = (where, type(exc).__name__, str(exc))
    if key in _logged_errors:
        return
    _logged_errors.add(key)
    print(f"[Render Time Estimator] {where}: {type(exc).__name__}: {exc}")


def _is_internal_pass(scene):
    """True for the add-on's own silent estimation render."""
    try:
        return "_ste_sample_render" in scene.render.filepath
    except Exception:
        return False


def _refresh_prefs_cache():
    """Main-thread (or background-mode) only: copy prefs into the cache."""
    prefs = get_addon_preferences(bpy.context)
    for key in _prefs_cache:
        _prefs_cache[key] = bool(getattr(prefs, key, _prefs_cache[key]))


# ---------------------------------------------------------------------------
# ETA helpers (pure Python, safe anywhere)
# ---------------------------------------------------------------------------

def _eta_seconds():
    """Remaining seconds for an animation, or None if not known yet."""
    st = _render_state
    rendered = st["rendered_frames"]
    if rendered <= 0:
        return None
    remaining = max(0, st["total_frames"] - rendered)
    recent = st["frame_times"][-ROLLING_AVG_WINDOW:]
    avg = sum(recent) / max(1, len(recent))
    # Credit time already spent on the frame currently rendering.
    in_frame = min(max(0.0, time.time() - st["frame_start_time"]), avg)
    return max(0.0, avg * remaining - in_frame)


def _eta_text():
    st = _render_state
    if st["total_frames"] <= 1:
        return "In Progress..."
    eta = _eta_seconds()
    return "Calculating..." if eta is None else format_time(eta)


# ---------------------------------------------------------------------------
# UI helpers (MAIN THREAD ONLY - called from _ui_tick)
# ---------------------------------------------------------------------------

def _set_status_bar(wm, text=None):
    if text is not None and not _prefs_cache["show_status_bar_eta"]:
        return
    try:
        for window in wm.windows:
            ws = window.workspace
            if ws is not None:
                ws.status_text_set(text)
    except Exception as e:
        _log_error_once("status bar", e)


def _tag_properties_redraw(wm):
    try:
        for window in wm.windows:
            screen = window.screen
            if screen is None:
                continue
            for area in screen.areas:
                if area.type == 'PROPERTIES':
                    area.tag_redraw()
    except Exception as e:
        _log_error_once("redraw", e)


def _assign_wm(wm, is_rendering, elapsed, eta):
    changed = False
    if wm.ste_live_is_rendering != is_rendering:
        wm.ste_live_is_rendering = is_rendering
        changed = True
    if wm.ste_live_elapsed != elapsed:
        wm.ste_live_elapsed = elapsed
        changed = True
    if wm.ste_live_eta != eta:
        wm.ste_live_eta = eta
        changed = True
    return changed


def _push_ui_state():
    wm = get_window_manager()
    if wm is None:
        return
    st = _render_state
    changed = False

    if st["is_rendering"]:
        now = time.time()
        elapsed_s = now - st["start_time"]
        elapsed = format_time(elapsed_s)
        eta = _eta_text()
        changed |= _assign_wm(wm, True, elapsed, eta)

        if st["total_frames"] > 1:
            eta_s = _eta_seconds()
            eta_part = "..." if eta_s is None else format_time(eta_s)
            _set_status_bar(
                wm,
                f"Render: Frame {st['rendered_frames']}/{st['total_frames']} | "
                f"Elapsed: {elapsed} | ETA: {eta_part}"
            )
        else:
            _set_status_bar(wm, f"Render: In Progress | Elapsed: {elapsed}")

    elif st["ui_final"] is not None:
        final = st["ui_final"]
        st["ui_final"] = None
        changed |= _assign_wm(wm, False, final["elapsed"], final["eta"])
        _set_status_bar(wm, None)

    if st["pending_history_sync"]:
        st["pending_history_sync"] = False
        sync_history_to_wm(bpy.context)
        changed = True

    if changed:
        _tag_properties_redraw(wm)


def _ui_tick():
    """Persistent main-thread timer that mirrors render state into the UI."""
    try:
        _refresh_prefs_cache()
        _push_ui_state()
    except Exception as e:
        _log_error_once("ui tick", e)
    return UI_TICK_SECONDS


# ---------------------------------------------------------------------------
# Render handlers (may run on the render thread: NO bpy.context in here)
# ---------------------------------------------------------------------------

def _start_session(scene):
    st = _render_state
    now = time.time()

    frame_start = scene.frame_start
    frame_end = scene.frame_end
    frame_step = max(1, scene.frame_step)
    if frame_end >= frame_start:
        total_frames = max(1, ((frame_end - frame_start) // frame_step) + 1)
    else:
        total_frames = 1

    st["is_rendering"] = True
    st["start_time"] = now
    st["frame_start_time"] = now
    st["frame_times"] = []
    st["rendered_frames"] = 0
    # Only a starting guess from the configured frame range. The true count
    # is known in hindsight from how many times render_post fires.
    st["total_frames"] = total_frames
    st["ui_final"] = None

    if bpy.app.background:
        # Headless/CLI renders run on the main thread and have no UI timer.
        try:
            _refresh_prefs_cache()
        except Exception as e:
            _log_error_once("prefs (background)", e)


@bpy.app.handlers.persistent
def on_render_init(scene, *args):
    """Fires ONCE when a render job (still or animation) starts."""
    try:
        if _is_internal_pass(scene):
            return
        _start_session(scene)
    except Exception as e:
        _log_error_once("render_init", e)


@bpy.app.handlers.persistent
def on_render_pre(scene, *args):
    """Fires before EACH frame. Only marks the frame start time."""
    try:
        if _is_internal_pass(scene):
            return
        if not _render_state["is_rendering"]:
            # render_init was missed for some reason: start the session now.
            _start_session(scene)
            return
        _render_state["frame_start_time"] = time.time()
    except Exception as e:
        _log_error_once("render_pre", e)


@bpy.app.handlers.persistent
def on_render_post(scene, *args):
    """Fires after EACH frame completes."""
    try:
        if _is_internal_pass(scene) or not _render_state["is_rendering"]:
            return
        now = time.time()
        st = _render_state
        st["frame_times"].append(now - st["frame_start_time"])
        st["frame_start_time"] = now
        st["rendered_frames"] += 1
    except Exception as e:
        _log_error_once("render_post", e)


@bpy.app.handlers.persistent
def on_render_complete(scene, *args):
    """Fires once when the whole render job finishes successfully."""
    _finish_render_session(scene, status="completed")


@bpy.app.handlers.persistent
def on_render_cancel(scene, *args):
    """Fires when the render job is cancelled by the user."""
    _finish_render_session(scene, status="cancelled")


def _finish_render_session(scene, status="completed"):
    st = _render_state
    try:
        if _is_internal_pass(scene) or not st["is_rendering"]:
            return

        total_duration = time.time() - st["start_time"]
        # Always release the session first so nothing below can leave it stuck.
        st["is_rendering"] = False

        rendered_frames = st["rendered_frames"]
        actually_single_frame = rendered_frames <= 1

        if status == "completed":
            eta_final = "Done (single frame)" if actually_single_frame else "Finished"
        else:
            eta_final = "Cancelled"
        st["ui_final"] = {"elapsed": format_time(total_duration), "eta": eta_final}

        _log_history_entry(scene, status, total_duration, actually_single_frame)
    except Exception as e:
        _log_error_once("finish", e)
        st["is_rendering"] = False


def _log_history_entry(scene, status, total_duration, actually_single_frame):
    st = _render_state

    # --- Pick a comparable stored estimate (if any) ---
    est_ts = scene.ste_last_estimate_timestamp
    estimate_is_fresh = (
        est_ts > 0
        and est_ts != st["consumed_estimate_ts"]
        and (time.time() - est_ts) < 1800
    )

    if estimate_is_fresh:
        stored_sig = getattr(scene, 'ste_last_estimate_signature', '')
        if stored_sig and stored_sig != compute_settings_signature(scene):
            estimate_is_fresh = False  # settings changed since estimating

    estimated = None
    if estimate_is_fresh:
        estimated_frame_count = getattr(scene, "ste_last_frame_count", 1)
        if actually_single_frame:
            if estimated_frame_count <= 1 and scene.ste_last_estimate_per_frame > 0:
                estimated = scene.ste_last_estimate_per_frame
        else:
            actual_frame_count = st["total_frames"]
            if (
                estimated_frame_count > 1
                and scene.ste_last_estimate_total > 0
                and actual_frame_count > 0
                and abs(estimated_frame_count - actual_frame_count) <= max(1, actual_frame_count * 0.1)
            ):
                estimated = scene.ste_last_estimate_total

    # Never reuse the same estimate for a later, unrelated render.
    if est_ts > 0:
        st["consumed_estimate_ts"] = est_ts

    has_estimate = estimated is not None and estimated > 0
    if has_estimate and status == "completed" and total_duration > 0:
        accuracy_pct = max(0.0, 100.0 - (abs(total_duration - estimated) / total_duration * 100.0))
        estimated_seconds = estimated
    else:
        accuracy_pct = None
        estimated_seconds = None

    if not _prefs_cache["auto_log_renders"]:
        return

    # --- Build the history entry ---
    blend_path = bpy.data.filepath
    blend_filename = os.path.basename(blend_path) if blend_path else "Unsaved"

    res_x = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
    res_y = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

    samples = None
    if scene.render.engine == 'CYCLES':
        samples = getattr(scene.cycles, 'samples', None)

    frame_range_str = (
        f"{scene.frame_current}" if actually_single_frame
        else f"{scene.frame_start}-{scene.frame_end}"
    )

    frame_times = [round(t, 2) for t in st["frame_times"]]
    if frame_times:
        avg_t = round(sum(frame_times) / len(frame_times), 2)
        min_t, max_t = min(frame_times), max(frame_times)
    else:
        avg_t = min_t = max_t = None

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
        "estimated_seconds": round(estimated_seconds, 2) if estimated_seconds is not None else None,
        "accuracy_pct": round(accuracy_pct, 1) if accuracy_pct is not None else None,
        "status": status,
        "output_path": scene.render.filepath or "Default",
        # v1.1.0: per-frame timing
        "frames_rendered": st["rendered_frames"],
        "avg_frame_seconds": avg_t,
        "min_frame_seconds": min_t,
        "max_frame_seconds": max_t,
        "frame_times": frame_times[:MAX_STORED_FRAME_TIMES] if len(frame_times) > 1 else None,
    }

    # sync=False: don't touch the WindowManager from a possible render thread.
    add_history_entry(entry, sync=False)
    st["pending_history_sync"] = True


@bpy.app.handlers.persistent
def on_load_post(*args):
    """Re-sync render history into the new WindowManager after file load."""
    try:
        sync_history_to_wm(bpy.context)
    except Exception as e:
        _log_error_once("load_post", e)


_HANDLER_MAP = (
    ("render_init", on_render_init),
    ("render_pre", on_render_pre),
    ("render_post", on_render_post),
    ("render_complete", on_render_complete),
    ("render_cancel", on_render_cancel),
    ("load_post", on_load_post),
)


def register_handlers():
    """Register callbacks into bpy.app.handlers and start the UI timer."""
    for name, fn in _HANDLER_MAP:
        lst = getattr(bpy.app.handlers, name)
        if fn not in lst:
            lst.append(fn)
    if not bpy.app.timers.is_registered(_ui_tick):
        bpy.app.timers.register(_ui_tick, first_interval=1.0, persistent=True)


def unregister_handlers():
    """Remove callbacks from bpy.app.handlers and stop the UI timer."""
    for name, fn in _HANDLER_MAP:
        lst = getattr(bpy.app.handlers, name)
        if fn in lst:
            lst.remove(fn)
    if bpy.app.timers.is_registered(_ui_tick):
        bpy.app.timers.unregister(_ui_tick)
