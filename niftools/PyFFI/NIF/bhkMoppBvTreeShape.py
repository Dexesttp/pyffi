# --------------------------------------------------------------------------
# NifFormat.bhkMoppBvTreeShape
# Custom functions for bhkMoppBvTreeShape.
# --------------------------------------------------------------------------
# ***** BEGIN LICENSE BLOCK *****
#
# Copyright (c) 2007, NIF File Format Library and Tools.
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
# ***** END LICENCE BLOCK *****
# --------------------------------------------------------------------------

import math # math.ceil

def updateOriginScale(self):
    """Update scale and origin."""
    minx = min([v.x for v in self.shape.data.vertices])
    miny = min([v.y for v in self.shape.data.vertices])
    minz = min([v.z for v in self.shape.data.vertices])
    maxx = max([v.x for v in self.shape.data.vertices])
    maxy = max([v.y for v in self.shape.data.vertices])
    maxz = max([v.z for v in self.shape.data.vertices])
    self.origin.x = minx - 0.1
    self.origin.y = miny - 0.1
    self.origin.z = minz - 0.1
    self.scale = (256*256*254) / (0.2+max([maxx-minx,maxy-miny,maxz-minz]))

def updateMopp(self):
    """Update the MOPP data."""
    
    mopp = [] # the mopp 'assembly' script
    q = 256*256 / self.scale # quantization factor

    # opcodes
    BOUNDX = 0x26    
    BOUNDY = 0x27    
    BOUNDZ = 0x28    
    TESTX = 0x10
    TESTY = 0x11
    TESTZ = 0x12

    # add first crude bounding box checks
    maxx = math.ceil((max([v.x for v in self.shape.data.vertices]) + 0.1 - self.origin.x) / q)
    maxy = math.ceil((max([v.y for v in self.shape.data.vertices]) + 0.1 - self.origin.y) / q)
    maxz = math.ceil((max([v.z for v in self.shape.data.vertices]) + 0.1 - self.origin.z) / q)
    if maxx < 0 or maxy < 0 or maxz < 0: raise ValueError("cannot update mopp tree with invalid origin")
    if maxx > 255 or maxy > 255 or maxz > 255: raise ValueError("cannot update mopp tree with invalid scale")
    mopp.extend([BOUNDZ, 0, maxz])
    mopp.extend([BOUNDY, 0, maxy])
    mopp.extend([BOUNDX, 0, maxx])

    # add a trivial tree
    numtriangles = len(self.shape.data.triangles)
    i = 0x30
    for t in xrange(numtriangles-1):
         mopp.extend([TESTZ, maxz, 0, 1, i])
         i += 1
         if i == 0x50:
             mopp.extend([0x09, 0x20]) # increment triangle offset
             i = 0x30
    mopp.extend([i])

    # delete mopp and replace with new data
    self.moppDataSize = len(mopp)
    self.moppData.updateSize()
    for i, b in enumerate(mopp):
        self.moppData[i] = b

