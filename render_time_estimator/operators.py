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
import csv
import time
import tempfile
import bpy
from bpy_extras.io_utils import ExportHelper
from .utils import format_time, get_addon_preferences
from .history import load_history, save_history, sync_history_to_wm


class RENDER_OT_estimate_render_time(bpy.types.Operator):
    """Perform a silent reduced sample/resolution pass to estimate full render time.

    NOTE ON UI RESPONSIVENESS: this runs bpy.ops.render.render() synchronously
    (EXEC context, write_still=False, not shown fullscreen), which does pause
    Blender's UI for the duration of both test passes. An INVOKE_DEFAULT
    async version was tried and reverted - it opened Blender's real render
    window and triggered a genuine full render instead of a quiet background
    test pass, which is worse than a brief freeze. The confirm dialog
    (RENDER_OT_confirm_estimate) warns the user before this runs so the
    pause is expected, not surprising.
    """
    bl_idname = "render.estimate_render_time"
    bl_label = "Estimate Render Time"
    bl_description = "Estimate full render time using sample or resolution reduction"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        wm = context.window_manager
        engine = scene.render.engine
        prefs = get_addon_preferences(context)

        # Handle unsupported engines (e.g. Workbench)
        if engine not in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'}:
            scene.ste_last_estimate = -1.0
            scene.ste_last_estimate_per_frame = -1.0
            scene.ste_last_estimate_total = -1.0
            scene.ste_last_method = f"Time estimation not supported for {engine}"
            self.report({'WARNING'}, f"Time estimation not supported for engine: {engine}")
            return {'CANCELLED'}

        # Calculate frame range
        frame_start = scene.frame_start
        frame_end = scene.frame_end
        frame_step = max(1, scene.frame_step)
        if frame_end >= frame_start:
            frame_count = max(1, ((frame_end - frame_start) // frame_step) + 1)
        else:
            frame_count = 1

        # Prepare silent temp render file
        temp_dir = tempfile.gettempdir()
        temp_render_path = os.path.join(temp_dir, "_ste_sample_render.png")
        orig_filepath = scene.render.filepath

        orig_samples = None
        orig_res_pct = None

        wm.progress_begin(0, 100)
        try:
            scene.render.filepath = temp_render_path
            wm.progress_update(20)

            if engine == 'CYCLES':
                cscene = scene.cycles
                orig_samples = getattr(cscene, 'samples', 0)
                if orig_samples <= 0:
                    scene.ste_last_estimate = -1.0
                    scene.ste_last_estimate_per_frame = -1.0
                    scene.ste_last_estimate_total = -1.0
                    scene.ste_last_method = "Cycles (Zero samples configured)"
                    self.report({'WARNING'}, "Cycles sample count is 0. Cannot estimate.")
                    return {'CANCELLED'}

                # Detect adaptive sampling
                is_adaptive = getattr(cscene, 'use_adaptive_sampling', False) or (getattr(cscene, 'adaptive_threshold', 0.0) > 0.0)
                scene.ste_is_adaptive_sampling = is_adaptive

                if is_adaptive:
                    # 2-point resolution pass for adaptive sampling (isolates fixed setup overhead)
                    orig_res_pct = scene.render.resolution_percentage
                    if orig_res_pct <= 0:
                        orig_res_pct = 100

                    res_ratio = prefs.eevee_resolution_ratio
                    ratio_a = max(0.10, res_ratio * 0.8)
                    ratio_b = min(0.60, max(ratio_a + 0.15, res_ratio * 1.6))

                    test_res_a = max(5, int(orig_res_pct * ratio_a))
                    test_res_b = max(10, int(orig_res_pct * ratio_b))

                    work_a = (test_res_a / orig_res_pct) ** 2
                    work_b = (test_res_b / orig_res_pct) ** 2

                    # Pass 1
                    scene.render.resolution_percentage = test_res_a
                    t_start = time.perf_counter()
                    bpy.ops.render.render(write_still=False)
                    time_a = time.perf_counter() - t_start
                    wm.progress_update(50)

                    # Pass 2
                    scene.render.resolution_percentage = test_res_b
                    t_start = time.perf_counter()
                    bpy.ops.render.render(write_still=False)
                    time_b = time.perf_counter() - t_start
                    wm.progress_update(90)

                    if work_b > work_a:
                        V = max(0.0, (time_b - time_a) / (work_b - work_a))
                        fixed_overhead = max(0.0, time_a - (V * work_a))
                        est_per_frame = max(time_b, fixed_overhead + V * 1.0)
                    else:
                        est_per_frame = time_b

                    est_total = est_per_frame * frame_count

                    scene.ste_last_estimate_per_frame = est_per_frame
                    scene.ste_last_estimate_total = est_total
                    scene.ste_last_frame_count = frame_count
                    scene.ste_last_estimate = est_total
                    scene.ste_last_method = f"Cycles (Adaptive 2-Point, {test_res_a}%/{test_res_b}% res)"

                else:
                    # 2-point sample pass for fixed sample rendering (isolates fixed setup overhead)
                    ratio = prefs.sample_ratio
                    ratio_a = max(0.05, ratio * 0.8)
                    ratio_b = min(0.60, max(ratio_a + 0.15, ratio * 2.0))

                    sample_a = max(2, int(orig_samples * ratio_a))
                    sample_b = max(sample_a + 2, int(orig_samples * ratio_b))

                    work_a = sample_a / orig_samples
                    work_b = sample_b / orig_samples

                    # Pass 1
                    scene.cycles.samples = sample_a
                    t_start = time.perf_counter()
                    bpy.ops.render.render(write_still=False)
                    time_a = time.perf_counter() - t_start
                    wm.progress_update(50)

                    # Pass 2
                    scene.cycles.samples = sample_b
                    t_start = time.perf_counter()
                    bpy.ops.render.render(write_still=False)
                    time_b = time.perf_counter() - t_start
                    wm.progress_update(90)

                    if work_b > work_a:
                        V = max(0.0, (time_b - time_a) / (work_b - work_a))
                        fixed_overhead = max(0.0, time_a - (V * work_a))
                        est_per_frame = max(time_b, fixed_overhead + V * 1.0)
                    else:
                        est_per_frame = time_b

                    est_total = est_per_frame * frame_count

                    scene.ste_last_estimate_per_frame = est_per_frame
                    scene.ste_last_estimate_total = est_total
                    scene.ste_last_frame_count = frame_count
                    scene.ste_last_estimate = est_total
                    scene.ste_last_method = f"Cycles (2-Point Sample-based, {sample_a}/{sample_b} samples)"

            else:
                # EEVEE / EEVEE Next 2-point resolution-based estimation (isolates fixed setup overhead)
                orig_res_pct = scene.render.resolution_percentage
                if orig_res_pct <= 0:
                    orig_res_pct = 100

                res_ratio = prefs.eevee_resolution_ratio
                ratio_a = max(0.10, res_ratio * 0.8)
                ratio_b = min(0.60, max(ratio_a + 0.15, res_ratio * 1.6))

                test_res_a = max(5, int(orig_res_pct * ratio_a))
                test_res_b = max(10, int(orig_res_pct * ratio_b))

                work_a = (test_res_a / orig_res_pct) ** 2
                work_b = (test_res_b / orig_res_pct) ** 2

                # Pass 1
                scene.render.resolution_percentage = test_res_a
                t_start = time.perf_counter()
                bpy.ops.render.render(write_still=False)
                time_a = time.perf_counter() - t_start
                wm.progress_update(50)

                # Pass 2
                scene.render.resolution_percentage = test_res_b
                t_start = time.perf_counter()
                bpy.ops.render.render(write_still=False)
                time_b = time.perf_counter() - t_start
                wm.progress_update(90)

                if work_b > work_a:
                    V = max(0.0, (time_b - time_a) / (work_b - work_a))
                    fixed_overhead = max(0.0, time_a - (V * work_a))
                    est_per_frame = max(time_b, fixed_overhead + V * 1.0)
                else:
                    est_per_frame = time_b

                est_total = est_per_frame * frame_count

                scene.ste_last_estimate_per_frame = est_per_frame
                scene.ste_last_estimate_total = est_total
                scene.ste_last_frame_count = frame_count
                scene.ste_last_estimate = est_total
                scene.ste_last_method = f"EEVEE (2-Point Resolution-based, {test_res_a}%/{test_res_b}% res)"

            wm.progress_update(100)

        except Exception as e:
            self.report({'ERROR'}, f"Estimation failed: {e}")
            scene.ste_last_estimate = -1.0
            scene.ste_last_estimate_per_frame = -1.0
            scene.ste_last_estimate_total = -1.0
            scene.ste_last_method = "Error during estimation pass"
            return {'CANCELLED'}

        finally:
            wm.progress_end()
            # Restore scene render settings.
            # IMPORTANT: restore everything that was actually touched, regardless
            # of which engine/branch ran. Do NOT branch on `engine` here - the
            # adaptive-sampling Cycles branch also modifies resolution_percentage,
            # so an engine-based branch silently skips restoring it.
            scene.render.filepath = orig_filepath
            if orig_samples is not None:
                scene.cycles.samples = orig_samples
            if orig_res_pct is not None:
                scene.render.resolution_percentage = orig_res_pct

            # Clean up temp render file
            if os.path.exists(temp_render_path):
                try:
                    os.remove(temp_render_path)
                except Exception:
                    pass

        if frame_count > 1:
            self.report({'INFO'}, f"Render time estimated: {format_time(scene.ste_last_estimate_total)} total ({frame_count} frames)")
        else:
            self.report({'INFO'}, f"Render time estimated: {format_time(scene.ste_last_estimate_per_frame)}")
        return {'FINISHED'}


class RENDER_OT_confirm_estimate(bpy.types.Operator):
    """Confirmation modal before running estimation pass."""
    bl_idname = "render.confirm_estimate"
    bl_label = "Confirm Time Estimate"
    bl_description = "Confirm running pre-render estimation pass"

    def invoke(self, context, event):
        prefs = get_addon_preferences(context)
        threshold = prefs.warn_threshold_seconds
        return context.window_manager.invoke_confirm(
            self, event,
            message=f"Estimation pass may take up to ~{threshold}s and will briefly pause Blender's UI. Continue?"
        )

    def execute(self, context):
        return bpy.ops.render.estimate_render_time()


class RENDER_OT_clear_render_history(bpy.types.Operator):
    """Clear all saved render history log entries."""
    bl_idname = "render.clear_render_history"
    bl_label = "Clear History"
    bl_description = "Permanently clear local render history log"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self, event,
            message="Are you sure you want to clear all render history entries?"
        )

    def execute(self, context):
        save_history([])
        sync_history_to_wm(context)
        self.report({'INFO'}, "Render history cleared.")
        return {'FINISHED'}


class RENDER_OT_export_render_history_csv(bpy.types.Operator, ExportHelper):
    """Export local render history to a CSV file."""
    bl_idname = "render.export_render_history_csv"
    bl_label = "Export History as CSV"
    bl_description = "Export render history entries to a CSV file for Excel or Google Sheets"
    filename_ext = ".csv"

    filter_glob: bpy.props.StringProperty(
        default="*.csv",
        options={'HIDDEN'},
        maxlen=255
    )

    def execute(self, context):
        entries = load_history()
        if not entries:
            self.report({'WARNING'}, "No history entries to export.")
            return {'CANCELLED'}

        filepath = self.filepath
        fieldnames = [
            "timestamp", "blend_filename", "scene_name", "render_engine",
            "resolution", "samples", "device", "frame_range",
            "duration_seconds", "status", "output_path"
        ]

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in entries:
                    writer.writerow({fn: row.get(fn, "") for fn in fieldnames})
            self.report({'INFO'}, f"Render history exported to {filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export CSV: {e}")
            return {'CANCELLED'}
