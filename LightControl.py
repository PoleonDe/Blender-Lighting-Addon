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
import blf
import gpu
from gpu_extras.batch import batch_for_shader


bl_info = {
    "name": "Light Control",
    "description": "Tools that let you easily create lights on Mouseposition (Shift + E) and adjust lights (when light active, E) fast and intuetively",
    "author": "Malte Decker",
    "version": (0, 9, 0),
    "blender": (3, 3, 0),
    "location": "Shortcuts : Shift E and E",
    "category": "Lighting"
}


#################################################################
######################## FUNCTIONS ##############################
#################################################################


# Wrap Cursor when its at first or last pixel of window
def wrapMouseInWindow(context: bpy.types.Context, event: bpy.types.Event) -> mathutils.Vector:
    width = context.area.width
    height = context.area.height

    delta: mathutils.Vector = mathutils.Vector(
        (event.mouse_x - event.mouse_prev_x, event.mouse_y - event.mouse_prev_y, 0.0))
    args = (event.mouse_x, event.mouse_y)
    offset: mathutils.Vector = mathutils.Vector((0.0, 0.0, 0.0))

    if event.mouse_x <= context.area.x:
        args = (context.area.x + width - 1, event.mouse_y)
        context.window.cursor_warp(context.area.x + width - 1, event.mouse_y)
        offset = mathutils.Vector((width, 0.0, 0.0))
        print(f"moved, offset is width {width}")

    if event.mouse_x >= context.area.x + width:
        args = (context.area.x + 1, event.mouse_y)
        offset = mathutils.Vector((-width, 0.0, 0.0))
        print(f"moved, offset is width {-width}")

    if event.mouse_y <= context.area.y:
        args = (event.mouse_x, context.area.y + 1)
        offset = mathutils.Vector((0.0, -height, 0.0))
        print(f"moved, offset is height {-height}")

    if event.mouse_y >= context.area.y + height:
        args = (event.mouse_x, context.area.y + height - 1)
        offset = mathutils.Vector((0.0, height, 0.0))
        print(f"moved, offset is height {height}")

    context.window.cursor_warp(*args)

    return offset


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
    # Handle the Vector (0,0,1) Case and the (0,0,-1) Case
    if vec == mathutils.Vector((0.0, 0.0, 1.0)):
        return mathutils.Vector((0.0, -pi * 0.5, 0.0))
    if vec == mathutils.Vector((0.0, 0.0, -1.0)):
        return mathutils.Vector((0.0, pi * 0.5, 0.0))

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


def boolToFloat(v: bool) -> float:
    if v:
        return 1.0
    else:
        return 0.0

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


def GetLightType(lightObject: bpy.types.Object):
    lightObjectData: bpy.types.Light = lightObject.data
    '''Returns the Type of Light as tuple - 1. AREA,SUN,POINT,SPOT as string, 2. lightData'''
    if lightObjectData.type == 'AREA':
        return ('AREA', bpy.types.AreaLight(lightObject.data))
    elif lightObjectData.type == 'POINT':
        return ('POINT', bpy.types.PointLight(lightObject.data))
    elif lightObjectData.type == 'SPOT':
        return ('SPOT', bpy.types.SpotLight(lightObject.data))
    elif lightObjectData.type == 'SUN':
        return ('SUN', bpy.types.SunLight(lightObject.data))
    else:
        return ('NONE', None)


def GetLightBrightness(lightObject: bpy.types.Object) -> float:
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


def SetLightBrightnessClamped(lightObject: bpy.types.Object, newIntensity: float, minimumIntensity: float = 0.001, maximumIntensity: float = 10000000):
    '''Set the Brightness of a Lamp, min 0.001, max 10000000'''
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


def SetLightBrightnessByRatioClamped(lightObject: bpy.types.Object, changeRatePercent: float, minimumIntensity: float = 0.001, maximumIntensity: float = 10000000):
    '''Change Brightness of a Lamp by a percentage Factor, clamped to min 0.001, max 10000000'''
    SetLightBrightnessClamped(lightObject, GetLightBrightness(
        lightObject) * changeRatePercent, minimumIntensity, maximumIntensity)


def GetLightSize(lightObject: bpy.types.Object) -> float:
    # Get lightSize based on Lamp Type
    lightObjectData: bpy.types.Light = lightObject.data

    if lightObjectData.type == 'AREA':
        areaLightObjectData: bpy.types.AreaLight = lightObject.data
        return areaLightObjectData.size
    elif lightObjectData.type == 'POINT':
        pointLightObjectData: bpy.types.PointLight = lightObject.data
        return pointLightObjectData.shadow_soft_size
    elif lightObjectData.type == 'SPOT':
        spotLightObjectData: bpy.types.SpotLight = lightObject.data
        return spotLightObjectData.shadow_soft_size
    else:
        return -1.0


def SetLightSizeClamped(lightObject: bpy.types.Object, lightSize: float, minimumSize: float = 0.001, maximumSize: float = 10000000):
    # Set lightSize based on Lamp Type
    lightObjectData: bpy.types.Light = lightObject.data

    if lightObjectData.type == 'AREA':
        areaLightObjectData: bpy.types.AreaLight = lightObject.data
        areaLightObjectData.size = clamp(lightSize, minimumSize, maximumSize)
    elif lightObjectData.type == 'POINT':
        pointLightObjectData: bpy.types.PointLight = lightObject.data
        pointLightObjectData.shadow_soft_size = clamp(
            lightSize, minimumSize, maximumSize)
    elif lightObjectData.type == 'SPOT':
        spotLightObjectData: bpy.types.SpotLight = lightObject.data
        spotLightObjectData.shadow_soft_size = clamp(
            lightSize, minimumSize, maximumSize)


