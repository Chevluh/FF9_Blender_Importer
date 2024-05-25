bl_info = {
    "name": "Import Final Fantasy 9 models",
    "author": "Chev",
    "version": (0,2),
    "blender": (4,0,0),
    "location": "File > Import > FF9 model (ff9.img)",
    "description": 'Import models from FF9',
    "warning": "",
    "wiki_url": "https://github.com/Chevluh/FF9_Blender_Importer/",
    "category": "Import-Export"
}

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from mathutils import *
import time
import os # for path stuff
import math 

from bpy.props import CollectionProperty #for multiple files
from bpy.types import OperatorFileListElement

try: 
    import struct
except: 
    struct = None

###


SECTORSIZE = 2048

DBCHUNK = 0xDB

DIRTYPE_NORMAL = 0x02
DIRTYPE_HIERARCHICAL = 0x03
DIRTYPE_ENDMARKER = 0x04

FILETYPE_MODEL = 0x02
FILETYPE_ANIM = 0x03
FILETYPE_TIM_IMAGE = 0x04
FILETYPE_SCRIPT = 0x05
FILETYPE_TEXT = 0x06 # 0x06 is text (for dialogs etc), one byte per char with one special char 
FILETYPE_SEQUENCER = 0x07 # 0x07 is sequencer data, in other words: music
FILETYPE_AUDIO = 0x09
FILETYPE_ENEMY_STATS = 0x010 #stats for enemies (ie. name, hp/mp, weaknesses, names of attacks etc)
FILETYPE_FIELD_TILES = 0x0A
FILETYPE_FIELD_WALKMESH = 0x0B
FILETYPE_FIELD_BATTLESCENE = 0x0C
FILETYPE_CLUT_AND_TPAGES_FOR_MODEL = 0x12
FILETYPE_DATABLOCK = 0x1B #a datablock contains files


SCALE_FACTOR = 1/256

#00  4-bit (color indices)
COLOR_PALETTED_4BPP=0
#01  8-bit (color indices)
COLOR_PALETTED_8BPP=1
#10  16-bit (actual colors)
COLOR_RGBA_16BPP=2
#11  24-bit (actual colors)
COLOR_RGB_24BPP=3

MIN_BONE_LENGTH = 0.1

RECT_X = 0
RECT_Y = 1
RECT_WIDTH = 2
RECT_HEIGHT = 3

# https://docs.python.org/3/library/struct.html
# < little endian, i integer. B would be unsigned char (ie ubyte in c#), ? would be C99 1-byte bool

def readInt32(file_object):
    return struct.unpack("<i", file_object.read(4))[0] 

def readUInt32(file_object):
    return struct.unpack("<I", file_object.read(4))[0]

def readUByte(file_object):
    return struct.unpack("<B", file_object.read(1))[0]
    
def readUInt16(file_object):
    return struct.unpack("<H", file_object.read(2))[0]

def readInt16(file_object):
    return struct.unpack("<h", file_object.read(2))[0]

def readUBytes(file_object, count):
    xs = bytearray()
    for i in range(count):
        xs.append(readUByte(file_object))
    return xs

def readUInt24(file_object):
    byte0 = readUByte(file_object)
    byte1 = readUByte(file_object)
    byte2 = readUByte(file_object)
    return byte0 * 65536 + byte1 * 256 + byte2


#### material data

def readMats(header, file_object):
    mats =[]
    for i, pointer in enumerate(header["objectPointers"]):
        file_object.seek(pointer)
        mats.append(readModelMaterials(file_object))
    return mats

def readModelMaterials(file_object):
    tag = readUByte(file_object) #always DC
    modelCount = readUByte(file_object)
    padding = readUInt16(file_object)

    print("model material data count:", modelCount)
    models = []
    for i in range(0, modelCount):
        startposition = file_object.tell()
        info = dict()
        info["mesh_id"] = readUInt16(file_object)               # 0x02 file id - mesh
        info["default_animation_id"] = readUInt16(file_object)  # 0x03 file id - animation ( this value can be -1, it means that there is no default animation )
        temp = readUInt32(file_object)
        info["materials_count"] = temp >> 24 #readUByte(file_object)        # materials count
        info["materials_pointer"] = startposition + (temp & 0xFFFFFF) #readUInt24(file_object)     # pointer to materials array ( calculated from begining of structure )
        info["id_0x19"] = readUInt16(file_object)               # 0x19 file id - ??? ( can be -1 )
        info["unknown1"] = readUByte(file_object)               # possibly id of some file
        info["unknown2"] = readUByte(file_object)               # unknown ( align to 32 bits? )
        models.append(info)
    for info in models:
        file_object.seek(info["materials_pointer"])
        materials = []
        for i in range (0, info["materials_count"]):
            material = dict()
            material["tpage"], material["texMode"], material["blendMode"] = decodeTPage(readUInt16(file_object))
            material["clut"] = decodeCLUT(readUInt16(file_object))
            materials.append(material)
        for material in materials:
            material["textureWindow"] = (readInt16(file_object), readInt16(file_object))
        for material in materials:
            material["faceEyePositions"] = ((readInt16(file_object), readInt16(file_object)),(readInt16(file_object), readInt16(file_object)))
        info["materials"] = materials
    return models

def decodeTPage(tpage):
    x = tpage & 0b1111
    y = (tpage >>4) & 1
    texmode = (tpage >> 7) & 0b11
    blendMode = (tpage >> 5) & 0b11
    return (x * 64,y * 256), texmode, blendMode

def decodeCLUT(clut):
    x = clut & 0b111111
    y = (clut >>6) & 0b11111111
    return (x * 16, y)
