import bpy
from bpy.types import Menu


class VIEW3D_MT_PIE_template(Menu):
    # label is displayed at the center of the pie menu.
    bl_label = "Select Mode"

    def draw(self, context):
        layout = self.layout

        pie = layout.menu_pie()
        # operator_enum will just spread all available options
        # for the type enum of the operator on the pie
        pie.operator_enum("mesh.select_mode", "type")
        #pie.prop(inputs, "view_rotate_method", expand=True)
        #pie.operator("wm.tool_set_by_id", text = "Scale").name = 'builtin.scale'
        #pie.separator()

class VIEW3D_OT_PIE_template_call(bpy.types.Operator):
    bl_idname = 'sop.sm_template'
    bl_label = 'S.Menu Navigation'
    bl_description = 'Calls pie menu'
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name="VIEW3D_MT_PIE_template")
        return {'FINISHED'}

# Registering and Hotkeys
addon_keymaps = []

def register():
    print("registered")
    bpy.utils.register_class(VIEW3D_MT_PIE_template)
    bpy.utils.register_class(VIEW3D_OT_PIE_template_call)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View',space_type='VIEW_3D')
        kmi = km.keymap_items.new("sop.sm_template",type='Q',value='PRESS',shift=True,ctrl=True)
        addon_keymaps.append((km,kmi))


def unregister():
    print("unregistered")
    bpy.utils.unregister_class(VIEW3D_MT_PIE_template)
    bpy.utils.unregister_class(VIEW3D_OT_PIE_template_call)
    for km,kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


if __name__ == "__main__":
    register()
    #bpy.ops.wm.call_menu_pie(name="VIEW3D_MT_PIE_template")