def GetLightDistance(lightObject: bpy.types.Object) -> float:
    # Get light Distance to pivot
    pivotPosition: mathutils.Vector = GetLightPivot(lightObject)
    lightPosition: mathutils.Vector = mathutils.Vector(
        (lightObject.location.x, lightObject.location.y, lightObject.location.z))
    distance: mathutils.Vector = lightPosition - pivotPosition
    return distance.magnitude


def SetLightDistance(lightObject: bpy.types.Object, lightDistance: float):
    '''Scales the location Vector based on Ratio between lightDistance Parameter and current Distance (CAUTION: only works when Parented to Pivot)'''
    # Set light Distance to pivot
    currentDistance: float = GetLightDistance(lightObject)
    scalingRatio: float = lightDistance / currentDistance
    lightObject.location *= scalingRatio


def GetLightAngle(lightObject: bpy.types.Object) -> float:
    # Get light Angle based on Lamp Type
    lightObjectData: bpy.types.Light = lightObject.data

    if lightObjectData.type == 'AREA':
        areaLightObjectData: bpy.types.AreaLight = lightObject.data
        return areaLightObjectData.spread
    elif lightObjectData.type == 'SPOT':
        spotLightObjectData: bpy.types.SpotLight = lightObject.data
        return spotLightObjectData.spot_size
    elif lightObjectData.type == 'SUN':
        sunLightObjectData: bpy.types.SunLight = lightObject.data
        return sunLightObjectData.angle
    else:
        return -1.0


def SetLightAngle(lightObject: bpy.types.Object, lightAngle: float):
    # Set light Angle based on Lamp Type
    lightObjectData: bpy.types.Light = lightObject.data

    if lightObjectData.type == 'AREA':
        areaLightObjectData: bpy.types.AreaLight = lightObject.data
        areaLightObjectData.spread = lightAngle
    elif lightObjectData.type == 'SPOT':
        spotLightObjectData: bpy.types.SpotLight = lightObject.data
        spotLightObjectData.spot_size = lightAngle
    elif lightObjectData.type == 'SUN':
        sunLightObjectData: bpy.types.SunLight = lightObject.data
        sunLightObjectData.angle = lightAngle


def GetLightPivot(lightObject: bpy.types.Object) -> mathutils.Vector:
    # Get Light Pivot
    if "pivotPoint" not in lightObject:
        lightObject["pivotPoint"] = (0.0, 0.0, 0.0)

    return mathutils.Vector((lightObject["pivotPoint"][0], lightObject["pivotPoint"][1], lightObject["pivotPoint"][2]))


def SetLightPivot(lightObject: bpy.types.Object, pivotObject: bpy.types.Object, lightPivot: mathutils.Vector):
    # Set Light Pivot
    lightObject["pivotPoint"] = (lightPivot.x, lightPivot.y, lightPivot.z)


def GetLightColor(lightObject: bpy.types.Object) -> mathutils.Color:
    # Get light color based on Lamp Type
    lightObjectData: bpy.types.Light = lightObject.data

    if lightObjectData.type == 'AREA':
        areaLightObjectData: bpy.types.AreaLight = lightObject.data
        return areaLightObjectData.color
    elif lightObjectData.type == 'POINT':
        pointLightObjectData: bpy.types.PointLight = lightObject.data
        return pointLightObjectData.color
    elif lightObjectData.type == 'SPOT':
        spotLightObjectData: bpy.types.SpotLight = lightObject.data
        return spotLightObjectData.color
    elif lightObjectData.type == 'SUN':
        sunLightObjectData: bpy.types.SunLight = lightObject.data
        return sunLightObjectData.color
    else:
        return mathutils.Color((1.0, 1.0, 1.0))


def SetLightColor(lightObject: bpy.types.Object, lightColor: mathutils.Color):
    # Set light color based on Lamp Type
    lightObjectData: bpy.types.Light = lightObject.data

    if lightObjectData.type == 'AREA':
        areaLightObjectData: bpy.types.AreaLight = lightObject.data
        areaLightObjectData.color = lightColor
    elif lightObjectData.type == 'POINT':
        pointLightObjectData: bpy.types.PointLight = lightObject.data
        pointLightObjectData.color = lightColor
    elif lightObjectData.type == 'SPOT':
        spotLightObjectData: bpy.types.SpotLight = lightObject.data
        spotLightObjectData.color = lightColor
    elif lightObjectData.type == 'SUN':
        sunLightObjectData: bpy.types.SunLight = lightObject.data
        sunLightObjectData.color = lightColor


def GetLightOrbit(pivotObject: bpy.types.Object) -> mathutils.Euler:
    if pivotObject:
        rotation: mathutils.Euler = (
            (pivotObject.rotation_euler.x, pivotObject.rotation_euler.y, pivotObject.rotation_euler.z))
        return rotation
    else:
        print("Cant get Light Orbit, there is no Object")
        return mathutils.Euler((0.0, 0.0, 0.0))


def SetLightOrbit(pivotObject: bpy.types.Object, rotation: mathutils.Vector):
    pivotObject.rotation_euler = rotation


