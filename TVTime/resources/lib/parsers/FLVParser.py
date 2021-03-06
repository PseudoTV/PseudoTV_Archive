#   Copyright (C) 2011 Jason Anderson
#
#
# This file is part of PseudoTV.
#
# PseudoTV is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PseudoTV is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PseudoTV.  If not, see <http://www.gnu.org/licenses/>.

import xbmc
import os, struct



class FLVTagHeader:
    def __init__(self):
        self.tagtype = 0
        self.datasize = 0
        self.timestamp = 0
        self.timestampext = 0


    def readHeader(self, thefile):
        try:
            data = struct.unpack('B', thefile.read(1))[0]
            self.tagtype = (data & 0x1F)
            self.datasize = struct.unpack('>H', thefile.read(2))[0]
            data = struct.unpack('>B', thefile.read(1))[0]
            self.datasize = (self.datasize << 8) | data
            self.timestamp = struct.unpack('>H', thefile.read(2))[0]
            data = struct.unpack('>B', thefile.read(1))[0]
            self.timestamp = (self.timestamp << 8) | data
            self.timestampext = struct.unpack('>B', thefile.read(1))[0]
        except:
            self.tagtype = 0
            self.datasize = 0
            self.timestamp = 0
            self.timestampext = 0



class FLVParser:
    def log(self, msg, level = xbmc.LOGDEBUG):
        xbmc.log('FLVParser: ' + msg, level)


    def determineLength(self, filename):
        ### TV TIME ###
        #self.log("determineLength " + filename)
        ###############
        
        try:
            self.File = open(filename, "rb")
        except:
            self.log("Unable to open the file")
            return

        if self.verifyFLV() == False:
            self.log("Not a valid FLV")
            self.File.close()
            return 0

        tagheader = self.findLastVideoTag()

        if tagheader is None:
            self.log("Unable to find a video tag")
            self.File.close()
            return 0

        dur = self.getDurFromTag(tagheader)
        self.File.close()
        ### TV TIME ###
        #self.log("Duration: " + str(dur))
        ###############
        return dur


    def verifyFLV(self):
        data = self.File.read(3)

        if data != 'FLV':
            return False

        return True



    def findLastVideoTag(self):
        self.File.seek(0, 2)
        curloc = self.File.tell()

        while curloc > 0:
            try:
                self.File.seek(-4, 1)
                data = int(struct.unpack('>I', self.File.read(4))[0])
                self.File.seek(-4 - data, 1)
                tag = FLVTagHeader()
                tag.readHeader(self.File)
                self.File.seek(-8, 1)
                self.log("detected tag type " + str(tag.tagtype))
                curloc = self.File.tell()

                if tag.tagtype == 9:
                    return tag
            except:
                self.log('Exception in findLastVideoTag')
                return None

        return None


    def getDurFromTag(self, tag):
        tottime = tag.timestamp | (tag.timestampext << 24)
        tottime = int(tottime / 1000)
        return tottime