# def decodeWindow(value): #https://psx-spx.consoledev.net/graphicsprocessingunitgpu/#gpu-other-commands
#     maskX =  (value & 0b11111) * 8
#     maskY =  ((value >>5) & 0b11111) * 8
#     offsetX =  ((value >>10) & 0b11111) * 8
#     offsetY =  ((value >>15) & 0b11111) * 8
#     return (offsetX, offsetY)


#### mesh data

def readMesh(file_object, group):
    polygons, maxIndex, maxUVIndex = readPolygons(file_object, group)
    vertices = readVertices(file_object, maxIndex+1, group)
    UVs = readUVs(file_object, maxUVIndex+1, group)
    return polygons, vertices, UVs

def readPolygons(file_object, group):
    maxIndex = 0
    maxUVIndex = 0
    file_object.seek(group["polygonDataPointer"])
    AQuads = []
    for i in range(0, group["typeAQuadrangleCount"]):
        quad = dict()
        quad["vertices"] = (readUInt16(file_object),readUInt16(file_object),readUInt16(file_object),readUInt16(file_object))
        quad["UV"] = (readUInt16(file_object),readUInt16(file_object),readUInt16(file_object),readUInt16(file_object))
        quad["color"] = readUBytes(file_object,3)
        quad["material"] = readUByte(file_object)
        AQuads.append(quad)
        file_object.seek(4, 1)
        maxIndex = max(maxIndex, max(quad["vertices"]))
        maxUVIndex = max(maxUVIndex, max(quad["UV"]))
    ATris = []
    for i in range(0, group["typeATriangleCount"]):
        tri = dict()
        tri["vertices"] = (readUInt16(file_object),readUInt16(file_object),readUInt16(file_object))
        tri["material"] = readUByte(file_object)
        file_object.seek(1, 1)
        tri["color"] = readUBytes(file_object,3)
        file_object.seek(1, 1)
        tri["UV"] = (readUInt16(file_object),readUInt16(file_object),readUInt16(file_object))
        file_object.seek(2, 1)
        ATris.append(tri)
        maxIndex = max(maxIndex, max(tri["vertices"]))
        maxUVIndex = max(maxUVIndex, max(tri["UV"]))
    BQuads = []
    for i in range(0, group["typeBQuadrangleCount"]):
        quad = dict()
        quad["vertices"] = (readUInt16(file_object),readUInt16(file_object),readUInt16(file_object),readUInt16(file_object))
        file_object.seek(24,1)
        BQuads.append(quad)
        maxIndex = max(maxIndex, max(quad["vertices"]))
    BTris = []
    for i in range(0, group["typeBTriangleCount"]):
        tri = dict()
        tri["vertices"] = (readUInt16(file_object),readUInt16(file_object),readUInt16(file_object))
        BTris.append(tri)
        file_object.seek(18, 1);
        maxIndex = max(maxIndex, max(tri["vertices"]))
    CQuads = []
    for i in range(0, group["typeCQuadrangleCount"]):
        quad = dict()
        quad["vertices"] = (readUInt16(file_object),readUInt16(file_object),readUInt16(file_object),readUInt16(file_object))
        file_object.seek(16,1)
        CQuads.append(quad)
        maxIndex = max(maxIndex, max(quad["vertices"]))
    CTris = []
    for i in range(0, group["typeCTriangleCount"]):
        tri = dict()
        tri["vertices"] = (readUInt16(file_object),readUInt16(file_object),readUInt16(file_object))
        CTris.append(tri)
        file_object.seek(14, 1);
        maxIndex = max(maxIndex, max(tri["vertices"]))
    polygons = dict()
    polygons["AQuads"] = AQuads
    polygons["ATris"] = ATris
    polygons["BQuads"] = BQuads
    polygons["BTris"] = BTris
    polygons["CQuads"] = CQuads
    polygons["CTris"] = CTris
    return polygons, maxIndex, maxUVIndex

def readVertices(file_object, count, group):
    file_object.seek(group["VertexDataPointer"])
    vertices = []
    for i in range(0, count):
        vertex = dict()
        vertex["position"] = (readInt16(file_object), readInt16(file_object), readInt16(file_object))
        vertex["boneIndex"] = readUByte(file_object)
        file_object.seek(1,1) #1 unused byte
        vertices.append(vertex)
    return vertices

def readUVs(file_object, count, group):
    file_object.seek(group["textureDataPointer"])
    UVs = []
    for i in range(0, count):
        UV = (readUByte(file_object), readUByte(file_object))
        UVs.append(UV)
    return UVs

