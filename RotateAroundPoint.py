import bpy
import mathutils
from math import radians
from math import degrees

# Math
def lerp(a: float, b: float, t: float) -> float:
    return (1 - t) * a + t * b

def inv_lerp(a: float, b: float, v: float) -> float:
    return (v - a) / (b - a)

def remap(v: float, i_min: float, i_max: float, o_min: float, o_max: float) -> float:
    return lerp(o_min, o_max, inv_lerp(i_min, i_max, v))

class CreateObject(bpy.types.Operator):
    """Object with Property"""
    bl_idname = "object.add_object_with_property"
    bl_label = "Add a custom Property and an Object"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context: 'Context', event: 'Event'):
        # Add new Empty Object
        emptyObject = bpy.data.objects.new("emptyObject", None)
        # Custom Property
        emptyObject["pivotPoint"] = (1,0,0)
        emptyObject["eulerRotation"] = (0,0,0)
        #set pos
        emptyObject.location = mathutils.Vector((3,0,0))
        # link empty to Scene
        bpy.context.scene.collection.objects.link(emptyObject)

        return {'FINISHED'}


class RotateAroundPoint(bpy.types.Operator):
    """Create a Light and Empty"""
    bl_idname = "object.rotate_around_point"
    bl_label = "Rotate Object around pivot"
    bl_options = {'REGISTER', 'UNDO'}


    pivotObjName = "pivotObject"

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D'

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if bpy.context.active_object == None:
            return {'CANCELLED'}

        if "pivotPoint" not in bpy.context.active_object and "eulerRotation" not in bpy.context.active_object:
            print("Property not found")
            return {'CANCELLED'}

        print("Property found")

        emptyObject = bpy.context.active_object

        # create Pivot
        pivotObject = bpy.data.objects.new(self.pivotObjName, None)
        pivotObject.empty_display_type = 'ARROWS'
        pos = emptyObject["pivotPoint"]
        pivotObject.location = mathutils.Vector((pos[0],pos[1],pos[2]))
        bpy.context.scene.collection.objects.link(pivotObject)
        # unrotate empty 
        pivotToEmpty = emptyObject.location - mathutils.Vector((pos[0],pos[1],pos[2]))
        emptyObject.location = mathutils.Vector(( pivotToEmpty.magnitude,0,0)) 
        emptyObject.rotation_euler = (0,0,0)
        # set Parenting
        emptyObject.parent_type = 'OBJECT'
        emptyObject.parent = pivotObject
        # rotate pivot
        rot = emptyObject["eulerRotation"]
        pivotObject.rotation_euler = rot
    
        print("invoke done")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context:  bpy.types.Context, event: bpy.types.Event):
        print ("in modal")

        if event.type == 'LEFTMOUSE':
            print("finish")
            # save rotation
            ob = bpy.data.objects["emptyObject"]
            rot = bpy.data.objects[self.pivotObjName].rotation_euler
            ob["eulerRotation"] = rot

            # Unparent
            world_loc = ob.matrix_world.to_translation()
            ob.parent = None
            ob.matrix_world.translation = world_loc

            # remove pivot Object
            bpy.data.objects.remove(bpy.data.objects[self.pivotObjName], do_unlink=True)

            print("finish")
            return {'FINISHED'}
        
        elif event.type == 'MIDDLEMOUSE':
            return {'PASS_THROUGH'}

        elif event.type == 'MOUSEMOVE' and event.shift:
            print("move")
            x = radians(remap(event.mouse_region_y /context.area.height,0.0,1.0,90.0,-90.0))
            y = radians(remap(event.mouse_region_x /context.area.width,0.0,1.0,0.0,360.0))
            rot = mathutils.Vector((0.0, x, y))
            bpy.data.objects[self.pivotObjName].rotation_euler = rot

        print (event.type)
            
        return {'RUNNING_MODAL'}



def register():
    print("registered")
    bpy.utils.register_class(CreateObject)
    bpy.utils.register_class(RotateAroundPoint)

def unregister():
    print("unregistered")
    bpy.utils.unregister_class(CreateObject)
    bpy.utils.unregister_class(RotateAroundPoint)

# TestRunning
if __name__ == '__main__':
    register()


# bpy.context.object["MyOwnProperty"] = 42

# if "SomeProp" in bpy.context.object:
#     print("Property found")

# # Use the get function like a Python dictionary
# # which can have a fallback value.
# value = bpy.data.scenes["Scene"].get("test_prop", "fallback value")

# # dictionaries can be assigned as long as they only use basic types.
# group = bpy.data.groups.new("MyTestGroup")
# group["GameSettings"] = {"foo": 10, "bar": "spam", "baz": {}}

# del group["GameSettings"]

#
#
#
# CALL AN OPERTATOR FROM AN OPERATOR
#
#
#