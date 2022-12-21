import bpy
import mathutils
import bl_math
from math import radians
from math import degrees
from math import atan2
from math import sqrt
from math import pi
from math import sin
from math import cos
from bpy_extras import view3d_utils

# TODO - Add bl_info, so that this is an addon.

#################################################################
######################## FUNCTIONS ##############################
#################################################################


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


def resetCursorToCenterRegion(context: bpy.types.Context):
    region = context.region
    cx = region.width // 2 + region.x
    cy = region.height // 2 + region.y
    context.window.cursor_warp(cx, cy)


# Math
def lerp(a: float, b: float, t: float) -> float:
    return (1 - t) * a + t * b


def inv_lerp(a: float, b: float, v: float) -> float:
    return (v - a) / (b - a)


def remap(v: float, i_min: float, i_max: float, o_min: float, o_max: float) -> float:
    return lerp(o_min, o_max, inv_lerp(i_min, i_max, v))


def clamp(num: float, min_value: float, max_value: float) -> float:
    return max(min(num, max_value), min_value)


def sign(v: float) -> float:
    if v >= 0.0:
        return 1.0
    return -1.0

# TODO : Rotations fail when not XYZ Rotation Order.


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

# TODO : Rotations fail when not XYZ Rotation Order.


def lookAtRotation(vec: mathutils.Vector, facingAxis="") -> mathutils.Vector:
    """ specify look at facing Axis by string x,y,z or -x,-y,-z"""
    azimuthElevation = vector_to_azimuth_elevation(vec)
    if facingAxis == "x":
        return mathutils.Vector((0.0, azimuthElevation.y + pi, azimuthElevation.z))
    elif facingAxis == "y":
        return mathutils.Vector((pi * 0.5, azimuthElevation.y - pi * 0.5, azimuthElevation.z))
    elif facingAxis == "z":
        return mathutils.Vector((0.0, azimuthElevation.y - pi * 0.5, azimuthElevation.z))
    elif facingAxis == "-x":
        return mathutils.Vector((0.0, azimuthElevation.y, azimuthElevation.z))
    elif facingAxis == "-y":
        return mathutils.Vector((pi * 0.5, azimuthElevation.y + pi * 0.5, azimuthElevation.z))
    elif facingAxis == "-z":
        return mathutils.Vector((0.0, azimuthElevation.y + pi * 0.5, azimuthElevation.z))
    else:
        return azimuthElevation


# Raycast


def raycast(context: bpy.types.Context, event: bpy.types.Event):
    """Run this function on left mouse, execute the ray cast"""
    # get the context arguments
    scene = context.scene  # scene
    region = context.region  # region
    rv3d = context.region_data  # region data
    coord = event.mouse_region_x, event.mouse_region_y  # mouse cords

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
        success, location, normal, face_index = obj.ray_cast(
            ray_origin_obj, ray_direction_obj)

        if success:
            return location, normal, face_index
        else:
            return None, None, None

    # cast rays and find the closest object
    best_length_squared = -1.0
    best_obj = None
    hit_world = None
    normal_world = None

    for obj, matrix in visible_objects_and_duplis():
        if obj.type == 'MESH':
            hit, normal, face_index = obj_ray_cast(obj, matrix)
            if hit is not None:
                hit_world = matrix @ hit
                normal_world = matrix @ normal
                # scene.cursor.location = hit_world
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
        return hit_world, normal_world, best_original
    else:
        return None, None, None


# Object Creation
def CreateLight(context: bpy.types.Context, pivotPosition: mathutils.Vector, lightType: str) -> bpy.types.Object:
    """Creates a Light at position, Light types are POINT, SUN, SPOT, AREA"""
    # TODO : Split this Method in multiple Methods. all with single Responseability
    # TODO : change lightDistance based on Camera Distance to Object
    # Create light datablock
    lightData = bpy.data.lights.new(
        name=lightType + "LightData", type=lightType)
    lightData.energy = 100
    # Create new object, pass the light data
    lightObject = bpy.data.objects.new(
        name=lightType + "Light", object_data=lightData)
    # Custom Property
    lightObject["pivotPoint"] = (
        pivotPosition.x, pivotPosition.y, pivotPosition.z)
    # link empty to Scene
    context.scene.collection.objects.link(lightObject)

    return lightObject


def PositionLight(lightObject: bpy.types.Object, normal: mathutils.Vector, lightDistance: float):
    if "pivotPoint" not in lightObject:
        print(
            f"The Object that was tried to be positioned, doesnt have the pivot Point Property. Object is {lightObject}")
        return

    # Set position
    pivotPosition = mathutils.Vector(
        (lightObject["pivotPoint"][0], lightObject["pivotPoint"][1], lightObject["pivotPoint"][2]))
    lightObject.location = pivotPosition + \
        (normal * mathutils.Vector((lightDistance, lightDistance, lightDistance)))
    # Set rotation
    lightObject.rotation_euler = lookAtRotation(normal, "-z")