def readModel(file_object, materials, chosenDirectory): #uvOffsets):
    startAddress = file_object.tell() #filePointer["address"]
    #file_object.seek(startAddress)
    zeroes = readUInt16(file_object)
    boneCount = readUByte(file_object)

    groupCount = readUByte(file_object)
    dataSize = readUInt16(file_object)
    xOffset = readInt16(file_object)
    yOffset = readInt16(file_object)
    zOffset = readInt16(file_object)
    bonesPointer = readUInt32(file_object) + startAddress
    current2 = file_object.tell()
    groupsPointer = readUInt32(file_object) + startAddress
    if file_object.tell() != bonesPointer:
        raise Exception("bone pointer error")
    bones = []
    for i in range(0, boneCount):
        bone = dict()
        byte0 = readUByte(file_object)
        byte1 = readUByte(file_object)
        byte2 = readUByte(file_object)
        bone["length"] = byte2 * 65536 + byte1 * 256 + byte0
        bone["parentBoneIndex"] = readUByte(file_object)
        bones.append(bone)
    if file_object.tell() != groupsPointer:
        raise Exception("group pointer error")
    groups =[]
    for i in range(0, groupCount):
        group = dict()
        group["datasize"] = readUInt16(file_object)
        group["typeAQuadrangleCount"] = readUInt16(file_object)
        group["typeATriangleCount"] = readUInt16(file_object)
        group["typeBQuadrangleCount"] = readUInt16(file_object)
        group["typeBTriangleCount"] = readUInt16(file_object)
        group["typeCQuadrangleCount"] = readUInt16(file_object)
        group["typeCTriangleCount"] = readUInt16(file_object)
            
        group["xOffset"] = readInt16(file_object)
        group["yOffset"] = readInt16(file_object)
        group["zOffset"] = readInt16(file_object)

        group["BoneDataPointer"] = readUInt32(file_object) + startAddress;
        group["VertexDataPointer"] = readUInt32(file_object) + startAddress;
        group["polygonDataPointer"] = readUInt32(file_object) + startAddress;
        group["textureDataPointer"] = readUInt32(file_object) + startAddress;
        group["endPointer"] = readUInt32(file_object) + startAddress;
        groups.append(group)
    
    #build armature and a mesh for each group
    armature = buildArmature(bones, 'Armature')
    groupLengths = dict()
    for i, group in enumerate(groups):
        polygons, vertices, UVs = readMesh(file_object, group)
        buildMesh(polygons, vertices, UVs, armature, f'mesh {i}', materials, chosenDirectory)#uvOffsets)
        getGroupLengths(groupLengths, vertices)
    adjustBoneLengths(armature, groupLengths)
    poseArmature(armature, bones)
    return armature

#### blender mesh and armature building

def getGroupLengths(lengths, vertices):
    for vertex in vertices:
        if vertex["boneIndex"] not in lengths:
            lengths[vertex["boneIndex"]] = vertex["position"][2] * SCALE_FACTOR
        else:
            lengths[vertex["boneIndex"]] = max(lengths[vertex["boneIndex"]], vertex["position"][2] * SCALE_FACTOR)

def buildArmature(bones, name):
    #adds empty skeleton
    armature = bpy.data.armatures.new(name)
    armatureObject = bpy.data.objects.new(name, armature)
    bpy.context.scene.collection.objects.link(armatureObject)
    
    armatureObject.show_in_front = True
    armatureObject.display_type ='WIRE'

    #move to edit mode
    bpy.context.window.view_layer.objects.active = armatureObject
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    edit_bones = armatureObject.data.edit_bones
    #for each object, create a bone
    #bone length is z position relative to parent)
    for i, boneDescription in enumerate (bones):
        bone = edit_bones.new(f'bone {i}')
        if i!=0:
            bone.parent = edit_bones[f'bone {boneDescription["parentBoneIndex"]}']
            bone.parent.tail[2] = max(bone.parent.tail[2], boneDescription["length"] * SCALE_FACTOR)
        bone.tail = bone.head + Vector([0,0,MIN_BONE_LENGTH])
    bpy.ops.object.mode_set(mode = 'OBJECT')
    return armatureObject

def poseArmature(armatureObject, bones):
    #set base bone positions
    bpy.ops.object.mode_set(mode='POSE', toggle=False)
    for i, boneDescription in enumerate (bones):
        bone = armatureObject.pose.bones[f'bone {i}']

        bone.location = Vector([0,boneDescription["length"] * SCALE_FACTOR,0])
        bone.keyframe_insert(data_path="location", frame=0)
        #bone.rotation_mode = EULER_ORDER
    bpy.ops.object.mode_set(mode = 'OBJECT')

#leaf bones get their size set relative to affected vertices instead of child bones
def adjustBoneLengths(armatureObject, lengths):
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    for boneIndex in lengths:
        boneName = f'bone {boneIndex}'
        bone = armatureObject.data.edit_bones[boneName]
        if len(bone.children) == 0: #only adjust leaf bones
            bone.tail[2] = max(bone.tail[2], lengths[boneIndex])
    bpy.ops.object.mode_set(mode = 'OBJECT')

