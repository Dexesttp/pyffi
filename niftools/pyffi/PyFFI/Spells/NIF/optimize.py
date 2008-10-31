"""Spells for optimizing nif files."""

# --------------------------------------------------------------------------
# ***** BEGIN LICENSE BLOCK *****
#
# Copyright (c) 2007-2008, NIF File Format Library and Tools.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#
#    * Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials provided
#      with the distribution.
#
#    * Neither the name of the NIF File Format Library and Tools
#      project nor the names of its contributors may be used to endorse
#      or promote products derived from this software without specific
#      prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# ***** END LICENSE BLOCK *****
# --------------------------------------------------------------------------

from itertools import izip

from PyFFI.Formats.NIF import NifFormat
from PyFFI.Utils import TriStrip
from PyFFI.Spells.NIF import fix_detachhavoktristripsdata

# set flag to overwrite files
__readonly__ = False

# example usage
__examples__ = """* Standard usage:

    python nifoptimize.py /path/to/copy/of/my/nifs

* Optimize, but do not merge NiMaterialProperty blocks:

    python nifoptimize.py --exclude=NiMaterialProperty /path/to/copy/of/my/nifs
"""

def isequalTriGeomData(shape1, shape2):
    """Compare two NiTriShapeData/NiTriStripsData blocks, checks if they
    describe the same geometry.

    @param shape1: A shape.
    @type shape1: L{NifFormat.NiTriBasedGeomData}
    @param shape2: Another shape.
    @type shape2: L{NifFormat.NiTriBasedGeomData}
    @return: C{True} if the shapes are equivalent, C{False} otherwise.
    """
    # check for object identity
    if shape1 is shape2:
        return True

    # check class
    if not isinstance(shape1, shape2.__class__) \
        or not isinstance(shape2, shape1.__class__):
        return False

    # check some trivial things first
    for attribute in (
        "numVertices", "keepFlags", "compressFlags", "hasVertices",
        "numUvSets", "hasNormals", "center", "radius",
        "hasVertexColors", "hasUv", "consistencyFlags"):
        if getattr(shape1, attribute) != getattr(shape2, attribute):
            return False

    # check vertices (this includes uvs, vcols and normals)
    verthashes1 = [hsh for hsh in shape1.getVertexHashGenerator()]
    verthashes2 = [hsh for hsh in shape2.getVertexHashGenerator()]
    for hash1 in verthashes1:
        if not hash1 in verthashes2:
            return False
    for hash2 in verthashes2:
        if not hash2 in verthashes1:
            return False

    # check triangle list
    triangles1 = [tuple(verthashes1[i] for i in tri)
                  for tri in shape1.getTriangles()]
    triangles2 = [tuple(verthashes2[i] for i in tri)
                  for tri in shape2.getTriangles()]
    for tri1 in triangles1:
        if not tri1 in triangles2:
            return False
    for tri2 in triangles2:
        if not tri2 in triangles1:
            return False

    # looks pretty identical!
    return True

def triangulateTriStrips(block):
    """Takes a NiTriStrip block and returns an equivalent NiTriShape block.

    @param block: The block to triangulate.
    @type block: L{NifFormat.NiTriStrips}
    @return: An equivalent L{NifFormat.NiTriShape} block.
    """
    assert(isinstance(block, NifFormat.NiTriStrips))
    # copy the shape (first to NiTriBasedGeom and then to NiTriShape)
    shape = NifFormat.NiTriShape().deepcopy(
        NifFormat.NiTriBasedGeom().deepcopy(block))
    # copy the geometry without strips
    shapedata = NifFormat.NiTriShapeData().deepcopy(
        NifFormat.NiTriBasedGeomData().deepcopy(block.data))
    # update the shape data
    shapedata.setTriangles(block.data.getTriangles())
    # relink the shape data
    shape.data = shapedata
    # and return the result
    return shape

