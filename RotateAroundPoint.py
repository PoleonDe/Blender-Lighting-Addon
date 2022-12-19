import bpy
import mathutils
from math import radians
from math import degrees
from math import atan2
from math import sqrt
from math import pi
from math import sin
from math import cos


# Wrap Cursor when its at first or last pixel of window
def wrapMouseInWindow(context: bpy.types.Context, event: bpy.types.Event):
    width = context.area.width
    height = context.area.height

    if event.mouse_x <= context.area.x:
        context.window.cursor_warp(context.area.x + width - 1, event.mouse_y)

    if event.mouse_x >= context.area.x + width:
        context.window.cursor_warp(context.area.x, event.mouse_y)

    if event.mouse_y <= context.area.y:
        context.window.cursor_warp(event.mouse_x, context.area.y)

    if event.mouse_y >= context.area.y + height:
        context.window.cursor_warp(event.mouse_x, context.area.y + height)
# Math


def lerp(a: float, b: float, t: float) -> float:
    return (1 - t) * a + t * b


def inv_lerp(a: float, b: float, v: float) -> float:
    return (v - a) / (b - a)


def remap(v: float, i_min: float, i_max: float, o_min: float, o_max: float) -> float:
    return lerp(o_min, o_max, inv_lerp(i_min, i_max, v))


def clamp(num, min_value, max_value):
    return max(min(num, max_value), min_value)


def sign(v: float):
    if v >= 0.0:
        return 1.0
    return -1.0

# def vector_to_azimuth_elevation(vector : mathutils.Vector) -> mathutils.Vector:
#     azimuth = atan2(vector.y, vector.x)
#     elevation = atan2(vector.z, sqrt(vector.x**2 + vector.y**2))
#     return mathutils.Vector(( 0.0,-elevation,azimuth))


def vector_to_azimuth_elevation(vec: mathutils.Vector) -> mathutils.Vector:
    # azimuth
    azimuth: float = atan2(vec.y, vec.x)
    # elevation
    # get the angle of the vector without Z component
    vecXY = mathutils.Vector((vec.x, vec.y, 0.0))
    # find out if angle is positive or negative
    angleSign = - sign(mathutils.Vector((0.0, 0.0, 1.0)).dot(vec.normalized()))
    # and calculate angle between flattened and elevation
    elevation: float = angleSign * vecXY.angle(vec, 0.0)
    # return
    return mathutils.Vector((0.0, elevation, azimuth))


class CreateObject(bpy.types.Operator):
    """Object with Property"""
    bl_idname = "object.add_object_with_property"
    bl_label = "Add a custom Property and an Object"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        # Add new Empty Object
        emptyObject = bpy.data.objects.new("emptyObject", None)
        # Custom Property
        emptyObject["pivotPoint"] = (1, 0, 0)
        # set pos
        emptyObject.location = mathutils.Vector((3, 0, 0))
        # link empty to Scene
        bpy.context.scene.collection.objects.link(emptyObject)

        return {'FINISHED'}


class RotateAroundPoint(bpy.types.Operator):
    """Create a Light and Empty"""
    bl_idname = "object.rotate_around_point"
    bl_label = "Rotate Object around pivot"
    bl_options = {'REGISTER', 'UNDO'}

    pivotObjName = "pivotObject"
    rotationSpeed = 0.01

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D'

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if context.active_object == None:
            return {'CANCELLED'}

        if "pivotPoint" not in context.active_object:
            print("Property not found => created")
            context.active_object["pivotPoint"] = (0, 0, 0)
            # return {'CANCELLED'}

        print("Property found")

        lightObject = bpy.context.active_object
        print(
            f"rotation is {lightObject.rotation_euler[0]},{lightObject.rotation_euler[1]},{lightObject.rotation_euler[2]}")

        # create Pivot
        pivotObject = bpy.data.objects.new(self.pivotObjName, None)
        pivotObject.empty_display_type = 'ARROWS'
        pivotPos = lightObject["pivotPoint"]
        pivotObject.location = mathutils.Vector(
            (pivotPos[0], pivotPos[1], pivotPos[2]))
        bpy.context.scene.collection.objects.link(pivotObject)
        # unrotate empty
        pivotToLight: mathutils.Vector = lightObject.location - pivotObject.location
        lightObject.rotation_euler = (0, 0, 0)
        lightObject.location = mathutils.Vector((pivotToLight.magnitude, 0, 0))
        # set Parenting
        lightObject.parent_type = 'OBJECT'
        lightObject.parent = pivotObject
        # rotate pivot
        rot = vector_to_azimuth_elevation(pivotToLight)
        print(
            f"calculated rotation is {vector_to_azimuth_elevation(pivotToLight)}")
        pivotObject.rotation_euler = rot

        print("invoke done")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context:  bpy.types.Context, event: bpy.types.Event):
        wrapMouseInWindow(context, event)  # wrap mouse movement

        if event.type == 'LEFTMOUSE':
            print("finish")
            # save rotation
            ob = context.active_object
            rot = bpy.data.objects[self.pivotObjName].rotation_euler

            # Unparent
            world_loc = ob.matrix_world.to_translation()
            ob.parent = None
            ob.matrix_world.translation = world_loc

            # remove pivot Object
            bpy.data.objects.remove(
                bpy.data.objects[self.pivotObjName], do_unlink=True)

            print("finish")
            return {'FINISHED'}

        elif event.type == 'MIDDLEMOUSE':
            return {'PASS_THROUGH'}

        elif event.type == 'MOUSEMOVE' and event.shift:
            print("move")
            xDelta = (event.mouse_x - event.mouse_prev_x) * self.rotationSpeed
            yDelta = (event.mouse_y - event.mouse_prev_y) * self.rotationSpeed
            pivotObj = bpy.data.objects[self.pivotObjName]
            # add delta rotation to existing rotation and clamp it (could fkup when mouse is forcemoved)
            pivotObj.rotation_euler = mathutils.Euler((pivotObj.rotation_euler.x, clamp(
                pivotObj.rotation_euler.y - yDelta, -pi/2.0, pi/2.0), pivotObj.rotation_euler.z + xDelta))

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