def GetLightValues(lightObject: bpy.types.Object, pivotObject: bpy.types.Object):
    lightOrbit = GetLightOrbit(pivotObject)
    lightDistance = GetLightDistance(lightObject)
    lightSize = GetLightSize(lightObject)
    lightBrightness = GetLightBrightness(lightObject)
    lightAngle = GetLightAngle(lightObject)
    lightPivot = GetLightPivot(lightObject)
    tempColor = GetLightColor(lightObject)
    lightColor = mathutils.Color((
        tempColor.r, tempColor.g, tempColor.b))  # Make Copy of Color
    return lightOrbit, lightDistance, lightSize, lightBrightness, lightAngle, lightPivot, lightColor


def SetLightOrbitByDelta(self, pivotObject: bpy.types.Object, delta: mathutils.Vector, rotationSpeed: float, slowChange: bool, slowChangeSpeed: float) -> bool:
    '''Adds to the Orientation of an Object an Azimuth and Elevation based on a delta, Rotation Order should be XYZ'''
    if pivotObject.rotation_mode != 'XYZ':
        self.report(
            {'INFO'}, 'cant guarantee expected Result, set Rotation Mode to XYZ')
    # calculate Delta
    step: mathutils.Vector = mathutils.Vector(
        (delta.x, delta.y, delta.z))
    step *= rotationSpeed
    if slowChange:
        step *= slowChangeSpeed
    xMultiplicator = step.x
    yMultiplicator = step.y
    # add delta rotation to existing rotation and clamp it
    pivotObject.rotation_euler = mathutils.Euler((pivotObject.rotation_euler.x, clamp(
        pivotObject.rotation_euler.y - yMultiplicator, -pi/2.0, pi/2.0), pivotObject.rotation_euler.z + xMultiplicator))


def SetLightDistanceByDeltaClamped(lightObject: bpy.types.Object, delta: mathutils.Vector, zoomSpeedPercent: float, slowChange: bool, slowChangeSpeed: float, minimumDistance: float = 0.001, maximumDistance: float = 1000000.0):
    '''changes the light distance based on a percentage per delta'''
    # Get Delta
    step: float = delta.x
    # Adjust Rate of Change
    if slowChange:
        step *= slowChangeSpeed
    step *= zoomSpeedPercent
    # Calculate Position
    newPosition = mathutils.Vector((clamp(lightObject.location[0] * (
        1 + step), minimumDistance, maximumDistance), lightObject.location[1], lightObject.location[2]))
    # Calculate Compensation of Lighting by Distance
    pivotPoint: mathutils.Vector = mathutils.Vector(
        (lightObject["pivotPoint"][0], lightObject["pivotPoint"][1], lightObject["pivotPoint"][2]))
    oldLightDistanceToPivot: float = (
        lightObject.location - pivotPoint).magnitude
    newLightDistanceToPivot: float = (
        newPosition - pivotPoint).magnitude
    adjustedIntensity: float = intensityByInverseSquareLaw(GetLightBrightness(
        lightObject), oldLightDistanceToPivot, newLightDistanceToPivot)
    # TODO: not the prettiest but for now it will do
    if newLightDistanceToPivot < 100.0:
        # Adjust Light Intensity
        SetLightBrightnessClamped(
            lightObject, adjustedIntensity, minimumDistance, maximumDistance)
        # Set Position
        lightObject.location = newPosition


def SetLightBrightnessByDeltaClamped(lightObject: bpy.types.Object, delta: mathutils.Vector, brightnessChangePercent: float, slowChange: bool, slowChangeSpeed: float, minimumIntensity: float = 0.001, maximumIntensity: float = 10000000):
    # Get Delta
    step: float = delta.x
    # Adjust Rate of Change
    if slowChange:
        step *= slowChangeSpeed
    step *= brightnessChangePercent
    rateOfChange: float = 1.0 + step
    # Set enery based on Lamp Type
    SetLightBrightnessByRatioClamped(
        lightObject, rateOfChange, minimumIntensity, maximumIntensity)


def SetLightSizeByDeltaClamped(lightObject: bpy.types.Object, delta: mathutils.Vector, sizeChangeSensitivity: float, slowChange: bool, slowChangeSpeed: float,  minimumSize: float = 0.001, maximumSize: float = 10000000):
    # Multiplication Factor
    step = delta.x * sizeChangeSensitivity
    if slowChange:
        step *= slowChangeSpeed
    rateOfChange = 1.0 + step
    # Setting Size
    SetLightSizeClamped(lightObject, GetLightSize(
        lightObject) * rateOfChange, minimumSize, maximumSize)


def SetLightAngleByDelta(lightObject: bpy.types.Object, delta: mathutils.Vector, angleChangeSensitivity: float, slowChange: bool, slowChangeSpeed: float,):
    # Get Delta
    step: mathutils.Vector = mathutils.Vector(
        (delta.x, delta.y, delta.z))
    # Adjust Rate of Change
    if slowChange:
        step *= slowChangeSpeed
    step *= angleChangeSensitivity
    rateOfChangeX: float = 1.0 + step.x
    rateOfChangeY: float = 1.0 + step.y
    lightObjectData: bpy.types.Light = lightObject.data
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


def SetLight_Pivot_Position_Rotation_ByNormal(lightObject: bpy.types.Object, pivotObject: bpy.types.Object, hitLocation: mathutils.Vector, hitNormal: mathutils.Vector):
    pivotObject.location = hitLocation
    lightObject["pivotPoint"] = (
        hitLocation.x, hitLocation.y, hitLocation.z)
    pivotObject.rotation_euler = lookAtRotation(
        hitNormal, "-x")


