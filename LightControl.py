from bpy_extras import view3d_utils
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d
from math import cos
from math import sin
import sys
from math import pi
from math import sqrt
from math import atan2
from math import degrees
from math import radians
import bl_math
import mathutils
import bpy
from bpy.types import Menu


bl_info = {
    "name": "Light Control",
    "description": "Tools that lets you easily create and adjust lights",
    "author": "Malte Decker",
    "version": (0, 3, 0),
    "blender": (3, 3, 0),
    "location": "Shortcuts : CTRL + SHIFT + 1/2/3/4 and E",
}


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


def setMousePositionAtCoordinate(context: bpy.types.Context, mousePosition: tuple[int, int]):

    context.window.cursor_warp(mousePosition[0], mousePosition[1])

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


def intensityByInverseSquareLaw(referenceIntensity: float, referenceDistance: float, newDistance: float) -> float:
    referenceConstant: float = referenceIntensity * \
        (referenceDistance * referenceDistance)
    lightIntensityAtNewDistance: float = referenceConstant / \
        (newDistance * newDistance)
    lightIntensityRateOfChange: float = referenceIntensity / lightIntensityAtNewDistance
    return referenceIntensity * lightIntensityRateOfChange


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


def lookAtRotation(vec: mathutils.Vector, facingAxis="") -> mathutils.Vector:
    """ specify look at facing Axis by string x,y,z or -x,-y,-z, its important to keep rotation Order as XYZ"""
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


def raycastCursor(context: bpy.types.Context, mousepos: tuple, debug=False):  # -> bpy.types.Object,
    """takes in the current context, a mouse position as a tuple x,y (region coords) and gives back the hit object, hit location, hit normal, hit index and hit distance"""
    region = context.region
    region_data = context.region_data

    origin_3d = region_2d_to_origin_3d(region, region_data, mousepos)
    vector_3d = region_2d_to_vector_3d(region, region_data, mousepos)

    candidates = context.visible_objects

    objects = [(obj, None) for obj in candidates if obj.type == "MESH"]

    if debug:
        print(
            f"mousePos: {mousepos} , origin_3d:{origin_3d} , vector_3d:{vector_3d} ")
    hitobj = None
    hitlocation = None
    hitnormal = None
    hitindex = None
    hitdistance = sys.maxsize

    for obj, src in objects:
        mx = obj.matrix_world
        mxi = mx.inverted_safe()

        ray_origin = mxi @ origin_3d
        ray_direction = mxi.to_3x3() @ vector_3d

        success, location, normal, index = obj.ray_cast(
            origin=ray_origin, direction=ray_direction)
        distance = (mx @ location - origin_3d).length

        if debug:
            print("candidate:", success, obj.name,
                  location, normal, index, distance)

        if success and distance < hitdistance:
            hitobj, hitlocation, hitnormal, hitindex, hitdistance = obj, mx @ location, mx.to_3x3() @ normal, index, distance

    if debug:
        print("best hit:", hitobj.name if hitobj else None, hitlocation,
              hitnormal, hitindex, hitdistance if hitobj else None)
        print()

    if hitobj:
        return hitobj, hitlocation, hitnormal, hitindex, hitdistance

    return None, None, None, None, None

# Object Creation


def CreateLight(context: bpy.types.Context, pivotPosition: mathutils.Vector, lightType: str) -> bpy.types.Object:
    """Creates a Light at position, Light types are POINT, SUN, SPOT, AREA"""
    # TODO : change lightDistance based on Camera Distance to Object
    # TODO : Create an Area Light always as a Rectangle
    # TODO : Change the initial Brightness of the sun to 3
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
    # if context.collection == context.scene.collection:
    #     lightCollection = bpy.data.collections.new(
    #         "Lighting")  # create collection
    #     context.scene.collection.children.link(
    #         lightCollection)  # link collection
    #     lightCollection.objects.link(lightObject)  # link light
    #     lightCollectionLayerColl: bpy.types.LayerCollection = lightCollection
    #     context.view_layer.active_layer_collection = lightCollectionLayerColl  # set active
    # else:
    context.collection.objects.link(lightObject)

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