def stripifyTriShape(block):
    """Takes a NiTriShape block and returns an equivalent NiTriStrips block.

    @param block: The block to stripify.
    @type block: L{NifFormat.NiTriShape}
    @return: An equivalent L{NifFormat.NiTriStrips} block.
    """
    assert(isinstance(block, NifFormat.NiTriShape))
    # copy the shape (first to NiTriBasedGeom and then to NiTriStrips)
    strips = NifFormat.NiTriStrips().deepcopy(
        NifFormat.NiTriBasedGeom().deepcopy(block))
    # copy the geometry without triangles
    stripsdata = NifFormat.NiTriStripsData().deepcopy(
        NifFormat.NiTriBasedGeomData().deepcopy(block.data))
    # update the shape data
    stripsdata.setTriangles(block.data.getTriangles())
    # relink the shape data
    strips.data = stripsdata
    # and return the result
    return strips

def optimizeTriBasedGeom(block, striplencutoff = 10.0, stitch = True):
    """Optimize a NiTriStrips or NiTriShape block:
      - remove duplicate vertices
      - stripify if strips are long enough
      - recalculate skin partition
      - recalculate tangent space 

    @param block: The shape block.
    @type block: L{NifFormat.NiTriBasedGeom}
    @param striplencutoff: Minimum average length for strips (below this
        length the block is triangulated).
    @type striplencutoff: float
    @param stitch: Whether to stitch strips or not.
    @type stitch: bool
    @return: An optimized version of the shape.

    @todo: Limit the length of strips (see operation optimization mod for
        Oblivion!)
    """
    print("optimizing block '%s'" % block.name)

    # cover degenerate case
    if block.data.numVertices < 3:
        print "  less than 3 vertices: removing block"
        return None

    data = block.data

    print "  removing duplicate vertices"
    v_map = [0 for i in xrange(data.numVertices)] # maps old index to new index
    v_map_inverse = [] # inverse: map new index to old index
    k_map = {} # maps hash to new vertex index
    index = 0  # new vertex index for next vertex
    for i, vhash in enumerate(data.getVertexHashGenerator()):
        try:
            k = k_map[vhash]
        except KeyError:
            # vertex is new
            k_map[vhash] = index
            v_map[i] = index
            v_map_inverse.append(i)
            index += 1
        else:
            # vertex already exists
            v_map[i] = k
    del k_map

    new_numvertices = index
    print("  (num vertices was %i and is now %i)"
          % (len(v_map), new_numvertices))
    # copy old data
    oldverts = [[v.x, v.y, v.z] for v in data.vertices]
    oldnorms = [[n.x, n.y, n.z] for n in data.normals]
    olduvs   = [[[uv.u, uv.v] for uv in uvset] for uvset in data.uvSets]
    oldvcols = [[c.r, c.g, c.b, c.a] for c in data.vertexColors]
    if block.skinInstance: # for later
        oldweights = block.getVertexWeights()
    # set new data
    data.numVertices = new_numvertices
    if data.hasVertices:
        data.vertices.updateSize()
    if data.hasNormals:
        data.normals.updateSize()
    data.uvSets.updateSize()
    if data.hasVertexColors:
        data.vertexColors.updateSize()
    for i, v in enumerate(data.vertices):
        old_i = v_map_inverse[i]
        v.x = oldverts[old_i][0]
        v.y = oldverts[old_i][1]
        v.z = oldverts[old_i][2]
    for i, n in enumerate(data.normals):
        old_i = v_map_inverse[i]
        n.x = oldnorms[old_i][0]
        n.y = oldnorms[old_i][1]
        n.z = oldnorms[old_i][2]
    for j, uvset in enumerate(data.uvSets):
        for i, uv in enumerate(uvset):
            old_i = v_map_inverse[i]
            uv.u = olduvs[j][old_i][0]
            uv.v = olduvs[j][old_i][1]
    for i, c in enumerate(data.vertexColors):
        old_i = v_map_inverse[i]
        c.r = oldvcols[old_i][0]
        c.g = oldvcols[old_i][1]
        c.b = oldvcols[old_i][2]
        c.a = oldvcols[old_i][3]
    del oldverts
    del oldnorms
    del olduvs
    del oldvcols

    # update vertex indices in strips/triangles
    if isinstance(block, NifFormat.NiTriStrips):
        for strip in data.points:
            for i in xrange(len(strip)):
                strip[i] = v_map[strip[i]]
    elif isinstance(block, NifFormat.NiTriShape):
        for tri in data.triangles:
            tri.v1 = v_map[tri.v1]
            tri.v2 = v_map[tri.v2]
            tri.v3 = v_map[tri.v3]

    # stripify trishape/tristrip
    if isinstance(block, NifFormat.NiTriStrips):
        print "  recalculating strips"
        origlen = sum(i for i in data.stripLengths)
        data.setTriangles(data.getTriangles())
        newlen = sum(i for i in data.stripLengths)
        print "  (strip length was %i and is now %i)" % (origlen, newlen)
    elif isinstance(block, NifFormat.NiTriShape):
        print "  stripifying"
        block = stripifyTriShape(block)
        data = block.data
    # average, weighed towards large strips
    if isinstance(block, NifFormat.NiTriStrips):
        # note: the max(1, ...) is to avoid ZeroDivisionError
        avgstriplen = float(sum(i * i for i in data.stripLengths)) \
            / max(1, sum(i for i in data.stripLengths))
        print "  (average strip length is %f)" % avgstriplen
        if avgstriplen < striplencutoff:
            print("  average strip length less than %f so triangulating"
                  % striplencutoff)
            block = triangulateTriStrips(block)
        elif stitch:
            print("  stitching strips (using %i stitches)"
                  % len(data.getStrips()))
            data.setStrips([TriStrip.stitchStrips(data.getStrips())])

    # update skin data
    if block.skinInstance:
        print "  update skin data vertex mapping"
        skindata = block.skinInstance.data
        newweights = []
        for i in xrange(new_numvertices):
            newweights.append(oldweights[v_map_inverse[i]])
        for bonenum, bonedata in enumerate(skindata.boneList):
            w = []
            for i, weightlist in enumerate(newweights):
                for bonenum_i, weight_i in weightlist:
                    if bonenum == bonenum_i:
                        w.append((i, weight_i))
            bonedata.numVertices = len(w)
            bonedata.vertexWeights.updateSize()
            for j, (i, weight_i) in enumerate(w):
                bonedata.vertexWeights[j].index = i
                bonedata.vertexWeights[j].weight = weight_i

        # update skin partition (only if block already exists)
        block._validateSkin()
        skininst = block.skinInstance
        skinpart = skininst.skinPartition
        if not skinpart:
            skinpart = skininst.data.skinPartition

        if skinpart:
            print "  updating skin partition"
            # use Oblivion settings
            block.updateSkinPartition(
                maxbonesperpartition = 18, maxbonespervertex = 4,
                stripify = True, verbose = 0)

    # update morph data
    for morphctrl in block.getControllers():
        if isinstance(morphctrl, NifFormat.NiGeomMorpherController):
            morphdata = morphctrl.data
            # skip empty morph data
            if not morphdata:
                continue
            # convert morphs
            print("  updating morphs")
            for morph in morphdata.morphs:
                # store a copy of the old vectors
                oldmorphvectors = [(vec.x, vec.y, vec.z)
                                   for vec in morph.vectors]
                for old_i, vec in izip(v_map_inverse, morph.vectors):
                    vec.x = oldmorphvectors[old_i][0]
                    vec.y = oldmorphvectors[old_i][1]
                    vec.z = oldmorphvectors[old_i][2]
                del oldmorphvectors
            # resize matrices
            morphdata.numVertices = new_numvertices
            for morph in morphdata.morphs:
                 morph.arg = morphdata.numVertices # manual argument passing
                 morph.vectors.updateSize()

    # recalculate tangent space (only if the block already exists)
    if block.find(block_name = 'Tangent space (binormal & tangent vectors)',
                  block_type = NifFormat.NiBinaryExtraData):
        print "  recalculating tangent space"
        block.updateTangentSpace()

    return block

