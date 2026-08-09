"""
Utility functions for Render Time Estimator + Logger addon.
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
    """Detect current render compute device (CPU / GPU / GPU+CPU / N/A)."""
    if scene.render.engine == 'CYCLES':
        cycles_prefs = bpy.context.preferences.addons.get('cycles')
        if cycles_prefs:
            cscene = scene.cycles
            if cscene.device == 'GPU':
                return "GPU"
            elif cscene.device == 'CPU':
                return "CPU"
        return getattr(scene.cycles, 'device', 'CPU')
    return "N/A"


def get_history_filepath() -> str:
    """Get persistent local JSON filepath in Blender's user config dir."""
    config_dir = bpy.utils.user_resource('CONFIG')
    addon_dir = os.path.join(config_dir, "render_time_estimator")
    os.makedirs(addon_dir, exist_ok=True)
    return os.path.join(addon_dir, "render_history.json")


def get_timestamp_iso() -> str:
    """Get current local timestamp formatted as ISO 8601 string."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_addon_preferences(context=None):
    """Safely get AddonPreferences instance with fallback defaults."""
    if context is None:
        context = bpy.context
    
    # Try __package__ first, then module name
    pkg_name = __package__.split('.')[0] if __package__ else "render_time_estimator"
    addon = context.preferences.addons.get(pkg_name)
    if addon and hasattr(addon, 'preferences') and addon.preferences:
        return addon.preferences
    
    # Fallback default values
    class DefaultPrefs:
        sample_ratio = 0.1
        eevee_resolution_ratio = 0.25
        warn_threshold_seconds = 15
        auto_log_renders = True
        live_eta_enabled = True
    return DefaultPrefs()