def buildMesh(polygons, vertices, UVs, armature, objectName, materials, chosenDirectory): #:uvOffsets):
    if chosenDirectory == 8:
        offset = -16
    else:
        offset = 0
    positions = []
    faces = []

    for vertex in vertices:
        positions.append(vertex["position"])
    for polygon in polygons["AQuads"]:
        faces.append((polygon["vertices"][0], polygon["vertices"][2], polygon["vertices"][3] ,polygon["vertices"][1]))
    for polygon in polygons["ATris"]:
        faces.append((polygon["vertices"][0], polygon["vertices"][2], polygon["vertices"][1]))
    for polygon in polygons["BQuads"]:
        faces.append((polygon["vertices"][0], polygon["vertices"][2], polygon["vertices"][3] ,polygon["vertices"][1]))
    for polygon in polygons["BTris"]:
        faces.append((polygon["vertices"][0], polygon["vertices"][2], polygon["vertices"][1]))
    for polygon in polygons["CQuads"]:
        faces.append((polygon["vertices"][0], polygon["vertices"][2], polygon["vertices"][3] ,polygon["vertices"][1]))
    for polygon in polygons["CTris"]:
        faces.append((polygon["vertices"][0], polygon["vertices"][2], polygon["vertices"][1]))

    mesh = bpy.data.meshes.new(objectName)
    mesh.from_pydata(positions, [], faces)#faces) #(x y z) vertices, (1 2) edges, (variable index count) faces 

    #TODO: if directory is 3 or 4, iterate through all UVs for each material and find min/max UVs, then crop the material's texture image (to closest multiple of 8)

    if materials is not None:

        #then resize UVs
        textureDimensions =[]
        for material in materials:
            image = material.node_tree.nodes["Image Texture"].image
            textureDimensions.append((image.size[0], image.size[1]))
            mesh.materials.append(material)
        scaledUVs = []
        materialIDs =[]
        for polygon in polygons["AQuads"]:
            dimensions = textureDimensions[polygon["material"]]
            #offset = uvOffsets[polygon["material"]]
            UV0 = (UVs[polygon["UV"][0]][0] / dimensions[0], (UVs[polygon["UV"][0]][1]-offset )/ dimensions[1])
            UV1 = (UVs[polygon["UV"][1]][0] / dimensions[0], (UVs[polygon["UV"][1]][1]-offset )/ dimensions[1])
            UV2 = (UVs[polygon["UV"][2]][0] / dimensions[0], (UVs[polygon["UV"][2]][1]-offset )/ dimensions[1])
            UV3 = (UVs[polygon["UV"][3]][0] / dimensions[0], (UVs[polygon["UV"][3]][1]-offset )/ dimensions[1])
            scaledUVs.extend((UV0, UV2, UV3, UV1))
            materialIDs.append(polygon["material"])
        for polygon in polygons["ATris"]:
            dimensions = textureDimensions[polygon["material"]]
            #offset = uvOffsets[polygon["material"]]
            UV0 = (UVs[polygon["UV"][0]][0] / dimensions[0], (UVs[polygon["UV"][0]][1]-offset) / dimensions[1])
            UV1 = (UVs[polygon["UV"][1]][0] / dimensions[0], (UVs[polygon["UV"][1]][1]-offset) / dimensions[1])
            UV2 = (UVs[polygon["UV"][2]][0] / dimensions[0], (UVs[polygon["UV"][2]][1]-offset) / dimensions[1])
            scaledUVs.extend((UV0, UV2, UV1))
            materialIDs.append(polygon["material"])
        #build UVs from polygons
        #build material IDs
        new_uv = mesh.uv_layers.new(name = 'DefaultUV')
        for loop in mesh.loops:
            new_uv.uv[loop.index].vector = scaledUVs[loop.index]
        for faceIndex, face in enumerate(mesh.polygons):
            face.material_index = materialIDs[faceIndex]

    #add to scene
    object = bpy.data.objects.new(objectName, mesh)
    scene = bpy.context.scene
    scene.collection.objects.link(object)
    object.scale = (SCALE_FACTOR, SCALE_FACTOR, SCALE_FACTOR)

    groups = dict()
    for i, vertex in enumerate(vertices):
        if vertex["boneIndex"] not in groups:
            groups[vertex["boneIndex"]] = []
        groups[vertex["boneIndex"]].append(i)
    for i in groups:
        vertexGroup = object.vertex_groups.new(name=f'bone {i}')
        vertexGroup.add(groups[i], 1.0, 'ADD')

    #parent mesh to armature
    object.parent = armature
    modifier = object.modifiers.new("Armature", 'ARMATURE')
    modifier.object = armature

#### animations

def readAnimations(animationHeader, armature, file_object):
    bpy.ops.object.mode_set(mode='POSE', toggle=False)
    animStart = 1
    for pointer in animationHeader["objectPointers"]:
        #no idea how to match the right animations, so we just try everything and ignore the ones that produce errors
        try:
            file_object.seek(pointer)
            startAddress = file_object.tell()
            zeroes = readUInt16(file_object)
            if zeroes != 0:
                raise Exception("invalid file header!!")
            frameCount = readUInt16(file_object)

            #this is actually positions
            X = readUInt16(file_object)
            Y = readUInt16(file_object)
            Z = readUInt16(file_object)
            mask = readUInt16(file_object)
            if mask > 7:
                raise Exception("invalid mask")

            highAnglesPointer = readUInt32(file_object)
            lowAnglesPointer = readUInt32(file_object)
            getPositions(armature, animStart, frameCount, mask, X, Y, Z, startAddress, file_object)
            getAngles(armature, animStart, frameCount, startAddress, highAnglesPointer, lowAnglesPointer, file_object)
            animStart+= frameCount
        except Exception as e:
          print("An exception occurred, skipping animation")
          print(e)

    bpy.ops.object.mode_set(mode = 'OBJECT')
    return animStart -1

#gets positions for origin
def getPositions(armature, animStart, frameCount, mask, X, Y, Z, startAddress, file_object):
    bone = armature.pose.bones['bone 0']
    for frame in range(0, frameCount):
        bone.location = getPosition(frame, mask, X, Y, Z, startAddress, file_object)
        bone.keyframe_insert(data_path="location", frame= frame+animStart)

def getPosition(frame, mask, X, Y, Z, startAddress, file_object):
    if (mask & 1) != 0: 
        positionX = toSignedInt16(X);
    else:
        file_object.seek(startAddress + X + 2 * frame)
        positionX = readInt16(file_object)
    if (mask & 2) != 0:
        positionY = toSignedInt16(Y);
    else:
        file_object.seek(startAddress + Y + 2 * frame)
        positionY = readInt16(file_object)
    if (mask & 4) != 0:
        positionZ = toSignedInt16(Z);
    else:
        file_object.seek(startAddress + Z + 2 * frame)
        positionZ = readInt16(file_object)
    return Vector([positionX * SCALE_FACTOR, -positionY * SCALE_FACTOR, -positionZ * SCALE_FACTOR])

