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
import httplib
import base64

### TV TIME ###
import urllib2
from operator import itemgetter
###############


from xml.dom.minidom import parse, parseString

from Playlist import Playlist
from Globals import *
from Channel import Channel
from VideoParser import VideoParser
#from FileLock import FileLock


class ChannelList:
    def __init__(self):
        self.networkList = []
        self.studioList = []
        self.mixedGenreList = []
        self.showGenreList = []
        self.movieGenreList = []
        ### TV TIME ###
        self.musicGenreList = []        
        ###############
        self.showList = []
        self.videoParser = VideoParser()
        #self.fileLock = FileLock()
        self.httpJSON = True
        self.sleepTime = 0
        self.exitThread = False
        self.discoveredWebServer = False
        
        ### TV TIME ###
        limit = REAL_SETTINGS.getSetting("limit")
        if limit == "0":
            self.limit = 50
        elif limit == "1":
            self.limit = 100
        elif limit == "2":
            self.limit = 250
        ###############


    def setupList(self):
        self.channels = []
        self.findMaxChannels()
        self.channelResetSetting = int(REAL_SETTINGS.getSetting("ChannelResetSetting"))
        self.log('Channel Reset Setting is ' + str(self.channelResetSetting))
        self.forceReset = REAL_SETTINGS.getSetting('ForceChannelReset') == "true"
        self.log('Force Reset is ' + str(self.forceReset))
        self.updateDialog = xbmcgui.DialogProgress()
        self.startMode = int(REAL_SETTINGS.getSetting("StartMode"))
        self.log('Start Mode is ' + str(self.startMode))
        ### TV TIME ###
        #self.updateDialog.create("PseudoTV", "Updating channel list")
        self.updateDialog.create("TV TIME", "Updating channel list")

        ###############
        self.updateDialog.update(0, "Updating channel list")

        try:
            self.lastResetTime = int(ADDON_SETTINGS.getSetting("LastResetTime"))
        except:
            self.lastResetTime = 0

        try:
            self.lastExitTime = int(ADDON_SETTINGS.getSetting("LastExitTime"))
        except:
            self.lastExitTime = int(time.time())


        # Go through all channels, create their arrays, and setup the new playlist
        for i in range(self.maxChannels):
            self.updateDialog.update(i * 100 // self.maxChannels, "Updating channel " + str(i + 1), "waiting for file lock")
            self.channels.append(Channel())

            # If the user pressed cancel, stop everything and exit
            if self.updateDialog.iscanceled():
                self.log('Update channels cancelled')
                self.updateDialog.close()
                return None

            # Block until the file is unlocked
            # This also has the affect of removing any stray locks (given, after 15 seconds).
            #self.fileLock.isFileLocked(CHANNELS_LOC + 'channel_' + str(i + 1) + '.m3u', True)
            self.setupChannel(i + 1)

        ### TV TIME ###
        ADDON_SETTINGS.writeSettings()
        ###############
        
        REAL_SETTINGS.setSetting('ForceChannelReset', 'false')
        self.updateDialog.update(100, "Update complete")
        self.updateDialog.close()

        return self.channels


    def log(self, msg, level = xbmc.LOGDEBUG):
        log('ChannelList: ' + msg, level)


    def determineWebServer(self):
        if self.discoveredWebServer:
            return

        self.discoveredWebServer = True
        self.webPort = 8080
        self.webUsername = ''
        self.webPassword = ''
        fle = xbmc.translatePath("special://profile/guisettings.xml")

        try:
            xml = open(fle, "r")
        except:
            self.log("determineWebServer Unable to open the settings file", xbmc.LOGERROR)
            self.httpJSON = False
            return

        try:
            dom = parse(xml)
        except:
            self.log('determineWebServer Unable to parse settings file', xbmc.LOGERROR)
            self.httpJSON = False
            return

        xml.close()

        try:
            plname = dom.getElementsByTagName('webserver')
            self.httpJSON = (plname[0].childNodes[0].nodeValue.lower() == 'true')
            self.log('determineWebServer is ' + str(self.httpJSON))
            
            if self.httpJSON == True:
                plname = dom.getElementsByTagName('webserverport')
                self.webPort = int(plname[0].childNodes[0].nodeValue)
                self.log('determineWebServer port ' + str(self.webPort))
                plname = dom.getElementsByTagName('webserverusername')
                self.webUsername = plname[0].childNodes[0].nodeValue
                self.log('determineWebServer username ' + self.webUsername)
                plname = dom.getElementsByTagName('webserverpassword')
                self.webPassword = plname[0].childNodes[0].nodeValue
                self.log('determineWebServer password is ' + self.webPassword)
        except:
            return


    # Determine the maximum number of channels by opening consecutive
    # playlists until we don't find one
    def findMaxChannels(self):
        self.log('findMaxChannels')
        self.maxChannels = 0

        for i in range(999):
            chtype = 9999
            chsetting1 = ''
            chsetting2 = ''

            try:
                chtype = int(ADDON_SETTINGS.getSetting('Channel_' + str(i + 1) + '_type'))
                chsetting1 = ADDON_SETTINGS.getSetting('Channel_' + str(i + 1) + '_1')
                chsetting2 = ADDON_SETTINGS.getSetting('Channel_' + str(i + 1) + '_2')
            except:
                pass

            ### TV TIME ###
            #if chtype == 0:
            #    if os.path.exists(xbmc.translatePath(chsetting1)):
            #        self.maxChannels = i + 1
            #elif chtype < 7:
            #    if len(chsetting1) > 0:
            #        self.maxChannels = i + 1
            if chtype == 0:
                if os.path.exists(xbmc.translatePath(chsetting1)):
                    self.maxChannels = i + 1
            elif chtype < NUMBER_CHANNEL_TYPES:
                if len(chsetting1) > 0:
                    self.maxChannels = i + 1            
            ###############
        self.log('findMaxChannels return ' + str(self.maxChannels))


    def determineWebServer(self):
        if self.discoveredWebServer:
            return

        self.discoveredWebServer = True
        self.webPort = 8080
        self.webUsername = ''
        self.webPassword = ''
        fle = xbmc.translatePath("special://profile/guisettings.xml")

        try:
            xml = open(fle, "r")
        except:
            self.log("determineWebServer Unable to open the settings file", xbmc.LOGERROR)
            self.httpJSON = False
            return

        try:
            dom = parse(xml)
        except:
            self.log('determineWebServer Unable to parse settings file', xbmc.LOGERROR)
            self.httpJSON = False
            return

        xml.close()

        try:
            plname = dom.getElementsByTagName('webserver')
            self.httpJSON = (plname[0].childNodes[0].nodeValue.lower() == 'true')
            self.log('determineWebServer is ' + str(self.httpJSON))

            if self.httpJSON == True:
                plname = dom.getElementsByTagName('webserverport')
                self.webPort = int(plname[0].childNodes[0].nodeValue)
                self.log('determineWebServer port ' + str(self.webPort))
                plname = dom.getElementsByTagName('webserverusername')
                self.webUsername = plname[0].childNodes[0].nodeValue
                self.log('determineWebServer username ' + self.webUsername)
                plname = dom.getElementsByTagName('webserverpassword')
                self.webPassword = plname[0].childNodes[0].nodeValue
                self.log('determineWebServer password is ' + self.webPassword)
        except:
            return


    # Code for sending JSON through http adapted from code by sffjunkie (forum.xbmc.org/showthread.php?t=92196)
    def sendJSON(self, command):
        self.log('sendJSON')
        data = ''
        usedhttp = False

        self.determineWebServer()
        
        # If there have been problems using the server, just skip the attempt and use executejsonrpc
        if self.httpJSON == True:
            payload = command.encode('utf-8')
            headers = {'Content-Type': 'application/json-rpc; charset=utf-8'}

            if username != '':
                userpass = base64.encodestring('%s:%s' % (username, password))[:-1]
                headers['Authorization'] = 'Basic %s' % userpass

            xbmc_host = '127.0.0.1'
            xbmc_port = 8080

            try:
                conn = httplib.HTTPConnection('127.0.0.1', self.webPort)
                conn.request('POST', '/jsonrpc', payload, headers)
                response = conn.getresponse()

                if response.status == 200:
                    data = response.read()
                    usedhttp = True

                conn.close()
            except:
                pass

        if usedhttp == False:
            self.httpJSON = False
            data = xbmc.executeJSONRPC(command)

        return data


    def setupChannel(self, channel):
        self.log('setupChannel ' + str(channel))
        returnval = False
        createlist = True
        chtype = 9999
        chsetting1 = ''
        chsetting2 = ''
        ### TV TIME ###
        chsetting3 = '' # channel name
        chsetting4 = '' # unwatched
        chsetting5 = '' # no specials
        chsetting6 = '' # resolution
        chsetting7 = '' # setting for num episodes in mixed genre
        chsetting8 = '' # setting for num movies in mixed genre
        chsetting9 = '' # setting for mixed tv show randomizing        
        ###############
        needsreset = False

        try:
            chtype = int(ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_type'))
            chsetting1 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_1')
            chsetting2 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_2')
            ### TV TIME ###
            chsetting3 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_3')
            chsetting4 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_4')
            chsetting5 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_5')
            chsetting6 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_6')
            chsetting7 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_7')
            chsetting8 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_8')
            chsetting9 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_9')            
            ###############
        except:
            pass

        try:
            needsreset = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_changed') == 'True'
        except:
            pass

        if chtype == 9999:
            self.channels[channel - 1].isValid = False
            return False

        # If possible, use an existing playlist
        if os.path.exists(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u'):
            try:
                self.channels[channel - 1].totalTimePlayed = int(ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_time'))

                if self.channels[channel - 1].setPlaylist(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u') == True:
                    self.channels[channel - 1].isValid = True
                    self.channels[channel - 1].fileName = CHANNELS_LOC + 'channel_' + str(channel) + '.m3u'
                    returnval = True

                    # If this channel has been watched for longer than it lasts, reset the channel
                    if self.channelResetSetting == 0 and self.channels[channel - 1].totalTimePlayed < self.channels[channel - 1].getTotalDuration():
                        createlist = self.forceReset

                    if self.channelResetSetting > 0 and self.channelResetSetting < 4:
                        timedif = time.time() - self.lastResetTime

                        if self.channelResetSetting == 1 and timedif < (60 * 60 * 24):
                            createlist = self.forceReset

                        if self.channelResetSetting == 2 and timedif < (60 * 60 * 24 * 7):
                            createlist = self.forceReset

                        if self.channelResetSetting == 3 and timedif < (60 * 60 * 24 * 30):
                            createlist = self.forceReset

                        if timedif < 0:
                            createlist = self.forceReset

                        if createlist:
                            ADDON_SETTINGS.setSetting('LastResetTime', str(int(time.time())))

                    if self.channelResetSetting == 4:
                        createlist = self.forceReset
            except:
                pass

        self.log("createlist = " + str(createlist))
        self.log("needsreset = " + str(needsreset))

        if createlist or needsreset:
            #self.fileLock.lockFile(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u', True)
            self.updateDialog.update((channel - 1) * 100 // self.maxChannels, "Updating channel " + str(channel), "adding videos")
            ### TV TIME ###
            #if self.makeChannelList(channel, chtype, chsetting1, chsetting2) == True:
            #    if self.channels[channel - 1].setPlaylist(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u') == True:
            #        self.channels[channel - 1].totalTimePlayed = 0
            #        self.channels[channel - 1].isValid = True
            #        self.channels[channel - 1].fileName = CHANNELS_LOC + 'channel_' + str(channel) + '.m3u'
            #        returnval = True
            #        ADDON_SETTINGS.setSetting('Channel_' + str(channel) + '_time', '0')
            #        ADDON_SETTINGS.setSetting('Channel_' + str(channel) + '_changed', 'False')
            if self.makeChannelList(channel, chtype, chsetting1, chsetting2, chsetting3, chsetting4, chsetting5, chsetting6, chsetting7, chsetting8, chsetting9) == True:
                self.log(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u')
                self.log("setPlaylist = " + str(self.channels[channel - 1].setPlaylist(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u')))
                if self.channels[channel - 1].setPlaylist(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u') == True:
                    self.channels[channel - 1].totalTimePlayed = 0
                    self.channels[channel - 1].isValid = True
                    self.channels[channel - 1].fileName = CHANNELS_LOC + 'channel_' + str(channel) + '.m3u'
                    returnval = True
                    ADDON_SETTINGS.setSetting('Channel_' + str(channel) + '_time', '0')
                    ADDON_SETTINGS.setSetting('Channel_' + str(channel) + '_changed', 'False')
                    ADDON_SETTINGS.writeSettings()
            else:
                self.log("Unable to make Channel List")
            ###############
            
            #self.fileLock.unlockFile(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u')

        self.updateDialog.update((channel - 1) * 100 // self.maxChannels, "Updating channel " + str(channel), "clearing history")
        self.clearPlaylistHistory(channel)

        if chtype == 6:
            if chsetting2 == str(MODE_SERIAL):
                self.channels[channel - 1].mode = MODE_SERIAL

        ### TV TIME ###
        # Add other chtypes which also have serial mode for which
        # we want to enable the pause feature
        ###############

        # if there is no start mode in the channel mode flags, set it to the default
        if self.channels[channel - 1].mode & MODE_STARTMODES == 0:
            if self.startMode == 0:
                self.channels[channel - 1].mode = MODE_RESUME
            elif self.startMode == 1:
                self.channels[channel - 1].mode = MODE_REALTIME
            elif self.startMode == 2:
                self.channels[channel - 1].mode = MODE_RANDOM

        if self.channels[channel - 1].mode & MODE_ALWAYSPAUSE > 0:
            self.channels[channel - 1].isPaused = True

        if self.channels[channel - 1].mode & MODE_RANDOM > 0:
            self.channels[channel - 1].showTimeOffset = random.randint(0, self.channels[channel - 1].getTotalDuration())

        if self.channels[channel - 1].mode & MODE_REALTIME > 0:
            chantime = 0

            try:
                chantime = int(ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_time'))
            except:
                pass

            timedif = int(time.time()) - self.lastExitTime
            self.channels[channel - 1].totalTimePlayed += timedif

        if self.channels[channel - 1].mode & MODE_RESUME > 0:
            self.channels[channel - 1].showTimeOffset = self.channels[channel - 1].totalTimePlayed
            self.channels[channel - 1].totalTimePlayed = 0

        while self.channels[channel - 1].showTimeOffset > self.channels[channel - 1].getCurrentDuration():
            self.channels[channel - 1].showTimeOffset -= self.channels[channel - 1].getCurrentDuration()
            self.channels[channel - 1].addShowPosition(1)

        ### TV TIME ###
        #self.channels[channel - 1].name = self.getChannelName(chtype, chsetting1)
        self.channels[channel - 1].name = self.uncleanString(chsetting3)
        ###############
        return returnval


    def clearPlaylistHistory(self, channel):
        self.log("clearPlaylistHistory")

        if self.channels[channel - 1].isValid == False:
            self.log("channel not valid, ignoring")
            return

        # if we actually need to clear anything
        #if (self.channels[channel - 1].totalTimePlayed > 60 * 60 * 24) and self.fileLock.lockFile(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u'):
        if (self.channels[channel - 1].totalTimePlayed > 60 * 60 * 24):
            try:
                fle = open(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u', 'w')
            except:
                self.log("clearPlaylistHistory Unable to open the smart playlist", xbmc.LOGERROR)
                #self.fileLock.unlockFile(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u')
                return

            fle.write("#EXTM3U\n")
            tottime = 0
            timeremoved = 0

            for i in range(self.channels[channel - 1].Playlist.size()):
                tottime += self.channels[channel - 1].getItemDuration(i)

                if tottime > (self.channels[channel - 1].totalTimePlayed - (60 * 60 * 24)):
                    tmpstr = str(self.channels[channel - 1].getItemDuration(i)) + ','
                    tmpstr += self.channels[channel - 1].getItemTitle(i) + "//" + self.channels[channel - 1].getItemEpisodeTitle(i) + "//" + self.channels[channel - 1].getItemDescription(i)
                    tmpstr = tmpstr[:600]
                    tmpstr = tmpstr.replace("\\n", " ").replace("\\r", " ").replace("\\\"", "\"")
                    tmpstr = tmpstr + '\n' + self.channels[channel - 1].getItemFilename(i)
                    fle.write("#EXTINF:" + tmpstr + "\n")
                else:
                    timeremoved = tottime

            fle.close()

            if timeremoved > 0:
                self.channels[channel - 1].setPlaylist(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u')

            self.channels[channel - 1].totalTimePlayed -= timeremoved
            #self.fileLock.unlockFile(CHANNELS_LOC + 'channel_' + str(channel) + '.m3u')


    ### TV TIME ###
    """
    def getChannelName(self, chtype, setting1):
        self.log('getChannelName ' + str(chtype))

        if len(setting1) == 0:
            return ''

        if chtype == 0:
            return self.getSmartPlaylistName(setting1)
        elif chtype == 1 or chtype == 2 or chtype == 5 or chtype == 6:
            return setting1
        elif chtype == 3:
            return setting1 + " TV"
        elif chtype == 4:
            return setting1 + " Movies"
        return ''
    """
    def getChannelName(self, chtype, setting1):
        self.log('getChannelName ' + str(chtype))

        if len(setting1) == 0:
            return ''

        if chtype == 0:
            return self.getSmartPlaylistName(setting1)
        else:
            return setting1
            
    ###############

    # Open the smart playlist and read the name out of it...this is the channel name
    def getSmartPlaylistName(self, fle):
        self.log("getSmartPlaylistName " + fle)
        fle = xbmc.translatePath(fle)

        try:
            xml = open(fle, "r")
        except:
            self.log("getSmartPlaylisyName Unable to open the smart playlist " + fle, xbmc.LOGERROR)
            return ''

        try:
            dom = parse(xml)
        except:
            self.log('getSmartPlaylistName Problem parsing playlist ' + fle, xbmc.LOGERROR)
            xml.close()
            return ''

        xml.close()

        try:
            plname = dom.getElementsByTagName('name')
            self.log('getSmartPlaylistName return ' + plname[0].childNodes[0].nodeValue)
            return plname[0].childNodes[0].nodeValue
        except:
            self.log("Unable to get the playlist name.", xbmc.LOGERROR)
            return ''


    # Based on a smart playlist, create a normal playlist that can actually be used by us
    ### TV TIME ###
    """
    def makeChannelList(self, channel, chtype, setting1, setting2, append = False):
        self.log('makeChannelList ' + str(channel))

        if chtype == 0:
            fle = setting1
        else:
            fle = self.makeTypePlaylist(chtype, setting1, setting2)

        fle = xbmc.translatePath(fle)

        if len(fle) == 0:
            self.log('Unable to locate the playlist for channel ' + str(channel), xbmc.LOGERROR)
            return False

        try:
            xml = open(fle, "r")
        except:
            self.log("makeChannelList Unable to open the smart playlist " + fle, xbmc.LOGERROR)
            return False

        try:
            dom = parse(xml)
        except:
            self.log('makeChannelList Problem parsing playlist ' + fle, xbmc.LOGERROR)
            xml.close()
            return False

        xml.close()

        if self.getSmartPlaylistType(dom) == 'mixed':
            fileList = self.buildMixedFileList(dom)
        else:
            fileList = self.buildFileList(fle)

        try:
            if append == True:
                channelplaylist = open(CHANNELS_LOC + "channel_" + str(channel) + ".m3u", "r+")
                channelplaylist.seek(0, 2)
            else:
                channelplaylist = open(CHANNELS_LOC + "channel_" + str(channel) + ".m3u", "w")
        except:
            self.log('Unable to open the cache file ' + CHANNELS_LOC + 'channel_' + str(channel) + '.m3u', xbmc.LOGERROR)
            return False

        if append == False:
            channelplaylist.write("#EXTM3U\n")

        if len(fileList) == 0:
            self.log("Unable to get information about channel " + str(channel), xbmc.LOGERROR)
            channelplaylist.close()
            return False

        try:
            order = dom.getElementsByTagName('order')

            if order[0].childNodes[0].nodeValue.lower() == 'random':
                random.shuffle(fileList)
        except:
            pass

        fileList = fileList[:250]

        # Write each entry into the new playlist
        for string in fileList:
            channelplaylist.write("#EXTINF:" + string + "\n")

        channelplaylist.close()
        self.log('makeChannelList return')
        return True
    """
    def makeChannelList(self, channel, chtype, setting1, setting2, setting3, setting4, setting5, setting6, setting7, setting8, setting9, append = False, prestage = False):
        fileList = []
        self.fileLists = []
        limit = self.limit
        chname = self.uncleanString(ADDON_SETTINGS.getSetting("Channel_" + str(channel) + "_3"))

        self.log('makeChannelList ' + str(channel) + " - " + str(chname))
        self.log('append ' + str(append))
        self.log('prestage ' + str(prestage))

        if self.threadPause() == False:
            return ''

        if chtype == 7: # folder based
            # doesn't use smartplaylist to build file list
            self.log("makeChannelList From Folder")
            folder = self.uncleanString(setting1)
            self.videoParser = VideoParser()
            # set the types of files we want in our folder based file list
            flext = [".avi",".mp4",".m4v",".3gp",".3g2",".f4v",".flv",".mkv",".flv"]

            # make sure folder exist
            if os.path.exists(folder):
                self.log("Scanning Folder")
                # get a list of filenames from the folder
                fnlist = []
                for root, subFolders, files in os.walk(folder):            
                    for file in files:

                        if self.threadPause() == False:
                            return ''

                        self.log("file found " + str(file) + " checking for valid extension")
                        # get file extension
                        basename, extension = os.path.splitext(file)
                        if extension in flext:
                            self.log("adding file " + str(file))
                            fnlist.append(os.path.join(root,file))

                # randomize list
                random.shuffle(fnlist)

                numfiles = 0
                if len(fnlist) < self.limit:
                    limit = len(fnlist)

                for i in range(limit):
                    fpath = fnlist[i]
                    # get metadata for file
                    title = self.getTitle(fpath)
                    showtitle = self.getShowTitle(fpath)
                    theplot = self.getThePlot(fpath)
                    # get durations
                    dur = self.videoParser.getVideoLength(fpath)
                    if dur > 0:
                        # add file to file list
                        tmpstr = str(dur) + ',' + title + "//" + showtitle + "//" + theplot
                        tmpstr = tmpstr[:600]
                        tmpstr = tmpstr.replace("\\n", " ").replace("\\r", " ").replace("\\\"", "\"")
                        tmpstr = tmpstr + '\n' + fpath.replace("\\\\", "\\")
                        fileList.append(tmpstr)
            else:
                self.log("Unable to open folder " + str(folder))                
        
        elif chtype == 9: # live channel
            self.fillFeedInfo()
            # doesn't use smartplaylist to build file list
            chname = ADDON_SETTINGS.getSetting("Channel_" + str(channel) + "_3")
            # get feed URL
            feedURL = self.getFeedURL(chname)
            if len(feedURL) > 0:
                # get feed XML
                feedXML = self.getFeedXML(feedURL)
                if len(feedXML) > 0:
                    # parse feed XML
                    try:
                        feed = parseString(feedXML)
                    except:
                        self.log("Unable to parse feedXML")
                        return

                    # need to add more logic to identify feed as either:
                    #   itunes
                    #   rss
                    #   atom
                    # get channel items in feed
                    itemNode = feed.getElementsByTagName("item")
                    # loop through items and determine which fields to get
                    for item in itemNode:
                        # find title
                        if len(item.getElementsByTagName("title")) > 0:
                            titleNode = item.getElementsByTagName("title") #element
                            try:
                                title = titleNode[0].firstChild.data
                                #self.log("title found")
                            except:
                                #self.log("no title data present")
                                title = ''
                        else:
                            #self.log("title not found")
                            title = ''
                        # find content url
                        if len(item.getElementsByTagName("media:content")) > 0:
                            contentNode = item.getElementsByTagName("media:content") #url attribute                    
                            try:
                                url = contentNode[0].getAttribute('url')
                                #self.log("content url found")
                            except:
                                #self.log("content url not found")
                                url = ''
                        elif len(item.getElementsByTagName("enclosure")) > 0:
                            contentNode = item.getElementsByTagName("enclosure") #url attribute                    
                            try:
                                url = contentNode[0].getAttribute('url')
                                #self.log("content url found")
                            except:
                                #self.log("content url not found")
                                url = ''
                        elif len(item.getElementsByTagName("link")) > 0:
                            contentNode = item.getElementsByTagName("link") #url attribute                    
                            try:
                                url = contentNode[0].firstChild.data
                                #self.log("content url found")
                            except:
                                #self.log("content url not found")
                                url = ''
                        else:
                            #self.log("content url not found")
                            url = ''
                        # find duration
                        self.log("durationNode found at " + str(item.getElementsByTagName("mvn:duration")))
                        if len(item.getElementsByTagName("mvn:duration")) > 0:
                            durationNode = item.getElementsByTagName("mvn:duration") #element
                            try:
                                dur = durationNode[0].firstChild.data
                                #self.log("duration found")
                            except:
                                #self.log("duration not found")
                                dur = 0
                        elif len(item.getElementsByTagName("itunes:duration")) > 0:
                            durationNode = item.getElementsByTagName("itunes:duration") #element
                            try:
                                dur = durationNode[0].firstChild.data
                                #self.log("duration found")
                            except:
                                #self.log("exception occurred: duration not found")
                                dur = 0

                            # duration is in <![CDATA[9:23]]>
                            # need to convert to seconds
                            try:
                                dur_parts = []
                                dur_parts = dur.split(':')
                                #self.log("length of duration string = " + str(len(dur_parts)))
                                if len(dur_parts) == 1:
                                    seconds = int(dur_parts[0])
                                    dur = seconds
                                    #self.log("seconds = " + str(seconds))
                                    #self.log("dur = " + str(dur))
                                elif len(dur_parts) == 2:
                                    minutes = int(dur_parts[0])
                                    seconds = int(dur_parts[1])
                                    dur = (minutes * 60) + seconds
                                    #self.log("minutes = " + str(minutes))
                                    #self.log("seconds = " + str(seconds))
                                    #self.log("dur = " + str(dur))
                                elif len(dur_parts) == 3:
                                    hours = int(dur_parts[0])
                                    minutes = int(dur_parts[1])
                                    seconds = int(dur_parts[2])
                                    dur = (hours * 3600) + (minutes * 60) + seconds
                            except:
                                #self.log("error parsing duration time")
                                dur = 0
                        else:
                            #self.log("duration element not found")
                            dur = 0
                        # find airdate
                        if len(item.getElementsByTagName("mvn:airDate")) > 0:
                            airdateNode = item.getElementsByTagName("mvn:airDate") #element
                            try:
                                airdate = airdateNode[0].firstChild.data
                                #self.log("airdate found")
                            except:
                                #self.log("airdate not found")
                                airdate = ''
                        elif len(item.getElementsByTagName("pubDate")) > 0:
                            airdateNode = item.getElementsByTagName("pubDate") #element
                            try:
                                airdate = airdateNode[0].firstChild.data
                                #self.log("airdate found")
                            except:
                                #self.log("airdate not found")
                                airdate = ''
                        else:
                            #self.log("airdate not found")
                            airdate = ''

                        # find description
                        if len(item.getElementsByTagName("media:description")) > 0:
                            descriptionNode = item.getElementsByTagName("media:description") #element
                            try:
                                description = descriptionNode[0].firstChild.data
                                #self.log("description found")
                            except:
                                #self.log("description not found")
                                description = ''
                        elif len(item.getElementsByTagName("description")) > 0:
                            descriptionNode = item.getElementsByTagName("description") #element
                            try:
                                description = descriptionNode[0].firstChild.data
                                # <![CDATA[Tony Reali and the national panel discuss the hot topics of the day in "The First Word."]]>
                                #self.log("description found")
                                if description.find("</embed>") > 0:
                                    #self.log("description has embedded object. Removing description")
                                    description = ''
                                if description.find("</a>") > 0:
                                    #self.log("description has links. Removing description")
                                    description = ''                            
                            except:
                                #self.log("description not found")
                                description = ''
                        else:
                            #self.log("description not found")
                            description = ''
                        # find show
                        if len(item.getElementsByTagName("mvn:fnc_show")) > 0:
                            showNode = item.getElementsByTagName("mvn:fnc_show") #element
                            try:
                                showtitle = showNode[0].firstChild.data
                                #self.log("show found")
                            except:
                                #self.log("show not found")
                                showtitle = ''
                        elif len(item.getElementsByTagName("mvn:fnc_show")) > 0:
                            showNode = item.getElementsByTagName("mvn:fnc_show") #element
                            try:
                                showtitle = showNode[0].firstChild.data
                                #self.log("show found")
                            except:
                                #self.log("show not found")
                                showtitle = ''
                        else:
                            #self.log("show not found")
                            showtitle = ''

                        if len(showtitle) > 0:
                            showtitle = showtitle + "(" + airdate + ")"
                        else:
                            showtitle = "(" + airdate + ")"

                        title = title.encode('utf-8')
                        title = self.uncleanString(title)
                        showtitle = showtitle.encode('utf-8')
                        showtitle = self.uncleanString(showtitle)
                        description = description.encode('utf-8')
                        description = self.uncleanString(description)
                        url = url.encode('utf-8')
                        # add file to file list
                        # will see if this works or whether
                        # we will need to add shows direct to playlist and 
                        # call play                        
                        if len(url) > 0 and int(dur) > 0:
                            tmpstr = str(dur) + ',' + title + "//" + showtitle + "//" + description
                            tmpstr = tmpstr[:600]
                            tmpstr = tmpstr.replace("\\n", " ").replace("\n", " ").replace("\r", " ").replace("\\r", " ").replace("\\\"", "\"")
                            tmpstr = tmpstr + '\n' + url.replace("\\\\", "\\")
                            fileList.append(tmpstr)
        else:
            self.log("chtype = " + str(chtype))
            if int(chtype) == 0: # custom playlist
                fle = setting1
            else: # all others use generated playlists
                self.log("call makeTypePlaylist")
                fle = self.makeTypePlaylist(chtype, setting1, setting2, setting3, setting4, setting5, setting6, setting7, setting8, setting9)

            fle = xbmc.translatePath(fle)

            self.log("check playlist file name")

            if len(fle) == 0:
                self.log('Unable to create a playlist for channel ' + str(channel), xbmc.LOGERROR)
                return False

            try:
                xml = open(fle, "r")
            except:
                self.log("makeChannelList Unable to open the smart playlist " + fle, xbmc.LOGERROR)
                return False

            try:
                dom = parse(xml)
            except:
                self.log('makeChannelList Problem parsing playlist ' + fle, xbmc.LOGERROR)
                xml.close()
                return False

            xml.close()

            try:
                orderNode = dom.getElementsByTagName('order')
                limitNode = dom.getElementsByTagName('limit')
            except:
                pass
            
            if limitNode:
                try:
                    plimit = limitNode[0].firstChild.nodeValue
                    # force a max limit of 250 for performance reason
                    if int(plimit) < limit:
                        limit = plimit
                except:
                    pass
                    
            randomize = False
            if orderNode:
                try:
                    if orderNode[0].childNodes[0].nodeValue.lower() == 'random':
                        randomize = True
                except:
                    pass
                    
            if self.getSmartPlaylistType(dom) == 'mixed':
                self.level = 0 # used in buildMixedFileListFromPlaylist to keep track of limit for different playlists            
                fileLists = self.buildMixedFileListsFromPlaylist(fle, channel)

                if not "movies" in self.fileLists and not "episodes" in self.fileLists:
                    fileList = self.buildMixedTVShowFileList(fileLists, channel, setting3, setting9)
                else:
                    fileList = self.buildMixedFileList(fileLists, channel, limit)
                    if randomize:
                        random.shuffle(fileList)
                self.log("mixed fileList = " + str(fileList))
            else:
                fileList = self.buildFileList(fle, channel)
                if randomize:
                    random.shuffle(fileList)                    
                self.log("fileList = " + str(fileList))
        
        #################
        # trailers bumpers commercials offair
        # check if fileList contains files
        if len(fileList) == 0:
            offair = REAL_SETTINGS.getSetting("offair")
            offairFile = REAL_SETTINGS.getSetting("offairfile")            
            if offair and len(offairFile) > 0:
                dur = self.videoParser.getVideoLength(offairFile)
                # insert offair video file
                if dur > 0:
                    numFiles = int((60 * 60 * 24)/dur)
                    for i in range(numFiles):
                        tmpstr = str(dur) + ','
                        title = "Off Air"
                        showtitle = "Off Air"
                        theplot = "This channel is currently off the air"
                        tmpstr = str(dur) + ',' + showtitle + "//" + title + "//" + theplot
                        tmpstr = tmpstr.replace("\\n", " ").replace("\\r", " ").replace("\\\"", "\"")
                        tmpstr = tmpstr + '\n' + offairFile.replace("\\\\", "\\")
                        fileList.append(tmpstr)
                ADDON_SETTINGS.setSetting("Channel_" + str(channel) + "_offair","1")
                ADDON_SETTINGS.setSetting("Channel_" + str(channel) + "_2",MODE_SERIAL)
        else:
            ADDON_SETTINGS.setSetting("Channel_" + str(channel) + "_offair","0")
            if not chtype == 8: # not music channel
                commercials = REAL_SETTINGS.getSetting("commercials")
                commercialsfolder = REAL_SETTINGS.getSetting("commercialsfolder")
                commercialInterval = 0            
                bumpers = REAL_SETTINGS.getSetting("bumpers")
                bumpersfolder = REAL_SETTINGS.getSetting("bumpersfolder")
                bumperInterval = 0
                if (commercials == "true" and os.path.exists(commercialsfolder)) or (bumpers == "true" and os.path.exists(bumpersfolder)):
                    if (commercials == "true" and os.path.exists(commercialsfolder)) :
                        commercialInterval = self.getCommercialInterval(channel, len(fileList))
                        commercialNum = self.getCommercialNum(channel, len(fileList))
                    else:
                        commercialInterval = 0
                        commercialNum = 0                        
                    if (bumpers == "true" and os.path.exists(bumpersfolder)):
                        bumperInterval = self.getBumperInterval(channel, len(fileList))
                        bumperNum = self.getBumperNum(channel, len(fileList))
                    else:
                        bumperInterval = 0
                        bumperNum = 0                        
                    trailerInterval = 0
                    trailerNum = 0
                    trailers = False
                    bumpers = False
                    commercials = False
                    
                    if not int(bumperInterval) == 0:
                        bumpers = True
                    if not int(commercialInterval) == 0:
                        commercials = True
                        
                    for i in range(len(fileList)):
                        self.log("file = " + str(i) + " = " + str(fileList[i]))
                    
                    fileList = self.insertFiles(channel, fileList, commercials, bumpers, trailers, commercialInterval, bumperInterval, trailerInterval, commercialNum, bumperNum, trailerNum)

        #################
        # finished building file lists now let's write it out to the m3u file
        
        try:
            if append == True:
                channelplaylist = open(CHANNELS_LOC + "channel_" + str(channel) + ".m3u", "r+")
                channelplaylist.seek(0, 2)
            if prestage == True:
                channelplaylist = open(PRESTAGE_LOC + "channel_" + str(channel) + ".m3u", "w")            
            else:
                channelplaylist = open(CHANNELS_LOC + "channel_" + str(channel) + ".m3u", "w")
        except:
            self.log('Unable to open the cache file ' + CHANNELS_LOC + 'channel_' + str(channel) + '.m3u', xbmc.LOGERROR)
            return False

        if append == False:
            channelplaylist.write("#EXTM3U\n")

        if len(fileList) == 0:
            self.log("Unable to get information about channel " + str(channel), xbmc.LOGERROR)
            channelplaylist.close()
            return False

        #try:
        #    order = dom.getElementsByTagName('order')
        #
        #    if order[0].childNodes[0].nodeValue.lower() == 'random':
        #        random.shuffle(fileList)
        #except:
        #    pass

        fileList = fileList[:250]

        # Write each entry into the new playlist
        for string in fileList:
            channelplaylist.write("#EXTINF:" + string + "\n")

        channelplaylist.close()

        ADDON_SETTINGS.writeSettings()

        self.log('makeChannelList return')
        return True
    ###############


    def appendChannel(self, channel):
        self.log("appendChannel")
        chtype = 9999
        chsetting1 = ''
        chsetting2 = ''
        ### TV TIME ###
        chsetting3 = ''
        chsetting4 = ''
        chsetting5 = ''
        chsetting6 = ''
        chsetting7 = ''
        chsetting8 = ''
        chsetting9 = ''        
        ###############

        try:
            chtype = int(ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_type'))
            chsetting1 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_1')
            chsetting2 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_2')
            ### TV TIME ###
            chsetting3 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_3')
            chsetting4 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_4')
            chsetting5 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_5')
            chsetting6 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_6')
            chsetting7 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_7')
            chsetting8 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_8')
            chsetting9 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_9')            
            ###############
        except:
            self.log("appendChannel unable to get channel settings")
            return False
        
        ### TV TIME ###
        #return self.makeChannelList(channel, chtype, chsetting1, chsetting2, True)
        return self.makeChannelList(channel, chtype, chsetting1, chsetting2, chsetting3, chsetting4, chsetting5, chsetting6, chsetting7, chsetting8, chsetting9, True)
        ###############


    ### TV TIME ###
    def prestageChannel(self, channel):
        self.log("prestageChannel")
        chtype = 9999
        chsetting1 = ''
        chsetting2 = ''
        chsetting3 = ''
        chsetting4 = ''
        chsetting5 = ''
        chsetting6 = ''
        chsetting7 = ''
        chsetting8 = ''
        chsetting9 = ''        

        try:
            chtype = int(ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_type'))
            chsetting1 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_1')
            chsetting2 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_2')
            chsetting3 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_3')
            chsetting4 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_4')
            chsetting5 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_5')
            chsetting6 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_6')
            chsetting7 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_7')
            chsetting8 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_8')
            chsetting9 = ADDON_SETTINGS.getSetting('Channel_' + str(channel) + '_9')            
        except:
            self.log("prestageChannel unable to get channel settings")
            return False
        
        return self.makeChannelList(channel, chtype, chsetting1, chsetting2, chsetting3, chsetting4, chsetting5, chsetting6, chsetting7, chsetting8, chsetting9, False, True)
    ###############
        

    ### TV TIME ###
    """
    def makeTypePlaylist(self, chtype, setting1, setting2):
        if chtype == 1:
            if len(self.networkList) == 0:
                self.fillTVInfo()

            return self.createNetworkPlaylist(setting1)
        elif chtype == 2:
            if len(self.studioList) == 0:
                self.fillMovieInfo()

            return self.createStudioPlaylist(setting1)
        elif chtype == 3:
            if len(self.showGenreList) == 0:
                self.fillTVInfo()

            return self.createGenrePlaylist('episodes', chtype, setting1)
        elif chtype == 4:
            if len(self.movieGenreList) == 0:
                self.fillMovieInfo()

            return self.createGenrePlaylist('movies', chtype, setting1)
        elif chtype == 5:
            if len(self.mixedGenreList) == 0:
                if len(self.showGenreList) == 0:
                    self.fillTVInfo()

                if len(self.movieGenreList) == 0:
                    self.fillMovieInfo()

                self.mixedGenreList = self.makeMixedList(self.showGenreList, self.movieGenreList)
                self.mixedGenreList.sort(key=lambda x: x.lower())

            return self.createGenreMixedPlaylist(setting1)
        elif chtype == 6:
            if len(self.showList) == 0:
                self.fillTVInfo()

            return self.createShowPlaylist(setting1, setting2)

        self.log('makeTypePlaylists invalid channel type: ' + str(chtype))
        return ''
    """
    def makeTypePlaylist(self, chtype, setting1, setting2, setting3, setting4, setting5, setting6, setting7, setting8, setting9):
        self.log("makeTypePlaylist " + str(chtype))
        chsubtype = setting1
        serial = setting2
        chname = setting3
        unwatched = setting4
        nospecials = setting5
        resolution = setting6
        numepisodes = setting7
        nummovies = setting8
        randomtvshow = setting9
        if chtype == 1:
            if len(self.networkList) == 0:
                self.fillTVInfo()

            return self.createNetworkPlaylist(chsubtype, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow)
        elif chtype == 2:
            if len(self.studioList) == 0:
                self.fillMovieInfo()

            return self.createStudioPlaylist(chsubtype, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow)
        elif chtype == 3:
            if len(self.showGenreList) == 0:
                self.fillTVInfo()
            mix = False
            return self.createGenrePlaylist('episodes', chtype, chsubtype, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow, mix)
        elif chtype == 4:
            if len(self.movieGenreList) == 0:
                self.fillMovieInfo()
            mix = False
            return self.createGenrePlaylist('movies', chtype, chsubtype, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow, mix)
        elif chtype == 5:
            if len(self.mixedGenreList) == 0:
                if len(self.showGenreList) == 0:
                    self.fillTVInfo()

                if len(self.movieGenreList) == 0:
                    self.fillMovieInfo()

                self.mixedGenreList = self.makeMixedList(self.showGenreList, self.movieGenreList)
                self.mixedGenreList.sort(key=lambda x: x.lower())
            mix = True
            return self.createGenreMixedPlaylist(chsubtype, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow, mix)
        elif chtype == 6:
            if len(self.showList) == 0:
                self.fillTVInfo()

            return self.createShowPlaylist(chsubtype, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow)

        elif chtype == 8:
            if len(self.musicGenreList) == 0:
                self.fillMusicInfo()
            mix = False
            return self.createGenrePlaylist('music', chtype, chsubtype, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow, mix)

        self.log('makeTypePlaylists invalid channel type: ' + str(chtype))
        return ''
    ###############

    ### TV TIME ###
    """
    def createNetworkPlaylist(self, network):
        flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'Network_' + network + '.xsp')

        try:
            fle = open(flename, "w")
        except:
            self.Error('Unable to open the cache file ' + flename, xbmc.LOGERROR)
            return ''

        self.writeXSPHeader(fle, "episodes", self.getChannelName(1, network))
        network = network.lower()
        added = False

        for i in range(len(self.showList)):
            if self.threadPause() == False:
                fle.close()
                return ''

            if self.showList[i][1].lower() == network:
                theshow = self.cleanString(self.showList[i][0])
                fle.write('    <rule field="tvshow" operator="is">' + theshow + '</rule>\n')
                added = True

        self.writeXSPFooter(fle, 250, "random")
        fle.close()

        if added == False:
            return ''

        return flename
    """
    def createNetworkPlaylist(self, network, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow):
        self.log("createNetworkPlaylist " + str(network))
        flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'Network_' + network + '.xsp')
        limit = self.limit
        if serial == "":
            serial = 0
        if randomtvshow == "":
            randomtvshow = 0

        added = False

        network_playlists = []
        network_tvshow_playlists = []

        # get number of shows matching
        numShows = 0
        for i in range(len(self.showList)):
            if self.showList[i][1].lower() == network.lower():
                numShows = numShows + 1        
        
        # create a seperate playlist for each tvshow
        for i in range(len(self.showList)):
        
            if self.threadPause() == False:
                return ''

            if self.showList[i][1].lower() == network.lower():
                network = network.lower()
                theshow = self.showList[i][0].lower()

                flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'network_' + network + '_' + theshow + '.xsp')

                # create playlist for network tvshow
                try:
                    fle = open(flename, "w")
                except:
                    self.Error('createNetworkPlaylist: Unable to open the cache file ', xbmc.LOGERROR)
                    return ''

                self.writeXSPHeader(fle, "episodes", 'network_' + network + '_' + theshow, 'all')
                fle.write('    <rule field="tvshow" operator="is">' + self.cleanString(theshow) + '</rule>\n')
                
                if unwatched == "1":
                    fle.write('    <rule field="playcount" operator="is">0</rule>\n')
                
                if nospecials == "1":
                    fle.write('    <rule field="season" operator="isnot">0</rule>\n')

                if len(resolution) > 0:
                    if resolution == 'SD Only':
                        fle.write('    <rule field="videoresolution" operator="lessthan">720</rule>\n')
                    if resolution == '720p or Higher':
                        fle.write('    <rule field="videoresolution" operator="greaterthan">719</rule>\n')
                    if resolution == '1080p Only':
                        fle.write('    <rule field="videoresolution" operator="greaterthan">1079</rule>\n')

                if int(serial) == MODE_SERIAL:
                    self.writeXSPFooter(fle, int(limit/numShows), "airdate")                        
                else:
                    self.writeXSPFooter(fle, int(limit/numShows), "random")

                fle.close()

                network_tvshow_playlists.append(flename)

        if len(network_tvshow_playlists) > 0:
            # build mixed playlist combining all the network tvshows
            flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'network_' + network + '.xsp')
            try:
                fle = open(flename, "w")
            except:
                self.Error('Unable to open the cache file ' + flename, xbmc.LOGERROR)
                return ''

            self.writeXSPHeader(fle, "mixed", chname, 'one')
            network = network.lower()
            
            for i in range(len(network_tvshow_playlists)):
                playlist = network_tvshow_playlists[i]
                fle.write('    <rule field="playlist" operator="is">' + self.cleanString(playlist) + '</rule>\n')

            if int(randomtvshow) > 0:
                self.writeXSPFooter(fle, limit, "random")
            else:
                self.writeXSPFooter(fle, limit, "")

            #network_playlists.append(flename)
            fle.close()
            added = True
        
        if added == False:
            return ''
            
        return flename            
    ###############


    ### TV TIME ###
    """
    def createShowPlaylist(self, show, setting2):
        order = 'random'

        try:
            setting = int(setting2)

            if setting & MODE_ORDERAIRDATE > 0:
                order = 'airdate'
        except:
            pass

        flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'Show_' + show + '_' + order + '.xsp')

        try:
            fle = open(flename, "w")
        except:
            self.Error('Unable to open the cache file ' + flename, xbmc.LOGERROR)
            return ''

        self.writeXSPHeader(fle, 'episodes', self.getChannelName(6, show))
        show = self.cleanString(show)
        fle.write('    <rule field="tvshow" operator="is">' + show + '</rule>\n')
        self.writeXSPFooter(fle, 250, order)
        fle.close()
        return flename
    """
    def createShowPlaylist(self, show, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow):
        self.log("createShowPlaylist " + str(show))
        
        if self.threadPause() == False:
            return ''

        #  need to fix to work with extended character sets
        limit = self.limit
        if serial == "":
            serial = 0
        if unwatched == "":
            unwatched = 0
        if nospecials == "":
            nospecials = 0
        #if resolution == "":
        #    resolution = 0

        show_playlists = []
        show = show.lower()

        order = 'random'

        try:
            setting = int(serial)

            if setting & MODE_ORDERAIRDATE > 0:
                order = 'airdate'
        except:
            pass

        flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'show_' + show + '_' + order + '.xsp')
        self.log("flename " + str(flename))
        try:
            fle = open(flename, "w")
        except:
            self.Error('Unable to open the cache file ' + flename, xbmc.LOGERROR)
            return ''

        self.writeXSPHeader(fle, 'episodes', chname, 'all')
        fle.write('    <rule field="tvshow" operator="is">' + self.cleanString(show) + '</rule>\n')
        if unwatched:
            fle.write('    <rule field="playcount" operator="is">0</rule>\n')
        if nospecials:
            fle.write('    <rule field="season" operator="isnot">0</rule>\n')
        if len(resolution)>0:
            if resolution == 'SD Only':
                fle.write('    <rule field="videoresolution" operator="lessthan">720</rule>\n')
            if resolution == '720p or Higher':
                fle.write('    <rule field="videoresolution" operator="greaterthan">719</rule>\n')
            if resolution == '1080p Only':
                fle.write('    <rule field="videoresolution" operator="greaterthan">1079</rule>\n')

        self.writeXSPFooter(fle, limit, order)
        fle.close()
        show_playlists.append(flename)
        
        return flename
    ###############


    ### TV TIME ###
    """
    def createGenreMixedPlaylist(self, genre):
        flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'Mixed_' + genre + '.xsp')

        try:
            fle = open(flename, "w")
        except:
            self.Error('Unable to open the cache file ' + flename, xbmc.LOGERROR)
            return ''

        epname = os.path.basename(self.createGenrePlaylist('episodes', 3, genre))
        moname = os.path.basename(self.createGenrePlaylist('movies', 4, genre))
        self.writeXSPHeader(fle, 'mixed', self.getChannelName(5, genre))
        fle.write('    <rule field="playlist" operator="is">' + epname + '</rule>\n')
        fle.write('    <rule field="playlist" operator="is">' + moname + '</rule>\n')
        self.writeXSPFooter(fle, 250, "random")
        fle.close()
        return flename
    """
    def createGenreMixedPlaylist(self, genre, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow, mix):
        self.log("createGenreMixedPlaylist " + str(genre))

        if self.threadPause() == False:
            return ''

        limit = self.limit
        if serial == "":
            serial = 0
        if unwatched == "":
            unwatched = 0
        if nospecials == "":
            nospecials = 0
        #if resolution == "":
        #    resolution = 0
        if randomtvshow == "":
            randomtvshow = 0
        
        genre = genre.lower()
        flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'mixed_' + genre + '.xsp')

        #epname = os.path.basename(self.createGenrePlaylist('episodes', 3, genre, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow))
        #moname = os.path.basename(self.createGenrePlaylist('movies', 4, genre, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow))
        epname = self.createGenrePlaylist('episodes', 3, genre, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow, mix)
        moname = self.createGenrePlaylist('movies', 4, genre, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow, mix)
        if len(epname) > 0 or len(moname) > 0:        
            try:
                fle = open(flename, "w")
            except:
                self.Error('Unable to open the cache file ' + flename, xbmc.LOGERROR)
                return ''
            self.writeXSPHeader(fle, 'mixed', chname, 'one')
            if len(epname) > 0:
                fle.write('    <rule field="playlist" operator="is">' + self.cleanString(epname) + '</rule>\n')
            if len(moname) > 0:
                fle.write('    <rule field="playlist" operator="is">' + self.cleanString(moname) + '</rule>\n')
            if int(randomtvshow) > 0:
                self.writeXSPFooter(fle, limit, "random")
            else:
                self.writeXSPFooter(fle, limit, "")
            fle.close()
        else:
            return ''        

        return flename    
    ###############


    ### TV TIME ###
    """
    def createGenrePlaylist(self, pltype, chtype, genre):
        flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + pltype + '_' + genre + '.xsp')

        try:
            fle = open(flename, "w")
        except:
            self.Error('Unable to open the cache file ' + flename, xbmc.LOGERROR)
            return ''

        self.writeXSPHeader(fle, pltype, self.getChannelName(chtype, genre))
        genre = self.cleanString(genre)
        fle.write('    <rule field="genre" operator="is">' + genre + '</rule>\n')
        self.writeXSPFooter(fle, 250, "random")
        fle.close()
        return flename
    """
    def createGenrePlaylist(self, pltype, chtype, genre, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow, mix):
        self.log("createGenrePlaylist " + str(genre) + " " + str(pltype))

        if self.threadPause() == False:
            return ''

        limit = self.limit
        if serial == "":
            serial = 0
        if unwatched == "":
            unwatched = 0
        if nospecials == "":
            nospecials = 0
        #if resolution == "":
        #    resolution = 0
        if randomtvshow == "":
            randomtvshow = 0

        added = False

        order = 'random'
        try:
            setting = int(serial)
            if setting & MODE_ORDERAIRDATE > 0:
                order = 'airdate'
        except:
            pass

        pltype = pltype.lower()
        genre = genre.lower()

        genre_playlists = []
        genre_tvshow_playlists = []

        if pltype == "movies":
            order = "random"

            if mix:
                flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'mixed_' + pltype + '_' + genre + '.xsp')            
            else:
                flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + pltype + '_' + genre + '.xsp')
            
            try:
                fle = open(flename, "w")
            except:
                self.Error('Unable to open the cache file ' + flename, xbmc.LOGERROR)
                return ''

            #
            # if serial mode, we need to build a mix file list
            # containing each show in genre
            #
            self.writeXSPHeader(fle, pltype, chname, 'all')
            fle.write('    <rule field="genre" operator="is">' + self.cleanString(genre) + '</rule>\n')

            if unwatched:
                fle.write('    <rule field="playcount" operator="is">0</rule>\n')

            if (pltype=="episodes" and nospecials):
                fle.write('    <rule field="season" operator="isnot">0</rule>\n')

            if (pltype=="movies" and len(resolution)>0):
                if resolution == 'SD Only':
                    fle.write('    <rule field="videoresolution" operator="lessthan">720</rule>\n')
                if resolution == '720p or Higher':
                    fle.write('    <rule field="videoresolution" operator="greaterthan">719</rule>\n')
                if resolution == '1080p Only':
                    fle.write('    <rule field="videoresolution" operator="greaterthan">1079</rule>\n')

            self.writeXSPFooter(fle, limit, order)

            fle.close()

            added = True
            
        elif pltype == "episodes":
            self.log("create episodes playlist")
            # get number of shows matching
            numShows = 0
            for i in range(len(self.showList)):
                if self.showList[i][2].lower() == genre.lower():
                    numShows = numShows + 1        

            self.log("number of shows matching " + genre.lower() + " genre = " + str(numShows))
            # create a seperate playlist for each tvshow
            for i in range(len(self.showList)):
            
                if self.threadPause() == False:
                    return ''

                if self.showList[i][2].lower() == genre.lower():
                    genre = genre.lower()
                    theshow = self.showList[i][0].lower()
                    if mix:
                        self.log("create mix playlist")
                        flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'mixed_' + pltype + '_' + genre + '_' + theshow + '.xsp')                    
                    else:
                        self.log("create playlist")
                        flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + pltype + '_' + genre + '_' + theshow + '.xsp')

                    self.log("filename = " + str(flename))
                    # create playlist for network tvshow
                    try:
                        fle = open(flename, "w")
                    except:
                        self.Error('createNetworkPlaylist: Unable to open the cache file ', xbmc.LOGERROR)
                        return ''
                    
                    self.log("write XSP Header")
                    self.writeXSPHeader(fle, "episodes", pltype + '_' + genre + '_' + theshow, 'all')
                    fle.write('    <rule field="tvshow" operator="is">' + self.cleanString(theshow) + '</rule>\n')
                    
                    if unwatched == "1":
                        fle.write('    <rule field="playcount" operator="is">0</rule>\n')
                    
                    if nospecials == "1":
                        fle.write('    <rule field="season" operator="isnot">0</rule>\n')

                    if len(resolution) > 0:
                        if resolution == 'SD Only':
                            fle.write('    <rule field="videoresolution" operator="lessthan">720</rule>\n')
                        if resolution == '720p or Higher':
                            fle.write('    <rule field="videoresolution" operator="greaterthan">719</rule>\n')
                        if resolution == '1080p Only':
                            fle.write('    <rule field="videoresolution" operator="greaterthan">1079</rule>\n')

                    self.log("write XSP Footer")
                    if int(serial) == MODE_SERIAL:
                        self.writeXSPFooter(fle, int(limit/numShows), "airdate")                        
                    else:
                        self.writeXSPFooter(fle, int(limit/numShows), "random")

                    fle.close()

                    genre_tvshow_playlists.append(flename)

            if len(genre_tvshow_playlists) > 0:
                self.log("build mixed playlist combining all the network tvshows")
                # build mixed playlist combining all the network tvshows
                if mix:
                    flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'mixed_' + pltype + '_' + genre + '.xsp')
                else:
                    flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + pltype + '_' + genre + '.xsp')
                
                self.log("filename = " + str(flename))

                try:
                    fle = open(flename, "w")
                except:
                    self.Error('Unable to open the cache file ' + flename, xbmc.LOGERROR)
                    return ''

                self.log("write XSP Header")
                self.writeXSPHeader(fle, "mixed", chname, 'one')
                genre = genre.lower()
                
                for i in range(len(genre_tvshow_playlists)):
                    fle.write('    <rule field="playlist" operator="is">' + self.cleanString(genre_tvshow_playlists[i]) + '</rule>\n')

                self.log("write XSP Footer")
                if int(randomtvshow) > 0:
                    self.writeXSPFooter(fle, limit, "random")
                else:
                    self.writeXSPFooter(fle, limit, "")

                fle.close()
                added = True
        
        elif pltype == "music":
            limit = 1000
            pltype = "songs"
            genre = genre.lower()
            flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + pltype + '_' + genre + '.xsp')
            try:
                fle = open(flename, "w")
            except:
                self.Error('Unable to open the cache file ' + flename, xbmc.LOGERROR)
                return ''
            self.writeXSPHeader(fle, pltype, chname, 'all')
            fle.write('    <rule field="genre" operator="is">' + self.cleanString(genre) + '</rule>\n')
            self.writeXSPFooter(fle, limit, "random")
            fle.close()
            added = True
                    
        if added == False:
            return ''
        
        self.log("flename " + str(flename))
        return flename            
    ###############


    ### TV TIME ###
    """
    def createStudioPlaylist(self, studio):
        flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'Studio_' + studio + '.xsp')

        try:
            fle = open(flename, "w")
        except:
            self.Error('Unable to open the cache file ' + flename, xbmc.LOGERROR)
            return ''

        self.writeXSPHeader(fle, "movies", self.getChannelName(2, studio))
        studio = self.cleanString(studio)
        fle.write('    <rule field="studio" operator="is">' + studio + '</rule>\n')
        self.writeXSPFooter(fle, 250, "random")
        fle.close()
        return flename
    """
    def createStudioPlaylist(self, studio, serial, chname, unwatched, nospecials, resolution, numepisodes, nummovies, randomtvshow):
        self.log("createStudioPlaylist " + str(studio))
        
        if self.threadPause() == False:
            return ''

        limit = self.limit
        if serial == "":
            serial = 0
        if unwatched == "":
            unwatched = 0
        if nospecials == "":
            nospecials = 0
        #if resolution == "":
        #    resolution = 0
        studio = studio.lower()
        flename = xbmc.makeLegalFilename(GEN_CHAN_LOC + 'studio_' + studio + '.xsp')
        try:
            fle = open(flename, "w")
        except:
            self.Error('Unable to open the cache file ' + flename, xbmc.LOGERROR)
            return ''                
        self.writeXSPHeader(fle, "movies", chname, 'all')
        fle.write('    <rule field="studio" operator="is">' + self.cleanString(studio) + '</rule>\n')
        if unwatched:
            fle.write('    <rule field="playcount" operator="is">0</rule>\n')
        if nospecials:
            fle.write('    <rule field="season" operator="isnot">0</rule>\n')
        if len(resolution)>0:
            if resolution == 'SD Only':
                fle.write('    <rule field="videoresolution" operator="lessthan">720</rule>\n')
            if resolution == '720p or Higher':
                fle.write('    <rule field="videoresolution" operator="greaterthan">719</rule>\n')
            if resolution == '1080p Only':
                fle.write('    <rule field="videoresolution" operator="greaterthan">1079</rule>\n')
        if serial:
            self.writeXSPFooter(fle, limit, "airdate")
        else:
            self.writeXSPFooter(fle, limit, "random")
        fle.close()

        return flename
    ###############


    ### TV TIME ###
    """
    def writeXSPHeader(self, fle, pltype, plname):
        fle.write('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n')
        fle.write('<smartplaylist type="' + pltype + '">\n')
        plname = self.cleanString(plname)
        fle.write('    <name>' + plname + '</name>\n')
        fle.write('    <match>one</match>\n')
    """
    def writeXSPHeader(self, fle, pltype, plname, match):
        fle.write('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n')
        fle.write('<smartplaylist type="' + pltype + '">\n')
        plname = self.cleanString(plname)
        fle.write('    <name>' + plname + '</name>\n')
        fle.write('    <match>' + match + '</match>\n')
    ###############


    def writeXSPFooter(self, fle, limit, order):
        fle.write('    <limit>' + str(limit) + '</limit>\n')
        if len(order) > 0:
            fle.write('    <order direction="ascending">' + order + '</order>\n')
        fle.write('</smartplaylist>\n')


    def cleanString(self, string):
        newstr = string
        newstr = newstr.replace('&', '&amp;')
        newstr = newstr.replace('>', '&gt;')
        newstr = newstr.replace('<', '&lt;')
        ### TV TIME ###
        newstr = newstr.replace("'", "&apos;")
        ###############
        return newstr


    ### TV TIME ###
    def fillMusicInfo(self):
        """
        #print xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "JSONRPC.Introspect", "id": 1}')
        self.log("fillMusicInfo")
        self.musicGenreList = [] 
        json_query = '{"jsonrpc": "2.0", "method": "AudioLibrary.GetAlbums", "params": {"fields":["genre"]}, "id": 1}'
        json_folder_detail = xbmc.executeJSONRPC(json_query)
        detail = re.compile( "{(.*?)}", re.DOTALL ).findall(json_folder_detail)
        for f in detail:
            match = re.search('"genre" *: *"(.*?)",', f)

            if match:
                genres = match.group(1).split('/')

                for genre in genres:
                    found = False
                    curgenre = genre.lower().strip()

                    for g in self.musicGenreList:
                        if curgenre == g.lower():
                            found = True
                            break

                    if found == False:
                        self.musicGenreList.append(genre.strip())

        self.musicGenreList.sort(key=lambda x: x.lower())    
        """
        self.log("fillMusicInfo")
        genreList = []
        self.musicGenreList = [] 
        json_query = '{"jsonrpc": "2.0", "method": "AudioLibrary.GetAlbums", "params": {"fields":["genre"]}, "id": 1}'
        json_folder_detail = self.sendJSON(json_query)
        #self.log(json_folder_detail)
        detail = re.compile( "{(.*?)}", re.DOTALL ).findall(json_folder_detail)

        for f in detail:
            if self.threadPause() == False:
                del self.musicGenreList[:]
                del genreList[:]
                break

            match = re.search('"genre" *: *"(.*?)",', f)

            if match:
                genres = match.group(1).split('/')

                for genre in genres:
                    curgenre = genre.strip()
                    found = False

                    for i in range(len(genreList)):
                        if genreList[i][0].lower() == curgenre.lower():
                            genreList[i][1] += 1
                            found = True

                    if found == False and len(curgenre) > 0:
                        genreList.append([curgenre, 1])

        genreList.sort(key=itemgetter(1), reverse=True)
        for i in range(len(genreList)):
            self.log(str(genreList[i]))

        ### TV TIME ###
        maxsize = int(REAL_SETTINGS.getSetting("maxMusicGenres"))            
        ###############
        
        for i in range(len(genreList)):
            if maxsize > 0:
                if i < maxsize:
                    self.musicGenreList.append(genreList[i][0])
            else:
                self.musicGenreList.append(genreList[i][0])

        self.musicGenreList.sort(key=lambda x: x.lower())
        self.log("fillMusicInfo return " + str(self.musicGenreList))


    def createFeedsSourcesXML(self):
        self.log("createFeedsSourcesXML")
        # create initial feed sources.xml
        sourcesXML = open(os.path.join(FEED_LOC,'sources.xml'),'w')
        sourcesXML.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        sourcesXML.write('<feeds>\n')
        #sourcesXML.write('    <feed url="http://archiveclassicmovies.com/acm.rss">ACM Classic Movies</feed>\n')
        sourcesXML.write('    <feed url="http://feeds.feedburner.com/alaskapodshow">Alaska HDTV</feed>\n')
        #sourcesXML.write('    <feed url="http://images.apple.com/trailers/home/rss/newtrailers.rss">Apple Movie Trailers</feed>\n')
        #sourcesXML.write('    <feed url="http://www.atomfilms.com/rss/all_new_films.xml">Atom Films</feed>\n')
        #sourcesXML.write('    <feed url="http://www.bassedge.com/Media/podcast/bassedge.xml">Bass Edge</feed>\n')
        #sourcesXML.write('    <feed url="http://blip.tv/rss/?pagelen=1238676299409">blip.tv</feed>\n')
        #sourcesXML.write('    <feed url="http://feeds.boingboing.net/boingboing/tv?format=xml">Boing Boing</feed>\n')
        #sourcesXML.write('    <feed url="http://cartoon-network.gemzies.com/rss/latest">Cartoon Network: Latest</feed>\n')
        #sourcesXML.write('    <feed url="http://feeds.cbsnews.com/podcast_eveningnews_video_1">CBS: Evening News</feed>\n')
        #sourcesXML.write('    <feed url="http://www.cbsnews.com/common/includes/podcast/podcast_nation_video_1.rss">CBS: Face the Nation</feed>\n')
        #sourcesXML.write('    <feed url="http://feeds.feedburner.com/classicanimation">Classic Animation</feed>\n')
        #sourcesXML.write('    <feed url="http://www.comedycentral.com/rss/recentvideos.jhtml">Comedy Central: Recent</feed>\n')
        #sourcesXML.write('    <feed url="http://www.comedycentral.com/rss/standupvideos.jhtml">Comedy Central: Stand Up</feed>\n')
        #sourcesXML.write('    <feed url="http://www.comedycentral.com/rss/colbertvideos.jhtml">Comedy Central: The Colbert Report</feed>\n')
        #sourcesXML.write('    <feed url="http://www.comedycentral.com/rss/tdsvideos.jhtml">Comedy Central: The Daily Show</feed>\n')
        sourcesXML.write('    <feed url="http://rss.cnn.com/services/podcasting/cnnnewsroom/rss.xml">CNN: Daily</feed>\n')
        sourcesXML.write('    <feed url="http://feeds2.feedburner.com/cnet/hacks">CNET Hacks</feed>\n')
        #sourcesXML.write('    <feed url="http://www.crackle.com/rss/media/bz0xMiZmcGw9MzkyMTIxJmZ4PQ.rss">Crackle: Minisodes</feed>\n')
        #sourcesXML.write('    <feed url="http://www.crackle.com/rss/media/ZmNtdD0zMDMmZnA9MSZmeD0.rss">Crackle: Movies</feed>\n')
        #sourcesXML.write('    <feed url="http://feeds.current.com/groups/green.rss">Current TV: Green</feed>\n')
        #sourcesXML.write('    <feed url="http://feeds.current.com/groups/movies.rss">Current TV: Movies</feed>\n')
        #sourcesXML.write('    <feed url="http://feeds.current.com/groups/music.rss">Current TV: Music Videos</feed>\n')
        #sourcesXML.write('    <feed url="http://feeds.current.com/homepage/en_US/news.rss">Current TV: News</feed>\n')
        #sourcesXML.write('    <feed url="http://revision3.com/diggnation/feed/quicktime-high-definition/">Diggnation</feed>\n')
        sourcesXML.write('    <feed url="http://www.ringtales.com/dilbert.xml">Dilbert</feed>\n')
        sourcesXML.write('    <feed url="http://www.discovery.com/radio/xml/discovery_video.xml">Discovery</feed>\n')
        #sourcesXML.write('    <feed url="http://sports.espn.go.com/espnradio/podcast/feeds/itunes/podCast?id=2870570">ESPN: Around the Horn</feed>\n')
        #sourcesXML.write('    <feed url="http://sports.espn.go.com/espnradio/podcast/feeds/itunes/podCast?id=2869921">ESPN: Mike and Mike</feed>\n')
        #sourcesXML.write('    <feed url="http://sports.espn.go.com/espnradio/podcast/feeds/itunes/podCast?id=3403194">ESPN: SportsCenter</feed>\n')
        sourcesXML.write('    <feed url="http://video.foxnews.com/v/feed/playlist/87249.xml">Fox News Live!</feed>\n')
        #sourcesXML.write('    <feed url="http://feeds.feedburner.com/imovies-bt">iMovies</feed>\n')
        #sourcesXML.write('    <feed url="http://www.youtube.com/ut_rss?type=username&amp;arg=MontyPython">MontyPython</feed>\n')
        sourcesXML.write('    <feed url="http://podcast.msnbc.com/audio/podcast/MSNBC-NN-NETCAST-M4V.xml">MSNBC: Nightly News</feed>\n')
        #sourcesXML.write('    <feed url="http://www.mtv.com/overdrive/rss/news.jhtml">MTV News</feed>\n')
        #sourcesXML.write('    <feed url="http://www.nba.com/topvideo/rss.xml">NBA: Top Videos</feed>\n')
        #sourcesXML.write('    <feed url="http://www.nfl.com/rss/rsslanding?searchString=gamehighlightsVideo">NFL: Highlights</feed>\n')
        #sourcesXML.write('    <feed url="http://feeds.theonion.com/OnionNewsNetwork">Onion News Network</feed>\n')
        sourcesXML.write('    <feed url="http://feeds.feedburner.com/pbs/wnet/nature-video">PBS: Nature</feed>\n')
        sourcesXML.write('    <feed url="http://feeds.pbs.org/pbs/wgbh/nova-video">PBS: Nova</feed>\n')
        #sourcesXML.write('    <feed url="http://www.comedycentral.com/rss/southparkvideos.jhtml">South Park</feed>\n')
        sourcesXML.write('    <feed url="http://feeds.feedburner.com/tedtalksHD">TED Talks</feed>\n')
        #sourcesXML.write('    <feed url="http://www.vh1.com/rss/news/today_on_vh1.jhtml">VH1: Today on VH1</feed>\n')
        sourcesXML.write('</feeds>\n')
        sourcesXML.close()
        

    def fillFeedInfo(self): 
        self.log("fillFeedInfo")
        if not os.path.exists(os.path.join(FEED_LOC,"sources.xml")):
            # create initial feeds list
            self.createFeedsSourcesXML()
        
        self.feedList = []
        fle = os.path.join(FEED_LOC,"sources.xml")
        fle = xbmc.translatePath(fle)
        try:
            xml = open(fle, "r")
        except:
            self.log("fillFeedInfo: Unable to open the feeds xml file " + fle, xbmc.LOGERROR)
            return ''

        try:
            dom = parse(xml)
        except:
            self.log('fillFeedInfo: Problem parsing feeds xml file ' + fle, xbmc.LOGERROR)
            xml.close()
            return ''
        xml.close()
        
        try:
            feedsNode = dom.getElementsByTagName('feed')
        except:
            self.log('fillFeedInfo: No feeds found ' + fle, xbmc.LOGERROR)
            xml.close()
            return ''
        xml.close()
   
        self.feedList = []
        # need to redo this for loop
        for feed in feedsNode:
            try:
                feedName = feed.childNodes[0].nodeValue
            except:
                feedName = ""
            if len(feedName) > 0:
                self.feedList.append(feedName)
         
        self.feedList.sort(key=lambda x: x.lower())


    def uncleanString(self, string):
        newstr = string
        newstr = newstr.replace('&amp;', '&')
        newstr = newstr.replace('&gt;', '>')
        newstr = newstr.replace('&lt;', '<')
        ### TV TIME ###
        newstr = newstr.replace("&apos;", "'")
        ###############
        return newstr


    def getFeedURL(self, chname):
        self.log("getFeedURL")
        feedURL = ''
        fle = os.path.join(FEED_LOC,"sources.xml") 

        try:
            xml = open(fle, "r")
        except:
            self.log("getFeedURL: Unable to open the feeds xml file " + fle, xbmc.LOGERROR)
            return ''

        try:
            dom = parse(xml)
        except:
            self.log('getFeedURL: Problem parsing feeds xml file ' + fle, xbmc.LOGERROR)
            xml.close()
            return ''
        xml.close()

        try:
            feedsNode = dom.getElementsByTagName('feed')
        except:
            self.log('getFeedURL: No feeds found ' + fle, xbmc.LOGERROR)
            xml.close()
            return ''
        xml.close()
   
        # need to redo this for loop
        for feed in feedsNode:
            feedName = feed.childNodes[0].nodeValue
            if str(feedName) == str(chname):
                # get feed URL attribute value                
                try:
                    feedURL = feed.getAttribute('url')
                    self.log("feedURL " + str(feedURL))
                except:
                    self.log("Error getting feed url")
                    feedURL = ''
                    

        return feedURL
     

    def getFeedXML(self, url):
        self.log("getFeedXML")
        self.log("url " + str(self.uncleanString(url)))
        feedXML = ''
        try:
            feed_request = urllib2.Request(self.uncleanString(url))
            #feed_request.add_header('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.8.1.14) Gecko/20080404 Firefox/2.0.0.14')
            feed_opener = urllib2.build_opener()
            feedXML = feed_opener.open(feed_request).read()
        except:
            self.log("Unable to open feed URL")
        #self.log("feedXML = " + str(feedXML))
        return feedXML


    def getTrailerInterval(self, channel, numfiles):
        self.log("getTrailerInterval")
        trailerInterval = ''
        numTrailers = REAL_SETTINGS.getSetting("numtrailers")
        maxTrailers = REAL_SETTINGS.getSetting("maxtrailers")
        
        if numTrailers == "":
            trailerInterval = 0
            
        elif numTrailers == "0":
            # need to determine how many commercials are available compared with number of files in tv channel to get a ratio
            numTotalTrailers = len(self.getTrailersList(channel))

            if numTotalTrailers > 0:
                trailerInterval = int(numfiles) / numTotalTrailers
                # if there are more commercials than files in the channel, set interval to 1
                if trailerInterval < 1:
                    trailerInterval = 1
            else:
                trailerInterval = 0
        else:
            trailerInterval = 1
            
        return trailerInterval


    def getTrailerNum(self, channel, numfiles):
        self.log("getTrailerNum")
        trailerInterval = ''
        numTrailers = REAL_SETTINGS.getSetting("numtrailers")
        maxTrailers = REAL_SETTINGS.getSetting("maxtrailers")

        if numTrailers == "":
            numTrailers = 0
            
        elif numTrailers == "0":
            # need to determine how many commercials are available compared with number of files in tv channel to get a ratio
            numTotalTrailers = len(self.getTrailersList(channel))

            if numTotalTrailers > 0:
                numTrailers = numTotalTrailers / int(numfiles)
                if numTrailers < 1:
                    numTrailers = 1
                if numTrailers > maxTrailers:
                    numTrailers = maxTrailers
            else:
                numTrailers = 0
            
        return numTrailers


    def getCommercialInterval(self, channel, numfiles):
        self.log("getCommercialInterval")
        commercialInterval = ''
        numCommercials = REAL_SETTINGS.getSetting("numcommercials")
        maxCommercials = int(REAL_SETTINGS.getSetting("maxcommercials")) + 1

        # check if number of commercials set to auto
        if numCommercials == "":
            commercialInterval = 0
            
        elif numCommercials == "0":
            # need to determine how many commercials are available compared with number of files in tv channel to get a ratio
            numTotalCommercials = len(self.getCommercialsList(channel))

            if numTotalCommercials > 0:
                commercialInterval = int(numfiles) / numTotalCommercials
                # if there are more commercials than files in the channel, set interval to 1
                if commercialInterval < 1:
                    commercialInterval = 1
            else:
                commercialInterval = 0
        else:
            commercialInterval = 1

        return commercialInterval


    def getCommercialNum(self, channel, numfiles):
        self.log("getCommercialNum")
        numCommercials = REAL_SETTINGS.getSetting("numcommercials")
        maxCommercials = int(REAL_SETTINGS.getSetting("maxcommercials")) + 1

        # check if number of commercials set to auto
        if numCommercials == "":
            numCommercials = 0
            
        elif numCommercials == "0":
            # need to determine how many commercials are available compared with number of files in tv channel to get a ratio
            numTotalCommercials = len(self.getCommercialsList(channel))

            if numTotalCommercials > 0:
                numCommercials = numTotalCommercials / int(numfiles)
                if numCommercials < 1:
                    numCommercials = 1
                if numCommercials > maxCommercials:
                    numCommercials = maxCommercials
            else:
                numCommercials = 0

        return numCommercials


    def getBumperInterval(self, channel, numfiles):
        self.log("getBumperInterval")
        bumperInterval = ''
        numBumpers = REAL_SETTINGS.getSetting("numbumpers")
        maxBumpers = REAL_SETTINGS.getSetting("maxbumpers")

        # check if number of commercials set to auto
        if numBumpers == "":
            bumperInterval = 0
            
        elif numBumpers == "0":
            # need to determine how many bumpers are available compared with number of files in tv channel to get a ratio
            numTotalBumpers = len(self.getBumpersList(channel))

            if numTotalBumpers > 0:
                bumperInterval = int(numfiles) / numTotalBumpers
                # if there are more bumpers than files in the channel, set interval to 1
                if bumperInterval < 1:
                    bumperInterval = 1
            else:
                bumperInterval = 0
        else:
            bumperInterval = 1                

        return bumperInterval


    def getBumperNum(self, channel, numfiles):
        numBumpers = REAL_SETTINGS.getSetting("numbumpers")
        maxBumpers = REAL_SETTINGS.getSetting("maxbumpers")
        bumpersFolder = REAL_SETTINGS.getSetting("bumpersfolder")
        channelName = ADDON_SETTINGS.getSetting("Channel_" + str(channel) + "_3")
        # check if number of commercials set to auto
        if numBumpers == "":
            numBumpers = 0
            
        elif numBumpers == "0":
            # need to determine how many bumpers are available compared with number of files in tv channel to get a ratio
            numTotalBumpers = len(self.getBumpersList(channel))

            if numTotalBumpers > 0:
                # need to determine number of bumpers to play during interval
                numBumpers = numTotalBumpers / int(numfiles)
                if numBumpers < 1:
                    numBumpers = 1
                if numBumpers > maxBumpers:
                    numBumpers = maxBumpers
            else:
                numBumpers = 0

        return numBumpers

    """
    def getTotalDuration(self, channel):
        try:
            fileList = open(CHANNELS_LOC + "channel_" + str(channel) + ".m3u", "r")
        except:
            self.Error('getTotalDuration: Unable to open the cache file ' + location + 'channel_' + str(channel) + '.m3u', xbmc.LOGERROR)

        totalDuration = 0
        i = 0
        for string in fileList:
            # capture duration of final filelist to get total duration for channel
            if string.find("#EXTINF:") == 0:
                string_split = string.split(',')
                string = string_split[0]
                string_split = string.split(':')
                dur = string_split[1]
                totalDuration = totalDuration + int(dur)
            i = i + 1
        fileList.close()
                
        return totalDuration
    """

    def getPlaylist(self, fle):
        try:
            xml = open(fle, "r")
        except:
            self.log("getPlaylist: Unable to open the smart playlist " + fle, xbmc.LOGERROR)
            return ''
        try:
            dom = parse(xml)
        except:
            self.log('getPlaylist: Problem parsing playlist ' + fle, xbmc.LOGERROR)
            xml.close()
            return ''
        xml.close()
        return dom


    """
    Combines multiple tv show file lists into a single file list
    Loops through file lists and inserts one file from each list
    until the limit is reached.  This ensures there is an even mix
    of tv shows in the channel
    """
    def buildMixedTVShowFileList(self, fileLists, channel, chname, randomlists):
        self.log("buildMixedTVShowFileList")
        fileList = []
        maxFileListItems = 0
        numTotalItems = 0
        
        if randomlists == "":
            randomlists = 0

        # get fileList sizes
        for i in range(len(fileLists)):
            numTotalItems = numTotalItems + len(fileLists[i].list)            
            if len(fileLists[i].list) > maxFileListItems:
                maxFileListItems = len(fileLists[i].list)

        if int(randomlists) == int(MODE_RANDOM_FILELISTS):
            random.shuffle(fileLists)
            
        # make sure we have files in the lists
        if maxFileListItems > 0:
            # loop through filelists for each item using maxFileList Items
            for i in range(maxFileListItems):
                # loop through each filelist in fileLists
                fl = 0 
                for fl in range(len(fileLists)):
                    # if i is less than number items in filelist then get next item
                    if i < len(fileLists[fl].list):
                        fileList.append(fileLists[fl].list[i])
                    fl = fl + 1                

        # limit filelist
        fileList = fileList[0:int(self.limit)]
        self.log(str(fileList))
        return fileList


    """
    Builds a filelist based on a set of filelists.
    Determines the ratio of movies, episodes and tv shows
    based on the number of files in each list.
    Determines the order to insert files based on where they
    first appeared in the file lists
    """
    def buildMixedFileList(self, fileLists, channel, randomlists):
        i = 0
        numMovieItems = 0
        numEpisodeItems = 0
        numTVShowItems = 0
        ratioMovies = 0
        ratioEpisodes = 0
        ratioTVShows = 0
        itemMultiplier = 0
        movieIndex = 999
        episodeIndex = 999
        tvshowIndex = 999
        movieList = []
        episodeList = []
        tvshowList = []
        fileList = []

        # create seperate lists for each type
        for i in range(len(fileLists)):
            # there could be multiple movie lists so merge into a single movie list
            if fileLists[i].type == "movies":
                if int(movieIndex) == 999:
                    movieIndex = i
                numMovieItems = numMovieItems + len(fileLists[i].list)
                movieList.extend(fileLists[i].list)
            # there could be multiple episode lists so merge into a single episode list
            elif fileLists[i].type == "episodes":
                if int(episodeIndex) == 999:
                    episodeIndex = i
                numEpisodeItems = numEpisodeItems + len(fileLists[i].list)
                episodeList.extend(fileLists[i].list)
            # there could be multiple tvshow lists so merge into a single tvshow list
            elif fileLists[i].type == "tvshows":
                if int(tvshowIndex) == 999:
                    tvshowIndex = i
                numTVShowItems = numTVShowItems + len(fileLists[i].list)
                tvshowList.extend(fileLists[i].list)

        # randomize if playlist order set to random
        if int(randomlists) == int(MODE_RANDOM_FILELISTS):
            random.shuffle(movieList)
            random.shuffle(episodeList)
            random.shuffle(tvshowList)
            
        numTotalItems = numMovieItems + numEpisodeItems + numTVShowItems
        
        if numMovieItems > 0:
            ratioMovies = int(round(numTotalItems / numMovieItems))

        if numEpisodeItems > 0:
            ratioEpisodes = int(round(numTotalItems / numEpisodeItems))

        if numTVShowItems > 0:
            ratioTVShows = int(round(numTotalItems / numTVShowItems))

        if int(ratioMovies) > 0 or int(ratioEpisodes) > 0 or int(ratioTVShows):
            itemMultiplier = int(round(int(limit)/(int(ratioMovies) + int(ratioEpisodes) + int(ratioTVShows))))
        else:
            itemMultiplier = 0

        numMovies = itemMultiplier * ratioMovies
        numEpisodes = itemMultiplier * ratioEpisodes
        numTVShows = itemMultiplier * ratioTVShows

        # get a subset of items based on the number required
        movieSeq = []
        episodeSeq = []
        tvshowSeq = []

        movieSeq = movieList[0:numMovies]
        episodeSeq = episodeList[0:numEpisodes]
        tvshowSeq = tvshowList[0:numTVShows]

        # build the final fileList for the channel
        if int(movieIndex) < int(episodeIndex) and int(movieIndex) < tvshowIndex:
            # add movie files first
            fileList.extend(movieSeq)

            if int(episodeIndex) < int(tvshowIndex):
                # add episode files second
                fileList.extend(episodeSeq)

                if int(tvshowIndex) > int(episodeIndex):
                    #add tvshow files third
                    fileList.extend(tvshowSeq)
            
            elif int(tvshowIndex) < int(episodeIndex):
                # add tvshow files second
                fileList.extend(tvShowSeq)
            
                if int(episodeIndex) > int(tvshowIndex):
                    #add episodes files third
                    fileList.extend(episodeSeq)
        
        elif int(episodeIndex) < int(movieIndex) and int(episodeIndex) < int(tvshowIndex):
            # add episde files first
            fileList.extend(episodeSeq)
        
            if int(movieIndex) < int(tvshowIndex):
                # add movie files second
                fileList.extend(movieSeq)
        
                if int(tvshowIndex) > int(movieIndex):
                    #add tvshow files third
                    fileList.extend(tvshowSeq)
        
            elif int(tvshowIndex) < int(movieIndex):
                # add tvshow files second
                fileList.extend(tvshowSeq)
        
                if int(movieIndex) > int(tvshowIndex):
                    #add movie files third
                    fileList.extend(movieSeq)
        
        elif int(tvshowIndex) < int(movieIndex) and int(tvshowIndex) < int(episodeIndex):
            # add tvshow files first
            fileList.extend(tvshowSeq)
        
            if int(movieIndex) < int(episodeIndex):
                # add movie files second
                fileList.extend(movieSeq)
        
                if int(episodeIndex) > int(movieIndex):
                    #add episode files third
                    fileList.extend(episodeSeq)
        
            elif int(episodeIndex) < int(movieIndex):
                # add episode files second
                fileList.extend(episodeSeq)
        
                if int(movieIndex) > int(episodeIndex):
                    #add movie files third
                    fileList.extend(movieSeq)

        # limit filelist
        fileList = fileList[0:int(limit)]

        return fileList


    def getTitle(self, fpath):
        dbase = os.path.dirname(fpath)
        fbase = os.path.basename(fpath)
        fname = os.path.splitext(fbase)[0]
        tvshowdir = os.path.split(dbase)[(len(os.path.split(dbase))-2)]
        fle = os.path.join(tvshowdir, "series.xml")
        title = ""
        # look for series.xml
        # same folder as file
        if os.path.isfile(fle):
            """
            <Series>
              <SeriesName>Chuck</SeriesName>
            </Series>        
            """
            try:
                dom = parse(fle)
            except:
                self.log("getTVShow: Problem parsing playlist " + fle, xbmc.LOGERROR)
                xml.close()
                return title

            try:
                seriesNameNode = dom.getElementsByTagName('SeriesName')
            except:
                xml.close()
       
            if seriesNameNode:
                try:
                    title = seriesNameNode[0].firstChild.nodeValue
                except:
                    title = ""
                    
        # look for tvshow.nfo
        # same folder as file
        fle = os.path.join(tvshowdir, "tvshow.nfo")
        if os.path.isfile(fle):
            """
            <tvshow>
                <title>Chuck</title>
            </tvshow>
            """
            try:
                dom = parse(fle)
            except:
                self.log("getTVShow: Problem parsing playlist " + fle, xbmc.LOGERROR)
                xml.close()
                return title

            try:
                titleNode = dom.getElementsByTagName('title')
            except:
                xml.close()
       
            if titleNode:
                try:
                    title = titleNode[0].firstChild.nodeValue
                except:
                    title = ""
                    
        # use folder name if all else fails
        if title == "":        
            title = os.path.split(fpath)[(len(os.path.split(fpath))-1)]
        
        return title


    def getShowTitle(self, fpath):
        dbase = os.path.dirname(fpath)
        fbase = os.path.basename(fpath)
        fname = os.path.splitext(fbase)[0]                
        showtitle = ""
        # Media Center Master
        # location = ./metadata
        # filename format = <filename>.xml
        fle = os.path.join(dbase, "metadata", fname + ".xml")
        if os.path.isfile(fle):
            """
            <Item>
              <EpisodeName>Chuck Versus the Intersect</EpisodeName>
              <FirstAired>2007-09-24</FirstAired>
              <Overview>Chuck Bartowski is an average computer geek until files of government secrets are downloaded into his brain. He is soon scouted by the CIA and NSA to act in place of their computer.</Overview>
            </Item>        
            """
            try:
                dom = parse(fle)
            except:
                self.log("getShowTitle: Problem parsing playlist " + fle, xbmc.LOGERROR)
                xml.close()
                return showtitle

            try:
                episodeNameNode = dom.getElementsByTagName('EpisodeName')
            except:
                xml.close()
       
            if episodeNameNode:
                try:
                    showtitle = episodeNameNode[0].firstChild.nodeValue
                except:
                    showtitle = ""
                    
        # XBMC
        # location = same as video files
        # filename format = <filename.nfo
        fle = os.path.join(dbase, fname + ".nfo")
        if os.path.isfile(fle):
            """
            <episodedetails>
                <title>Chuck Versus the Intersect</title>
                <plot>Chuck Bartowski is an average computer geek until files of government secrets are downloaded into his brain. He is soon scouted by the CIA and NSA to act in place of their computer.</plot>
                <aired>2007-09-24</aired>
            </episodedetails>        
            """
            try:
                dom = parse(fle)
            except:
                self.log("getShowTitle: Problem parsing playlist " + fle, xbmc.LOGERROR)
                xml.close()
                return showtitle

            try:
                titleNode = dom.getElementsByTagName('title')
            except:
                xml.close()
       
            if titleNode:
                try:
                    showtitle = titleNode[0].firstChild.nodeValue
                except:
                    showtitle = ""
                    
        # if all else fails, get showtitle from folder
        if showtitle == "":
            showtitle = os.path.split(fpath)[(len(os.path.split(fpath))-2)]

        return showtitle


    def getThePlot(self, fpath):
        self.log("getThePlot")
        dbase = os.path.dirname(fpath)
        fbase = os.path.basename(fpath)
        fname = os.path.splitext(fbase)[0]

        theplot = ""
        # Media Center Master
        # location = ./metadata
        # filename format = <filename>.xml
        fle = os.path.join(dbase, "metadata", fname + ".xml")
        if os.path.isfile(fle):
            # Read the video meta data
            """
            <Item>
              <EpisodeName>Chuck Versus the Intersect</EpisodeName>
              <FirstAired>2007-09-24</FirstAired>
              <Overview>Chuck Bartowski is an average computer geek until files of government secrets are downloaded into his brain. He is soon scouted by the CIA and NSA to act in place of their computer.</Overview>
            </Item>        
            """
            try:
                dom = parse(fle)
            except:
                self.log("getShowTitle: Problem parsing playlist " + fle, xbmc.LOGERROR)
                xml.close()
                return showtitle

            try:
                overviewNode = dom.getElementsByTagName('Overview')
            except:
                xml.close()
       
            if overviewNode:
                try:
                    theplot = overviewNode[0].firstChild.nodeValue
                except:
                    theplot = ""
        # XBMC
        # location = same as video files
        # filename format = <filename.nfo
        fle = os.path.join(dbase, fname + ".nfo")
        if os.path.isfile(fle):
            """
            <episodedetails>
                <title>Chuck Versus the Intersect</title>
                <plot>Chuck Bartowski is an average computer geek until files of government secrets are downloaded into his brain. He is soon scouted by the CIA and NSA to act in place of their computer.</plot>
                <aired>2007-09-24</aired>
            </episodedetails>        
            """
            try:
                dom = parse(fle)
            except:
                self.log("getShowTitle: Problem parsing playlist " + fle, xbmc.LOGERROR)
                xml.close()
                return showtitle

            try:
                plotNode = dom.getElementsByTagName('plot')
            except:
                xml.close()
       
            if plotNode:
                try:
                    theplot = plotNode[0].firstChild.nodeValue
                except:
                    theplot = ""

        return theplot


    def autoTune(self):
        self.log('autoTune')
        
        ADDON_SETTINGS.clearSettings()
                
        channelNum = 0

        self.dlg = xbmcgui.DialogProgress()
        self.dlg.create("TV Time", "Auto Tune")

        progressIndicator = 0
        # need to get number of Channel_X files in the video and mix folders
        for i in range(500):
            if os.path.exists(xbmc.translatePath('special://profile/playlists/video') + '/Channel_' + str(i + 1) + '.xsp'):
                self.log("Adding Custom Video Playlist Channel")
                channelNum = channelNum + 1
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", xbmc.translatePath('special://profile/playlists/video/') + 'Channel_' + str(i + 1) + '.xsp')
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", self.cleanString(self.getSmartPlaylistName(xbmc.translatePath('special://profile/playlists/video') + '/Channel_' + str(i + 1) + '.xsp')))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_playlist", xbmc.translatePath('special://profile/playlists/video/') + 'Channel_' + str(i + 1) + '.xsp')
                self.dlg.update(progressIndicator,"Auto Tune","Found " + str(self.getSmartPlaylistName(xbmc.translatePath('special://profile/playlists/video') + '/Channel_' + str(i + 1) + '.xsp')),"")
            elif os.path.exists(xbmc.translatePath('special://profile/playlists/mixed') + '/Channel_' + str(i + 1) + '.xsp'):
                self.log("Adding Custom Mixed Playlist Channel")
                channelNum = channelNum + 1
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", xbmc.translatePath('special://profile/playlists/mixed/') + 'Channel_' + str(i + 1) + '.xsp')
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", self.cleanString(self.getSmartPlaylistName(xbmc.translatePath('special://profile/playlists/mixed') + '/Channel_' + str(i + 1) + '.xsp')))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_playlist", xbmc.translatePath('special://profile/playlists/mixed/') + 'Channel_' + str(i + 1) + '.xsp')
                self.dlg.update(progressIndicator,"Auto Tune","Found " + str(self.getSmartPlaylistName(xbmc.translatePath('special://profile/playlists/mixed') + '/Channel_' + str(i + 1) + '.xsp')),"")
            elif os.path.exists(xbmc.translatePath('special://profile/playlists/music') + '/Channel_' + str(i + 1) + '.xsp'):
                self.log("Adding Custom Music Playlist Channel")
                channelNum = channelNum + 1
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", xbmc.translatePath('special://profile/playlists/music/') + 'Channel_' + str(i + 1) + '.xsp')
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", self.cleanString(self.getSmartPlaylistName(xbmc.translatePath('special://profile/playlists/music') + '/Channel_' + str(i + 1) + '.xsp')))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_playlist", xbmc.translatePath('special://profile/playlists/music/') + 'Channel_' + str(i + 1) + '.xsp')
                self.dlg.update(progressIndicator,"Auto Tune","Found " + str(self.getSmartPlaylistName(xbmc.translatePath('special://profile/playlists/music') + '/Channel_' + str(i + 1) + '.xsp')),"")
            #i = i + 1
        
        progressIndicator = 10
        if (REAL_SETTINGS.getSetting("autoFindNetworks") == "true" or REAL_SETTINGS.getSetting("autoFindTVGenres") == "true"):
            self.log("Searching for TV Channels")
            self.dlg.update(progressIndicator,"Auto Tune","Searching for TV Channels","")
            self.fillTVInfo()

        # need to add check for auto find network channels
        progressIndicator = 20
        if REAL_SETTINGS.getSetting("autoFindNetworks") == "true":
            self.log("Adding TV Networks")
            self.dlg.update(progressIndicator,"Auto Tune","Adding TV Networks","")
            for i in range(len(self.networkList)):
                channelNum = channelNum + 1
                # add network presets
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "1")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", str(self.networkList[i]))
                if REAL_SETTINGS.getSetting("autoFindNetworks_serial") == "true":
                    serial = 1
                else:
                    serial = 0
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(serial))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", str(self.networkList[i]))
                if REAL_SETTINGS.getSetting("autoFindNetworks_unwatched") == "true":
                    unwatched = 1
                else:
                    unwatched = 0
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(unwatched))
                if REAL_SETTINGS.getSetting("autoFindNetworks_nospecials") == "true":
                    nospecials = 1
                else:
                    nospecials = 0
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(nospecials))
                resolution = int(REAL_SETTINGS.getSetting("autoFindNetworks_resolution"))
                if resolution == 0:
                    resolution = "All"
                elif resolution == 1:
                    resolution = "SD Only"
                elif resolution == 2:
                    resolution = "720p or Higher"
                elif resolution == 3:
                    resolution = "1080p Only"                    
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(resolution))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(""))
                if REAL_SETTINGS.getSetting("autoFindNetworks_randtvshows") == "true":
                    randtvshows = 1
                else:
                    randtvshows = 0
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(randtvshows))
                ADDON_SETTINGS.setSetting('Channel_' + str(channelNum) + '_changed', 'True')
                self.dlg.update(progressIndicator,"Auto Tune","Adding TV Network",str(self.networkList[i]))

        progressIndicator = 30
        if REAL_SETTINGS.getSetting("autoFindTVGenres") == "true":
            self.log("Adding TV Genres")
            self.dlg.update(progressIndicator,"Auto Tune","Adding TV Genres","")
            for i in range(len(self.showGenreList)):
                channelNum = channelNum + 1
                # add network presets
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "3")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", str(self.showGenreList[i]))
                if REAL_SETTINGS.getSetting("autoFindTVGenres_serial") == "true":
                    serial = 1
                else:
                    serial = 0
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(serial))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", str(self.showGenreList[i]) + ' TV')
                if REAL_SETTINGS.getSetting("autoFindTVGenres_unwatched") == "true":
                    unwatched = 1
                else:
                    unwatched = 0
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(unwatched))
                if REAL_SETTINGS.getSetting("autoFindTVGenres_nospecials") == "true":
                    nospecials = 1
                else:
                    nospecials = 0
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(nospecials))
                resolution = int(REAL_SETTINGS.getSetting("autoFindTVGenres_resolution"))
                if resolution == 0:
                    resolution = "All"
                elif resolution == 1:
                    resolution = "SD Only"
                elif resolution == 2:
                    resolution = "720p or Higher"
                elif resolution == 3:
                    resolution = "1080p Only"                    
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(resolution))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(""))
                ADDON_SETTINGS.setSetting('Channel_' + str(channelNum) + '_changed', 'True')
                self.dlg.update(progressIndicator,"Auto Tune","Adding TV Genres",str(self.showGenreList[i]) + " TV")
        
        progressIndicator = 40
        if (REAL_SETTINGS.getSetting("autoFindStudios") == "true" or REAL_SETTINGS.getSetting("autoFindMovieGenres") == "true"):
            self.dlg.update(progressIndicator,"Auto Tune","Searching for Movie Channels","")
            self.fillMovieInfo()

        progressIndicator = 50
        if REAL_SETTINGS.getSetting("autoFindStudios") == "true":
            self.log("Adding Movie Studios")
            self.dlg.update(progressIndicator,"Auto Tune","Adding Movie Studios","")
            for i in range(len(self.studioList)):
                channelNum = channelNum + 1
                progressIndicator = progressIndicator + (10/len(self.studioList))
                # add network presets
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "2")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", str(self.studioList[i]))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", str(self.studioList[i]))
                if REAL_SETTINGS.getSetting("autoFindStudios_unwatched") == "true":
                    unwatched = 1
                else:
                    unwatched = 0
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(unwatched))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(""))
                resolution = int(REAL_SETTINGS.getSetting("autoFindStudios_resolution"))
                if resolution == 0:
                    resolution = "All"
                elif resolution == 1:
                    resolution = "SD Only"
                elif resolution == 2:
                    resolution = "720p or Higher"
                elif resolution == 3:
                    resolution = "1080p Only"                    
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(resolution))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(""))
                ADDON_SETTINGS.setSetting('Channel_' + str(channelNum) + '_changed', 'True')
                self.dlg.update(progressIndicator,"Auto Tune","Adding Movie Studios",str(self.studioList[i]))

        progressIndicator = 60
        if REAL_SETTINGS.getSetting("autoFindMovieGenres") == "true":
            self.log("Adding Movie Genres")
            self.dlg.update(progressIndicator,"Auto Tune","Adding Movie Genres","")
            for i in range(len(self.movieGenreList)):
                channelNum = channelNum + 1
                progressIndicator = progressIndicator + (10/len(self.movieGenreList))
                # add network presets
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "4")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", str(self.movieGenreList[i]))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", str(self.movieGenreList[i]) + ' Movies')
                if REAL_SETTINGS.getSetting("autoFindMovieGenres_unwatched") == "true":
                    unwatched = 1
                else:
                    unwatched = 0
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(unwatched))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(""))
                resolution = int(REAL_SETTINGS.getSetting("autoFindMovieGenres_resolution"))
                if resolution == 0:
                    resolution = "All"
                elif resolution == 1:
                    resolution = "SD Only"
                elif resolution == 2:
                    resolution = "720p or Higher"
                elif resolution == 3:
                    resolution = "1080p Only"                    
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(resolution))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(""))
                ADDON_SETTINGS.setSetting('Channel_' + str(channelNum) + '_changed', 'True')
                self.dlg.update(progressIndicator,"Auto Tune","Adding Movie Genres","Found " + str(self.movieGenreList[i]) + " Movies")

        progressIndicator = 65
        if REAL_SETTINGS.getSetting("autoFindMixGenres") == "true":
            self.dlg.update(progressIndicator,"Auto Tune","Searching for Mixed Channels","")
            self.fillMixedGenreInfo()
        
        progressIndicator = 70
        if REAL_SETTINGS.getSetting("autoFindMixGenres") == "true":
            self.log("Adding Mixed Genres")
            self.dlg.update(progressIndicator,"Auto Tune","Adding Mixed Genres","")
            for i in range(len(self.mixedGenreList)):
                channelNum = channelNum + 1
                # add network presets
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "5")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", str(self.mixedGenreList[i]))
                if REAL_SETTINGS.getSetting("autoFindMixGenres_serial") == "true":
                    serial = 1
                else:
                    serial = 0
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(serial))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", str(self.mixedGenreList[i]) + ' Mix')
                if REAL_SETTINGS.getSetting("autoFindMixGenres_unwatched") == "true":
                    unwatched = 1
                else:
                    unwatched = 0
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(unwatched))
                if REAL_SETTINGS.getSetting("autoFindMixGenres_nospecials") == "true":
                    nospecials = 1
                else:
                    nospecials = 0
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(nospecials))
                resolution = int(REAL_SETTINGS.getSetting("autoFindMixGenres_resolution"))
                if resolution == 0:
                    resolution = "All"
                elif resolution == 1:
                    resolution = "SD Only"
                elif resolution == 2:
                    resolution = "720p or Higher"
                elif resolution == 3:
                    resolution = "1080p Only"                    
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(resolution))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(REAL_SETTINGS.getSetting("autoFindMixGenres_numepisodes")))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(REAL_SETTINGS.getSetting("autoFindMixGenres_nummovies")))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(""))
                ADDON_SETTINGS.setSetting('Channel_' + str(channelNum) + '_changed', 'True')
                self.dlg.update(progressIndicator,"Auto Tune","Adding Mixed Genres",str(self.mixedGenreList[i]) + " Mix")

        progressIndicator = 80
        if REAL_SETTINGS.getSetting("autoFindMusicGenres") == "true":
            self.dlg.update(progressIndicator,"Auto Tune","Searching for Music Channels","")
            self.fillMusicInfo()

        progressIndicator = 85
        if REAL_SETTINGS.getSetting("autoFindMusicGenres") == "true":
            self.log("Adding Music Genres")
            self.dlg.update(progressIndicator,"Auto Tune","Adding Music Genres","")
            for i in range(len(self.musicGenreList)):
                channelNum = channelNum + 1
                # add network presets
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "8")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", str(self.musicGenreList[i]))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", str(self.musicGenreList[i]) + ' Music')
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(""))
                ADDON_SETTINGS.setSetting('Channel_' + str(channelNum) + '_changed', 'True')
                self.dlg.update(progressIndicator,"Auto Tune","Adding Music Genres",str(self.musicGenreList[i]) + " Music")

        progressIndicator = 90
        if REAL_SETTINGS.getSetting("autoFindLive") == "true":
            self.dlg.update(progressIndicator,"Auto Tune","Searching for Live Channels","")
            self.fillFeedInfo()

        progressIndicator = 95
        if REAL_SETTINGS.getSetting("autoFindLive") == "true":
            self.log("Adding Live Channel")
            self.dlg.update(progressIndicator,"Auto Tune","Adding Live Channel","")
            for i in range(len(self.feedList)):
                channelNum = channelNum + 1
                # add network presets
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "9")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", str(self.feedList[i]))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", str(self.feedList[i]))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(""))
                ADDON_SETTINGS.setSetting('Channel_' + str(channelNum) + '_changed', 'True')
                self.dlg.update(progressIndicator,"Auto Tune","Adding Live Channel",str(self.feedList[i]))

        ADDON_SETTINGS.writeSettings()

        # reset auto tune settings
        REAL_SETTINGS.setSetting("autoFindNetworks","false")
        REAL_SETTINGS.setSetting("autoFindStudios","false")
        REAL_SETTINGS.setSetting("autoFindTVGenres","false")
        REAL_SETTINGS.setSetting("autoFindMovieGenres","false")
        REAL_SETTINGS.setSetting("autoFindMixGenres","false")
        REAL_SETTINGS.setSetting("autoFindTVShows","false")
        REAL_SETTINGS.setSetting("autoFindMusicGenres","false")
        REAL_SETTINGS.setSetting("autoFindLive","false")
        
        # force a reset
        REAL_SETTINGS.setSetting("ForceChannelReset","true")

        self.dlg.close()


    def fillMixedGenreInfo(self):
        if len(self.mixedGenreList) == 0:
            if len(self.showGenreList) == 0:
                self.fillTVInfo()
            if len(self.movieGenreList) == 0:
                self.fillMovieInfo()

            self.mixedGenreList = self.makeMixedList(self.showGenreList, self.movieGenreList)
            self.mixedGenreList.sort(key=lambda x: x.lower())


    def loadCustomPlaylists(self):
        # read in channel playlists in video, music and mixed folders
        channelNum = 0
        for i in range(500):
            if os.path.exists(xbmc.translatePath('special://profile/playlists/video') + '/Channel_' + str(i + 1) + '.xsp'):
                channelNum = channelNum + 1
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", xbmc.translatePath('special://profile/playlists/video/') + 'Channel_' + str(i + 1) + '.xsp')
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", self.cleanString(self.getSmartPlaylistName(xbmc.translatePath('special://profile/playlists/video') + '/Channel_' + str(i + 1) + '.xsp')))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_playlist", xbmc.translatePath('special://profile/playlists/video/') + 'Channel_' + str(i + 1) + '.xsp')
                #self.updateDialog(progressIndicator,"Auto Tune","Found " + str(self.getSmartPlaylistName(xbmc.translatePath('special://profile/playlists/video') + '/Channel_' + str(i + 1) + '.xsp')),"")
            elif os.path.exists(xbmc.translatePath('special://profile/playlists/mixed') + '/Channel_' + str(i + 1) + '.xsp'):
                channelNum = channelNum + 1
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", xbmc.translatePath('special://profile/playlists/mixed/') + 'Channel_' + str(i + 1) + '.xsp')
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", self.cleanString(self.getSmartPlaylistName(xbmc.translatePath('special://profile/playlists/mixed') + '/Channel_' + str(i + 1) + '.xsp')))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_playlist", xbmc.translatePath('special://profile/playlists/mixed/') + 'Channel_' + str(i + 1) + '.xsp')
                #self.updateDialog(progressIndicator,"Auto Tune","Found " + str(self.getSmartPlaylistName(xbmc.translatePath('special://profile/playlists/mixed') + '/Channel_' + str(i + 1) + '.xsp')),"")
            elif os.path.exists(xbmc.translatePath('special://profile/playlists/music') + '/Channel_' + str(i + 1) + '.xsp'):
                channelNum = channelNum + 1
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_type", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_time", "0")
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_1", xbmc.translatePath('special://profile/playlists/music/') + 'Channel_' + str(i + 1) + '.xsp')
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_2", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_3", self.cleanString(self.getSmartPlaylistName(xbmc.translatePath('special://profile/playlists/music') + '/Channel_' + str(i + 1) + '.xsp')))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_4", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_5", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_6", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_7", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_8", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_9", str(""))
                ADDON_SETTINGS.setSetting("Channel_" + str(channelNum) + "_playlist", xbmc.translatePath('special://profile/playlists/music/') + 'Channel_' + str(i + 1) + '.xsp')
                #self.updateDialog(progressIndicator,"Auto Tune","Found " + str(self.getSmartPlaylistName(xbmc.translatePath('special://profile/playlists/music') + '/Channel_' + str(i + 1) + '.xsp')),"")
        ADDON_SETTINGS.writeSettings()


    def buildMetaFiles(self):
        self.dlg = xbmcgui.DialogProgress()
        self.dlg.create("TV Time", "Initializing")
        progressIndicator = 0
        if REAL_SETTINGS.getSetting("bumpers"):
            if not os.path.exists(META_LOC + "bumpers.meta"):
                # prompt user that we need to build this meta file
                self.dlg.update(progressIndicator,"Initializing","Creating Bumper File List")
                bumpersfolder = REAL_SETTINGS.getSetting("bumpersfolder")
                if len(bumpersfolder) > 0:
                    self.buildMetaFile("bumpers",bumpersfolder)

        if REAL_SETTINGS.getSetting("commercials"):
            if not os.path.exists(META_LOC + "commercials.meta"):
                # prompt user that we need to build this meta file
                self.dlg.update(progressIndicator,"Initializing","Creating Commercial File List")
                commercialsfolder = REAL_SETTINGS.getSetting("commercialsfolder")
                if len(commercialsfolder) > 0:
                    self.buildMetaFile("commercials",commercialsfolder)

        if REAL_SETTINGS.getSetting("trailers"):
            if not os.path.exists(META_LOC + "trailers.meta"):
                # prompt user that we need to build this meta file
                self.dlg.update(progressIndicator,"Initializing","Creating Trailer File List")
                trailersfolder = REAL_SETTINGS.getSetting("trailersfolder")
                if len(trailersfolder) > 0:
                    self.buildMetaFile("trailers",trailersfolder)

        self.dlg.close()


    def buildMetaFile(self, type, folder):
        self.log("buildMetaFile")
        self.videoParser = VideoParser()
        flext = [".avi",".mp4",".m4v",".3gp",".3g2",".f4v",".flv",".mkv",".flv"]
        metaFileList = []

        if os.path.exists(folder):
            # get a list of valid filenames from the folder
            fnlist = []
            for root, subFolders, files in os.walk(folder):
                for filename in files:
                    # get file extension
                    basename, extension = os.path.splitext(filename)
                    if extension in flext: # passed first test
                        # get file duration
                        filepath = os.path.join(root, filename)
                        dur = self.videoParser.getVideoLength(filepath)
                        if (dur > 0): # passed second test
                            # let's parse out some file information
                            filename_base = []
                            filename_parts = []
                            filename_parts2 = []
                            filename_base = filename.split(".")
                            filename_parts = filename_base[0].split("_")
                            filename_parts2 = filename_base[0].split("-")
                            if len(filename_parts) > len(filename_parts2):
                                # use filename_parts
                                title = filename_parts[0]
                                if len(filename_parts) > 1:
                                    showtitle = filename_parts[1]
                                else:
                                    showtitle = ""
                                if len(filename_parts) > 2:
                                    description = filename_parts[2]
                                else:
                                    description = ""
                            else:
                                # use filename_parts2
                                title = filename_parts2[0]
                                if len(filename_parts2) > 1:
                                    showtitle = filename_parts2[1]
                                else:
                                    showtitle = ""
                                if len(filename_parts2) > 2:
                                    description = filename_parts2[2]
                                else:
                                    description = ""
                            metastr = str(filepath) + '|' + str(dur) + '|' + str(title) + '|' + str(showtitle) + '|' + str(description)
                            metaFileList.append(metastr)
        self.writeMetaFile(type, metaFileList)


    def writeMetaFile(self, type, metaFileList):
        try:
            metafile = open(META_LOC + str(type) + ".meta", "w")
        except:
            self.Error('Unable to open the meta file ' + META_LOC + str(type) + '.meta', xbmc.LOGERROR)
            return False

        for file in metaFileList:
            metafile.write(file + "\n")

        metafile.close()


    def convertMetaToFile(self, metaFileStr):
        # parse file meta data
        metaFile = []
        metaFile = metaFileStr.split('|')
        thepath = metaFile[0]
        dur = metaFile[1]
        title = metaFile[2]
        showtitle = metaFile[3]
        theplot = metaFile[4]
        title = title.encode('utf-8')
        showtitle = showtitle.encode('utf-8')
        theplot = theplot.encode('utf-8')
        # format to file list structure
        tmpstr = str(dur) + ','
        tmpstr += showtitle + "//" + title + "//" + theplot
        tmpstr = tmpstr[:600]
        tmpstr = tmpstr.replace("\\n", " ").replace("\n", " ").replace("\r", " ").replace("\\r", " ").replace("\\\"", "\"")
        tmpstr = tmpstr + '\n' + thepath.replace("\\\\", "\\")
        return tmpstr


    def insertFiles(self, channel, fileList, commercials, bumpers, trailers, cinterval, binterval, tinterval, cnum, bnum, tnum):
        newFileList = []
        
        if bumpers:
            bumpersList = []
            bumpersList = self.getBumpersList(channel)
            
        if commercials:
            commercialsList = []
            commercialsList = self.getCommercialsList(channel)
        
        if trailers:
            trailersList = []
            trailersList = self.getTrailersList(channel)
        
        for i in range(len(fileList)):
            self.log("fileList " + str(fileList[i]))
            newFileList.append(fileList[i])
            if commercials:
                if len(commercialsList) > 0:
                    if (i+1) % cinterval == 0:
                        for n in range(int(cnum)):
                            commercialFile = random.choice(commercialsList)
                            if len(commercialFile) > 0:
                                newFileList.append(self.convertMetaToFile(commercialFile))
                            else:
                                self.log('insertFiles: Unable to get commercial')                                        
                else:
                    self.log("No valid commercials available")

            if bumpers:
                self.log("bumper interval = " + str(binterval))
                self.log("bumper list length = " + str(len(bumpersList)))
                self.log("bumper number = " + str(bnum))
                if len(bumpersList) > 0:
                    # mix in bumpers
                    self.log("file number = " + str(i+1))
                    if (i+1) % binterval == 0:
                        self.log("inserting bumper")
                        for n in range(int(bnum)):
                            self.log("inserting bumper " + str(n))
                            bumperFile = random.choice(bumpersList)
                            if len(bumperFile) > 0:
                                self.log(str(self.convertMetaToFile(bumperFile)))
                                newFileList.append(self.convertMetaToFile(bumperFile))
                            else:
                                self.log('insertFiles: Unable to get bumper')                                                                
                else:
                    self.log("No valid bumpers available")

            if trailers:
                if len(trailersList) > 0:
                    # mix in trailers
                    if (i+1) % tinterval == 0:
                        for n in range(int(tnum)):
                            trailerFile = random.choice(trailersList)
                            if len(trailerFile) > 0:
                                newFileList.append(self.convertMetaToFile(trailerFile))
                            else:
                                self.log('insertFiles: Unable to get trailer')
                
        fileList = newFileList    

        return fileList


    def getBumpersList(self, channel):
        self.log("getBumpersList")
        bumpersList = []
        chname = ADDON_SETTINGS.getSetting("Channel_" + str(channel) + "_3")
        type = "bumpers"

        try:
            metafile = open(META_LOC + str(type) + ".meta", "r")
        except:
            self.Error('Unable to open the meta file ' + META_LOC + str(type) + '.meta', xbmc.LOGERROR)
            return False

        for file in metafile:
            # filter by channel name
            bumperMeta = []
            bumperMeta = file.split('|')
            thepath = bumperMeta[0]
            basepath = os.path.dirname(thepath)
            chfolder = os.path.split(basepath)[1]
            # bumpers are channel specific
            if chfolder == chname:
                bumpersList.append(file)

        metafile.close()

        return bumpersList


    def getCommercialsList(self, channel):
        self.log("getCommercialsList")
        commercialsList = []
        chname = ADDON_SETTINGS.getSetting("Channel_" + str(channel) + "_3")
        type = "commercials"
        channelOnlyCommercials = False

        try:
            metafile = open(META_LOC + str(type) + ".meta", "r")
        except:
            self.Error('Unable to open the meta file ' + META_LOC + str(type) + '.meta', xbmc.LOGERROR)
            return False

        for file in metafile:
            # filter by channel name
            commercialMeta = []
            commercialMeta = file.split('|')
            thepath = commercialMeta[0]
            basepath = os.path.dirname(thepath)
            chfolder = os.path.split(basepath)[1]
            if chfolder == chname:
                if channelOnlyCommercials:
                    # channel specific trailers are in effect
                    commercialsList.append(file)
                else:
                    # reset list to only contain channel specific trailers
                    channelOnlyCommercials = True
                    commercialsList = []
                    commercialsList.append(file)
            else:
                if not channelOnlyCommercials:
                    commercialsList.append(file)

        metafile.close()

        return commercialsList


    def getTrailersList(self, channel):
        self.log("getTrailersList")
        trailersList = []
        chname = ADDON_SETTINGS.getSetting("Channel_" + str(channel) + "_3")
        type = "trailers"
        channelOnlyTrailers = False

        try:
            metafile = open(META_LOC + str(type) + ".meta", "r")
        except:
            self.log('Unable to open the meta file ' + META_LOC + str(type) + '.meta')
            return False

        for file in metafile:
            # filter by channel name
            trailerMeta = []
            trailerMeta = file.split('|')
            thepath = trailerMeta[0]
            basepath = os.path.dirname(thepath)
            chfolder = os.path.split(basepath)[1]
            if chfolder == chname:
                if channelOnlyTrailers:
                    # channel specific trailers are in effect
                    trailersList.append(file)
                else:
                    # reset list to only contain channel specific trailers
                    channelOnlyTrailers = True
                    trailersList = []
                    trailersList.append(file)
            else:
                if not channelOnlyTrailers:
                    trailersList.append(file)

        metafile.close()

        return trailersList
    ###############


    def fillTVInfo(self):
        self.log("fillTVInfo")
        json_query = '{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": {"fields":["studio", "genre"]}, "id": 1}'
        json_folder_detail = self.sendJSON(json_query)
        #self.log(json_folder_detail)
        detail = re.compile( "{(.*?)}", re.DOTALL ).findall(json_folder_detail)

        for f in detail:
            if self.threadPause() == False:
                del self.networkList[:]
                del self.showList[:]
                del self.showGenreList[:]
                break

            match = re.search('"studio" *: *"(.*?)",', f)
            network = ''

            if match:
                found = False
                network = match.group(1).strip()

                for item in self.networkList:
                    if item.lower() == network.lower():
                        found = True
                        break

                if found == False and len(network) > 0:
                    self.networkList.append(network)

        ### TV TIME ###
        #    match = re.search('"label" *: *"(.*?)",', f)
        
        #    if match:
        #        show = match.group(1).strip()
        #        self.showList.append([show, network])

        #    match = re.search('"genre" *: *"(.*?)",', f)

        #    if match:
        #        genres = match.group(1).split('/')

        #        for genre in genres:
        #            found = False
        #            curgenre = genre.lower().strip()

        #            for g in self.showGenreList:
        #                if curgenre == g.lower():
        #                    found = True
        #                    break

        #            if found == False:
        #                self.showGenreList.append(genre.strip())        
            match = re.search('"genre" *: *"(.*?)",', f)

            if match:
                genres = match.group(1).split('/')

                for genre in genres:
                    found = False
                    curgenre = genre.lower().strip()

                    for g in self.showGenreList:
                        if curgenre == g.lower():
                            found = True
                            break

                    if found == False:
                        self.showGenreList.append(genre.strip())        

            match = re.search('"label" *: *"(.*?)",', f)

            if match:
                show = match.group(1).strip()
                genre = genre.strip()
                self.showList.append([show, network, genre])
        ###############

        self.networkList.sort(key=lambda x: x.lower())
        self.showGenreList.sort(key=lambda x: x.lower())
        self.log("found shows " + str(self.showList))
        self.log("found genres " + str(self.showGenreList))
        self.log("fillTVInfo return " + str(self.networkList))


    def fillMovieInfo(self):
        self.log("fillMovieInfo")
        studioList = []
        json_query = '{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"fields":["studio", "genre"]}, "id": 1}'
        json_folder_detail = self.sendJSON(json_query)
        #self.log(json_folder_detail)
        detail = re.compile( "{(.*?)}", re.DOTALL ).findall(json_folder_detail)

        for f in detail:
            if self.threadPause() == False:
                del self.movieGenreList[:]
                del self.studioList[:]
                del studioList[:]
                break

            match = re.search('"genre" *: *"(.*?)",', f)

            if match:
                genres = match.group(1).split('/')

                for genre in genres:
                    found = False
                    curgenre = genre.lower().strip()

                    for g in self.movieGenreList:
                        if curgenre == g.lower():
                            found = True
                            break

                    if found == False:
                        self.movieGenreList.append(genre.strip())

            match = re.search('"studio" *: *"(.*?)",', f)

            if match:
                studios = match.group(1).split('/')

                for studio in studios:
                    curstudio = studio.strip()
                    found = False

                    for i in range(len(studioList)):
                        if studioList[i][0].lower() == curstudio.lower():
                            studioList[i][1] += 1
                            found = True

                    if found == False and len(curstudio) > 0:
                        studioList.append([curstudio, 1])
        
        ### TV TIME ###
        """
        maxcount = 0

        for i in range(len(studioList)):
            if studioList[i][1] > maxcount:
                maxcount = studioList[i][1]

        bestmatch = 1
        lastmatch = 1000

        for i in range(maxcount, 0, -1):
            itemcount = 0

            for j in range(len(studioList)):
                if studioList[j][1] == i:
                    itemcount += 1

            if abs(itemcount - 15) < abs(lastmatch - 15):
                bestmatch = i
                lastmatch = itemcount

        for i in range(len(studioList)):
            if studioList[i][1] == bestmatch:
                self.studioList.append(studioList[i][0])
        """
        studioList.sort(key=itemgetter(1), reverse=True)
        for i in range(len(studioList)):
            self.log(str(studioList[i]))
            
        ### TV TIME ###
        maxsize = int(REAL_SETTINGS.getSetting("maxMovieGenres"))            
        
        for i in range(len(studioList)):
            if maxsize > 0:
                if i < maxsize:
                    self.studioList.append(studioList[i][0])
            else:
                self.studioList.append(studioList[i][0])

        #for i in range(len(studioList)):
        #    if i < maxsize:
        #        self.studioList.append(studioList[i][0])        
        ###############
        self.studioList.sort(key=lambda x: x.lower())
        self.movieGenreList.sort(key=lambda x: x.lower())
        self.log("found genres " + str(self.movieGenreList))
        self.log("fillMovieInfo return " + str(self.studioList))


    def makeMixedList(self, list1, list2):
        self.log("makeMixedList")
        mixedList = []

        for item in list1:
            curitem = item.lower()

            for a in list2:
                if curitem == a.lower():
                    mixedList.append(item)
                    break

        self.log("found mixed genres " + str(mixedList))
        self.log("makeMixedList return " + str(mixedList))
        return mixedList


    def buildFileList(self, dir_name, channel, media_type="video", recursive="TRUE"):
        self.log("buildFileList")

        if self.threadPause() == False:
            return ''

        fileList = []
        json_query = '{"jsonrpc": "2.0", "method": "Files.GetDirectory", "params": {"directory": "%s", "media": "%s", "fields":["duration","runtime","tagline","showtitle","album","artist","plot"]}, "id": 1}' % ( self.escapeDirJSON( dir_name ), media_type )
        self.log("json_query = " + str(json_query))
        json_folder_detail = self.sendJSON(json_query)
        self.log(json_folder_detail)
        file_detail = re.compile( "{(.*?)}", re.DOTALL ).findall(json_folder_detail)

        for f in file_detail:

            if self.threadPause() == False:
                return ''
            
            match = re.search('"file" *: *"(.*?)",', f)

            if match:

                if(match.group(1).endswith("/") or match.group(1).endswith("\\")):
                    if(recursive == "TRUE"):
                        fileList.extend(self.buildFileList(match.group(1), channel, media_type, recursive))
                else:
                    duration = re.search('"duration" *: *([0-9]*?),', f)

                    try:
                        dur = int(duration.group(1))
                    except:
                        dur = 0

                    if dur == 0:
                        duration = re.search('"runtime" *: *"([0-9]*?)",', f)

                        try:
                            # Runtime is reported in minutes
                            dur = int(duration.group(1)) * 60
                        except:
                            dur = 0

                        if dur == 0:
                            dur = self.videoParser.getVideoLength(match.group(1).replace("\\\\", "\\"))
                                        
                    try:
                        if dur > 0:
                            title = re.search('"label" *: *"(.*?)"', f)
                            tmpstr = str(dur) + ','
                            showtitle = re.search('"showtitle" *: *"(.*?)"', f)
                            plot = re.search('"plot" *: *"(.*?)",', f)
                            
                            ### TV TIME ###
                            #title = title.encode('utf-8')
                            #showtitle = showtitle.encode('utf-8')
                            #plot = plot.encode('utf-8')
                            ###############

                            if plot == None:
                                theplot = ""
                            else:
                                theplot = plot.group(1)

                            # This is a TV show
                            if showtitle != None and len(showtitle.group(1)) > 0:
                                tmpstr += showtitle.group(1) + "//" + title.group(1) + "//" + theplot
                            else:
                                tmpstr += title.group(1) + "//"
                                album = re.search('"album" *: *"(.*?)"', f)

                                # This is a movie
                                if album == None or len(album.group(1)) == 0:
                                    tagline = re.search('"tagline" *: *"(.*?)"', f)

                                    if tagline != None:
                                        tmpstr += tagline.group(1)

                                    tmpstr += "//" + theplot
                                else:
                                    artist = re.search('"artist" *: *"(.*?)"', f)
                                    tmpstr += album.group(1) + "//" + artist.group(1)

                            tmpstr = tmpstr[:600]
                            tmpstr = tmpstr.replace("\\n", " ").replace("\\r", " ").replace("\\\"", "\"")
                            tmpstr = tmpstr + '\n' + match.group(1).replace("\\\\", "\\")
                            fileList.append(tmpstr)
                    except:
                        pass
            else:
                continue

        self.videoParser.finish()
        return fileList
    
    
    ### TV TIME ###
    """
    def buildMixedFileList(self, dom1):
        fileList = []
        self.log('buildMixedFileList')

        try:
            rules = dom1.getElementsByTagName('rule')
            order = dom1.getElementsByTagName('order')
        except:
            self.log('buildMixedFileList Problem parsing playlist ' + filename, xbmc.LOGERROR)
            xml.close()
            return fileList

        for rule in rules:
            rulename = rule.childNodes[0].nodeValue

            if os.path.exists(xbmc.translatePath('special://profile/playlists/video/') + rulename):
                fileList.extend(self.buildFileList(xbmc.translatePath('special://profile/playlists/video/') + rulename))
            else:
                fileList.extend(self.buildFileList(GEN_CHAN_LOC + rulename))

        self.log("buildMixedFileList returning")
        return fileList
    """
    def buildMixedFileListsFromPlaylist(self, src1, channel):
        self.log('buildMixedFileList')

        if self.threadPause() == False:
            return ''

        fileList = []

        dom1 = self.getPlaylist(src1)

        limit = self.limit
        order = "random"
        pltype = self.getSmartPlaylistType(dom1)

        try:
            rulesNode = dom1.getElementsByTagName('rule')
            orderNode = dom1.getElementsByTagName('order')
            limitNode = dom1.getElementsByTagName('limit')
        except:
            self.log('buildMixedFileList: Problem parsing playlist ' + filename, xbmc.LOGERROR)
            xml.close()
            return fileList
   
        if limitNode:
            try:
                plimit = limitNode[0].firstChild.nodeValue
                # force a max limit of 250 for performance reason
                if int(plimit) < self.limit:
                    limit = plimit
            except:
                pass
                
        # get order to determine whether fileList should be randomized
        if orderNode:
            try:
                order = orderNode[0].firstChild.nodeValue
            except:
                pass

        self.level = self.level + 1        
        if self.level == 1:
            #ADDON_SETTINGS.setSetting("Channel_" + str(channel) + "_limit",limit)
            if order == "random":
                ADDON_SETTINGS.setSetting("Channel_" + str(channel) + "_9",MODE_RANDOM_FILELISTS)
            
        # need to redo this for loop
        for rule in rulesNode:
            i = 0                        
            fileList = []

            if self.threadPause() == False:
                del fileList[:]
                del self.fileLists[:]
                break

            rulename = rule.childNodes[i].nodeValue
            rulename = rulename.encode('utf-8')
            rulename = self.uncleanString(rulename)
            self.log("rulename = " + str(rulename))
            if os.path.exists(rulename):
                src1 = rulename            
            elif os.path.exists(os.path.join(xbmc.translatePath('special://profile/playlists/video'), rulename)):
                src1 = os.path.join(xbmc.translatePath('special://profile/playlists/video'), rulename)
            elif os.path.exists(os.path.join(xbmc.translatePath('special://profile/addon_data/' + ADDON_ID + '/cache/generated'), rulename)):
                src1 = os.path.join(xbmc.translatePath('special://profile/addon_data/' + ADDON_ID + '/cache/generated'), rulename)
            else:
                src1 = ""
                self.log("buildMixedFileList: Problem finding source file: " + str(rulename))
            self.log("src1 = " + str(src1))
            dom1 = self.getPlaylist(src1)
            pltype1 = self.getSmartPlaylistType(dom1)
            if pltype1 == 'movies' or pltype1 == 'episodes' or pltype1 == 'tvshows':
                #tmpList = []
                fileList = self.buildFileList(src1, channel)
                if len(fileList) > 0:
                    #if order == 'random':
                    #    random.shuffle(tmpList)
                    #fileList.extend(tmpList)
                    self.fileLists.append(channelFileList(pltype1, limit, fileList))
            elif pltype1 == 'mixed':
                if os.path.exists(src1):
                    self.buildMixedFileListsFromPlaylist(src1, channel)
                else:
                    self.log("buildMixedFileList: Problem finding source file: " + src1)
            i = i + 1
        return self.fileLists


    def threadPause(self):
        if threading.activeCount() > 1:
            if self.exitThread == True:
                return False

            time.sleep(self.sleepTime)

        return True


    def escapeDirJSON(self, dir_name):
        if (dir_name.find(":")):
            dir_name = dir_name.replace("\\", "\\\\")

        return dir_name


    def getSmartPlaylistType(self, dom):
        self.log('getSmartPlaylistType')

        try:
            pltype = dom.getElementsByTagName('smartplaylist')
            return pltype[0].attributes['type'].value
        except:
            self.log("Unable to get the playlist type.", xbmc.LOGERROR)
            return ''

### TV TIME ###
class channelFileList(object):
    def __init__(self, type, limit, list):
        self.type = type
        self.limit = limit
        self.list = list
###############