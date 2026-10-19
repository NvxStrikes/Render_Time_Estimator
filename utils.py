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
import datetime
import bpy


def format_time(seconds: float) -> str:
    """Format seconds into a clean human-readable duration string."""
    if seconds is None or seconds < 0:
        return "N/A"

    seconds = round(seconds, 1)
    if seconds < 1.0:
        return f"{seconds:.1f}s"

    total_sec = int(round(seconds))
    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60

    if hrs > 0:
        return f"{hrs}h {mins:02d}m {secs:02d}s"
    elif mins > 0:
        return f"{mins}m {secs:02d}s"
    else:
        return f"{secs}s"


def get_render_device(scene) -> str:
    """Detect current render compute device (CPU / GPU).

    EEVEE (legacy and Next) and Workbench are GPU-only rasterizers, so they
    report "GPU". For Cycles we read the scene setting directly.

    v1.1.0: no longer touches bpy.context. This is called from render
    handlers, which run on Blender's render thread where bpy.context is not safe.
    """
    if scene.render.engine == 'CYCLES':
        return "GPU" if getattr(scene.cycles, 'device', 'CPU') == 'GPU' else "CPU"
    return "GPU"


def get_window_manager():
    """Return the first WindowManager without going through bpy.context.

    v1.1.0: safe to call from timers and handlers. Returns None if unavailable.
    """
    try:
        wms = bpy.data.window_managers
        return wms[0] if len(wms) else None
    except Exception:
        return None


def get_history_filepath() -> str:
    """Get persistent local JSON filepath in Blender's user config dir.

    NOTE: folder name is intentionally kept as "render_time_estimator"
    (not "render_time_estimator_ext") so existing user history is not orphaned.
    """
    config_dir = bpy.utils.user_resource('CONFIG')
    addon_dir = os.path.join(config_dir, "render_time_estimator")
    os.makedirs(addon_dir, exist_ok=True)
    return os.path.join(addon_dir, "render_history.json")


def get_timestamp_iso() -> str:
    """Get current local timestamp formatted as ISO 8601 string."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def compute_settings_signature(scene) -> str:
    """Build a compact fingerprint of the scene's render settings.

    Fix 5: Stored at estimation time and compared again in _finish_render_session.
    If settings changed between estimating and rendering, the estimate is discarded
    so a mismatched accuracy percentage is never logged.

    Format: engine|samples|res_x|res_y|res_pct|frame_start|frame_end|frame_step
    """
    engine = scene.render.engine
    # Only Cycles exposes a meaningful sample count used in the estimation.
    samples = getattr(scene.cycles, 'samples', 0) if engine == 'CYCLES' else 0
    res_x = scene.render.resolution_x
    res_y = scene.render.resolution_y
    res_pct = scene.render.resolution_percentage
    fs = scene.frame_start
    fe = scene.frame_end
    fstep = scene.frame_step
    return f"{engine}|{samples}|{res_x}|{res_y}|{res_pct}|{fs}|{fe}|{fstep}"


def get_addon_preferences(context=None):
    """Safely get AddonPreferences instance with fallback defaults.

    v1.1.0: fully guarded. If bpy.context is unavailable or in a bad state
    (e.g. called from a render thread) we return defaults instead of raising.
    """
    try:
        if context is None:
            context = bpy.context
        pkg_name = __package__ if __package__ else "render_time_estimator_ext"
        addon = context.preferences.addons.get(pkg_name)
        if addon and hasattr(addon, 'preferences') and addon.preferences:
            return addon.preferences
    except Exception:
        pass

    class DefaultPrefs:
        sample_ratio = 0.1
        eevee_resolution_ratio = 0.25
        warn_threshold_seconds = 15
        auto_log_renders = True
        live_eta_enabled = True
        show_status_bar_eta = True
    return DefaultPrefs()