def getAngles(armature, animStart, frameCount, startAddress, highAnglesPointer, lowAnglesPointer, file_object):
    boneCount = len(armature.pose.bones)
    rootCorrection = Quaternion((1,0,0), 3 * math.pi/2) #half rotate root to match blender's frame of reference 
    for frame in range(0, frameCount):
        for boneIndex in range(0, boneCount):
            bone = armature.pose.bones[f'bone {boneIndex}']
            bone.rotation_quaternion = GetAngle(boneIndex, frame, startAddress, highAnglesPointer, lowAnglesPointer, file_object)
            if boneIndex == 0:
                bone.rotation_quaternion = rootCorrection @ bone.rotation_quaternion
            bone.keyframe_insert(data_path="rotation_quaternion", frame= frame+animStart)

def GetAngle(boneIndex, frame, startAddress, highAnglesPointer, lowAnglesPointer, file_object):
    #high bytes of angles
    file_object.seek(startAddress + highAnglesPointer + boneIndex * 8)
    s1 = readUInt16(file_object)
    s2 = readUInt16(file_object)
    s3 = readUInt16(file_object)
    mask = readUInt16(file_object)
    if mask > 7:
        raise Exception("invalid mask")

    if (mask & 1) != 0:
        yawHigh = (s1 & 0xff) << 4
    else:
        file_object.seek(startAddress + s1 + frame)
        yawHigh = readUByte(file_object) << 4
    if (mask & 2) != 0:
        pitchHigh = (s2 & 0xff) << 4
    else:
        file_object.seek(startAddress + s2 + frame)
        pitchHigh = readUByte(file_object) << 4
    if (mask & 4) != 0:
        rollHigh = (s3 & 0xff) << 4
    else:
        file_object.seek(startAddress + s3 + frame)
        rollHigh = readUByte(file_object) << 4

    #low bytes of angles


    if lowAnglesPointer!=0:
        file_object.seek(startAddress + lowAnglesPointer + boneIndex * 8)
        s1 = readUInt16(file_object)
        s2 = readUInt16(file_object)
        s3 = readUInt16(file_object)
        mask = readUInt16(file_object)
        if mask > 7:
            raise Exception("invalid mask")
        #Invalid on guard, IE I'm not reading the right stuff 

        if (mask & 1) != 0:
            yawLow = s1 & 0x0f;
        else:
            file_object.seek(startAddress + s1 + frame)
            yawLow = readUByte(file_object) & 0x0f
        if (mask & 2) != 0:
            pitchLow = s2 & 0x0f;
        else:
            file_object.seek(startAddress + s2 + frame)
            pitchLow = readUByte(file_object) & 0x0f
        if (mask & 4) != 0: 
            rollLow = s3 & 0x0f;
        else:
            file_object.seek(startAddress + s3 + frame)
            rollLow = readUByte(file_object) & 0x0f
    else:
        yawLow = 0
        pitchLow = 0
        rollLow = 0
    if (yawHigh > 4095 or yawHigh < 0 or pitchHigh > 4095
        or pitchHigh < 0 or rollHigh > 4095 or rollHigh < 0):
        raise Exception("angles error");
    yaw = (yawHigh + yawLow) / 4096.0 * (2.0 * math.pi)
    pitch = (pitchHigh + pitchLow) / 4096.0 * (2.0 * math.pi)
    roll = (rollHigh + rollLow) / 4096.0 * (2.0 * math.pi)

    rotX = Quaternion((1, 0, 0), yaw)
    rotY = Quaternion((0, 0, -1), pitch)
    rotZ = Quaternion((0, 1, 0), roll)
    return rotZ @ rotY @ rotX
    #return Euler((yaw, roll, pitch), 'ZYX').to_quaternion()

def toSignedInt16(value):
    return value-65536 if value & 0x8000 else value      

#### textures and materials

def readTextures(textureHeader, file_object):
    materials = []
    for i, pointer in enumerate(textureHeader["objectPointers"]):
        file_object.seek(pointer)
        texture = timToImage(readTIMTexture(file_object), f'image {i}')
        materials.append(makeMaterial(texture))
    return materials

def readTexturesEx(textureHeader, matInfo, file_object):
    #matinfo has an entry for each model
    #each model has x materials
    #so there's one more level than I think
    allMaterials = dict()
    tims = []
    for i, pointer in enumerate(textureHeader["objectPointers"]):
        file_object.seek(pointer)
        tims.append(readTIMTexture(file_object))
    for modelInfo in matInfo:
        materials =[]
        for i, texInfo in enumerate(modelInfo["materials"]):
            print("texinfo: ", texInfo)
            #iterate through tims to find the ones containing texture and clut
            for tim in tims:
                if (texInfo["tpage"][0] >= tim["TextureRect"][0]
                and texInfo["tpage"][0] < tim["TextureRect"][0] + tim["TextureRect"][2]
                and texInfo["tpage"][1] >= tim["TextureRect"][1]
                and texInfo["tpage"][1] < tim["TextureRect"][1] + tim["TextureRect"][3]):
                    tpage = tim
                    break
            for tim in tims:
                if (texInfo["clut"][0] >= tim["TextureRect"][0]
                and texInfo["clut"][0] < tim["TextureRect"][0] + tim["TextureRect"][2]
                and texInfo["clut"][1] >= tim["TextureRect"][1]
                and texInfo["clut"][1] < tim["TextureRect"][1] + tim["TextureRect"][3]):
                    clut = tim
                    break
            texture = timToImageEx(tpage, clut, texInfo, f'model {modelInfo["mesh_id"]} image {i}')
            materials.append(makeMaterial(texture))
        allMaterials[modelInfo["mesh_id"]] =materials
    return allMaterials #this one will be a dict of list, because it has to handle several models