def SetLight_Pivot_Position_Rotation_ByReflection(activeRegion3D: bpy.types.RegionView3D, lightObject: bpy.types.Object, pivotObject: bpy.types.Object, hitLocation: mathutils.Vector, hitNormal: mathutils.Vector):
    cameraPosition: mathutils.Vector = activeRegion3D.view_matrix.inverted().translation
    camToHit: mathutils.Vector = hitLocation - cameraPosition
    reflection: mathutils.Vector = camToHit.reflect(hitNormal)
    pivotObject.rotation_euler = lookAtRotation(
        reflection, "-x")
    pivotObject.location = hitLocation
    lightObject["pivotPoint"] = (
        hitLocation.x, hitLocation.y, hitLocation.z)
    # self.activeRegion3D.view_matrix = view_matrix # Change View matrix.
    # context.space_data.region_3d.view_perspective = 'CAMERA' # Set as Cam


def SetLight_Pivot_Position_ByHit(lightObject: bpy.types.Object, pivotObject: bpy.types.Object, hitLocation: mathutils.Vector):
    pivotObject.location = hitLocation
    lightObject["pivotPoint"] = (
        hitLocation.x, hitLocation.y, hitLocation.z)


def SetLight_Pivot_ByHit(context: bpy.types.Context, lightObject: bpy.types.Object, pivotObject: bpy.types.Object, hitLocation: mathutils.Vector):
    # Position Calculation
    lightWorldPos: mathutils.Vector = lightObject.matrix_world.to_translation()
    lightToPivot: mathutils.Vector = lightWorldPos - pivotObject.location
    lightToHit: mathutils.Vector = lightWorldPos - hitLocation
    prevDistance: float = lightToPivot.magnitude
    newDistance: float = lightToHit.magnitude
    pivotObject.location = hitLocation
    pivotObject.rotation_euler = lookAtRotation(
        lightToHit)
    context.view_layer.update()
    scalingRatio: float = newDistance / prevDistance
    # Set Position
    lightObject.location *= scalingRatio
    # Update Pivot Attribute
    lightObject["pivotPoint"] = (
        hitLocation.x, hitLocation.y, hitLocation.z)


def SetLightColorByDelta(lightObject: bpy.types.Object, delta: mathutils.Vector, hueChangeSensitivity: float, saturationChangeSensitivity: float):
    # Get Light Color
    lightObjectData: bpy.types.Light = lightObject.data
    lightColor: mathutils.Color = lightObjectData.color
    # Calculate Rate of Change
    hue: float = (lightColor.hsv[0] + delta.y *
                  hueChangeSensitivity) % 1.0
    sat: float = bl_math.clamp(
        lightColor.hsv[1] + delta.x * saturationChangeSensitivity, 0.0, 1.0)
    val: float = lightColor.hsv[2]
    # Set light Color
    lightColor.hsv = (hue, sat, val)

# drawing Labels


