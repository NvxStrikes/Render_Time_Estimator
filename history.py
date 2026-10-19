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
import json
import shutil
import bpy
from .utils import get_history_filepath, format_time, get_window_manager

# Fix 6: hard cap on stored history entries.
# Oldest entries (tail of the list, since newest are inserted at index 0)
# are dropped when this limit is exceeded.
MAX_HISTORY_ENTRIES = 500


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
    estimated_seconds: bpy.props.FloatProperty(name="Estimated (s)", default=-1.0)
    accuracy_pct: bpy.props.FloatProperty(name="Accuracy %", default=-1.0)
    status: bpy.props.StringProperty(name="Status")  # 'completed', 'cancelled', 'failed'
    output_path: bpy.props.StringProperty(name="Output Path")
    # v1.1.0: per-frame timing summary (full per-frame list lives in the JSON/CSV)
    frames_rendered: bpy.props.IntProperty(name="Frames Rendered", default=0)
    frame_avg_seconds: bpy.props.FloatProperty(name="Avg Frame (s)", default=-1.0)
    frame_min_seconds: bpy.props.FloatProperty(name="Fastest Frame (s)", default=-1.0)
    frame_max_seconds: bpy.props.FloatProperty(name="Slowest Frame (s)", default=-1.0)

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
        os.replace(tmp_filepath, filepath)
    except Exception as e:
        print(f"[Render Time Estimator] Error saving render history: {e}")


def add_history_entry(entry: dict, sync: bool = True):
    """Add a new render entry to the local JSON and sync UI collection.

    Fix 6: entries are capped at MAX_HISTORY_ENTRIES. The list is newest-first
    (index 0), so trimming the tail removes the oldest entries.
    """
    entries = load_history()
    entries.insert(0, entry)  # Most recent first

    # Enforce cap — drop oldest (tail) entries beyond the limit
    if len(entries) > MAX_HISTORY_ENTRIES:
        entries = entries[:MAX_HISTORY_ENTRIES]

    save_history(entries)
    # v1.1.0: render handlers pass sync=False (they run off the main thread);
    # the UI timer syncs the WindowManager list safely afterwards.
    if sync:
        sync_history_to_wm(bpy.context)


def sync_history_to_wm(context):
    """Sync JSON entries into WindowManager render_history_items UI collection."""
    wm = None
    try:
        if context is not None and hasattr(context, 'window_manager'):
            wm = context.window_manager
    except Exception:
        wm = None
    if wm is None:
        wm = get_window_manager()
    if wm is None or not hasattr(wm, 'render_history_items'):
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
        val_est = item.get("estimated_seconds")
        row.estimated_seconds = float(val_est) if val_est is not None else -1.0
        val_acc = item.get("accuracy_pct")
        row.accuracy_pct = float(val_acc) if val_acc is not None else -1.0
        row.status = item.get("status", "completed")
        row.output_path = item.get("output_path", "")
        row.frames_rendered = int(item.get("frames_rendered") or 0)
        for attr, key in (("frame_avg_seconds", "avg_frame_seconds"),
                          ("frame_min_seconds", "min_frame_seconds"),
                          ("frame_max_seconds", "max_frame_seconds")):
            v = item.get(key)
            setattr(row, attr, float(v) if v is not None else -1.0)
