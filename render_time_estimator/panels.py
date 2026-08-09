"""
UI Panels for Render Properties tab and History UIList rendering.
"""

import bpy
from .utils import format_time, get_addon_preferences


class RENDER_UL_history_list(bpy.types.UIList):
    """UIList renderer for local render history entries."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Pick status icon
            if item.status == 'completed':
                status_icon = 'CHECKMARK'
            elif item.status == 'cancelled':
                status_icon = 'CANCEL'
            else:
                status_icon = 'ERROR'

            row = layout.row(align=True)
            row.label(text="", icon=status_icon)
            row.label(text=item.timestamp)
            row.label(text=item.scene_name)
            row.label(text=item.render_engine)
            row.label(text=item.duration_formatted)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.scene_name, icon='RENDER_STILL')


class RENDER_PT_insights_panel(bpy.types.Panel):
    """Main Render Insights panel in Render Properties tab."""
    bl_label = "Render Insights"
    bl_idname = "RENDER_PT_insights_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'render'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        wm = context.window_manager
        prefs = get_addon_preferences(context)

        # Section 1: Pre-Render Time Estimator (a rough guess before you commit)
        box_est = layout.box()
        box_est.label(text="Pre-Render Estimator (Rough Guess)", icon='TIME')
        row_hint = box_est.row()
        row_hint.active = False
        row_hint.label(text="Predicts before rendering starts - typically within ~20-25%")

        # Check threshold warning
        threshold = prefs.warn_threshold_seconds
        sample_ratio = prefs.sample_ratio
        
        # Determine operator call (uses confirm modal to warn before UI pause)
        row_btn = box_est.row()
        row_btn.scale_y = 1.3
        row_btn.operator("render.confirm_estimate", icon='PLAY')

        # Display estimation result
        last_est_per_frame = getattr(scene, 'ste_last_estimate_per_frame', 0.0)
        last_est_total = getattr(scene, 'ste_last_estimate_total', 0.0)
        last_frame_count = getattr(scene, 'ste_last_frame_count', 1)
        last_method = getattr(scene, 'ste_last_method', "")

        if last_est_per_frame > 0:
            res_box = box_est.box()
            if last_frame_count > 1:
                res_box.label(text=f"Est. per frame: {format_time(last_est_per_frame)}", icon='CHECKMARK')
                res_box.label(text=f"Est. total ({last_frame_count} frames): {format_time(last_est_total)}")
            else:
                res_box.label(text=f"Est. full render: {format_time(last_est_per_frame)}", icon='CHECKMARK')

            if getattr(scene, 'ste_is_adaptive_sampling', False):
                row_adap = res_box.row()
                row_adap.active = False
                row_adap.label(text="Adaptive sampling active — using resolution pass", icon='INFO')

            if last_method:
                row_sub = res_box.row()
                row_sub.active = False
                row_sub.label(text=f"Method: {last_method}")
        elif last_est_per_frame == -1.0 and last_method:
            res_box = box_est.box()
            res_box.label(text=last_method, icon='ERROR')

        # Section 2: Live ETA (during active render or after) - the reliable
        # number, since it's computed from real, currently-rendering frame
        # times rather than a fast proxy pass. Kept in its own clearly
        # labeled box so it doesn't get confused with the rough guess above.
        if prefs.live_eta_enabled:
            box_eta = layout.box()
            box_eta.label(text="Live Render Tracking (Accurate)", icon='STATUS_INFO')
            row_hint2 = box_eta.row()
            row_hint2.active = False
            row_hint2.label(text="Live timing from the real render currently in progress")

            row_elapsed = box_eta.row()
            row_elapsed.label(text="Elapsed:")
            row_elapsed.label(text=wm.ste_live_elapsed)

            row_eta = box_eta.row()
            row_eta.label(text="Remaining ETA:")
            row_eta.label(text=wm.ste_live_eta)

        # Support Link
        layout.separator()
        row_supp = layout.row()
        op = row_supp.operator("wm.url_open", text="Support the Creator", icon='FUND')
        op.url = "https://novastrikes.gumroad.com/coffee"


class RENDER_PT_history_panel(bpy.types.Panel):
    """Render History sub-panel."""
    bl_label = "Render History"
    bl_idname = "RENDER_PT_history_panel"
    bl_parent_id = "RENDER_PT_insights_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'render'

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        # UIList display
        row = layout.row()
        row.template_list(
            "RENDER_UL_history_list", "",
            wm, "render_history_items",
            wm, "render_history_index",
            rows=4
        )

        # Selected Item Details View
        items = wm.render_history_items
        idx = wm.render_history_index

        if 0 <= idx < len(items):
            item = items[idx]
            box_det = layout.box()
            box_det.label(text=f"Details ({item.timestamp})", icon='INFO')
            
            col = box_det.column(align=True)
            col.label(text=f"File: {item.blend_filename} | Scene: {item.scene_name}")
            col.label(text=f"Engine: {item.render_engine} | Res: {item.resolution}")
            col.label(text=f"Device: {item.device} | Samples: {item.samples}")
            col.label(text=f"Duration: {item.duration_formatted} | Status: {item.status.capitalize()}")
            col.label(text=f"Output: {item.output_path}")

        # Action Buttons
        row_act = layout.row(align=True)
        row_act.operator("render.export_render_history_csv", icon='EXPORT')
        row_act.operator("render.clear_render_history", icon='TRASH')