def drawOperationOptions(self, context):
    activeOperationPos: mathutils.Vector = mathutils.Vector((80, 350, 0))
    availableOperationPos: mathutils.Vector = mathutils.Vector((80, 200, 0))
    font_id: int = 0

    currentOperation = [
        {"Header": "Light Size", "Description": "Hold S move Mouse Left/Right",
            "Value": self.lightSize, "ActivationBool": self.changeLightSize},
        {"Header": "Light Distance", "Description": "Hold D move Mouse Left/Right",
            "Value": self.lightDistance, "ActivationBool": self.changeLightDistance},
        {"Header": "Light Brightness", "Description": "Hold B move Mouse Left/Right",
            "Value": self.lightBrightness, "ActivationBool": self.changeLightBrightness},
        {"Header": "Light Angle", "Description": "Hold A move Mouse Left/Right",
            "Value": self.lightAngle, "ActivationBool": self.changeLightAngle},
        {"Header": "Light Pivot", "Description": "Hold CTRL or CTRL+SHIFT or CTRL+ALT or CTRL+ALT+SHIFT",
            "Value": self.lightPivot, "ActivationBool": self.changeLightPivot},
        {"Header": "Light Color", "Description": "Hold C move Mouse Up/Down (Saturation) and Left/Right (Hue)",
            "Value": self.lightColor, "ActivationBool": self.changeLightColor},
        {"Header": "Orbit", "Description": "Hold Space/R move Mouse Left/Right",
            "Value": self.lightOrbit, "ActivationBool": self.changeLightOrbit},
        {"Header": "Tilt", "Description": "Hold T move Mouse Left/Right",
            "Value": self.lightTilt, "ActivationBool": self.changeLightTilt}
    ]

    stopLoop: bool = False
    # Draw current Operation Dictionary
    for operation in currentOperation:
        for key, val in operation.items():
            if operation['ActivationBool'] == True:
                if key == 'Value':
                    blf.color(font_id, 1.0, 1.0, 1.0, 1.0)  # white
                    blf.size(font_id, 32, 72)
                    blf.position(font_id, activeOperationPos.x,
                                 activeOperationPos.y + 60, 0.0)
                    blf.draw(font_id, str(val))
                if key == 'Header':
                    blf.color(font_id, 1.0, 1.0, 0.0, 1.0)  # yellow
                    blf.size(font_id, 28, 72)
                    blf.position(font_id, activeOperationPos.x,
                                 activeOperationPos.y, 0.0)
                    blf.draw(font_id, str(val))
                if key == 'Description':
                    lineSpacing: float = 24.0
                    baseOffset: float = 8.0
                    blf.color(font_id, 1.0, 1.0, 1.0, 0.5)  # white 50 trans
                    blf.size(font_id, 18, 72)
                    blf.position(font_id, activeOperationPos.x,
                                 activeOperationPos.y - lineSpacing - baseOffset, 0.0)
                    blf.draw(font_id, str(val))
                    blf.position(font_id, activeOperationPos.x,
                                 activeOperationPos.y - (lineSpacing * 2.0) - baseOffset, 0.0)
                    blf.draw(font_id, "Hold Shift for Slow Operation")
                stopLoop = True
        if stopLoop:
            break

    availableOperations = [
        {"Key": "SPACE / R", "Description": "Orbit", "AvailableLightType": {
            'AREA', 'POINT', 'SPOT', 'SUN'}},
        {"Key": "CTRL", "Description": "Pivot",
            "AvailableLightType": {'AREA', 'POINT', 'SPOT', 'SUN'}},

        {"Key": "", "Description": "",
            "AvailableLightType": {'AREA', 'POINT', 'SPOT', 'SUN'}},  # Blank Entry

        {"Key": "C", "Description": "Color", "AvailableLightType": {
            'AREA', 'POINT', 'SPOT', 'SUN'}},
        {"Key": "A", "Description": "Angle",
            "AvailableLightType": {'AREA', 'SPOT', 'SUN'}},
        {"Key": "D", "Description": "Distance",
            "AvailableLightType": {'AREA', 'POINT', 'SPOT'}},
        {"Key": "B", "Description": "Brightness",
            "AvailableLightType": {'AREA', 'POINT', 'SPOT', 'SUN'}},
        {"Key": "S", "Description": "Size",
            "AvailableLightType": {'AREA', 'POINT', 'SPOT'}},
        {"Key": "T", "Description": "Tilt",
            "AvailableLightType": {'AREA', 'SPOT'}},

        {"Key": "", "Description": "", "AvailableLightType": {
            'AREA', 'POINT', 'SPOT', 'SUN'}},  # Blank Entry

        {"Key": "V", "Description": "Toggle Gizmos",
            "AvailableLightType": {'AREA', 'POINT', 'SPOT', 'SUN'}}
    ]

    blf.size(font_id, 16, 72)
    spacing: float = 18
    counter: int = 0
    # Draw available Operation Dictionary
    for operation in availableOperations:
        for key, val in operation.items():
            offset: float = counter * spacing
            increaseCounter: float = boolToFloat(
                self.currentLightType in operation['AvailableLightType'])
            if self.currentLightType in operation['AvailableLightType']:
                if key == 'Key':
                    blf.color(font_id, 1.0, 1.0, 0.5, 0.7)  # white 50 trans
                    blf.position(font_id, availableOperationPos.x,
                                 availableOperationPos.y - offset, 0.0)
                    blf.draw(font_id, str(val))
                if key == 'Description':
                    blf.color(font_id, 1.0, 1.0, 1.0, 0.5)  # white 50 trans
                    blf.position(font_id, availableOperationPos.x +
                                 80.0, availableOperationPos.y - offset, 0.0)
                    blf.draw(font_id, str(val))
        counter += increaseCounter

    # draw ACTIVE
    width = context.area.width
    height = context.area.height
    offset = 25
    rectangleHeight = 40
    blf.color(font_id, 1.0, 1.0, 1.0, 1.0)  # white
    blf.size(font_id, 32, 72)
    textWidth = blf.dimensions(0, "EDITING")[0]
    blf.position(font_id, width - textWidth - offset,
                 rectangleHeight + offset, 0.0)
    blf.draw(font_id, "EDITING")
    drawRectangle(width - textWidth - offset, offset, textWidth,
                  rectangleHeight / 2, (1.0, 1.0, 1.0, 1.0))

    # draw Approve, Cancel
    blf.color(font_id, 1.0, 1.0, 1.0, 0.5)  # white 50 trans
    blf.size(font_id, 12, 72)
    extraOffset = 32.0
    blf.position(font_id, width - offset - textWidth,
                 rectangleHeight + offset + extraOffset, 0.0)
    blf.draw(font_id, "CANCEL : RIGHT CLICK")  # MOUSE_RMB
    blf.position(font_id, width - offset - textWidth,
                 rectangleHeight + offset + extraOffset + 16.0, 0.0)
    blf.draw(font_id, "APPROVE : LEFT CLICK")  # MOUSE_LMB


def drawRectangle(x: int, y: int, width: int, height: int, color: tuple[float, float, float, float]):
    vertices = (
        (x, y), (x+width, y),
        (x, y+height), (x+width, y+height))

    indices = (
        (0, 1, 2), (2, 1, 3))

    shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
    batch = batch_for_shader(
        shader, 'TRIS', {"pos": vertices}, indices=indices)

    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def GetLightValuesForDrawingLabels(lightObject: bpy.types.Object, pivotObject: bpy.types.Object):
    lightSize: str = '{0:.2f}'.format(
        GetLightSize(lightObject)) + " m"  # 2 Decimals

    lightDistance: str = '{0:.2f}'.format(
        GetLightDistance(lightObject)) + " m"  # 2 Decimals

    lightBrightness: str = '{0:.2f}'.format(
        GetLightBrightness(lightObject)) + " w"  # 2 Decimals

    lightAngle: str = '{0:.2f}'.format(degrees(
        GetLightAngle(lightObject))) + " °"  # 2 Decimals

    pivot: mathutils.Vector = GetLightPivot(lightObject)
    lightPivot: str = '{0:.1f}'.format(
        pivot.x) + " x " + '{0:.1f}'.format(pivot.y) + " y " + '{0:.1f}'.format(pivot.z) + " z "

    orbit: mathutils.Euler = GetLightOrbit(pivotObject)
    lightOrbit: str = '{0:.1f}'.format(
        degrees(orbit[1])) + " ° " + '{0:.1f}'.format((degrees(orbit[2]) + 180.0) % 360.0) + " °"

    color: mathutils.Color = GetLightColor(lightObject).hsv
    lightColor: str = '{0:.1f}'.format(
        color[0] * 360.0) + " hue " + '{0:.0f}'.format(color[1] * 100.0) + " sat"

    return lightSize, lightDistance, lightBrightness, lightAngle, lightPivot, lightOrbit, lightColor


