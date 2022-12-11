import bpy
import mathutils
import bl_math
from math import radians
from bpy_extras import view3d_utils


# Wrap Cursor when its at first or last pixel of window
def wrapMouseInWindow(context : bpy.types.Context, event : bpy.types.Event):
    width = context.area.width
    height = context.area.height

    print(f'the mouse position is ({event.mouse_x}, {event.mouse_y})')
    print(f'the width and height is ({width}, {height})')
    print(f'the context area xy is ({context.area.x}, {context.area.y})')
    print(f'the context region xy is ({context.region.x}, {context.region.y})')

    if event.mouse_x <= context.area.x:
        context.window.cursor_warp(context.area.x + width - 1, event.mouse_y)

    if event.mouse_x >= context.area.x + width:
        context.window.cursor_warp(context.area.x , event.mouse_y)

    if event.mouse_y <= context.area.y:
        context.window.cursor_warp(event.mouse_x, context.area.y)

    if event.mouse_y >= context.area.y + height:
        context.window.cursor_warp(event.mouse_x, context.area.y + height)

def resetCursorToCenterRegion(context : bpy.types.Context):
    region = context.region
    cx = region.width // 2 + region.x
    cy = region.height // 2 + region.y
    context.window.cursor_warp(cx, cy)
    
# Raycast
def raycast(context : bpy.types.Context, event : bpy.types.Event):
    """Run this function on left mouse, execute the ray cast"""
    # get the context arguments
    scene = context.scene # scene
    region = context.region # region
    rv3d = context.region_data # region data
    coord = event.mouse_region_x, event.mouse_region_y # mouse cords

    # get the ray from the viewport and mouse
    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)

    ray_target = ray_origin + view_vector

    def visible_objects_and_duplis():
        """Loop over (object, matrix) pairs (mesh only)"""

        depsgraph = context.evaluated_depsgraph_get()
        for dup in depsgraph.object_instances:
            if dup.is_instance:  # Real dupli instance
                obj = dup.instance_object
                yield (obj, dup.matrix_world.copy())
            else:  # Usual object
                obj = dup.object
                yield (obj, obj.matrix_world.copy())

    def obj_ray_cast(obj, matrix):
        """Wrapper for ray casting that moves the ray into object space"""

        # get the ray relative to the object
        matrix_inv = matrix.inverted()
        ray_origin_obj = matrix_inv @ ray_origin
        ray_target_obj = matrix_inv @ ray_target
        ray_direction_obj = ray_target_obj - ray_origin_obj

        # cast the ray
        success, location, normal, face_index = obj.ray_cast(ray_origin_obj, ray_direction_obj)

        if success:
            return location, normal, face_index
        else:
            return None, None, None

    # cast rays and find the closest object
    best_length_squared = -1.0
    best_obj = None
    hit_world = None

    for obj, matrix in visible_objects_and_duplis():
        if obj.type == 'MESH':
            hit, normal, face_index = obj_ray_cast(obj, matrix)
            if hit is not None:
                hit_world = matrix @ hit
                #scene.cursor.location = hit_world
                length_squared = (hit_world - ray_origin).length_squared
                if best_obj is None or length_squared < best_length_squared:
                    best_length_squared = length_squared
                    best_obj = obj

    # now we have the object under the mouse cursor,
    # we could do lots of stuff but for the example just select.
    if best_obj is not None:
        # for selection etc. we need the original object,
        # evaluated objects are not in viewlayer
        best_original = best_obj.original
        return hit_world, normal, best_original
    else: 
        return None,None,None


# Math
def lerp(a: float, b: float, t: float) -> float:
    return (1 - t) * a + t * b

def inv_lerp(a: float, b: float, v: float) -> float:
    return (v - a) / (b - a)

def remap(v: float, i_min: float, i_max: float, o_min: float, o_max: float) -> float:
    return lerp(o_min, o_max, inv_lerp(i_min, i_max, v))

# Functions
def CreateEmpty(position : mathutils.Vector):
    # Add new Empty Object
    emptyObject = bpy.data.objects.new("ObjectName", None)
    # Display Empty as Arrows
    emptyObject.empty_display_type = 'ARROWS'
    # link empty to Scene
    bpy.context.scene.collection.objects.link(emptyObject)
    # Change light position
    emptyObject.location = position
    # Change Empty Display Scale
    emptyObject.empty_display_size = 80.0
    # Return empty 
    return emptyObject

def CreateLight(position : mathutils.Vector):
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
    lgtObjName = ""
    zoomPercent = 0.1
    energyGrowthPercent = 0.25
    sizeChangeSensitivity = 0.02


    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        # Vectors
        hit, normal, best_original = raycast(context,event)
        print(f'hit point is {hit} normal is  {normal}, best Original Object is {best_original}')
        if hit:
            creationPoint = mathutils.Vector((0,0,0))
            offset  = mathutils.Vector((3,0,0))
            # Creation
            emptyObject = CreateEmpty(creationPoint)
            lgtObject = CreateLight(offset)
            # Set Properties on Objects
            self.emptyObjName = emptyObject.name #Set Name for Reference
            self.lgtObjName = lgtObject.name #Set Name for Reference
            lgtObject.parent = emptyObject
            emptyObject.location = hit

            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            return {'CANCELLED'}


    def modal(self, context, event):

        wrapMouseInWindow(context,event) # wrap mouse movement

        if event.type == 'MOUSEMOVE' and event.shift:
            #bpy.data.objects[self.emptyObjName].location += mathutils.Vector((0,0,(event.mouse_prev_y - event.mouse_y) * 0.02))
            hit, normal, best_original = raycast(context,event)
            if hit:
                bpy.data.objects[self.emptyObjName].location = hit
                print('mousemove')

        elif event.type == 'MOUSEMOVE' and event.alt:
            obj : bpy.types.PointLight = bpy.data.objects[self.lgtObjName].data
            obj.shadow_soft_size *= 1 + ((event.mouse_region_x - event.mouse_prev_x )* self.sizeChangeSensitivity)
            obj.shadow_soft_size = bl_math.clamp(obj.shadow_soft_size, 0.001,10000000)

        elif event.type == 'MOUSEMOVE':
            x = radians(remap(event.mouse_region_y /context.area.height,0.0,1.0,90.0,-90.0))
            y = radians(remap(event.mouse_region_x /context.area.width,0.0,1.0,0.0,360.0))
            rot = mathutils.Vector((0.0, x, y))
            bpy.data.objects[self.emptyObjName].rotation_euler = rot

        elif event.type == 'WHEELUPMOUSE' and event.shift:
            obj : bpy.types.PointLight = bpy.data.objects[self.lgtObjName].data
            obj.energy *= bl_math.clamp(1.0 + self.energyGrowthPercent, 0.001,10000000)

        elif event.type == 'WHEELUPMOUSE':
            obj = bpy.data.objects[self.lgtObjName]
            pos = mathutils.Vector((obj.location[0] * (1 - self.zoomPercent), obj.location[1], obj.location[2]))
            obj.location = pos

        elif event.type == 'WHEELDOWNMOUSE' and event.shift:
            obj : bpy.types.PointLight = bpy.data.objects[self.lgtObjName].data
            obj.energy *= bl_math.clamp(1.0 - self.energyGrowthPercent, 0.001,10000000)

        elif event.type == 'WHEELDOWNMOUSE':
            obj = bpy.data.objects[self.lgtObjName]
            pos = mathutils.Vector((obj.location[0] * (1 + self.zoomPercent), obj.location[1], obj.location[2]))
            obj.location = pos

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
