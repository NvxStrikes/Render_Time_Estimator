"""
Render History storage logic and UIList PropertyGroup definitions.
"""

import os
import json
import shutil
import bpy
from .utils import get_history_filepath, format_time


class RenderHistoryItem(bpy.types.PropertyGroup):
    """Property group representing a single render log entry in Blender's UIList."""
    timestamp: bpy.props.StringProperty(name="Timestamp")
    blend_filename: bpy.props.StringProperty(name="File")
    scene_name: bpy.props.StringProperty(name="Scene")
    render_engine: bpy.props.StringProperty(name="Engine")
    resolution: bpy.props.StringProperty(name="Resolution")
    samples: bpy.props.IntProperty(name="Samples", default=0)
    device: bpy.props.StringProperty(name="Device")
    frame_range: bpy.props.StringProperty(name="Frame Range")
    duration_seconds: bpy.props.FloatProperty(name="Duration (s)")
    status: bpy.props.StringProperty(name="Status")  # 'completed', 'cancelled', 'failed'
    output_path: bpy.props.StringProperty(name="Output Path")

    @property
    def duration_formatted(self) -> str:
        return format_time(self.duration_seconds)


def load_history() -> list:
    """
    Load render history list from local JSON.
    Handles corrupted JSON gracefully by backing up and starting fresh.
    """
    filepath = get_history_filepath()
    if not os.path.exists(filepath):
        return []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                raise ValueError("JSON root must be a list.")
    except Exception as e:
        print(f"[Render Time Estimator] Warning: Corrupted history file ({e}). Backing up to .bak")
        bak_filepath = filepath + ".bak"
        try:
            shutil.copy2(filepath, bak_filepath)
        except Exception:
            pass
        # Reset history
        save_history([])
        return []


def save_history(entries: list):
    """Save history entries list to local JSON safely."""
    filepath = get_history_filepath()
    try:
        tmp_filepath = filepath + ".tmp"
        with open(tmp_filepath, 'w', encoding='utf-8') as f:
            json.dump(entries, f, indent=2)
        if os.path.exists(filepath):
            os.remove(filepath)
        os.rename(tmp_filepath, filepath)
    except Exception as e:
        print(f"[Render Time Estimator] Error saving render history: {e}")


def add_history_entry(entry: dict):
    """Add a new render entry to the local JSON and sync UI collection."""
    entries = load_history()
    entries.insert(0, entry)  # Most recent first
    save_history(entries)
    sync_history_to_wm(bpy.context)


def sync_history_to_wm(context):
    """Sync JSON entries into WindowManager render_history_items UI collection."""
    if not context or not hasattr(context, 'window_manager'):
        return
    wm = context.window_manager
    if not hasattr(wm, 'render_history_items'):
        return

    wm.render_history_items.clear()
    entries = load_history()
    for item in entries:
        row = wm.render_history_items.add()
        row.timestamp = item.get("timestamp", "")
        row.blend_filename = item.get("blend_filename", "Unsaved")
        row.scene_name = item.get("scene_name", "")
        row.render_engine = item.get("render_engine", "")
        row.resolution = item.get("resolution", "")
        row.samples = item.get("samples") or 0
        row.device = item.get("device", "N/A")
        row.frame_range = str(item.get("frame_range", ""))
        row.duration_seconds = float(item.get("duration_seconds", 0.0))
        row.status = item.get("status", "completed")
        row.output_path = item.get("output_path", "")