#################################################################
######################## OPERATORS ##############################
#################################################################


class LIGHTCONTROL_OT_add_light(bpy.types.Operator):
    bl_idname = "lightcontrol.add_light"
    bl_label = "Adds an Area Light"
    bl_options = {'REGISTER', 'UNDO'}

    # Properties
    lightType: bpy.props.EnumProperty(items=[('POINT', 'Point Light', ''), ('AREA', 'Area Light', ''), ('SPOT', 'Spot Light', ''), (
        'SUN', 'Sun Light', '')], name="Light Types", description="Which Light Type should be spawned", default='AREA')
    initialLightDistancePercent: float = 0.45  # range from 0.0 to 1.0

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        # Addon Preferences
        preferences = context.preferences
        addon_prefs = preferences.addons[__name__].preferences
        if self.lightType == 'AREA':
            addon_prefs.areaLightCountSpawned += 1
        elif self.lightType == 'POINT':
            addon_prefs.pointLightCountSpawned += 1
        elif self.lightType == 'SPOT':
            addon_prefs.spotLightCountSpawned += 1
        elif self.lightType == 'SUN':
            addon_prefs.sunLightCountSpawned += 1
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
            print('No Object under Mouse Cursor - Nothing Added')
            self.report(
                {'INFO'}, 'No Object under Mouse Cursor - Nothing Added')
            return {'CANCELLED'}
        # Calculate Light Distance
        pivotPoint = mathutils.Vector(
            (hitlocation[0], hitlocation[1], hitlocation[2]))
        r3d = context.area.spaces.active.region_3d
        cameraPosition: mathutils.Vector = r3d.view_matrix.inverted().translation
        lightDistance: float = (
            cameraPosition - pivotPoint).magnitude * self.initialLightDistancePercent
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
        SetLightBrightnessClamped(lightObject, lightIntensity)
        # Position Light
        PositionLight(lightObject, mathutils.Vector(
            (hitnormal[0], hitnormal[1], hitnormal[2])), lightDistance)
        # Set as selected and active Object
        for obj in context.selected_objects:  # deselect all
            obj.select_set(False)
        lightObject.select_set(True)
        context.view_layer.objects.active = lightObject
        # Set Flag on lightObject so it can be deleted if action canceled
        lightObject['deleteOnCancel'] = True
        # Go into Adjust Light mode
        print("invoke Adjust Light no Params")
        if bpy.ops.lightcontrol.adjust_light.poll():
            # , deleteOnCancelModal = True)
            bpy.ops.lightcontrol.adjust_light('INVOKE_DEFAULT')
        return {'FINISHED'}