def UnparentAndKeepPositionRemoveParent(parent: bpy.types.Object, child: bpy.types.Object):
    # save rotation
    rot = parent.rotation_euler
    # Unparent
    world_loc = child.matrix_world.to_translation()
    child.parent = None
    child.matrix_world.translation = world_loc
    # remove pivot Object
    bpy.data.objects.remove(parent, do_unlink=True)

# Light Adjustment Functions


def GetLightIntensity(lightObject: bpy.types.Object) -> float:
    # Get enery based on Lamp Type
    lightObjectData: bpy.types.Light = lightObject.data

    if lightObjectData.type == 'AREA':
        areaLightObjectData: bpy.types.AreaLight = lightObject.data
        return areaLightObjectData.energy
    elif lightObjectData.type == 'POINT':
        pointLightObjectData: bpy.types.PointLight = lightObject.data
        return pointLightObjectData.energy
    elif lightObjectData.type == 'SPOT':
        spotLightObjectData: bpy.types.SpotLight = lightObject.data
        return spotLightObjectData.energy
    elif lightObjectData.type == 'SUN':
        sunLightObjectData: bpy.types.SunLight = lightObject.data
        return sunLightObjectData.energy
    else:
        return -1.0


def SetLightIntensity(lightObject: bpy.types.Object, newIntensity: float):
    # minimum and maximum Light Intensity
    minimumIntensity: float = 0.001
    maximumIntensity: float = 10000000
    # Set enery based on Lamp Type
    lightObjectData: bpy.types.Light = lightObject.data

    if lightObjectData.type == 'AREA':
        areaLightObjectData: bpy.types.AreaLight = lightObject.data
        areaLightObjectData.energy = newIntensity
        areaLightObjectData.energy = bl_math.clamp(
            areaLightObjectData.energy, minimumIntensity, maximumIntensity)
    elif lightObjectData.type == 'POINT':
        pointLightObjectData: bpy.types.PointLight = lightObject.data
        pointLightObjectData.energy = newIntensity
        pointLightObjectData.energy = bl_math.clamp(
            pointLightObjectData.energy, minimumIntensity, maximumIntensity)
    elif lightObjectData.type == 'SPOT':
        spotLightObjectData: bpy.types.SpotLight = lightObject.data
        spotLightObjectData.energy = newIntensity
        spotLightObjectData.energy = bl_math.clamp(
            spotLightObjectData.energy, minimumIntensity, maximumIntensity)
    elif lightObjectData.type == 'SUN':
        sunLightObjectData: bpy.types.SunLight = lightObject.data
        sunLightObjectData.energy = newIntensity
        sunLightObjectData.energy = bl_math.clamp(
            sunLightObjectData.energy, minimumIntensity, maximumIntensity)


def SetLightIntensityByRatioClamped(lightObject: bpy.types.Object, changeRatePercent: float):
    SetLightIntensity(lightObject, GetLightIntensity(
        lightObject) * changeRatePercent)

#################################################################
######################## OPERATORS ##############################
#################################################################