def readTIMTexture(file_object):
    #read header
    start = startAddress = file_object.tell()
    TIMtag = readUByte(file_object)
    if TIMtag != 0x10:
        raise Exception("Invalid texture!")
    version = readUByte(file_object)
    file_object.seek(2, 1) #skip 2 bytes
    flags = readUInt32(file_object)
    colorformat = flags & 3
    ColorTablePresent = (flags & 8) != 0

    TIM = dict()
    TIM["format"] = colorformat
    #read palettes
    if ColorTablePresent:
        colorTableLength = readUInt32(file_object)
        colorTableX = readUInt16(file_object) #x,y,width, height are in 16-bit pixels
        colorTableY = readUInt16(file_object)
        colorTableWidth = readUInt16(file_object)
        colorTableHeight = readUInt16(file_object)
        tablelength = colorTableHeight * colorTableWidth
        colorTable = []
        for i in range(0, tablelength):
            colorTable.append(UInt16ToRGBA(readUInt16(file_object)))
        print("colorTableX:" , colorTableX)
        print("colorTableY:" , colorTableY)
        print("colorTableWidth:" , colorTableWidth)
        print("colorTableHeight:" , colorTableHeight)
        TIM["ColorTableRect"] = (colorTableX, colorTableY, colorTableWidth, colorTableHeight)
        TIM["ColorTable"] = colorTable
    #read texture data
    textureLength = readUInt32(file_object)
    textureX = readUInt16(file_object)
    textureY = readUInt16(file_object)
    textureWordWidth = readUInt16(file_object)
    textureHeight = readUInt16(file_object)
    
    print("textureX:" , textureX)
    print("textureY:" , textureY)
    print("textureWordWidth:" , textureWordWidth)
    print("textureHeight:" , textureHeight)
    print("")
    TIM["TextureRect"] = (textureX, textureY, textureWordWidth, textureHeight)

    #read array of Uint16
    data = []
    for i in range (0, textureWordWidth * textureHeight):
        data.append(readUInt16(file_object))
    TIM["TextureData"] = data
    return TIM

def timToImage(TIM, textureName):
    if TIM["format"] == COLOR_PALETTED_4BPP:
        textureWidth = TIM["TextureRect"][RECT_WIDTH]*4
        imageData = Read4bppImage(TIM["TextureData"])
    elif TIM["format"] == COLOR_PALETTED_8BPP:
        textureWidth = TIM["TextureRect"][RECT_WIDTH]*2
        imageData = Read8bppImage(TIM["TextureData"], TIM["ColorTable"])
    elif TIM["format"] == COLOR_RGBA_16BPP:
        textureWidth = TIM["TextureRect"][RECT_WIDTH]
        imageData = Read16bppImage(TIM["TextureData"])
    else: #elif TIM["format"] == COLOR_RGB_24BPP:
        imageData = Read24bppImage(TIM["TextureData"])

    image = bpy.data.images.new(textureName, textureWidth, TIM["TextureRect"][RECT_HEIGHT], alpha = True)
    image.pixels = imageData
    image.file_format = 'PNG'
    image.pack()
    return image

def timToImageEx(tim, clut, info, textureName):

    #build palette
    #clut is a full tim image, need to get the raw palette line from it
    if info["texMode"] == COLOR_PALETTED_4BPP:
        clutLength = 16
    else:
        clutLength = 256
    print(clut)
    palette = []
    clutorigin =  (info["clut"][1] -clut["TextureRect"][RECT_Y]) * clut["TextureRect"][RECT_WIDTH] + info["clut"][0] -clut["TextureRect"][RECT_X]
    for i in range(clutLength):
        palette.append(UInt16ToRGBA(clut["TextureData"][clutorigin +i]))

    pageWidth = tim["TextureRect"][RECT_WIDTH] #<< info["texMode"] # this is how far from tpage start we're allowed to look ahead horizontally. Always 256 vertically
    pageHeight = tim["TextureRect"][RECT_HEIGHT] #256

    x = info["textureWindow"][0]
    x = (x  >> (2-info["texMode"])) + info["tpage"][0] - tim["TextureRect"][0] #now in vram size, from start of tpage

    y = info["textureWindow"][1] + info["tpage"][1] - tim["TextureRect"][1]

    imagePixels =[]
    print (pageWidth, pageHeight)
    print (pageWidth * pageHeight, len(tim["TextureData"]))
    print(info)
    for pixelY in range (0, pageHeight):
        for pixelX in range(0, pageWidth):
            pixel = tim["TextureData"][((pageHeight + pixelY+y)%pageHeight) * tim["TextureRect"][RECT_WIDTH] + ((pageWidth+ pixelX+x)%pageWidth)]
            if info["texMode"] == COLOR_PALETTED_4BPP:
                imagePixels.extend(palette[pixel & 0xF])
                imagePixels.extend(palette[(pixel >> 4) & 0xF])
                imagePixels.extend(palette[(pixel >> 8) & 0xF])
                imagePixels.extend(palette[(pixel >> 12) & 0xF])
            elif info["texMode"] == COLOR_PALETTED_8BPP:
                imagePixels.extend(palette[pixel & 0xFF])
                imagePixels.extend(palette[(pixel >> 8) & 0xFF])
            elif info["texMode"] == COLOR_RGBA_16BPP:
                imagePixels.extend(UInt16ToRGBA(pixel))
            else:
                raise Exception("invalid color format")

    image = bpy.data.images.new(textureName, pageWidth * (1 << (2-info["texMode"])), pageHeight, alpha = True)
    image.pixels = imagePixels
    image.file_format = 'PNG'
    image.pack()
    return image