class LIGHTCONTROL_MT_add_light_pie_menu(Menu):
    # label is displayed at the center of the pie menu.
    bl_label = "Add Light at Mouse Position"

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
    # grab cursor and blocking activates continous grab
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    # temporary storeage
    pivotObject: bpy.types.Object = None
    activeSpace3D: bpy.types.SpaceView3D = None
    activeRegion3D: bpy.types.RegionView3D = None
    currentLightType = None
    # settings for modal
    zoomSpeedPercent = 0.01
    rotationSpeed = 0.006
    brightnessChangePercent = 0.01
    angleChangeSensitivity = 0.01
    sizeChangeSensitivity = 0.01
    hueChangeSensitivity = 0.0003
    tiltChangeSensitivity = 0.01
    saturationChangeSensitivity = 0.002
    mouseWheelSensitivity = 20.0
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
    changeLightTilt: bool = False
    toggleViewportVisibility: bool = False
    # values for drawing
    lightSize: str = ""
    lightDistance: str = ""
    lightBrightness: str = ""
    lightAngle: str = ""
    lightPivot: str = ""
    lightOrbit: str = ""
    lightColor: str = ""
    lightTilt: str = ""
    # values for reverting
    initialLightOrbit: mathutils.Vector = mathutils.Vector(
        (0.0, 0.0, 0.0))
    initialLightDistance: float = 0.0
    initialLightSize: float = 0.0
    initialLightBrightness: float = 0.0
    initialLightAngle: float = 0.0
    initialLightPivot: mathutils.Vector = mathutils.Vector((0.0, 0.0, 0.0))
    initialLightColor: mathutils.Color = mathutils.Color((0.0, 0.0, 0.0))
    initialLightTilt: mathutils.Vector = mathutils.Vector((0.0, 0.0, 0.0))

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
        # Draw Operator Options
        args = (self, context)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            drawOperationOptions, args, 'WINDOW', 'POST_PIXEL')
        # Set the current active Region3D as Reference
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                self.activeSpace3D = bpy.types.SpaceView3D(area.spaces.active)
                self.activeRegion3D = bpy.types.RegionView3D(
                    area.spaces[0].region_3d)
        # and self.activeSpace3D.show_gizmo
        self.toggleViewportVisibility = self.activeSpace3D.overlay.show_overlays
        # Set light Object as the active object
        lightObject = context.active_object
        # Set current Light Type
        lightObjectData: bpy.types.Light = lightObject.data
        self.currentLightType = lightObjectData.type
        # Initialize Light Values for drawing
        self.lightSize, self.lightDistance, self.lightBrightness, self.lightAngle, self.lightPivot, self.lightOrbit, self.lightColor = GetLightValuesForDrawingLabels(
            lightObject, self.pivotObject)
        # when there is no custom attribute in the object.
        if "pivotPoint" not in lightObject:
            print("pivotPoint property not found => created")
            lightObject["pivotPoint"] = (0, 0, 0)  # create it
        # when there is no custom attribute in the object.
        if GetLightType(lightObject)[0] not in {'AREA', 'SPOT'}:
            if "tilt" not in lightObject:
                print("Tilt property not found => created")
                lightObject["tilt"] = (0, 0, 0)  # create it
        # create pivot
        self.pivotObject = bpy.data.objects.new("temporaryPivot", None)
        self.pivotObject.empty_display_type = 'ARROWS'  # 'SINGLE_ARROW'
        self.pivotObject.location = GetLightPivot(lightObject)
        bpy.context.scene.collection.objects.link(self.pivotObject)
        # size pivot correctly
        cameraPosition: mathutils.Vector = self.activeRegion3D.view_matrix.inverted().translation
        distance: mathutils.Vector = self.pivotObject.location - cameraPosition
        self.pivotObject.empty_display_size = distance.magnitude * self.emptyDisplaySize
        # unrotate and place light
        pivotToLight: mathutils.Vector = lightObject.location - self.pivotObject.location
        if 'tilt' in lightObject:
            lightObject.rotation_euler = (
                0 + lightObject['tilt'][0], pi*0.5 + + lightObject['tilt'][1], 0 + + lightObject['tilt'][2])
        else:
            lightObject.rotation_euler = (0, pi*0.5, 0)  # make -Z look forward
        lightObject.location = mathutils.Vector((pivotToLight.magnitude, 0, 0))
        # set parenting of light and pivot
        lightObject.parent_type = 'OBJECT'
        lightObject.parent = self.pivotObject
        # rotate pivot
        rot = lookAtRotation(pivotToLight, "-x")
        self.pivotObject.rotation_euler = rot
        # Initialize Initial Light Values for Reverting
        self.initialLightOrbit, self.initialLightDistance, self.initialLightSize, self.initialLightBrightness, self.initialLightAngle, self.initialLightPivot, self.initialLightColor = GetLightValues(
            lightObject, self.pivotObject)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        # draw Labels
        context.area.tag_redraw()

        # save the active object
        lightObject: bpy.types.Object = context.active_object

        # Set pivot empty display size based on distance
        cameraPosition: mathutils.Vector = self.activeRegion3D.view_matrix.inverted().translation
        newDistance: mathutils.Vector = self.pivotObject.location - cameraPosition
        self.pivotObject.empty_display_size = newDistance.magnitude * self.emptyDisplaySize

        # Calculate delta for later usage
        mouseWheelDeltaUP = boolToFloat(event.type == 'WHEELUPMOUSE')
        mouseWheelDeltaDOWN = -boolToFloat(event.type == 'WHEELDOWNMOUSE')
        mouseWheelDelta: mathutils.Vector = mathutils.Vector(((mouseWheelDeltaUP +
                                                               mouseWheelDeltaDOWN) * self.mouseWheelSensitivity, 0.0, 0.0))
        delta: mathutils.Vector = mathutils.Vector(
            (event.mouse_x - event.mouse_prev_x, event.mouse_y - event.mouse_prev_y, 0.0))
        delta += mouseWheelDelta

        # Update Labels for Drawing
        self.lightSize, self.lightDistance, self.lightBrightness, self.lightAngle, self.lightPivot, self.lightOrbit, self.lightColor = GetLightValuesForDrawingLabels(
            lightObject, self.pivotObject)

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
        if event.type == 'T':
            self.changeLightTilt = event.value == 'PRESS'
        if event.type in {'SPACE', 'R'}:
            self.changeLightOrbit = event.value == 'PRESS'
        if event.type == 'V':
            if event.value == 'PRESS':
                self.toggleViewportVisibility = not self.toggleViewportVisibility
        self.changeLightPivot = event.type == 'MOUSEMOVE' and event.ctrl

        # Pass through Navigation
        # allow view navigation, and collapsing the panels

        if self.approveOperation:
            # Remove Operation Labels
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            # Unparent
            UnparentAndKeepPositionRemoveParent(self.pivotObject, lightObject)
            # set Light as Active Object
            context.view_layer.objects.active = lightObject
            # delete the Set Light Tag if its there
            if "deleteOnCancel" in lightObject:
                del lightObject['deleteOnCancel']
            print('finished adjusting Light')
            return {'FINISHED'}

        if self.cancelOperation:
            # Remove Operation Labels
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            # Reset Values
            SetLightPivot(lightObject, self.pivotObject,
                          self.initialLightPivot)
            SetLightDistance(lightObject, self.initialLightDistance)
            SetLightOrbit(self.pivotObject, self.initialLightOrbit)
            SetLightSizeClamped(lightObject, self.initialLightSize)
            SetLightBrightnessClamped(lightObject, self.initialLightBrightness)
            SetLightAngle(lightObject, self.initialLightAngle)
            SetLightColor(lightObject, self.initialLightColor)
            # Update Matrices
            context.view_layer.update()
            # Unparent
            UnparentAndKeepPositionRemoveParent(self.pivotObject, lightObject)
            # set Light as Active Object
            context.view_layer.objects.active = lightObject
            # delete light as well if True
            if "deleteOnCancel" in lightObject:
                bpy.data.objects.remove(lightObject, do_unlink=True)
            print('canceled adjusting Light')
            return {'CANCELLED'}

        if event.type in {'MIDDLEMOUSE', 'N'}:
            return {'PASS_THROUGH'}

        elif self.changeLightTilt:
            # break early
            if GetLightType(lightObject)[0] not in {'AREA', 'SPOT'}:
                return {'RUNNING_MODAL'}
            # Multiplication Factor
            rateOfChange: mathutils.Vector = delta * self.tiltChangeSensitivity
            if event.shift:
                rateOfChange *= self.slowChangeSpeedPercent
            rateOfChangeAngleX: float = radians(rateOfChange.x)
            rateOfChangeAngleY: float = radians(rateOfChange.y)
            # Setting Tilt
            tilt = (lightObject.rotation_euler.x + rateOfChangeAngleX,
                    lightObject.rotation_euler.y + rateOfChangeAngleY, lightObject.rotation_euler.z)
            lightObject.rotation_euler = mathutils.Euler(tilt)
            # Update Tilt on Object
            lightObject['tilt'] = (
                lightObject.rotation_euler.x, lightObject.rotation_euler.y - pi*0.5, lightObject.rotation_euler.z)

        elif self.changeLightColor:
            SetLightColorByDelta(
                lightObject, delta, self.hueChangeSensitivity, self.saturationChangeSensitivity)

        elif self.changeLightPivot:
            # RAYCAST
            hitObj, hitLocation, hitNormal, hitIndex, hitDistance = raycastCursor(
                context, mousepos=(event.mouse_region_x, event.mouse_region_y), debug=False)
            if hitObj:
                if event.alt and event.shift:  # rotate Pivot, reflected view vector
                    SetLight_Pivot_Position_Rotation_ByReflection(
                        self.activeRegion3D, lightObject, self.pivotObject, hitLocation, hitNormal)
                    lightObject.rotation_euler = (0, pi*0.5, 0)
                    lightObject['tilt'] = (0.0, 0.0, 0.0)
                elif event.shift:  # only move pivot
                    SetLight_Pivot_ByHit(
                        context, lightObject, self.pivotObject, hitLocation)
                    lightObject.rotation_euler = (0, pi*0.5, 0)
                    lightObject['tilt'] = (0.0, 0.0, 0.0)
                elif event.alt:  # rotate Pivot, normal of Object
                    SetLight_Pivot_Position_Rotation_ByNormal(
                        lightObject, self.pivotObject, hitLocation, hitNormal)
                    lightObject.rotation_euler = (0, pi*0.5, 0)
                    lightObject['tilt'] = (0.0, 0.0, 0.0)
                else:  # move pivot and light object
                    SetLight_Pivot_Position_ByHit(
                        lightObject, self.pivotObject, hitLocation)

        elif self.changeLightAngle:

            if GetLightType(lightObject)[0] not in {'AREA', 'SPOT', 'SUN'}:
                return {'RUNNING_MODAL'}
            SetLightAngleByDelta(
                lightObject, delta, self.angleChangeSensitivity, event.shift, self.slowChangeSpeedPercent)

        elif self.changeLightSize:
            if GetLightType(lightObject)[0] not in {'AREA', 'POINT', 'SPOT'}:
                return {'RUNNING_MODAL'}
            SetLightSizeByDeltaClamped(
                lightObject, delta, self.sizeChangeSensitivity, event.shift, self.slowChangeSpeedPercent)

        elif self.changeLightBrightness:
            SetLightBrightnessByDeltaClamped(
                lightObject, delta, self.brightnessChangePercent, event.shift, self.slowChangeSpeedPercent)

        elif self.changeLightDistance:
            if GetLightType(lightObject)[0] == 'SUN':
                return {'RUNNING_MODAL'}
            SetLightDistanceByDeltaClamped(
                lightObject, delta, self.zoomSpeedPercent, event.shift, self.slowChangeSpeedPercent)

        elif self.changeLightOrbit:
            SetLightOrbitByDelta(self, self.pivotObject, delta,
                                 self.rotationSpeed, event.shift, self.slowChangeSpeedPercent)

        # Set Visibility
        if self.activeSpace3D:
            self.activeSpace3D.overlay.show_overlays = self.toggleViewportVisibility
            # self.activeSpace3D.show_gizmo = self.toggleViewportVisibility

        # TODO : Change Pivot Point Size depending on Distance to Pivot

        return {'RUNNING_MODAL'}


class LIGHTCONTROL_Addon_Preferences(bpy.types.AddonPreferences):
    # this must match the add-on name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __name__

    areaLightCountSpawned: bpy.props.IntProperty(
        name="Spawned Area Lights",
        default=0,
    )
    pointLightCountSpawned: bpy.props.IntProperty(
        name="Spawned Point Lights",
        default=0,
    )
    sunLightCountSpawned: bpy.props.IntProperty(
        name="Spawned Sun Lights",
        default=0,
    )
    spotLightCountSpawned: bpy.props.IntProperty(
        name="Spawned Spot Lights",
        default=0,
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Spawned Area Lights " +
                     str(self.areaLightCountSpawned))
        layout.label(text="Spawned Point Lights " +
                     str(self.pointLightCountSpawned))
        layout.label(text="Spawned Sun Lights " +
                     str(self.sunLightCountSpawned))
        layout.label(text="Spawned Spot Lights " +
                     str(self.spotLightCountSpawned))
        # layout.prop(self, "areaLightCountSpawned")


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
           LIGHTCONTROL_OT_add_light_pie_menu_call, LIGHTCONTROL_OT_adjust_light, LIGHTCONTROL_Addon_Preferences)


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
