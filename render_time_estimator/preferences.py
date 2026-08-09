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

import bpy


class RenderTimeEstimatorPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    sample_ratio: bpy.props.FloatProperty(
        name="Sample Ratio (Cycles)",
        description="Portion of full sample count used for Cycles pre-render estimation",
        default=0.1,
        min=0.05,
        max=0.5,
        subtype='FACTOR'
    )

    eevee_resolution_ratio: bpy.props.FloatProperty(
        name="Resolution Ratio (EEVEE)",
        description="Resolution ratio used for EEVEE/EEVEE Next pre-render estimation",
        default=0.25,
        min=0.1,
        max=0.5,
        subtype='FACTOR'
    )

    warn_threshold_seconds: bpy.props.IntProperty(
        name="Warn Threshold (s)",
        description="Warn before sample render if estimated calculation time exceeds this limit",
        default=15,
        min=1,
        max=300
    )

    auto_log_renders: bpy.props.BoolProperty(
        name="Auto-log Renders",
        description="Automatically record completed and cancelled renders into local history",
        default=True
    )

    live_eta_enabled: bpy.props.BoolProperty(
        name="Show Live ETA",
        description="Display real-time render progress and estimated completion time",
        default=True
    )

    def draw(self, context):
        layout = self.layout

        # Section 1: Settings
        box_settings = layout.box()
        box_settings.label(text="Estimation & Logging Settings", icon='PREFERENCES')
        
        col = box_settings.column(align=True)
        col.prop(self, "sample_ratio", slider=True)
        col.prop(self, "eevee_resolution_ratio", slider=True)
        col.prop(self, "warn_threshold_seconds")
        
        col.separator()
        col.prop(self, "live_eta_enabled")
        col.prop(self, "auto_log_renders")

        # Section 2: About / Credits
        box_about = layout.box()
        box_about.label(text="About", icon='INFO')
        box_about.label(text="Maintainer: NovaStrikes (Hamayl Shahbaz)")

        row_links = box_about.row(align=True)
        op_port = row_links.operator("wm.url_open", text="Portfolio", icon='URL')
        op_port.url = "https://novastrikes.com/"
        
        op_gh = row_links.operator("wm.url_open", text="GitHub", icon='URL')
        op_gh.url = "https://github.com/NvxStrikes"
        
        op_mail = row_links.operator("wm.url_open", text="Contact", icon='URL')
        op_mail.url = "mailto:contact@novastrikes.com"

        box_about.separator()
        row_support = box_about.row()
        row_support.scale_y = 1.2
        op_supp = row_support.operator("wm.url_open", text="Support the Creator", icon='FUND')
        op_supp.url = "https://novastrikes.gumroad.com/coffee"