class LIGHTCONTROL_OT_add_light(bpy.types.Operator):
    bl_idname = "lightcontrol.add_light"
    bl_label = "Adds an Area Light"
    bl_options = {'REGISTER', 'UNDO'}

    # Properties
    lightType: bpy.props.EnumProperty(items=[('POINT', 'Point Light', ''), ('AREA', 'Area Light', ''), ('SPOT', 'Spot Light', ''), (
        'SUN', 'Directional Light', '')], name="Light Types", description="Which Light Type should be spawned", default='AREA')
    initialLightDistancePercent: float = 0.35  # range from 0.0 to 1.0

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        # Cancel if Light type doesnt work
        if self.lightType not in {'AREA', 'POINT', 'SPOT', 'SUN'}:
            print("Couldnt add this lighttype.")
            return {'CANCELLED'}
        # Set Mouse Position based on Pie Menu Call
        mousePosition: tuple[int, int] = (
            event.mouse_region_x, event.mouse_region_y)
        if context.scene['PieMenuMousePosition']:
            # Set Mouse Pos
            mousePosition = int(
                context.scene.PieMenuMousePosition[0]), int(context.scene.PieMenuMousePosition[1])
            # Delete Property
            del bpy.types.Scene.PieMenuMousePosition
        # Raycast and Cancel if nothing hit
        hitobj, hitlocation, hitnormal, hitindex, hitdistance = raycastCursor(
            context, mousepos=mousePosition, debug=False)
        if not hitobj:
            print("hit nothing, canceled")
            return {'CANCELLED'}
        # Calculate Light Distance
        pivotPoint = mathutils.Vector(
            (hitlocation[0], hitlocation[1], hitlocation[2]))
        lightDistance: float = 3.0
        # if there is a camera, use it to calculate an appropriate light distance.
        if context.scene.camera:
            cameraToPivot: mathutils.Vector = context.scene.camera.location - pivotPoint
            lightDistance: float = cameraToPivot.magnitude * self.initialLightDistancePercent
        # Create Light
        lightObject = CreateLight(context, pivotPoint, str(self.lightType))
        # Calculate Light Intensity
        lightIntensity: float = 3.0  # light Intensity when Sunlight
        lightObjectData: bpy.types.Light = lightObject.data
        if lightObjectData.type == 'AREA':  # Light Intensity when Area
            lightIntensity = intensityByInverseSquareLaw(
                40, 2.5, lightDistance)
        elif lightObjectData.type != 'SUN':  # Light Intensity when other light Type
            lightIntensity = intensityByInverseSquareLaw(
                60, 2.5, lightDistance)
        # Set Light Intensity
        SetLightIntensity(lightObject, lightIntensity)
        # Position Light
        PositionLight(lightObject, mathutils.Vector(
            (hitnormal[0], hitnormal[1], hitnormal[2])), lightDistance)
        # Set as selected and active Object
        for obj in context.selected_objects:  # deselect all
            obj.select_set(False)
        lightObject.select_set(True)
        context.view_layer.objects.active = lightObject
        # Go into Adjust Light mode
        print("invoke Adjust Light no Params")
        if bpy.ops.lightcontrol.adjust_light.poll():
            bpy.ops.lightcontrol.adjust_light('INVOKE_DEFAULT')
        return {'FINISHED'}


class LIGHTCONTROL_MT_add_light_pie_menu(Menu):
    # label is displayed at the center of the pie menu.
    bl_label = "Add Light at Mouse"

    def draw(self, context):
        layout = self.layout

        pie = layout.menu_pie()
        # operator_enum will just spread all available options
        # for the type enum of the operator on the pie
        pie.operator_enum("lightcontrol.add_light", "lightType")


class LIGHTCONTROL_OT_add_light_pie_menu_call(bpy.types.Operator):
    bl_idname = 'lightcontrol.add_light_pie_menu_call'
    bl_label = 'Lightcontrol Add Pie Menu'
    bl_description = 'Call Add Light Pie Menu, to create a Light Source at Cursor'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        bpy.ops.wm.call_menu_pie(name="LIGHTCONTROL_MT_add_light_pie_menu")
        # remember Mouse position when Object was created
        bpy.types.Scene.PieMenuMousePosition = bpy.props.FloatVectorProperty(
            name="Pie Menu Mouse Position", description="Mouse Position when Pie Menu was Initialized")
        context.scene.PieMenuMousePosition = (
            (event.mouse_region_x, event.mouse_region_y, 0.0))
        return {'FINISHED'}