def Read4bppImage(data):
    raise Exception("not implemented")

def Read8bppImage(data, palette):
    result = []
    for pixel in data:
        result.extend(palette[pixel & 0xFF])
        result.extend(palette[(pixel >> 8) & 0xFF])
    return result

def Read16bppImage(data):
    result = []
    for pixel in data:
        result.extend(UInt16ToRGBA(pixel))
    return result

def Read24bppImage(data):
    raise Exception("not implemented")   
            

def UInt16ToRGBA(colorword):
    red = (colorword & 31) / 31.0
    green = ((colorword >> 5) & 31) / 31.0
    blue = ((colorword >> 10) & 31) / 31.0
    STP = (colorword & 32768) != 0 #Special Transparency Processing
    alpha = 1
    if (red == 0 and blue == 0 and green == 0 and STP == False):
        alpha = 0
    return (red, green, blue, alpha)

def makeMaterial(texture):
    #simple texture with transparency and nearest neighbor filtering
    mat = bpy.data.materials.new(texture.name)
    mat.use_nodes = True
    mat.use_backface_culling = True
    nodes = mat.node_tree.nodes
    nodes.remove(nodes["Principled BSDF"])
    textureNode=nodes.new("ShaderNodeTexImage")
    textureNode.image = texture
    textureNode.interpolation = 'Closest'
    transparentNode =nodes.new("ShaderNodeBsdfTransparent")
    mixNode =nodes.new("ShaderNodeMixShader")
    mat.node_tree.links.new(mixNode.inputs[0], textureNode.outputs[1]) #texture alpha as factor
    mat.node_tree.links.new(mixNode.inputs[1], transparentNode.outputs[0])
    mat.node_tree.links.new(mixNode.inputs[2], textureNode.outputs[0])
    mat.node_tree.links.new(nodes['Material Output'].inputs[0], mixNode.outputs[0])
    mat.blend_method = 'CLIP'
    mat.alpha_threshold = 0.999
    mat.shadow_method = 'CLIP'
    return mat

#### file system

def readDataBlockHeader(file_object):
    header = dict()
    header["fileCount"] = readUByte(file_object)
    header["zero"] = readUInt16(file_object)
    if header["zero"] !=0:
        raise Exception("db header error")
    header["pointers"] = []
    header["childChunks"] = []
    for i in range(0, header["fileCount"]):
        #read db pointer
        pointer = dict()
        baseAddress = file_object.tell()
        byte0 = readUByte(file_object)
        byte1 = readUByte(file_object)
        byte2 = readUByte(file_object)
        pointer["address"] = byte2 * 65536 + byte1 * 256 + byte0 + baseAddress
        pointer["type"] = readUByte(file_object)
        header["pointers"].append(pointer)
    for pointer in header["pointers"]:
        if pointer["type"] == FILETYPE_DATABLOCK:
            #file_object.seek(pointer["address"]) #seek is done inside
            fileheader = readFileHeader(pointer, file_object)
            for datapointer in fileheader["objectPointers"]:
                file_object.seek(datapointer)
                DBmarker = readUByte(file_object)
                if DBmarker != DBCHUNK:
                    raise Exception("not a datablock")
                DBheader = readDataBlockHeader(file_object)
                DBheader["parent"] = header
                header["childChunks"].append(DBheader)
    return header

def collectFiles(dataBlocks, fileType, fileCollection):
    for block in dataBlocks:
        for pointer in block["pointers"]:
            if pointer["type"] == fileType:
                fileCollection.append(pointer)
                pointer["parent"] = block
        collectFiles(block["childChunks"], fileType, fileCollection)

def readFileHeader(filePointer, file_object):
    startAddress = filePointer["address"]
    file_object.seek(startAddress)

    #read header
    DBmark = readUByte(file_object)
    objectCount = readUByte(file_object)
    zero = readUInt16(file_object)
    if zero != 0:
         raise Exception("invalid file header!!")
    #read the IDs
    objectIdentifiers = []
    for i in range(0, objectCount):
        objectIdentifiers.append(readUInt16(file_object))

    #IDs are 4 bytes aligned, so skip two bytes if odd count
    if objectCount % 2 !=0:
        file_object.seek(2, 1) #1: seek relative to position
    #read the object pointers
    objectPointers = [];
    for i in range(0, objectCount):
        baseaddress = file_object.tell()
        objectPointers.append(baseaddress + readInt32(file_object))
    endOfFile = file_object.tell() + readUInt32(file_object)
    header = dict()
    header["objectCount"] = objectCount
    header["objectIdentifiers"] = objectIdentifiers
    header["objectPointers"] = objectPointers

    return header

def readIndex(file_object):
    index = dict() #aka root directory
    index["header"] = readUBytes(file_object, 4)
    index["unknown1"] = readUInt32(file_object)
    index["directoryCount"] = readUInt32(file_object)
    index["unknown2"] = readUInt32(file_object)
    index["directories"] = []
    for i in range(0, index["directoryCount"]):
        directory = dict()
        directory["type"] = readUInt32(file_object)
        directory["fileCount"] = readUInt32(file_object)
        directory["startSector"] = readUInt32(file_object) #directory information sector
        directory["sectorOfFirstFile"] = readUInt32(file_object)
        index["directories"].append(directory)
    return index

