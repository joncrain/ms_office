#!/usr/bin/python
# Some of the user elements are from the user_sessions.py script
# made by Clayton Burlison and Michael Lynn
# Other parts of the script from Pbowden's scripts found in his Github
#
# To disable the msupdate parts:
#   sudo defautls write org.munkireport.ms_office msupdate_check_disabled -bool true
#   sudo defautls write org.munkireport.ms_office msupdate_config_disabled -bool true

import subprocess
import os
import plistlib
import sys
import time
import platform
import string
#import re

sys.path.insert(0, '/usr/local/munki')

from munkilib import FoundationPlist
from CoreFoundation import CFPreferencesCopyAppValue

from SystemConfiguration import SCDynamicStoreCopyConsoleUser
from ctypes import (CDLL,
                    Structure,
                    POINTER,
                    c_int64,
                    c_int32,
                    c_int16,
                    c_char,
                    c_uint32)
from ctypes.util import find_library

# constants
c = CDLL(find_library("System"))

class timeval(Structure):
    _fields_ = [
                ("tv_sec",  c_int64),
                ("tv_usec", c_int32),
               ]

class utmpx(Structure):
    _fields_ = [
                ("ut_user", c_char*256),
                ("ut_id",   c_char*4),
                ("ut_line", c_char*32),
                ("ut_pid",  c_int32),
                ("ut_type", c_int16),
                ("ut_tv",   timeval),
                ("ut_host", c_char*256),
                ("ut_pad",  c_uint32*16),
               ]