#################################################################
######################## OPERATORS ##############################
#################################################################


class LIGHTCONTROL_OT_add_light(bpy.types.Operator):
    bl_idname = "lightcontrol.add_light"
    bl_label = "Adds an Area Light"
    bl_options = {'REGISTER', 'UNDO'}

    lightType: bpy.props.EnumProperty(items=[('AREA', 'Area Light', ''), ('POINT', 'Point Light', ''), ('SPOT', 'Spot Light', ''), (
        'SUN', 'Directional Light', '')], name="Light Types", description="Which Light Type should be spawned", default='AREA')

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        hit, normal, best_original = raycast(context, event)
        # print(f'hit point is {hit} normal is  {normal}, best Original Object is {best_original}')
        if not hit:
            print("hit nothing, canceled")
            return {'CANCELLED'}

        # Create light
        lightDistance: float = 3.0
        pivotPoint = mathutils.Vector(
            (hit[0], hit[1], hit[2]))

        if self.lightType == 'AREA':
            lightObject = CreateLight(context, pivotPoint, 'AREA')
        elif self.lightType == 'POINT':
            lightObject = CreateLight(context, pivotPoint, 'POINT')
        elif self.lightType == 'SPOT':
            lightObject = CreateLight(context, pivotPoint, 'SPOT')
        elif self.lightType == 'SUN':
            lightObject = CreateLight(context, pivotPoint, 'SUN')
        else:
            print("Couldnt add this lighttype.")
            return {'CANCELLED'}

        # Position Light
        PositionLight(lightObject, mathutils.Vector(
            (normal[0], normal[1], normal[2])), lightDistance)

        # Set as active Object
        context.view_layer.objects.active = lightObject

        # Create Adjust Light
        print("invoke Adjust Light no Params")
        if bpy.ops.lightcontrol.adjust_light.poll():
            bpy.ops.lightcontrol.adjust_light('INVOKE_DEFAULT')
        return {'FINISHED'}