# TODO: use fix_texturepath spell instead
def fixTexturePath(block, **args):
    """Fix the texture path. Transforms 0x0a into \\n and 0x0d into \\r.
    This fixes a bug in nifs saved with older versions of nifskope.

    @param block: The block to fix.
    @type block: L{NifFormat.NiSourceTexture}
    """
    if ('\n' in block.fileName) or ('\r' in block.fileName):
        block.fileName = block.fileName.replace('\n', '\\n')
        block.fileName = block.fileName.replace('\r', '\\r')
        print("fixing corrupted file name")
        print("  %s" % block.fileName)

def testRoot(root, **args):
    """Optimize the tree at root. This is the main entry point for the
    nifoptimize script.

    @param root: The root of the tree.
    @type root: L{NifFormat.NiObject}
    """
    # check which blocks to exclude
    exclude = args.get("exclude", [])

    # detach havok tree tristripsdata
    fix_detachhavoktristripsdata.testRoot(root, **args)

    # initialize hash maps
    # (each of these dictionaries maps a block hash to an actual block of
    # the given type)
    sourceTextures = {}
    property_map = {}

    # get list of all blocks
    block_list = [ block for block in root.tree(unique = True) ]

    # fix source texture path
    for block in block_list:
        if isinstance(block, NifFormat.NiSourceTexture) \
            and not "NiSourceTexture" in exclude:
            fixTexturePath(block)

    # clamp corrupted material alpha values
    if not "NiMaterialProperty" in exclude:
        for block in block_list:
            # skip non-material blocks
            if not isinstance(block, NifFormat.NiMaterialProperty):
                continue
            # check if alpha exceeds usual values
            if block.alpha > 1:
                # too large
                print("clamping alpha value (%f -> 1.0) in material %s"
                      % (block.alpha, block.name))
                block.alpha = 1.0
            elif block.alpha < 0:
                # too small
                print("clamping alpha value (%f -> 0.0) in material %s"
                      % (block.alpha, block.name))
                block.alpha = 0.0

    # join duplicate source textures
    print("checking for duplicate source textures")
    if not "NiSourceTexture" in exclude:
        for block in block_list:
            # source texture blocks are children of texturing property blocks
            if not isinstance(block, NifFormat.NiTexturingProperty):
                continue
            # check all textures
            for tex in ("Base", "Dark", "Detail", "Gloss", "Glow"):
                if getattr(block, "has%sTexture" % tex):
                    texdesc = getattr(block, "%sTexture" % tex.lower())
                    # skip empty textures
                    if not texdesc.source:
                        continue
                    hashvalue = texdesc.source.getHash()
                    # try to find a matching source texture
                    try:
                        new_texdesc_source = sourceTextures[hashvalue]
                    # if not, save for future reference
                    except KeyError:
                        sourceTextures[hashvalue] = texdesc.source
                    else:
                        # found a match, so report and reassign
                        if texdesc.source != new_texdesc_source:
                            print("  removing duplicate NiSourceTexture block")
                            texdesc.source = new_texdesc_source

    # joining duplicate properties
    print("checking for duplicate properties")
    for block in block_list:
        # check block type
        if not isinstance(block, NifFormat.NiAVObject):
            continue

        # remove duplicate and empty properties within the list
        proplist = []
        # construct list of unique and non-empty properties
        for prop in block.properties:
            if not(prop is None or prop in proplist):
                proplist.append(prop)
        # update block properties with the list just constructed
        block.numProperties = len(proplist)
        block.properties.updateSize()
        for i, prop in enumerate(proplist):
            block.properties[i] = prop

        # merge properties
        for i, prop in enumerate(block.properties):
            # skip properties that have controllers
            # (the controller data cannot always be reliably checked, see also
            # issue #2106668)
            if prop.controller:
                continue
            # check if the name of the property is relevant
            specialnames = ("envmap2", "envmap", "skin", "hair",
                            "dynalpha", "hidesecret", "lava")
            if (isinstance(prop, NifFormat.NiMaterialProperty)
                and prop.name.lower() in specialnames):
                ignore_strings = False
            else:
                ignore_strings = True
            # calculate property hash
            prop_class_str = prop.__class__.__name__
            hashvalue = (prop_class_str,
                         prop.getHash(ignore_strings = ignore_strings))
            # skip if excluded
            if prop_class_str in exclude:
                continue
            # join duplicate properties
            try:
                new_prop = property_map[hashvalue]
            except KeyError:
                property_map[hashvalue] = prop
            else:
                if new_prop != prop:
                    print("  removing duplicate %s block" % prop_class_str)
                    block.properties[i] = new_prop
                    property_map[hashvalue] = new_prop

    # fix properties in NiTimeController targets
    for block in block_list:
        if isinstance(block, NifFormat.NiTimeController):
            prop = block.target
            if not prop:
                continue
            prop_class_str = prop.__class__.__name__
            hashvalue = (prop_class_str,
                         prop.getHash(ignore_strings = True))
            if hashvalue in property_map:
                block.target = property_map[hashvalue]

    # do not optimize shapes if there is particle data
    # (see MadCat221's metstaff.nif)
    opt_shapes = True
    for block in block_list:
        if isinstance(block, NifFormat.NiPSysMeshEmitter):
            opt_shapes = False

    print("removing duplicate and empty children")
    for block in block_list:
        # skip if we are not optimizing shapes
        if not opt_shapes:
            continue

        # check if it is a NiNode
        if not isinstance(block, NifFormat.NiNode):
            continue

        # remove duplicate and empty children
        childlist = []
        for child in block.children:
            if not(child is None or child in childlist):
                childlist.append(child)
        block.numChildren = len(childlist)
        block.children.updateSize()
        for i, child in enumerate(childlist):
            block.children[i] = child

    print("optimizing geometries")
    # first update list of all blocks
    block_list = [ block for block in root.tree(unique = True) ]
    optimized_geometries = []
    for block in block_list:
        # optimize geometries
        if (isinstance(block, NifFormat.NiTriStrips) \
            and not "NiTriStrips" in exclude) or \
            (isinstance(block, NifFormat.NiTriShape) \
            and not "NiTriShape" in exclude):
            # already optimized? skip!
            if block in optimized_geometries:
                continue
            # optimize
            newblock = optimizeTriBasedGeom(block)
            optimized_geometries.append(block)
            # search for all locations of the block, and replace it
            if not(newblock is block):
                optimized_geometries.append(newblock)
                for otherblock in block_list:
                    if not(block in otherblock.getLinks()):
                        continue
                    if isinstance(otherblock, NifFormat.NiNode):
                        for i, child in enumerate(otherblock.children):
                            if child is block:
                                otherblock.children[i] = newblock
                    elif isinstance(otherblock, NifFormat.NiTimeController):
                        if otherblock.target is block:
                            otherblock.target = newblock
                    elif isinstance(otherblock, NifFormat.NiDefaultAVObjectPalette):
                        for i, avobj in enumerate(otherblock.objs):
                            if avobj.avObject is block:
                                avobj.avObject = newblock
                    elif isinstance(otherblock, NifFormat.bhkCollisionObject):
                        if otherblock.target is block:
                            otherblock.target = newblock
                    else:
                        raise RuntimeError(
                            "don't know how to replace block %s in %s"
                            % (block.__class__.__name__,
                               otherblock.__class__.__name__))

    # merge shape data
    # first update list of all blocks
    block_list = [ block for block in root.tree(unique = True) ]
    # then set up list of unique shape data blocks
    # (actually the NiTriShape/NiTriStrips blocks are stored in the list
    # so we can refer back to their name)
    triShapeDataList = []
    for block in block_list:
        # skip if we are not optimizing shapes
        if not opt_shapes:
            continue

        if isinstance(block, (NifFormat.NiTriShape, NifFormat.NiTriStrips)):
            # check with all shapes that were already exported
            for shape in triShapeDataList:
                if isequalTriGeomData(shape.data, block.data):
                    # match! so merge
                    block.data = shape.data
                    print("  merging shape data of shape %s with shape %s"
                          % (block.name, shape.name))
                    break
            else:
                # no match, so store for future matching
                triShapeDataList.append(block)