def get_msupdate_config():
# Get the MAU's config as seen from the current or last person logged in
# Because some settings are user specific

    try:
        cmd = ['/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate', '-c', '-f','plist']
        proc = subprocess.Popen(cmd, shell=False, bufsize=-1,
                                preexec_fn=demote(),
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (output, unused_error) = proc.communicate()

        mau_config = plistlib.readPlistFromString(output.split("\n",2)[2])
        mau_config_items = {}

        for item in mau_config:
            if item == 'UpdateCache':
                mau_config_items['updatecache'] = mau_config[item]
            elif item == 'ManifestServer':
                mau_config_items['manifestserver'] = mau_config[item]
            elif item == 'AutoUpdateVersion':
                mau_config_items['autoupdateversion'] = mau_config[item]
            elif item == 'ChannelName':
                mau_config_items['channelname'] = mau_config[item]
            elif item == 'HowToCheck':
                mau_config_items['howtocheck'] = mau_config[item]
            elif item == 'LastCheckForUpdates':
                mau_config_items['lastcheckforupdates'] = mau_config[item]
            elif item == 'StartDaemonOnAppLaunch':
                mau_config_items['startdaemononapplaunch'] = to_bool(mau_config[item])

            elif item == 'RegisteredApplications':
                mau_config_items['registeredapplications'] = process_registered_apps(mau_config)        
            
        # Add in update information if enabled
        msupdate_check_disabled = to_bool(CFPreferencesCopyAppValue('msupdate_check_disabled', 'org.munkireport.ms_office'))
        if msupdate_check_disabled != 1:
            mau_config_items = get_msupdate_update_check(mau_config_items)
        
        return (mau_config_items)

    except Exception:
        return {}
    
def process_registered_apps(mau_config):
    apps = mau_config['RegisteredApplications']
    registered_apps = {}
        
    for app in apps:
        app_name = app['ApplicationPath'].split("/")[-1].split(".")[0]
        registered_apps[app_name] = {}
        for item in app: 
            if item == 'Application ID':
                registered_apps[app_name]['application_id'] = app[item]
            elif item == 'ApplicationPath':
                registered_apps[app_name]['applicationpath'] = app[item]
            elif item == 'VersionOnDisk':
                registered_apps[app_name]['versionondisk'] = app[item]
    return registered_apps

def get_msupdate_update_check(mau_update_items):
# Quickly check for updates as the current or last person logged in
    try:    
        cmd = ['/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate', '-l', '-f','plist']
        proc = subprocess.Popen(cmd, shell=False, bufsize=-1,
                                preexec_fn=demote(),
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (output, unused_error) = proc.communicate()
        
        mau_update = plistlib.readPlistFromString(output.split("\n",2)[2])

        for app in mau_update:
            app_name = app['ApplicationToBeUpdatedPath'].split("/")[-1].split(".")[0]
            for item in app:
                if item == 'Application ID':
                    mau_update_items['registeredapplications'][app_name]['application_id'] = app[item]
#                elif item == 'ApplicationToBeUpdatedPath':
#                    mau_update_items['registeredapplications'][app_name]['applicationpathtobeupdated'] = app[item]
                elif item == 'Baseline Version':
                    mau_update_items['registeredapplications'][app_name]['baseline_version'] = app[item]
                elif item == 'Date':
                    mau_update_items['registeredapplications'][app_name]['date'] = app[item]
                elif item == 'FullUpdaterLocation':
                    mau_update_items['registeredapplications'][app_name]['fullupdaterlocation'] = app[item]
                elif item == 'FullUpdaterSize':
                    mau_update_items['registeredapplications'][app_name]['fullupdatersize'] = app[item]
                elif item == 'Location':
                    mau_update_items['registeredapplications'][app_name]['deltalocation'] = app[item]
                elif item == 'Payload':
                    mau_update_items['registeredapplications'][app_name]['payload'] = app[item]
                elif item == 'Size':
                    mau_update_items['registeredapplications'][app_name]['deltasize'] = app[item]
                elif item == 'Title':
                    mau_update_items['registeredapplications'][app_name]['title'] = app[item]
                elif item == 'Update Version':
                    mau_update_items['registeredapplications'][app_name]['update_version'] = app[item]
        return (mau_update_items)

    except Exception:
        return {}

def get_mau_prefs():
# Get system level preferences

    try:            
        mau_prefs = {}
        if CFPreferencesCopyAppValue('UpdateCache', 'com.microsoft.autoupdate2'): mau_prefs['updatecache'] = CFPreferencesCopyAppValue('UpdateCache', 'com.microsoft.autoupdate2')
        if CFPreferencesCopyAppValue('ChannelName', 'com.microsoft.autoupdate2'): mau_prefs['channelname'] = CFPreferencesCopyAppValue('ChannelName', 'com.microsoft.autoupdate2')
        if CFPreferencesCopyAppValue('HowToCheck', 'com.microsoft.autoupdate2'): mau_prefs['howtocheck'] = CFPreferencesCopyAppValue('HowToCheck', 'com.microsoft.autoupdate2')
        if CFPreferencesCopyAppValue('ManifestServer', 'com.microsoft.autoupdate2'): mau_prefs['manifestserver'] = CFPreferencesCopyAppValue('ManifestServer', 'com.microsoft.autoupdate2')
        if CFPreferencesCopyAppValue('LastUpdate', 'com.microsoft.autoupdate2'): mau_prefs['lastcheckforupdates'] = CFPreferencesCopyAppValue('LastUpdate', 'com.microsoft.autoupdate2')
        if CFPreferencesCopyAppValue('LastService', 'com.microsoft.autoupdate2'): mau_prefs['lastservice'] = CFPreferencesCopyAppValue('LastService', 'com.microsoft.autoupdate2')
            
        if CFPreferencesCopyAppValue('EnableCheckForUpdatesButton', 'com.microsoft.autoupdate2'):
            mau_prefs['enablecheckforupdatesbutton'] = to_bool(CFPreferencesCopyAppValue('EnableCheckForUpdatesButton', 'com.microsoft.autoupdate2'))
        else:
            mau_prefs['enablecheckforupdatesbutton'] = 1
            
        if CFPreferencesCopyAppValue('SendAllTelemetryEnabled', 'com.microsoft.autoupdate2'):
            mau_prefs['sendalltelemetryenabled'] = to_bool(CFPreferencesCopyAppValue('SendAllTelemetryEnabled', 'com.microsoft.autoupdate2'))
        else:
            mau_prefs['sendalltelemetryenabled'] = 1
            
        if CFPreferencesCopyAppValue('DisableInsiderCheckbox', 'com.microsoft.autoupdate2'):
            mau_prefs['disableinsidercheckbox'] = CFPreferencesCopyAppValue('DisableInsiderCheckbox', 'com.microsoft.autoupdate2')  
        else:
            mau_prefs['disableinsidercheckbox'] = 0
            
        if CFPreferencesCopyAppValue('StartDaemonOnAppLaunch', 'com.microsoft.autoupdate2'):
            mau_prefs['startdaemononapplaunch'] = CFPreferencesCopyAppValue('StartDaemonOnAppLaunch', 'com.microsoft.autoupdate2')
        else:
            mau_prefs['startdaemononapplaunch'] = 1
        
        if os.path.exists('/Library/PrivilegedHelperTools/com.microsoft.autoupdate.helper'):
            mau_prefs['mau_privilegedhelpertool'] = 1 
        else:
            mau_prefs['mau_privilegedhelpertool'] = 0

        return mau_prefs
    except Exception:
        return {}
    
def vl_license_detect():
# Detect if there is a volumne license installed and what kind it is

    if os.path.exists('/Library/Preferences/com.microsoft.office.licensingV2.plist'):
        office_vl = open('/Library/Preferences/com.microsoft.office.licensingV2.plist').read()

        if 'A7vRjN2l/dCJHZOm8LKan11/zCYPCRpyChB6lOrgfi' in office_vl:
            vl_license = "Office 2019 Volume License"
        elif 'Bozo+MzVxzFzbIo+hhzTl4JKv18WeUuUhLXtH0z36s' in office_vl:
            vl_license = "Office 2019 Preview Volume License"
        elif 'A7vRjN2l/dCJHZOm8LKan1Jax2s2f21lEF8Pe11Y+V' in office_vl:
            vl_license = "Office 2016 Volume License"
        elif 'DrL/l9tx4T9MsjKloHI5eX' in office_vl:
            vl_license = "Office 2016 Home and Business License"
        elif 'C8l2E2OeU13/p1FPI6EJAn' in office_vl:
            vl_license = "Office 2016 Home and Student License"
        elif 'Bozo+MzVxzFzbIo+hhzTl4m' in office_vl:
            vl_license = "Office 2019 Home and Business License"
        elif 'Bozo+MzVxzFzbIo+hhzTl4j' in office_vl:
            vl_license = "Office 2019 Home and Student License"

        return {"vl_license_type":vl_license}
    else:
        return {}
    
def o365_license_detect():
# Check all users' home folders for Office 365 license

    o365_count = 0
    o365_detect = 0
    
    # Get all users' home folders
    cmd = ['dscl', '.', '-readall', '/Users', 'NFSHomeDirectory']
    proc = subprocess.Popen(cmd, shell=False, bufsize=-1,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (output, unused_error) = proc.communicate()
    
    # Check in all users' home folders for Office 365 license
    for user in output.split('\n'):
        if 'NFSHomeDirectory' in user and '/var/empty' not in user:
            userpath1 = user.replace("NFSHomeDirectory: ", "")+'/Library/Group Containers/UBF8T346G9.Office/com.microsoft.Office365.plist'
            userpath2 = user.replace("NFSHomeDirectory: ", "")+'/Library/Group Containers/UBF8T346G9.Office/com.microsoft.e0E2OUQxNUY1LTAxOUQtNDQwNS04QkJELTAxQTI5M0JBOTk4O.plist'
            userpath3 = user.replace("NFSHomeDirectory: ", "")+'/Library/Group Containers/UBF8T346G9.Office/e0E2OUQxNUY1LTAxOUQtNDQwNS04QkJELTAxQTI5M0JBOTk4O'
            
            if (os.path.exists(userpath1)) or (os.path.exists(userpath2)) or (os.path.exists(userpath3)):
                o365_count = o365_count + 1
                o365_detect = 1

    return {"o365_license_count":o365_count,"o365_detected":o365_detect}
    
     
def shared_o365_license_detect():
# Check if there is a shared Office 365 license in use

    if (os.path.exists("/Library/Application Support/Microsoft/Office365/com.microsoft.Office365.plist")):
        shared_o365 = {"shared_o365_license":1}
    else:
        shared_o365 = {"shared_o365_license":0}
    
    return shared_o365   
    
def get_app_data(app_path):
    
    # Read in Info.plist for processing 
    try:
        info_plist = FoundationPlist.readPlist(app_path+"/Contents/Info.plist")
        app_name = app_path.split("/")[-1].split(".")[0].replace("Microsoft ", "").replace(" ", "_").lower()
        
        app_data = {}
        if "remote_desktop" in app_name or "onedrive" in app_name:
            app_data[app_name+'_app_version'] = info_plist['CFBundleShortVersionString']
        else:
            app_data[app_name+'_app_version'] = info_plist['CFBundleVersion']
            
        gencheck = '.'.join(info_plist['CFBundleShortVersionString'].split(".")[:2])
        
        # Check generation of Office 
        if (15.11 <= float(gencheck) <= 16.16) and ( "excel" in app_name or "outlook" in app_name or "onenote" in app_name or "powerpoint" in app_name or "word" in app_name ):
            app_data[app_name+'_office_generation'] = 2016
        elif (16.17 <= float(gencheck)) and ( "excel" in app_name or "outlook" in app_name or "onenote" in app_name or "powerpoint" in app_name or "word" in app_name ):
            app_data[app_name+'_office_generation'] = 2019
        
        # Check if app is a Mac App Store app
        if os.path.exists(app_path+"/Contents/_MASReceipt"):
            app_data[app_name+'_mas'] = 1
        else:
            app_data[app_name+'_mas'] = 0
            
        return app_data
    except Exception:
        return {}
    
def getOsVersion():
    """Returns the minor OS version."""
    os_version_tuple = platform.mac_ver()[0].split('.')
    return int(os_version_tuple[1])

def to_bool(s):
    if s == True:
        return 1
    else:
        return 0    
    
def merge_two_dicts(x, y):
    z = x.copy()
    z.update(y)
    return z

def get_uid(username):
    cmd = ['/usr/bin/id', '-u', username]
    proc = subprocess.Popen(cmd, shell=False, bufsize=-1,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (output, unused_error) = proc.communicate()
    output = output.strip()
    return int(output)

def get_gid(username):
    cmd = ['/usr/bin/id', '-gr', username]
    proc = subprocess.Popen(cmd, shell=False, bufsize=-1,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (output, unused_error) = proc.communicate()
    output = output.strip()
    return int(output)

def demote():
# Get user id and group id for msupdate command
    def result():
        # Attempt to get currently logged in person
        username = (SCDynamicStoreCopyConsoleUser(None, None, None) or [None])[0]
        username = [username,""][username in [u"loginwindow", None, u""]]
        # If we can't get the current user, get last console login
        if username == "":
            username = get_last_user()
        os.setgid(get_gid(username))
        os.setuid(get_uid(username))
    return result
    
def get_last_user():

    # local constants
    setutxent_wtmp = c.setutxent_wtmp
    setutxent_wtmp.restype = None
    getutxent_wtmp = c.getutxent_wtmp
    getutxent_wtmp.restype = POINTER(utmpx)
    endutxent_wtmp = c.setutxent_wtmp
    endutxent_wtmp.restype = None
    # initialize
    setutxent_wtmp(0)
    entry = getutxent_wtmp()
    while entry:
        e = entry.contents
        entry = getutxent_wtmp()
        if (e.ut_type == 7 and e.ut_line == "console" and e.ut_user != "root" and e.ut_user != ""):
            endutxent_wtmp()
            return e.ut_user

def main():
    """Main"""
    # Create cache dir if it does not exist
    cachedir = '%s/cache' % os.path.dirname(os.path.realpath(__file__))
    if not os.path.exists(cachedir):
        os.makedirs(cachedir)

    # Skip manual check
    if len(sys.argv) > 1:
        if sys.argv[1] == 'manualcheck':
            print 'Manual check: skipping'
            exit(0)

    # If less than 10.10 (because we don't support Office 2011 or older), skip and write empty file
    if getOsVersion() < 10:
        
        result = dict()
        # Write results to cache
        output_plist = os.path.join(cachedir, 'ms_office.plist')
        plistlib.writePlist(result, output_plist)
        
    else :
            
        # Get results
        result = dict()
        
        # Check if we should run the msupdate parts, some people may want them disabled 
        msupdate_config_disabled = to_bool(CFPreferencesCopyAppValue('msupdate_config_disabled', 'org.munkireport.ms_office'))
        if os.path.exists('/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate') and msupdate_config_disabled != 1:
            msupdate_config = get_msupdate_config()
        else:
            msupdate_config = {}

        result = merge_two_dicts(msupdate_config, get_mau_prefs())
        result = merge_two_dicts(result, vl_license_detect())
        result = merge_two_dicts(result, o365_license_detect())
        result = merge_two_dicts(result, shared_o365_license_detect())
        result = merge_two_dicts(result, get_app_data("/Applications/Microsoft Excel.app"))
        result = merge_two_dicts(result, get_app_data("/Applications/Microsoft PowerPoint.app"))
        result = merge_two_dicts(result, get_app_data("/Applications/Microsoft Outlook.app"))
        result = merge_two_dicts(result, get_app_data("/Applications/Microsoft OneNote.app"))
        result = merge_two_dicts(result, get_app_data("/Applications/Microsoft Remote Desktop.app"))
        result = merge_two_dicts(result, get_app_data("/Applications/Microsoft Word.app"))
        result = merge_two_dicts(result, get_app_data("/Applications/OneDrive.app"))
        result = merge_two_dicts(result, get_app_data("/Applications/Skype for Business.app"))
        result = merge_two_dicts(result, get_app_data("/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app"))
   
        # Write memory results to cache
        output_plist = os.path.join(cachedir, 'ms_office.plist')
        FoundationPlist.writePlist(result, output_plist)
#        print FoundationPlist.writePlistToString(result)

if __name__ == "__main__":
    main()
