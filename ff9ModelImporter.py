bl_info = {
    "name": "Import Final Fantasy 9 models",
    "author": "Chev",
    "version": (0,1),
    "blender": (4,0,0),
    "location": "File > Import > FF9 model (ff9.img)",
    "description": 'Import models from FF9',
    "warning": "",
    "wiki_url": "https://github.com/Chevluh/",
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


#### mesh data

def readMesh(file_object, group):
    polygons, maxIndex, maxUVIndex, maxMaterialIndex = readPolygons(file_object, group)
    vertices = readVertices(file_object, maxIndex+1, group)
    UVs = readUVs(file_object, maxUVIndex+1, group)
    return polygons, vertices, UVs

def readPolygons(file_object, group):
    maxIndex = 0
    maxUVIndex = 0
    maxMaterialIndex = 0
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
        maxMaterialIndex = max(maxMaterialIndex, quad["material"]) 
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
        maxMaterialIndex = max(maxMaterialIndex, tri["material"]) 
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
    return polygons, maxIndex, maxUVIndex, maxMaterialIndex

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

def readModel(file_object, materials, isWeaponDir): #uvOffsets):
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
        buildMesh(polygons, vertices, UVs, armature, f'mesh {i}', materials, isWeaponDir)#uvOffsets)
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

def buildMesh(polygons, vertices, UVs, armature, objectName, materials, isWeaponDir): #:uvOffsets):
    if isWeaponDir:
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
    if materials is not None:
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
    uvOffsets = []
    for i, pointer in enumerate(textureHeader["objectPointers"]):
        file_object.seek(pointer)
        texture, offset = readTIMTexture(file_object, f'image {i}')
        materials.append(makeMaterial(texture))
        uvOffsets.append(offset)
    return materials, uvOffsets

def readTIMTexture(file_object, textureName):
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
    
    #read texture data
    textureLength = readUInt32(file_object)
    textureX = readUInt16(file_object)
    textureY = readUInt16(file_object)
    textureWordWidth = readUInt16(file_object)
    textureHeight = readUInt16(file_object)
    if colorformat == COLOR_PALETTED_4BPP:
        imageData = Read4bppImage(file_object)
    elif colorformat == COLOR_PALETTED_8BPP:
        textureWidth = textureWordWidth*2
        imageData = Read8bppImage(file_object, textureWidth * textureHeight, colorTable)
    elif colorformat == COLOR_RGBA_16BPP:
        textureWidth = textureWordWidth
        imageData = Read16bppImage(file_object, textureWidth * textureHeight)
    else: #elif colorformat == COLOR_RGB_24BPP:
        imageData = Read24bppImage(file_object)

    image = bpy.data.images.new(textureName, textureWidth, textureHeight, alpha = True)
    image.pixels = imageData
    image.file_format = 'PNG'
    image.pack()
    return image, textureY % textureHeight

def Read4bppImage(file_object):
    raise Exception("not implemented")

def Read8bppImage(file_object, pixelCount, palette):
    result = []
    for pixel in range(pixelCount):
        result.extend(palette[readUByte(file_object)])
    return result

def Read16bppImage(file_object, pixelCount):
    result = []
    for pixel in range(pixelCount):
        result.extend(UInt16ToRGBA(readUInt16(file_object)))
    return result

def Read24bppImage(file_object):
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

            textureFiles = []
            collectFiles([modelFile["parent"]["parent"]], FILETYPE_TIM_IMAGE, textureFiles)
            print("texture files count:",len(textureFiles))

            if len(textureFiles) > 0:
                textureHeader = readFileHeader(textureFiles[0], file_object)
                materials, uvOffsets = readTextures(textureHeader, file_object)
            else:
                materials = None

            fileHeader = readFileHeader(modelFile, file_object)

            sceneAnimEnd = -1
            for pointer in fileHeader["objectPointers"]:
                file_object.seek(pointer) #should become a foreach?
                if chosenDirectory == 4 or chosenDirectory == 3:
                    materials = None
                armature = readModel(file_object, materials, chosenDirectory == 8)

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