class LIGHTCONTROL_OT_adjust_light(bpy.types.Operator):
    """Takes control of Blender and Lets you adjust the Light"""
    bl_idname = "lightcontrol.adjust_light"
    bl_label = "Adjust Light"
    bl_options = {'REGISTER', 'UNDO'}

    # temporary storeage of pivotObjectID
    pivotObject: bpy.types.Object = None
    # settings for modal
    zoomSpeedPercent = 0.01
    rotationSpeed = 0.006
    energyGrowthPercent = 0.01
    angleChangeSensitivity = 0.01
    sizeChangeSensitivity = 0.01
    hueChangeSensitivity = 0.0003
    saturationChangeSensitivity = 0.002
    slowChangeSpeedPercent = 0.2
    emptyDisplaySize = 0.04
    # Input enablers for modal
    approveOperation: bool = False
    cancelOperation: bool = False
    changeLightOrbit: bool = False
    changeLightSize: bool = False
    changeLightDistance: bool = False
    changeLightBrightness: bool = False
    changeLightAngle: bool = False
    changeLightColor: bool = False
    changeLightPivot: bool = False
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
        # set light Object as the active object
        lightObject = context.active_object
        # when there is no custom attribute in the object.
        if "pivotPoint" not in lightObject:
            print("Property not found => created")
            context.active_object["pivotPoint"] = (0, 0, 0)  # create it
        # create pivot
        self.pivotObject = bpy.data.objects.new("temporaryPivot", None)
        self.pivotObject.empty_display_type = 'ARROWS'  # 'SINGLE_ARROW'
        self.pivotObject.location = mathutils.Vector(
            (lightObject["pivotPoint"][0], lightObject["pivotPoint"][1], lightObject["pivotPoint"][2]))
        bpy.context.scene.collection.objects.link(self.pivotObject)
        # size pivot correctly
        r3d = context.area.spaces.active.region_3d
        distance: mathutils.Vector = self.pivotObject.location - \
            r3d.view_matrix.inverted().translation
        self.pivotObject.empty_display_size = distance.magnitude * self.emptyDisplaySize
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

        # Set pivot empty display size based on distance
        r3d = context.area.spaces.active.region_3d
        distance: mathutils.Vector = self.pivotObject.location - \
            r3d.view_matrix.inverted().translation
        self.pivotObject.empty_display_size = distance.magnitude * self.emptyDisplaySize

        # Calculate delta for later usage
        delta: mathutils.Vector = mathutils.Vector(
            (event.mouse_x - event.mouse_prev_x, event.mouse_y - event.mouse_prev_y, 0.0))

        # Set Input Enabeling Variables
        if event.type in {'LEFTMOUSE', 'RET'}:
            self.approveOperation = True
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancelOperation = True
        if event.type == 'S':
            self.changeLightSize = event.value == 'PRESS'
        if event.type == 'B':
            self.changeLightBrightness = event.value == 'PRESS'
        if event.type == 'D':
            self.changeLightDistance = event.value == 'PRESS'
        if event.type == 'C':
            self.changeLightColor = event.value == 'PRESS'
        if event.type == 'A':
            self.changeLightAngle = event.value == 'PRESS'
        self.changeLightPivot = event.type == 'MOUSEMOVE' and event.ctrl
        self.changeLightOrbit = event.type == 'MOUSEMOVE'
        if event.type == 'SPACE':
            self.pauseExecution = event.value == 'PRESS'

        # Pause Execution for repositioning Mouse
        if self.pauseExecution:
            return {'RUNNING_MODAL'}

        # Pass through Navigation
        if event.type == 'MIDDLEMOUSE':  # allow view navigation
            return {'PASS_THROUGH'}

        elif self.changeLightColor:
            # Get Light Color
            lightObjectData: bpy.types.Light = lightObject.data
            lightColor: mathutils.Color = lightObjectData.color
            # Calculate Rate of Change
            hue: float = (lightColor.hsv[0] + delta.x *
                          self.hueChangeSensitivity) % 1.0
            sat: float = bl_math.clamp(
                lightColor.hsv[1] + delta.y * self.saturationChangeSensitivity, 0.0, 1.0)
            val: float = lightColor.hsv[2]
            # Set light Color
            lightColor.hsv = (hue, sat, val)

        elif self.changeLightPivot:
            # hit, normal, best_original = raycast(context, event)
            hitobj, hitlocation, hitnormal, hitindex, hitdistance = raycastCursor(
                context, mousepos=(event.mouse_region_x, event.mouse_region_y), debug=False)
            if hitobj:
                self.pivotObject.location = hitlocation
                # TODO : Implement Special case, normal is 0,0,1
                self.pivotObject.rotation_euler = lookAtRotation(hitnormal)
                lightObject["pivotPoint"] = (
                    hitlocation.x, hitlocation.y, hitlocation.z)
                print('mousemove')

        elif self.changeLightAngle:
            # return early
            lightObjectData: bpy.types.Light = lightObject.data
            if lightObjectData.type not in {'AREA', 'SPOT', 'SUN'}:
                return {'RUNNING_MODAL'}
            # Get Delta
            step: mathutils.Vector = delta
            # Adjust Rate of Change
            if event.shift:
                step *= self.slowChangeSpeedPercent
            step *= self.angleChangeSensitivity
            rateOfChangeX: float = 1.0 + step.x
            rateOfChangeY: float = 1.0 + step.y
            if lightObjectData.type == 'SPOT':
                spotLightObjectData: bpy.types.SpotLight = lightObjectData
                spotLightObjectData.spot_size = bl_math.clamp(
                    spotLightObjectData.spot_size * rateOfChangeX, 0.017, 3.1415)  # in Radians
                spotLightObjectData.spot_blend = bl_math.clamp(
                    spotLightObjectData.spot_blend * rateOfChangeY, 0.01, 1.0)
            elif lightObjectData.type == 'AREA':
                areaLightObjectData: bpy.types.AreaLight = lightObjectData
                areaLightObjectData.spread = bl_math.clamp(
                    areaLightObjectData.spread * rateOfChangeX, 0.017, 3.1415)  # in Radians
            elif lightObjectData.type == 'SUN':
                sunLightObjectData: bpy.types.SunLight = lightObjectData
                sunLightObjectData.angle = bl_math.clamp(
                    sunLightObjectData.angle * rateOfChangeX, 0.001, 180.0)

        elif self.changeLightSize:
            lightObjectData: bpy.types.Light = lightObject.data
            if lightObjectData.type not in {'AREA', 'POINT', 'SPOT'}:
                return {'RUNNING_MODAL'}
            # minimum and maximum Light Intensity
            minimumIntensity: float = 0.001
            maximumIntensity: float = 10000000
            # Multiplication Factor
            changeRate = delta.x * self.sizeChangeSensitivity
            if event.shift:
                changeRate *= self.slowChangeSpeedPercent
            rateOfChange = 1.0 + changeRate
            # Setting Size
            if lightObjectData.type == 'AREA':
                areaLightObjectData: bpy.types.AreaLight = lightObject.data
                areaLightObjectData.size = bl_math.clamp(
                    areaLightObjectData.size * rateOfChange, minimumIntensity, maximumIntensity)
            elif lightObjectData.type == 'POINT':
                pointLightObjectData: bpy.types.PointLight = lightObject.data
                pointLightObjectData.shadow_soft_size = bl_math.clamp(
                    pointLightObjectData.shadow_soft_size * rateOfChange, minimumIntensity, maximumIntensity)
            elif lightObjectData.type == 'SPOT':
                spotLightObjectData: bpy.types.SpotLight = lightObject.data
                spotLightObjectData.shadow_soft_size = bl_math.clamp(
                    spotLightObjectData.shadow_soft_size * rateOfChange, minimumIntensity, maximumIntensity)

        elif self.changeLightBrightness:
            # minimum and maximum Light Intensity
            minimumIntensity: float = 0.001
            maximumIntensity: float = 10000000
            # Get Delta
            step: float = delta.x
            # Adjust Rate of Change
            if event.shift:
                step *= self.slowChangeSpeedPercent
            step *= self.energyGrowthPercent
            rateOfChange: float = 1.0 + step
            # Set enery based on Lamp Type
            SetLightIntensityByRatioClamped(lightObject, rateOfChange)

        elif self.changeLightDistance:
            lightObjectData: bpy.types.Light = lightObject.data
            if lightObjectData.type == 'SUN':
                return {'RUNNING_MODAL'}
            # Get Delta
            step: float = delta.x
            # Adjust Rate of Change
            if event.shift:
                step *= self.slowChangeSpeedPercent
            step *= self.zoomSpeedPercent
            # Calculate Position
            newPosition = mathutils.Vector(
                (lightObject.location[0] * (1 + step), lightObject.location[1], lightObject.location[2]))
            # Calculate Compensation of Lighting by Distance
            pivotPoint: mathutils.Vector = mathutils.Vector(
                (lightObject["pivotPoint"][0], lightObject["pivotPoint"][1], lightObject["pivotPoint"][2]))
            oldLightDistanceToPivot: float = (
                lightObject.location - pivotPoint).magnitude
            newLightDistanceToPivot: float = (
                newPosition - pivotPoint).magnitude
            adjustedIntensity: float = intensityByInverseSquareLaw(GetLightIntensity(
                lightObject), oldLightDistanceToPivot, newLightDistanceToPivot)
            # TODO: not the prettiest but for now it will do
            if newLightDistanceToPivot < 100.0:
                # Adjust Light Intensity
                SetLightIntensity(lightObject, adjustedIntensity)
                # Set Position
                lightObject.location = newPosition

        elif self.changeLightOrbit:
            step: mathutils.Vector = delta * self.rotationSpeed
            if event.shift:
                step *= self.slowChangeSpeedPercent
            xMultiplicator = step.x
            yMultiplicator = step.y
            # add delta rotation to existing rotation and clamp it
            self.pivotObject.rotation_euler = mathutils.Euler((self.pivotObject.rotation_euler.x, clamp(
                self.pivotObject.rotation_euler.y - yMultiplicator, -pi/2.0, pi/2.0), self.pivotObject.rotation_euler.z + xMultiplicator))

        elif self.approveOperation:
            UnparentAndKeepPositionRemoveParent(self.pivotObject, lightObject)
            # set Light as Active Object
            context.view_layer.objects.active = lightObject
            print('finished adjusting Light')
            return {'FINISHED'}

        elif self.cancelOperation:
            UnparentAndKeepPositionRemoveParent(self.pivotObject, lightObject)
            # set Light as Active Object
            context.view_layer.objects.active = lightObject
            print('canceled adjusting Light')
            return {'CANCELLED'}

        # TODO : Change Pivot Point Size depending on Distance to Pivot
        # TODO : Give User the option to Single The Light Source
        # TODO : Give User the option to have Light Groups
        # TODO : Give User the option to cycle Light Groups
        return {'RUNNING_MODAL'}