# ported from NifVis/bhkMoppBvTreeShape.py
def parseMopp(self, start = 0, depth = 0, toffset = 0, verbose = False):
    """If verbose is True then the mopp data is printed while parsed. Returns list of indices into mopp data of the bytes processed and a list of triangle indices encountered."""
    mopp = self.moppData # shortcut notation
    ids = [] # indices of bytes processed
    tris = [] # triangle indices
    i = start # current index
    ret = False # set to True if an opcode signals a triangle index
    while i < self.moppDataSize and not ret:
        # get opcode and print it
        code = mopp[i]
        print "%4i:"%i + "  "*depth + '0x%02X'%code,

        if code == 0x09:
            # increment triangle offset
            toffset += mopp[i+1]
            print mopp[i+1], '[ triangle offset += %i, offset is now %i ]'%(mopp[i+1], toffset)
            ids.extend([i,i+1])
            i += 2

        elif code in [ 0x0A ]:
            # increment triangle offset
            toffset += mopp[i+1]*256 + mopp[i+2]
            print mopp[i+1],mopp[i+2], '[ triangle offset += %i, offset is now %i ]'%(mopp[i+1]*256 + mopp[i+2], toffset)
            ids.extend([i,i+1,i+2])
            i += 3

        elif code in [ 0x0B ]:
            # unsure about first two arguments, but the 3rd and 4th set triangle offset
            toffset = 256*mopp[i+3] + mopp[i+4]
            print mopp[i+1],mopp[i+2],mopp[i+3],mopp[i+4], '[ triangle offset = %i ]'%toffset
            ids.extend([i,i+1,i+2,i+3,i+4])
            i += 5

        elif code in xrange(0x30,0x50):
            # triangle compact
            print '[ triangle %i ]'%(code-0x30+toffset)
            ids.append(i)
            tris.append(code-0x30+toffset)
            i += 1
            ret = True

        elif code == 0x50:
            # triangle byte
            print mopp[i+1], '[ triangle %i ]'%(mopp[i+1]+toffset)
            ids.extend([i,i+1])
            tris.append(mopp[i+1]+toffset)
            i += 2
            ret = True

        elif code in [ 0x51 ]:
            # triangle short
            t = mopp[i+1]*256 + mopp[i+2] + toffset
            print mopp[i+1],mopp[i+2], '[ triangle %i ]'%t
            ids.extend([i,i+1,i+2])
            tris.append(t)
            i += 3
            ret = True

        elif code in [ 0x53 ]:
            # triangle short?
            t = mopp[i+3]*256 + mopp[i+4] + toffset
            print mopp[i+1],mopp[i+2],mopp[i+3],mopp[i+4], '[ triangle %i ]'%t
            ids.extend([i,i+1,i+2,i+3,i+4])
            tris.append(t)
            i += 5
            ret = True

        elif code in [ 0x05 ]:
            # byte jump
            print '[ jump -> %i: ]'%(i+2+mopp[i+1])
            ids.extend([i,i+1])
            i += 2+mopp[i+1]

        elif code in [ 0x06 ]:
            # short jump
            jump = mopp[i+1]*256 + mopp[i+2]
            print '[ jump -> %i: ]'%(i+3+jump)
            ids.extend([i,i+1,i+2])
            i += 3+jump

        elif code in [0x10,0x11,0x12, 0x13,0x14,0x15, 0x16,0x17,0x18, 0x19, 0x1A, 0x1C]:
            # compact if-then-else with two arguments
            print mopp[i+1], mopp[i+2],
            if code == 0x10:
                print '[ branch X',
            elif code == 0x11:
                print '[ branch Y',
            elif code == 0x12:
                print '[ branch Z',
            else:
                print '[ branch ?',
            print '-> %i: %i: ]'%(i+4,i+4+mopp[i+3])
            print "     " + "  "*depth + 'if:'
            idssub1, trissub1 = self.parseMopp(start = i+4, depth = depth+1, toffset = toffset, verbose = verbose)
            print "     " + "  "*depth + 'else:'
            idssub2, trissub2 = self.parseMopp(start = i+4+mopp[i+3], depth = depth+1, toffset = toffset, verbose = verbose)
            ids.extend([i,i+1,i+2,i+3])
            ids.extend(idssub1)
            ids.extend(idssub2)
            tris.extend(trissub1)
            tris.extend(trissub2)
            ret = True

        elif code in [0x20,0x21,0x22]:
            # compact if-then-else with one argument
            print mopp[i+1], '[ branch ? -> %i: %i: ]'%(i+3,i+3+mopp[i+2])
            print "     " + "  "*depth + 'if:'
            idssub1, trissub1 = self.parseMopp(start = i+3, depth = depth+1, toffset = toffset, verbose = verbose)
            print "     " + "  "*depth + 'else:'
            idssub2, trissub2 = self.parseMopp(start = i+3+mopp[i+2], depth = depth+1, toffset = toffset, verbose = verbose)
            ids.extend([i,i+1,i+2])
            ids.extend(idssub1)
            ids.extend(idssub2)
            tris.extend(trissub1)
            tris.extend(trissub2)
            ret = True

        elif code in [0x23,0x24,0x25]: # short if x <= a then 1; if x > b then 2;
            jump1 = mopp[i+3] * 256 + mopp[i+4] 
            jump2 = mopp[i+5] * 256 + mopp[i+6]
            print mopp[i+1], mopp[i+2], '[ branch ? -> %i: %i: ]'%(i+7+jump1,i+7+jump2)
            print "     " + "  "*depth + 'if:'
            idssub1, trissub1 = self.parseMopp(start = i+7+jump1, depth = depth+1, toffset = toffset, verbose = verbose)
            print "     " + "  "*depth + 'else:'
            idssub2, trissub2 = self.parseMopp(start = i+7+jump2, depth = depth+1, toffset = toffset, verbose = verbose)
            ids.extend([i,i+1,i+2,i+3,i+4,i+5,i+6])
            ids.extend(idssub1)
            ids.extend(idssub2)
            tris.extend(trissub1)
            tris.extend(trissub2)
            ret = True
        elif code in [0x26,0x27,0x28]:
            print mopp[i+1], mopp[i+2],
            if code == 0x26:
                print '[ bound X ]'
            elif code == 0x27:
                print '[ bound Y ]'
            elif code == 0x28:
                print '[ bound Z ]'
            else:
                print
            ids.extend([i,i+1,i+2])
            i += 3
        elif code in [0x01, 0x02, 0x03, 0x04]:
            print mopp[i+1], mopp[i+2], mopp[i+3], '[ bound XYZ? ]'
            ids.extend([i,i+1,i+2,i+3])
            i += 4
        else:
            print "unknown mopp code 0x%02X"%code
            print "following bytes are"
            extrabytes = [mopp[j] for j in xrange(i+1,min(self.moppDataSize,i+10))]
            extraindex = [j       for j in xrange(i+1,min(self.moppDataSize,i+10))]
            print extrabytes
            for b, j in zip(extrabytes, extraindex):
                if j+b+1 < self.moppDataSize:
                    print "opcode after jump %i is 0x%02X"%(b,mopp[j+b+1]), [mopp[k] for k in xrange(j+b+2,min(self.moppDataSize,j+b+11))]
            raise ValueError("unknown mopp opcode 0x%02X"%code)

    return ids, tris

