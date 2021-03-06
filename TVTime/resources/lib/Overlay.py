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

from xml.dom.minidom import parse, parseString

from Playlist import Playlist
from Globals import *
from Channel import Channel
from EPGWindow import EPGWindow
from ChannelList import ChannelList
from ChannelListThread import ChannelListThread

### TV TIME ###
from time import sleep
###############

class MyPlayer(xbmc.Player):
    def __init__(self):
        xbmc.Player.__init__(self, xbmc.PLAYER_CORE_AUTO)
        self.stopped = False


    def log(self, msg, level = xbmc.LOGDEBUG):
        log('Player: ' + msg, level)


    def onPlayBackStopped(self):
        if self.stopped == False:
            self.log('Playback stopped')

            if self.overlay.sleepTimeValue == 0:
                self.overlay.sleepTimer = threading.Timer(1, self.overlay.sleepAction)    

            self.overlay.sleepTimeValue = 1
            self.overlay.startSleepTimer()
            self.stopped = True



# overlay window to catch events and change channels
class TVOverlay(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)
        self.log('__init__')
        # initialize all variables
        self.channels = []
        self.Player = MyPlayer()
        self.Player.overlay = self
        self.inputChannel = -1
        self.channelLabel = []
        self.lastActionTime = 0
        self.actionSemaphore = threading.BoundedSemaphore()
        self.channelThread = ChannelListThread()
        self.channelThread.myOverlay = self
        self.setCoordinateResolution(1)
        self.timeStarted = 0
        self.infoOnChange = True
        self.infoOffset = 0
        self.invalidatedChannelCount = 0
        self.showingInfo = False
        self.showChannelBug = False
        random.seed()

        for i in range(3):
            self.channelLabel.append(xbmcgui.ControlImage(50 + (50 * i), 50, 50, 50, IMAGES_LOC + 'solid.png', colorDiffuse='0xAA00ff00'))
            self.addControl(self.channelLabel[i])
            self.channelLabel[i].setVisible(False)

        self.doModal()
        self.log('__init__ return')


    def resetChannelTimes(self):
        curtime = time.time()

        for i in range(self.maxChannels):
            self.channels[i].setAccessTime(curtime - self.channels[i].totalTimePlayed)


    def onFocus(self, controlId):
        pass


    # override the doModal function so we can setup everything first
    def onInit(self):
        self.log('onInit')
        migrate()
        self.channelLabelTimer = threading.Timer(5.0, self.hideChannelLabel)
        self.infoTimer = threading.Timer(5.0, self.hideInfo)
        self.background = self.getControl(101)
        self.getControl(102).setVisible(False)

        if not os.path.exists(GEN_CHAN_LOC):
            try:
                os.makedirs(GEN_CHAN_LOC)
            except:
                self.Error('Unable to create the cache directory')
                return

        self.myEPG = EPGWindow("script.pseudotv.EPG.xml", ADDON_INFO, "default")
        self.myEPG.MyOverlayWindow = self
        # Don't allow any actions during initialization
        self.actionSemaphore.acquire()

        ### TV TIME ###
        chn = ChannelList()
        # build meta files if first time loading
        if (
            REAL_SETTINGS.getSetting("bumpers") == "true" or 
            REAL_SETTINGS.getSetting("commercials") == "true" or  
            REAL_SETTINGS.getSetting("trailers") == "true"
            ):
            chn.buildMetaFiles() 

        chn.loadCustomPlaylists()

        if (REAL_SETTINGS.getSetting("autoFindMixGenres") == "true" or       
            REAL_SETTINGS.getSetting("autoFindMovieGenres") == "true" or        
            REAL_SETTINGS.getSetting("autoFindNetworks") == "true" or        
            REAL_SETTINGS.getSetting("autoFindStudios") == "true" or   
            REAL_SETTINGS.getSetting("autoFindTVGenres") == "true" or       
            REAL_SETTINGS.getSetting("autoFindTVShows") == "true" or
            REAL_SETTINGS.getSetting("autoFindMusicGenres") == "true" or
            REAL_SETTINGS.getSetting("autoFindLive") == "true"):
            chn.autoTune()
        ###############

        if self.readConfig() == False:
            return

        self.myEPG.channelLogos = self.channelLogos
        self.maxChannels = len(self.channels)

        ### TV TIME ###
        #if self.maxChannels == 0:
        #    self.Error('Unable to find any channels. Please configure the addon.')
        #    return
        if self.maxChannels == 0:
            dlg = xbmcgui.Dialog()
            
            autoTune = False
            if dlg.yesno("No Channels Configured", "Would you like TV Time to Auto Tune TV Network\nchannels the next time it loads?"):
                REAL_SETTINGS.setSetting("autoFindNetworks","true")
                autoTune = True

            if dlg.yesno("No Channels Configured", "Would you like TV Time to Auto Tune TV Genre\nchannels the next time it loads?"):
                REAL_SETTINGS.setSetting("autoFindTVGenres","true")
                autoTune = True

            if dlg.yesno("No Channels Configured", "Would you like TV Time to Auto Tune Movie Studio\nchannels the next time it loads?"):
                REAL_SETTINGS.setSetting("autoFindStudios","true")
                autoTune = True

            if dlg.yesno("No Channels Configured", "Would you like TV Time to Auto Tune Movie Genre\nchannels the next time it loads?"):
                REAL_SETTINGS.setSetting("autoFindMovieGenres","true")
                autoTune = True

            if dlg.yesno("No Channels Configured", "Would you like TV Time to Auto Tune Mix Genre\nchannels the next time it loads?"):
                REAL_SETTINGS.setSetting("autoFindMixGenres","true")
                autoTune = True

            if dlg.yesno("No Channels Configured", "Would you like TV Time to Auto Tune Music Genre\nchannels the next time it loads?"):
                REAL_SETTINGS.setSetting("autoFindMusicGenres","true")
                autoTune = True

            if dlg.yesno("No Channels Configured", "Would you like TV Time to Auto Tune Live\nchannels the next time it loads?"):
                REAL_SETTINGS.setSetting("autoFindLive","true")
                autoTune = True

            if autoTune:
                self.background.setVisible(True)
                self.end()
                return

            del dlg
        ###############
        
        found = False

        for i in range(self.maxChannels):
            if self.channels[i].isValid:
                found = True
                break

        ### TV TIME ###
        #if found == False:
        #    self.Error("No valid channel data found")
        #    return
        if found == False:
            self.Error('Unable to find any channels. \nPlease go to the Addon Settings to configure TV Time.')
            return
        ###############
        
        if self.sleepTimeValue > 0:
            self.sleepTimer = threading.Timer(self.sleepTimeValue, self.sleepAction)

        try:
            if self.forceReset == False:
                self.currentChannel = self.fixChannel(int(ADDON_SETTINGS.getSetting("CurrentChannel")))
            else:
                ### TV TIME ###
                #self.currentChannel = self.fixChannel(1)
                if self.startupChannel == 0:
                    self.currentChannel = self.fixChannel(1)
                else:
                    if self.channels[self.startupChannel - 1].isValid:
                        self.currentChannel = self.fixChannel(self.startupChannel)
                    else:
                        self.currentChannel = self.fixChannel(1)
                ###############
        except:
            self.currentChannel = self.fixChannel(1)

        self.resetChannelTimes()
        self.setChannel(self.currentChannel)
        self.timeStarted = time.time()
        self.background.setVisible(False)
        ### TV TIME ###
        if int(ADDON_SETTINGS.getSetting("Channel_" + str(self.currentChannel) + "_type")) == 8:
            xbmc.executebuiltin("ActivateWindow(12006)")            
        ###############
        self.startSleepTimer()
        
        ### TV TIME ###
        #if self.channelResetSetting == "0":
        #    self.channelThread.start()
        self.channelThread.start()
        ###############
        
        self.actionSemaphore.release()
        self.log('onInit return')


    # setup all basic configuration parameters, including creating the playlists that
    # will be used to actually run this thing
    def readConfig(self):
        self.log('readConfig')
        ### TV TIME ###
        # Output all settings for debugging purposes
        self.log('#####################################################################################')
        self.log('General Settings:')
        self.log('  Auto off is - ' + str(REAL_SETTINGS.getSetting('AutoOff')))
        self.log('  Show info label on channel change is - ' + str(REAL_SETTINGS.getSetting('InfoOnChange') == "true")) 
        self.log('  Force Channel Reset is - ' + str(REAL_SETTINGS.getSetting('ForceChannelReset')))
        self.log('  Channel Reset Setting is - ' + str(REAL_SETTINGS.getSetting('ChannelResetSetting')))
        self.log('  Show Channel Bug is - ' + str(REAL_SETTINGS.getSetting('ShowChannelBug') == "true"))
        self.log('  Channel Logo Folder is - ' + str(REAL_SETTINGS.getSetting('ChannelLogoFolder')))   
        self.log('  Start Mode is - ' + str(REAL_SETTINGS.getSetting('StartMode')))   
        self.log('  Version is - ' + str(REAL_SETTINGS.getSetting('Version')))

        self.log('Channel Settings:')
        self.log('  Prestage Channels - ' + str(REAL_SETTINGS.getSetting('PrestageChannels')))
        self.log('  Startup Channel is - ' + str(REAL_SETTINGS.getSetting('startupChannel')))
        self.log('  Maximum Number of Music Genres to return - ' + str(REAL_SETTINGS.getSetting('maxMusicGenres')))
        self.log('  Maximum Number of Movie Genres to return  - ' + str(REAL_SETTINGS.getSetting('maxMovieGenres')))

        self.log('Auto Tune Settings:')
        self.log('  Auto Find TV Network Channels is - ' + str(REAL_SETTINGS.getSetting('autoFindNetworks')))
        self.log('  Auto Find Movie Studios Channels is - ' + str(REAL_SETTINGS.getSetting('autoFindStudios')))
        self.log('  Auto Find TV Genres Channels is - ' + str(REAL_SETTINGS.getSetting('autoFindTVGenres')))
        self.log('  Auto Find Movie Genres Channels is - ' + str(REAL_SETTINGS.getSetting('autoFindMovieGenres')))
        self.log('  Auto Find Mixed Genres Channels is - ' + str(REAL_SETTINGS.getSetting('autoFindMixGenres')))
        self.log('  Auto Find Music Genres Channels is - ' + str(REAL_SETTINGS.getSetting('autoFindMusicGenres')))
        self.log('  Auto Find Live Channels is - ' + str(REAL_SETTINGS.getSetting('autoFindLive')))
        self.log('  Channel Limit is - ' + str(REAL_SETTINGS.getSetting('limit')))
        
        self.log('Off Air Settings:')
        self.log('  Off Air Mode is - ' + str(REAL_SETTINGS.getSetting('offair') == "true" ))
        self.log('  Off Air File is - ' + str(REAL_SETTINGS.getSetting('offairfile')))

        self.log('Bumpers Settings:')
        self.log('  Bumpers Mode is - ' + str(REAL_SETTINGS.getSetting('bumpers') == "true" ))
        self.log('  Bumpers Folder is - ' + str(REAL_SETTINGS.getSetting('bumpersfolder')))
        self.log('  Number of Bumpers is - ' + str(REAL_SETTINGS.getSetting('numbumpers')))
        self.log('  Max Number of Bumpers is - ' + str(REAL_SETTINGS.getSetting('maxbumpers')))

        self.log('Commercials Settings:')
        self.log('  Commercials Mode is - ' + str(REAL_SETTINGS.getSetting('commercials') == "true" ))
        self.log('  Commercials Folder is - ' + str(REAL_SETTINGS.getSetting('commercialsfolder')))
        self.log('  Number of Commercials is - ' + str(REAL_SETTINGS.getSetting('numcommercials')))
        self.log('  Max Number of Commercials is - ' + str(REAL_SETTINGS.getSetting('maxcommercials')))

        self.log('Trailers Settings:')
        self.log('  Trailers Mode is - ' + str(REAL_SETTINGS.getSetting('trailers') == "true" ))
        self.log('  Trailers Folder is - ' + str(REAL_SETTINGS.getSetting('trailersfolder')))
        self.log('  Number of Trailers is - ' + str(REAL_SETTINGS.getSetting('numtrailers')))
        self.log('  Max Number of Trailers is - ' + str(REAL_SETTINGS.getSetting('maxtrailers')))

        self.log('Runtime Settings:')
        self.log('  Current Channel is - ' + str(REAL_SETTINGS.getSetting('CurrentChannel')))
        self.log('  Last Reset Time is - ' + str(REAL_SETTINGS.getSetting('LastResetTime')))
        self.log('#####################################################################################')        
        ###############
        
        # Sleep setting is in 30 minute incriments...so multiply by 30, and then 60 (min to sec)
        self.sleepTimeValue = int(REAL_SETTINGS.getSetting('AutoOff')) * 1800
        self.log('Auto off is ' + str(self.sleepTimeValue))
        self.infoOnChange = REAL_SETTINGS.getSetting("InfoOnChange") == "true"
        self.log('Show info label on channel change is ' + str(self.infoOnChange))
        self.showChannelBug = REAL_SETTINGS.getSetting("ShowChannelBug") == "true"
        self.log('Show channel bug - ' + str(self.showChannelBug))
        self.forceReset = REAL_SETTINGS.getSetting('ForceChannelReset') == "true"
        self.channelResetSetting = REAL_SETTINGS.getSetting('ChannelResetSetting')
        self.log("Channel reset setting - " + str(self.channelResetSetting))
        self.channelLogos = xbmc.translatePath(REAL_SETTINGS.getSetting('ChannelLogoFolder'))
        ### TV TIME ###
        self.startupChannel = int(REAL_SETTINGS.getSetting("startupChannel"))
        ###############

        if os.path.exists(self.channelLogos) == False:
            self.channelLogos = IMAGES_LOC

        self.log('Channel logo folder - ' + self.channelLogos)
        self.startupTime = time.time()
        chn = ChannelList()
        self.background.setVisible(True)
        self.channels = chn.setupList()

        if self.channels is None:
            self.log('readConfig No channel list returned')
            self.end()
            return False

        self.Player.stop()

        self.log('readConfig return')
        return True


    # handle fatal errors: log it, show the dialog, and exit
    def Error(self, message):
        self.log('FATAL ERROR: ' + message, xbmc.LOGFATAL)
        dlg = xbmcgui.Dialog()
        dlg.ok('Error', message)
        del dlg
        self.end()


    def channelDown(self):
        self.log('channelDown')

        if self.maxChannels == 1:
            return

        self.background.setVisible(True)
        channel = self.fixChannel(self.currentChannel - 1, False)
        self.setChannel(channel)
        self.background.setVisible(False)
        self.log('channelDown return')


    def channelUp(self):
        self.log('channelUp')

        if self.maxChannels == 1:
            return

        self.background.setVisible(True)
        channel = self.fixChannel(self.currentChannel + 1)
        self.setChannel(channel)
        self.background.setVisible(False)
        self.log('channelUp return')


    def message(self, data):
        self.log('Dialog message: ' + data)
        dlg = xbmcgui.Dialog()
        dlg.ok('Info', data)
        del dlg


    def log(self, msg, level = xbmc.LOGDEBUG):
        log('TVOverlay: ' + msg, level)


    # set the channel, the proper show offset, and time offset
    def setChannel(self, channel):
        self.log('setChannel ' + str(channel))

        if channel < 1 or channel > self.maxChannels:
            self.log('setChannel invalid channel ' + str(channel), xbmc.LOGERROR)
            return

        if self.channels[channel - 1].isValid == False:
            self.log('setChannel channel not valid ' + str(channel), xbmc.LOGERROR)
            return

        self.lastActionTime = 0
        timedif = 0
        self.getControl(102).setVisible(False)
        self.showingInfo = False

        # first of all, save playing state, time, and playlist offset for
        # the currently playing channel
        if self.Player.isPlaying():
            if channel != self.currentChannel:
                self.channels[self.currentChannel - 1].setPaused(xbmc.getCondVisibility('Player.Paused'))

                # Automatically pause in serial mode
                if self.channels[self.currentChannel - 1].mode & MODE_ALWAYSPAUSE > 0:
                    self.channels[self.currentChannel - 1].setPaused(True)

                self.channels[self.currentChannel - 1].setShowTime(self.Player.getTime())
                self.channels[self.currentChannel - 1].setShowPosition(xbmc.PlayList(xbmc.PLAYLIST_MUSIC).getposition())
                self.channels[self.currentChannel - 1].setAccessTime(time.time())

        self.currentChannel = channel
        # now load the proper channel playlist
        xbmc.PlayList(xbmc.PLAYLIST_MUSIC).clear()
        if xbmc.PlayList(xbmc.PLAYLIST_MUSIC).load(self.channels[channel - 1].fileName) == False:
            self.log("Error loading playlist")
            self.InvalidateChannel(channel)
            return

        # Disable auto playlist shuffling if it's on
        if xbmc.getInfoLabel('Playlist.Random').lower() == 'random':
            self.log('Random on.  Disabling.')
            xbmc.PlayList(xbmc.PLAYLIST_MUSIC).unshuffle()

        xbmc.executebuiltin("PlayerControl(repeatall)")

        timedif += (time.time() - self.channels[self.currentChannel - 1].lastAccessTime)

        # adjust the show and time offsets to properly position inside the playlist
        while self.channels[self.currentChannel - 1].showTimeOffset + timedif > self.channels[self.currentChannel - 1].getCurrentDuration():
            timedif -= self.channels[self.currentChannel - 1].getCurrentDuration() - self.channels[self.currentChannel - 1].showTimeOffset
            self.channels[self.currentChannel - 1].addShowPosition(1)
            self.channels[self.currentChannel - 1].setShowTime(0)

        # set the show offset
        self.Player.playselected(self.channels[self.currentChannel - 1].playlistPosition)
        # set the time offset
        self.channels[self.currentChannel - 1].setAccessTime(time.time())

        if self.channels[self.currentChannel - 1].isPaused:
            self.channels[self.currentChannel - 1].setPaused(False)

            try:
                self.Player.seekTime(self.channels[self.currentChannel - 1].showTimeOffset)
                
                if self.channels[self.currentChannel - 1].mode & MODE_ALWAYSPAUSE == 0:
                    self.Player.pause()
    
                    if self.waitForVideoPaused() == False:
                        return
            except:
                self.log('Exception during seek on paused channel', xbmc.LOGERROR)
        else:
            seektime = self.channels[self.currentChannel - 1].showTimeOffset + timedif

            try:
                self.Player.seekTime(seektime)
            except:
                self.log('Exception during seek', xbmc.LOGERROR)

        self.showChannelLabel(self.currentChannel)
        self.lastActionTime = time.time()
        self.log('setChannel return')


    def InvalidateChannel(self, channel):
        self.log("InvalidateChannel" + str(channel))

        if channel < 1 or channel > self.maxChannels:
            self.log("InvalidateChannel invalid channel " + str(channel))
            return

        self.channels[channel - 1].isValid = False
        self.invalidatedChannelCount += 1

        if self.invalidatedChannelCount > 3:
            self.Error("Exceeded 3 invalidated channels. Exiting.")
            return

        remaining = 0

        for i in range(self.maxChannels):
            if self.channels[i].isValid:
                remaining += 1

        if remaining == 0:
            self.Error("No channels available. Exiting.")
            return

        self.setChannel(self.fixChannel(channel))


    def waitForVideoPaused(self):
        self.log('waitForVideoPaused')
        sleeptime = 0

        while sleeptime < TIMEOUT:
            xbmc.sleep(100)

            if self.Player.isPlaying():
                if xbmc.getCondVisibility('Player.Paused'):
                    break

            sleeptime += 100
        else:
            self.log('Timeout waiting for pause', xbmc.LOGERROR)
            return False

        self.log('waitForVideoPaused return')
        return True


    def setShowInfo(self):
        self.log('setShowInfo')

        if self.infoOffset > 0:
            self.getControl(502).setLabel('COMING UP:')
        elif self.infoOffset < 0:
            self.getControl(502).setLabel('ALREADY SEEN:')
        elif self.infoOffset == 0:
            self.getControl(502).setLabel('NOW WATCHING:')

        position = xbmc.PlayList(xbmc.PLAYLIST_VIDEO).getposition() + self.infoOffset
        self.getControl(503).setLabel(self.channels[self.currentChannel - 1].getItemTitle(position))
        self.getControl(504).setLabel(self.channels[self.currentChannel - 1].getItemEpisodeTitle(position))
        self.getControl(505).setLabel(self.channels[self.currentChannel - 1].getItemDescription(position))
        self.getControl(506).setImage(self.channelLogos + self.channels[self.currentChannel - 1].name + '.png')
        self.log('setShowInfo return')


    # Display the current channel based on self.currentChannel.
    # Start the timer to hide it.
    def showChannelLabel(self, channel):
        self.log('showChannelLabel ' + str(channel))

        if self.channelLabelTimer.isAlive():
            self.channelLabelTimer.cancel()
            self.channelLabelTimer = threading.Timer(5.0, self.hideChannelLabel)

        tmp = self.inputChannel
        self.hideChannelLabel()
        self.inputChannel = tmp
        curlabel = 0

        if channel > 99:
            self.channelLabel[curlabel].setImage(IMAGES_LOC + 'label_' + str(channel // 100) + '.png')
            self.channelLabel[curlabel].setVisible(True)
            curlabel += 1

        if channel > 9:
            self.channelLabel[curlabel].setImage(IMAGES_LOC + 'label_' + str((channel % 100) // 10) + '.png')
            self.channelLabel[curlabel].setVisible(True)
            curlabel += 1

        self.channelLabel[curlabel].setImage(IMAGES_LOC + 'label_' + str(channel % 10) + '.png')
        self.channelLabel[curlabel].setVisible(True)

        ##ADDED BY SRANSHAFT: USED TO SHOW NEW INFO WINDOW WHEN CHANGING CHANNELS
        if self.inputChannel == -1 and self.infoOnChange == True:
            self.infoOffset = 0
            self.showInfo(5.0)

        if self.showChannelBug == True:
            try:
                self.getControl(103).setImage(self.channelLogos + self.channels[self.currentChannel - 1].name + '.png')
            except:
                pass
        ##

        self.channelLabelTimer.start()
        self.log('showChannelLabel return')


    # Called from the timer to hide the channel label.
    def hideChannelLabel(self):
        self.log('hideChannelLabel')
        self.channelLabelTimer = threading.Timer(5.0, self.hideChannelLabel)

        for i in range(3):
            self.channelLabel[i].setVisible(False)

        self.inputChannel = -1
        self.log('hideChannelLabel return')


    def hideInfo(self):
        self.getControl(102).setVisible(False)
        self.infoOffset = 0
        self.showingInfo = False

        if self.infoTimer.isAlive():
            self.infoTimer.cancel()

        self.infoTimer = threading.Timer(5.0, self.hideInfo)


    def showInfo(self, timer):
        self.getControl(102).setVisible(True)
        self.showingInfo = True
        self.setShowInfo()

        if self.infoTimer.isAlive():
            self.infoTimer.cancel()

        self.infoTimer = threading.Timer(timer, self.hideInfo)
        self.infoTimer.start()


    # return a valid channel in the proper range
    def fixChannel(self, channel, increasing = True):
        while channel < 1 or channel > self.maxChannels:
            if channel < 1: channel = self.maxChannels + channel
            if channel > self.maxChannels: channel -= self.maxChannels

        if increasing:
            direction = 1
        else:
            direction = -1

        if self.channels[channel - 1].isValid == False:
            return self.fixChannel(channel + direction, increasing)

        return channel


    # Handle all input while videos are playing
    def onAction(self, act):
        action = act.getId()
        self.log('onAction ' + str(action))

        # Since onAction isnt always called from the same thread (weird),
        # ignore all actions if we're in the middle of processing one
        if self.actionSemaphore.acquire(False) == False:
            self.log('Unable to get semaphore')
            return

        lastaction = time.time() - self.lastActionTime

        # during certain times we just want to discard all input
        if lastaction < 2:
            self.log('Not allowing actions')
            action = ACTION_INVALID

        self.startSleepTimer()

        if action == ACTION_SELECT_ITEM:
            # If we're manually typing the channel, set it now
            if self.inputChannel > 0:
                if self.inputChannel != self.currentChannel:
                    self.setChannel(self.inputChannel)

                self.inputChannel = -1
            else:
                ### TV TIME ###
                if self.channelThread.isAlive():
                    self.channelThread.shouldExit = True
                    self.channelThread.chanlist.exitThread = True
                    self.channelThread.join()                
                ###############
                
                # Otherwise, show the EPG
                if self.sleepTimeValue > 0:
                    if self.sleepTimer.isAlive():
                        self.sleepTimer.cancel()
                        self.sleepTimer = threading.Timer(self.sleepTimeValue, self.sleepAction)

                self.hideInfo()
                self.newChannel = 0
                self.myEPG.doModal()

                if self.newChannel != 0:
                    self.background.setVisible(True)
                    self.setChannel(self.newChannel)
                    self.background.setVisible(False)
        elif action == ACTION_MOVE_UP or action == ACTION_PAGEUP:
            self.channelUp()
        elif action == ACTION_MOVE_DOWN or action == ACTION_PAGEDOWN:
            self.channelDown()
        elif action == ACTION_MOVE_LEFT:
            if self.showingInfo:
                self.infoOffset -= 1
                self.showInfo(10.0)
            else:
                xbmc.executebuiltin("PlayerControl(SmallSkipBackward)")
        elif action == ACTION_MOVE_RIGHT:
            if self.showingInfo:
                self.infoOffset += 1
                self.showInfo(10.0)
            else:
                xbmc.executebuiltin("PlayerControl(SmallSkipForward)")
        elif action == ACTION_PREVIOUS_MENU:
            if self.showingInfo:
                self.hideInfo()
            else:
                dlg = xbmcgui.Dialog()

                if self.sleepTimeValue > 0:
                    if self.sleepTimer.isAlive():
                        self.sleepTimer.cancel()
                        self.sleepTimer = threading.Timer(self.sleepTimeValue, self.sleepAction)
                ### TV TIME ###
                #if dlg.yesno("Exit?", "Are you sure you want to exit PseudoTV?"):
                if dlg.yesno("Exit?", "Are you sure you want to exit TV Time?"):
                ###############
                    self.end()
                else:
                    self.startSleepTimer()

                del dlg
        elif action == ACTION_SHOW_INFO:
            if self.showingInfo:
                self.hideInfo()
            else:
                self.showInfo(10.0)
        elif action >= ACTION_NUMBER_0 and action <= ACTION_NUMBER_9:
            if self.inputChannel < 0:
                self.inputChannel = action - ACTION_NUMBER_0
            else:
                if self.inputChannel < 100:
                    self.inputChannel = self.inputChannel * 10 + action - ACTION_NUMBER_0

            self.showChannelLabel(self.inputChannel)
        elif action == ACTION_OSD:
            xbmc.executebuiltin("ActivateWindow(12901)")

        self.actionSemaphore.release()
        self.log('onAction return')


    # Reset the sleep timer
    def startSleepTimer(self):
        if self.sleepTimeValue == 0:
            return

        # Cancel the timer if it is still running
        if self.sleepTimer.isAlive():
            self.sleepTimer.cancel()
            self.sleepTimer = threading.Timer(self.sleepTimeValue, self.sleepAction)

        self.sleepTimer.start()


    # This is called when the sleep timer expires
    def sleepAction(self):
        self.log("sleepAction")
        self.actionSemaphore.acquire()
#        self.sleepTimer = threading.Timer(self.sleepTimeValue, self.sleepAction)
        # TODO: show some dialog, allow the user to cancel the sleep
        # perhaps modify the sleep time based on the current show
        self.end()
        self.actionSemaphore.release()


    # cleanup and end
    def end(self):
        self.log('end')
        self.background.setVisible(True)
        xbmc.executebuiltin("self.PlayerControl(repeatoff)")

        if self.Player.isPlaying():
            # Prevent the player from setting the sleep timer
            self.Player.stopped = True
            self.Player.stop()
                
        try:
            if self.channelLabelTimer.isAlive():
                self.channelLabelTimer.cancel()
        except:
            pass

        try:
            if self.infoTimer.isAlive():
                self.infoTimer.cancel()
        except:
            pass

        try:
            ### TV TIME ###
            #if self.sleepTimeValue > 0:
            #    if self.sleepTimer.isAlive():
            #        self.sleepTimer.cancel()
            if self.sleepTimer.isAlive():
                self.sleepTimer.cancel()
        except:
            pass

        if self.channelThread.isAlive():
            self.channelThread.shouldExit = True
            self.channelThread.chanlist.exitThread = True
            self.channelThread.join()

        if self.timeStarted > 0:
            for i in range(self.maxChannels):
                if self.channels[i].isValid:
                    if self.channels[i].mode & MODE_RESUME == 0:
                        ADDON_SETTINGS.setSetting('Channel_' + str(i + 1) + '_time', str(int(time.time() - self.timeStarted + self.channels[i].totalTimePlayed)))
                    else:
                        tottime = 0

                        for j in range(self.channels[i].playlistPosition):
                            tottime += self.channels[i].getItemDuration(j)

                        tottime += self.channels[i].showTimeOffset

                        if i == self.currentChannel - 1:
                            tottime += (time.time() - self.channels[i].lastAccessTime)

                        ADDON_SETTINGS.setSetting('Channel_' + str(i + 1) + '_time', str(int(tottime)))

        ### TV TIME ###
        #try:
        #    ADDON_SETTINGS.setSetting('CurrentChannel', str(self.currentChannel))
        #except:
        #    pass
        try:
            if self.startupChannel == 0:
                ADDON_SETTINGS.setSetting('CurrentChannel', str(self.currentChannel))
            else:
                if self.channels[self.startupChannel - 1].isValid:
                    ADDON_SETTINGS.setSetting('CurrentChannel', str(self.startupChannel))
                else:
                    ADDON_SETTINGS.setSetting('CurrentChannel', str(self.currentChannel))
        except:
            pass
        ###############
        ADDON_SETTINGS.setSetting('LastExitTime', str(int(time.time())))

        ### TV TIME ###
        ADDON_SETTINGS.writeSettings()
        ###############
                
        self.background.setVisible(False)
        self.close()