class LIGHTCONTROL_OT_adjust_light(bpy.types.Operator):
    """Takes control of Blender and Lets you adjust the Light"""
    bl_idname = "lightcontrol.adjust_light"
    bl_label = "Adjust Light"
    bl_options = {'REGISTER', 'UNDO'}

    # temporary storeage of pivotObjectID
    pivotObject: bpy.types.Object = None
    # settings for modal
    zoomSpeedPercent = 0.1
    rotationSpeed = 0.01
    energyGrowthPercent = 0.25
    sizeChangeSensitivity = 0.02
    pauseExecution: bool = False

    @ classmethod
    def poll(cls, context):
        # true when in 3D View and Active Object is Light.
        if context.active_object == None:
            print("No Active Object to adjust the lighting of")
            return False
        return context.area.type == 'VIEW_3D' and context.active_object.type == 'LIGHT'

    def execute(self, context: bpy.types.Context):
        print("Adjust Light Can only be invoked, not executed.")
        return {'CANCELLED'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        # save the active object
        lightObject = context.active_object
        # when there is no custom attribute in the object.
        if "pivotPoint" not in lightObject:
            print("Property not found => created")
            context.active_object["pivotPoint"] = (0, 0, 0)  # create it
        # create pivot
        self.pivotObject = bpy.data.objects.new("temporaryPivot", None)
        self.pivotObject.empty_display_type = 'ARROWS'
        self.pivotObject.location = mathutils.Vector(
            (lightObject["pivotPoint"][0], lightObject["pivotPoint"][1], lightObject["pivotPoint"][2]))
        bpy.context.scene.collection.objects.link(self.pivotObject)
        # unrotate and place light
        pivotToLight: mathutils.Vector = lightObject.location - self.pivotObject.location
        lightObject.rotation_euler = (0, pi*0.5, 0)  # make -Z look forward
        lightObject.location = mathutils.Vector((pivotToLight.magnitude, 0, 0))
        # set parenting of light and pivot
        lightObject.parent_type = 'OBJECT'
        lightObject.parent = self.pivotObject
        # rotate pivot
        rot = lookAtRotation(pivotToLight, "-x")
        self.pivotObject.rotation_euler = rot

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        # wrap mouse movement so it stays in window
        wrapMouseInWindow(context, event)

        # save the active object
        lightObject: bpy.types.Object = context.active_object

        # Pause Execution for repositioning Mouse
        if event.type == 'SPACE':
            self.pauseExecution = event.value == 'PRESS'
            print(f"pressed space , should pause {self.pauseExecution}")

        if self.pauseExecution:
            return {'RUNNING_MODAL'}
        # Set Light Adjustments
        if event.type == 'MIDDLEMOUSE':  # allow view navigation
            return {'PASS_THROUGH'}

        elif event.type == 'MOUSEMOVE' and event.shift:
            hit, normal, best_original = raycast(context, event)
            if hit:
                self.pivotObject.location = hit
                self.pivotObject.rotation_euler = lookAtRotation(normal)
                print('mousemove')

        elif event.type == 'MOUSEMOVE':
            xDelta = (event.mouse_x - event.mouse_prev_x) * \
                self.rotationSpeed
            yDelta = (event.mouse_y - event.mouse_prev_y) * \
                self.rotationSpeed
            # add delta rotation to existing rotation and clamp it
            self.pivotObject.rotation_euler = mathutils.Euler((self.pivotObject.rotation_euler.x, clamp(
                self.pivotObject.rotation_euler.y - yDelta, -pi/2.0, pi/2.0), self.pivotObject.rotation_euler.z + xDelta))

        # TODO : Add all Light Size Options
        # elif event.type == 'MOUSEMOVE' and event.alt:
        #     lightObjectData: bpy.types.PointLight = lightObject.data
        #     #
        #     lightObjectData.shadow_soft_size *= 1 + \
        #         ((event.mouse_region_x - event.mouse_prev_x)
        #          * self.sizeChangeSensitivity)
        #     #clamp size
        #     lightObjectData.shadow_soft_size = bl_math.clamp(
        #         lightObjectData.shadow_soft_size, 0.001, 10000000)

        # TODO : Make Rotation based on Delta
        # elif event.type == 'MOUSEMOVE':
        #     x = radians(remap(event.mouse_region_y /
        #                 context.area.height, 0.0, 1.0, 90.0, -90.0))
        #     y = radians(remap(event.mouse_region_x /
        #                 context.area.width, 0.0, 1.0, 0.0, 360.0))
        #     rot = mathutils.Vector((0.0, x, y))
        #     pivotObject.rotation_euler = rot

        # TODO : Add All Light Options Energy
        # elif event.type == 'WHEELUPMOUSE' and event.shift:
        #     obj: bpy.types.PointLight = bpy.data.objects[self.lgtObjName].data
        #     obj.energy *= bl_math.clamp(1.0 +
        #                                 self.energyGrowthPercent, 0.001, 10000000)

        # elif event.type == 'WHEELDOWNMOUSE' and event.shift:
        #     lightObjectData: bpy.types.PointLight = bpy.data.objects[self.lgtObjName].data
        #     obj.energy *= bl_math.clamp(1.0 -
        #                                 self.energyGrowthPercent, 0.001, 10000000)

        elif event.type == 'WHEELUPMOUSE':
            pos = mathutils.Vector(
                (lightObject.location[0] * (1 - self.zoomSpeedPercent), lightObject.location[1], lightObject.location[2]))
            lightObject.location = pos

        elif event.type == 'WHEELDOWNMOUSE':
            pos = mathutils.Vector(
                (lightObject.location[0] * (1 + self.zoomSpeedPercent), lightObject.location[1], lightObject.location[2]))
            lightObject.location = pos

        elif event.type == 'LEFTMOUSE':
            # save rotation
            rot = self.pivotObject.rotation_euler

            # Unparent
            world_loc = lightObject.matrix_world.to_translation()
            lightObject.parent = None
            lightObject.matrix_world.translation = world_loc

            # remove pivot Object
            bpy.data.objects.remove(self.pivotObject, do_unlink=True)

            # set Light as Active Object
            context.view_layer.objects.active = lightObject

            print('finished adjusting Light')
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            print('canceled adjusting Light')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


#################################################################
####################### REGISTRATION ############################
#################################################################
addon_keymaps = []
classes = (LIGHTCONTROL_OT_add_light, LIGHTCONTROL_OT_adjust_light)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        # TODO : Change the name="" to Object mode
        # spawn lights
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(
            "lightcontrol.add_light", type='ONE', value='PRESS', shift=True, ctrl=True)
        kmi.properties.lightType = 'AREA'
        kmi = km.keymap_items.new(
            "lightcontrol.add_light", type='TWO', value='PRESS', shift=True, ctrl=True)
        kmi.properties.lightType = 'POINT'
        kmi = km.keymap_items.new(
            "lightcontrol.add_light", type='THREE', value='PRESS', shift=True, ctrl=True)
        kmi.properties.lightType = 'SPOT'
        kmi = km.keymap_items.new(
            "lightcontrol.add_light", type='FOUR', value='PRESS', shift=True, ctrl=True)
        kmi.properties.lightType = 'SUN'
        # adjust lights
        kmi = km.keymap_items.new(
            "lightcontrol.adjust_light", type='Q', value='PRESS', shift=True, ctrl=True)
        addon_keymaps.append((km, kmi))


def unregister():
    print("unregistered")
    for cls in classes:
        bpy.utils.unregister_class(cls)

    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


# TestRunning
if __name__ == '__main__':
    register()
