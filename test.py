import bpy
import mathutils
from math import radians

# Math
def lerp(a: float, b: float, t: float) -> float:
    return (1 - t) * a + t * b

def inv_lerp(a: float, b: float, v: float) -> float:
    return (v - a) / (b - a)

def remap(v: float, i_min: float, i_max: float, o_min: float, o_max: float) -> float:
    return lerp(o_min, o_max, inv_lerp(i_min, i_max, v))

# Functions
def CreateEmpty(position : tuple):
    # Add new Empty Object
    emptyObject = bpy.data.objects.new("ObjectName", None)
    # Display Empty as Arrows
    emptyObject.empty_display_type = 'ARROWS'
    # link empty to Scene
    bpy.context.scene.collection.objects.link(emptyObject)
    # Change light position
    emptyObject.location = position
    return emptyObject

def CreateLight(position : tuple):
    # Create light datablock
    lightData = bpy.data.lights.new(name="pointLightData", type='POINT')
    lightData.energy = 100
    # Create new object, pass the light data 
    lightObject = bpy.data.objects.new(name="pointLightObject", object_data=lightData)
    # Link object to collection in context
    bpy.context.scene.collection.objects.link(lightObject)
    # Change light position
    lightObject.location = position
    #return LightObject
    return lightObject

# Operators
class OBJECT_OT_add_light_and_empty(bpy.types.Operator):
    """Create a Light and Empty"""
    bl_idname = "object.add_light_and_empty"
    bl_label = "Add Light and Empty"
    bl_options = {'REGISTER', 'UNDO'}

    #first_mouse_x = Vector.zero
    emptyObjName = ""

    def invoke(self, context, event):
        emptyObject = CreateEmpty((0,0,0))
        self.emptyObjName = emptyObject.name #Set Name for Reference
        lgt = CreateLight((3,0,0))
        lgt.parent = emptyObject
        # if context.object:
        #     self.first_mouse_x = event.mouse_x
        #     self.first_value = context.object.location.x

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
        # else:
        #     self.report({'WARNING'}, "No active object, could not finish")
        #     return {'CANCELLED'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            x = radians(remap(event.mouse_region_y /context.area.height,0.0,1.0,90.0,-90.0))
            y = radians(remap(event.mouse_region_x /context.area.width,0.0,1.0,0.0,360.0))
            rot = mathutils.Vector((0.0, x, y))
            bpy.data.objects[self.emptyObjName].rotation_euler = rot
            print(f'mouse offset {event.mouse_region_x} width is {x} height is {y}')

        elif event.type == 'LEFTMOUSE':
            print('finish modal')
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            print('canceled modal')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


# Registering and Hotkeys
addon_keymaps = []

def register():
    print("registered")
    bpy.utils.register_class(OBJECT_OT_add_light_and_empty)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View',space_type='VIEW_3D')
        kmi = km.keymap_items.new("object.add_light_and_empty",type='ONE',value='PRESS',shift=True,ctrl=True)
        addon_keymaps.append((km,kmi))

def unregister():
    print("unregistered")
    bpy.utils.unregister_class(OBJECT_OT_add_light_and_empty)
    for km,kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

# TestRunning
if __name__ == '__main__':
    register()
