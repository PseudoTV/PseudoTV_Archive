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

import xbmc, xbmcgui, xbmcaddon
import subprocess, os
import time, threading
import datetime
import sys, re
import random

from ChannelList import ChannelList
from Globals import *



class ChannelListThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.myOverlay = None
        self.shouldExit = False
        sys.setcheckinterval(25)
        self.chanlist = ChannelList()
        self.chanlist.sleepTime = 0.1


    def log(self, msg, level = xbmc.LOGDEBUG):
        log('ChannelListThread: ' + msg, level)


    def run(self):
        self.log("Starting")
        self.shouldExit = False
        self.chanlist.exitThread = False

        if self.myOverlay == None:
            self.log("Overlay not defined. Exiting.")
            return

        ### TV TIME ### 
        prestageChannels = REAL_SETTINGS.getSetting('PrestageChannels') == "true"
        if prestageChannels:
            for i in range(self.myOverlay.maxChannels):
                if self.shouldExit == True:
                    self.log("Closing thread")
                    return

                self.log("Prestage Channel " + str(i + 1))
                self.chanlist.prestageChannel(i + 1)
        
        self.channelResetSetting = REAL_SETTINGS.getSetting('ChannelResetSetting')
        if self.channelResetSetting == "0":
        ###############
            for i in range(self.myOverlay.maxChannels):
                modified = True

                while modified == True and self.myOverlay.channels[i].isValid and self.myOverlay.channels[i].getTotalDuration() < PREP_CHANNEL_TIME:
                    modified = False

                    if self.shouldExit == True:
                        self.log("Closing thread")
                        return

                    time.sleep(2)
                    curtotal = self.myOverlay.channels[i].getTotalDuration()
                    self.chanlist.appendChannel(i + 1)

                    if self.shouldExit == True:
                        self.log("Closing thread")
                        return

                    time.sleep(2)
                    self.myOverlay.channels[i].setPlaylist(CHANNELS_LOC + "channel_" + str(i + 1) + ".m3u")

                    if self.myOverlay.channels[i].getTotalDuration() > curtotal:
                        modified = True
 
        self.log("All channels up to date.  Exiting thread.")