# class LIGHTCONTROL_OT_create_world_setup(bpy.types.Operator):
#     bl_idname = "lightcontrol.create_world_setup"
#     bl_label = "Add mapping"
#     bl_description = "Add mapping to world, if not existent"
#     bl_options = {'REGISTER', 'UNDO'}

#     def execute(self,context):

#         # world = bpy.data.worlds.new("World HDRI")
#         world = context.scene.world
#         world.name = "World HDRI"
#         world['is_world_hdri'] = True
#         world.use_nodes = True
#         nodes = world.node_tree.nodes
#         links = world.node_tree.links

#         # Mapping
#         mapping = nodes.new('ShaderNodeMapping')
#         mapping.location = (-200,0)

#         coord = nodes.new('ShaderNodeTexCoord')
#         coord.location = (-400,0)

#         # Texture
#         img = nodes.new('ShaderNodeTexEnvironment')
#         img.location = (0,0)
#         img.name = 'World HDRI Tex'

#         # Shader
#         bg = nodes['Background']
#         bg.location = (300,0)

#         # Output
#         output = nodes['World Output']
#         output.location = (500,0)
#################################################################
####################### REGISTRATION ############################
#################################################################
addon_keymaps = []
classes = (LIGHTCONTROL_OT_add_light, LIGHTCONTROL_MT_add_light_pie_menu,
           LIGHTCONTROL_OT_add_light_pie_menu_call, LIGHTCONTROL_OT_adjust_light)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        # TODO : Change the name="" to Object mode somehow
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        # spawn lights
        kmi = km.keymap_items.new(
            "lightcontrol.add_light_pie_menu_call", type='E', value='PRESS', shift=True)
        # adjust lights
        kmi = km.keymap_items.new(
            "lightcontrol.adjust_light", type='E', value='PRESS')  # shift=True, ctrl=True
        addon_keymaps.append((km, kmi))


def unregister():
    print("unregistered")
    for cls in classes:
        bpy.utils.unregister_class(cls)

    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


if __name__ == "__main__":
    register()