def ImportModel(archiveFile, chosenDirectory = None, chosenModel = None):
    with open(archiveFile, "rb") as file_object:
        index = readIndex(file_object)
        print("index read")

        ## directory should be chosen at this stage


        dir = index["directories"][chosenDirectory]
        file_object.seek(dir["startSector"] * SECTORSIZE)
        #read files in the directory root
        pointers = []
        for i in range(0, dir["fileCount"]):
            filePointer = dict()
            filePointer["id"] = readUInt16(file_object)
            filePointer["type"] = readUInt16(file_object)
            filePointer["FirstSectorOfFile"] = readUInt32(file_object)
            pointers.append(filePointer)

        print("pointers read")
        #then load the file headers or subdirectories
        if dir["type"] == DIRTYPE_NORMAL: #only if type 2
            dataBlocks = []
            for pointer in pointers:
                file_object.seek(pointer["FirstSectorOfFile"] * SECTORSIZE)
                fileType = readUByte(file_object)
                if fileType == DBCHUNK:
                    #read db chunk header
                    header = readDataBlockHeader(file_object)
                    dataBlocks.append(header)
                #else:
                #    #other sort of file

            modelfiles = []
            collectFiles(dataBlocks, FILETYPE_MODEL, modelfiles)
            print("model files count:", len(modelfiles))
            if len(modelfiles) == 0:
                raise Exception("No model files found")

            ##model file index should be chosen at this stage at the latest
            modelFile = modelfiles[chosenModel]

            matFiles = []
            if chosenDirectory == 3 or chosenDirectory == 4:
                collectFiles([modelFile["parent"]], FILETYPE_CLUT_AND_TPAGES_FOR_MODEL, matFiles)
            else:
                collectFiles([modelFile["parent"]["parent"]], FILETYPE_CLUT_AND_TPAGES_FOR_MODEL, matFiles)
            print("model material files count:",len(matFiles))
            if len(matFiles) > 0:
                matHeader = readFileHeader(matFiles[0], file_object)
                matInfo = readMats(matHeader, file_object)
                for mat in matInfo:
                    print(mat)

            textureFiles = []
            collectFiles([modelFile["parent"]["parent"]], FILETYPE_TIM_IMAGE, textureFiles)
            print("texture files count:",len(textureFiles))

            if len(textureFiles) > 0:
                textureHeader = readFileHeader(textureFiles[0], file_object)
                if chosenDirectory == 3 or chosenDirectory == 4:
                    allMaterials = readTexturesEx(textureHeader, matInfo[0], file_object) #this one will be a dict of list, because it has to handle several models
                else:
                    materials = readTextures(textureHeader, file_object)
            else:
                materials = None

            fileHeader = readFileHeader(modelFile, file_object)

            sceneAnimEnd = -1
            for i, pointer in enumerate(fileHeader["objectPointers"]):
                file_object.seek(pointer) #should become a foreach?
                if chosenDirectory == 4 or chosenDirectory == 3:
                    materials = allMaterials[fileHeader["objectIdentifiers"][i]]
                armature = readModel(file_object, materials, chosenDirectory)

                animationFiles =[]
                collectFiles([modelFile["parent"]], FILETYPE_ANIM, animationFiles)
                if len(animationFiles) > 0:
                    print("animation file count:", len(animationFiles))
                    animationHeader = readFileHeader(animationFiles[0], file_object)
                    print(animationHeader)
                    animEnd = readAnimations(animationHeader, armature, file_object)
                    sceneAnimEnd = max(sceneAnimEnd, animEnd)
            if sceneAnimEnd != -1:
                bpy.context.scene.frame_end = sceneAnimEnd
            #scene.frame_set(originalFrame)
        else:
            raise Exception(f'Unsupported directory type: {dir["type"]}')

### import dialog

class MyDialog(bpy.types.Operator):

    bl_idname = "tools.mydialog"
    bl_label = "Import FF9 Model"

    archiveFilePath: bpy.props.StringProperty(name="archiveFilePath", options={'HIDDEN'})

    directory: bpy.props.IntProperty(name="Directory index", max=13, min=0)
    modelIndex: bpy.props.IntProperty(name="Model file index", min=0)

    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        ImportModel(self.archiveFilePath, self.directory, self.modelIndex)
        return {'FINISHED'}

### file picker

class ImportFF9Model(bpy.types.Operator, ImportHelper): 
    bl_idname       = "import_ff9_model.chev";
    bl_label        = "import model";
    bl_options      = {'PRESET'};
    
    filename_ext    = ".img";

    filter_glob: StringProperty(
        default="*",
        options={'HIDDEN'},
        maxlen=255,
    )
    
    def execute(self, context):
        print("importer start")
        then = time.time()

        archiveFilePath = self.filepath
        
        print("importing {0}".format(archiveFilePath))
        
        #ImportModel(archiveFilePath, 10, 4)
        #3,4,7,8, 10
        #overworld, rooms, monsters, weapons, party

        bpy.ops.tools.mydialog('INVOKE_DEFAULT', archiveFilePath = archiveFilePath)

        now = time.time()
        print("It took: {0} seconds".format(now-then))
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(ImportFF9Model.bl_idname, text="FF9 model (ff9.img)");

def register():
    from bpy.utils import register_class
    register_class(ImportFF9Model)
    register_class(MyDialog)
    bpy.types.TOPBAR_MT_file_import.append(menu_func)
    
def unregister():
    from bpy.utils import unregister_class
    unregister_class(ImportFF9Model)
    unregister_class(MyDialog)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func);

if __name__ == "__main__":
    register()