import urllib
import urllib2
import re
import xbmcplugin
import xbmcgui
import xbmcaddon
import httplib
import socket
import sys
import os
import datetime 
import time
import inspect 
import base64 
import hashlib
import random
import cProfile

__settings__ = xbmcaddon.Addon(id='plugin.video.plexbmc')
__cwd__ = __settings__.getAddonInfo('path')
BASE_RESOURCE_PATH = xbmc.translatePath( os.path.join( __cwd__, 'resources', 'lib' ) )
PLUGINPATH=xbmc.translatePath( os.path.join( __cwd__) )
sys.path.append(BASE_RESOURCE_PATH)
PLEXBMC_VERSION="2.0b rev 1"

try:
    from bonjourFind import *
except:
    print "BonjourFind Import Error"
    
print "===== PLEXBMC START ====="

print "PleXBMC -> running on " + str(sys.version_info)
print "PleXBMC -> running on " + str(PLEXBMC_VERSION)

try:
  from lxml import etree
  print("PleXBMC -> Running with lxml.etree")
except ImportError:
  try:
    # Python 2.5
    import xml.etree.cElementTree as etree
    print("PleXBMC -> Running with cElementTree on Python 2.5+")
  except ImportError:
    try:
      # Python 2.5
      import xml.etree.ElementTree as etree
      print("PleXBMC -> Running with ElementTree on Python 2.5+")
    except ImportError:
      try:
        # normal cElementTree install
        import cElementTree as etree
        print("PleXBMC -> Running with built-in cElementTree")
      except ImportError:
        try:
          # normal ElementTree install
          import elementtree.ElementTree as etree
          print("PleXBMC -> Running with built-in ElementTree")
        except ImportError: 
            try:
                import ElementTree as etree
                print("PleXBMC -> Running addon ElementTree version")
            except ImportError:    
                print("PleXBMC -> Failed to import ElementTree from any known place")

#Get the setting from the appropriate file.
DEFAULT_PORT="32400"
MYPLEX_SERVER="my.plexapp.com"
_MODE_GETCONTENT=0
_MODE_TVSHOWS=1
_MODE_MOVIES=2
_MODE_ARTISTS=3
_MODE_TVSEASONS=4
_MODE_PLAYLIBRARY=5
_MODE_TVEPISODES=6
_MODE_PLEXPLUGINS=7
_MODE_BASICPLAY=12
_MODE_ALBUMS=14
_MODE_TRACKS=15
_MODE_PHOTOS=16
_MODE_MUSIC=17
_MODE_VIDEOPLUGINPLAY=18
_MODE_PLEXONLINE=19
_MODE_CHANNELINSTALL=20
_MODE_CHANNELVIEW=21
_MODE_DISPLAYSERVERS=22
_MODE_PLAYLIBRARY_TRANSCODE=23

#Check debug first...
g_debug = __settings__.getSetting('debug')

def printDebug(msg,functionname=True):
    if g_debug == "true":
        if functionname is False:
            print str(msg)
        else:
            print "PleXBMC -> " + inspect.stack()[1][3] + ": " + str(msg)

#Next Check the WOL status - lets give the servers as much time as possible to come up
g_wolon = __settings__.getSetting('wolon')
if g_wolon == "true":
    from WOL import wake_on_lan
    printDebug("PleXBMC -> Wake On LAN: " + g_wolon, False)
    for i in range(1,12):
        wakeserver = __settings__.getSetting('wol'+str(i))
        if not wakeserver == "":
            try:
                printDebug ("PleXBMC -> Waking server " + str(i) + " with MAC: " + wakeserver, False)
                wake_on_lan(wakeserver)
            except ValueError:
                printDebug("PleXBMC -> Incorrect MAC address format for server " + str(i), False)
            except:
                printDebug("PleXBMC -> Unknown wake on lan error", False)

g_serverDict=[]
g_sections=[]
                    
global g_stream 
g_stream = __settings__.getSetting('streaming')
g_secondary = __settings__.getSetting('secondary')
g_streamControl = __settings__.getSetting('streamControl')
g_channelview = __settings__.getSetting('channelview')
g_flatten = __settings__.getSetting('flatten')
printDebug("PleXBMC -> Flatten is: "+ g_flatten, False)
#g_playtheme = __settings__.getSetting('playtvtheme')
g_forcedvd = __settings__.getSetting('forcedvd')
g_skintype= __settings__.getSetting('skinwatch')    
g_skinwatched="xbmc"
g_skin = xbmc.getSkinDir()

if g_skintype == "true":
    if g_skin.find('.plexbmc'):
        g_skinwatched="plexbmc"
        
if g_debug == "true":
    print "PleXBMC -> Settings streaming: " + g_stream
    print "PleXBMC -> Setting secondary: " + g_secondary
    print "PleXBMC -> Setting debug to " + g_debug
    print "PleXBMC -> Setting stream Control to : " + g_streamControl
    print "PleXBMC -> Running skin: " + g_skin
    print "PleXBMC -> Running watch view skin: " + g_skinwatched
    print "PleXBMC -> Force DVD playback: " + g_forcedvd
else:
    print "PleXBMC -> Debug is turned off.  Running silent"

#NAS Override
g_nasoverride = __settings__.getSetting('nasoverride')
printDebug("PleXBMC -> SMB IP Override: " + g_nasoverride, False)
if g_nasoverride == "true":
    g_nasoverrideip = __settings__.getSetting('nasoverrideip')
    if g_nasoverrideip == "":
        printDebug("PleXBMC -> No NAS IP Specified.  Ignoring setting")
    else:
        printDebug("PleXBMC -> NAS IP: " + g_nasoverrideip, False)
        
    g_nasroot = __settings__.getSetting('nasroot')
  
#Get look and feel
if __settings__.getSetting("contextreplace") == "true":
    g_contextReplace=True
else:
    g_contextReplace=False

g_skipcontext = __settings__.getSetting("skipcontextmenus")    
g_skipmetadata= __settings__.getSetting("skipmetadata")
g_skipmediaflags= __settings__.getSetting("skipflags")
g_skipimages= __settings__.getSetting("skipimages")

g_loc = "special://home/addons/plugin.video.plexbmc"

#Create the standard header structure and load with a User Agent to ensure we get back a response.
g_txheaders = {
              'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US;rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3 ( .NET CLR 3.5.30729)',	
              }

#Set up holding variable for session ID
global g_sessionID
g_sessionID=None
    

def discoverAllServers():
    '''
        Take the users settings and add the required master servers
        to the server list.  These are the devices which will be queried
        for complete library listings.  There are 3 types:
            local server - from IP configuration
            bonjour server - from a bonjour lookup
            myplex server - from myplex configuration
        Alters the global g_serverDict value
        @input: None
        @return: None       
    '''
    printDebug("== ENTER: discoverAllServers ==", False)
    g_bonjour = __settings__.getSetting('bonjour')

    #Set to Bonjour
    if g_bonjour == "1":
        printDebug("PleXBMC -> local Bonjour discovery setting enabled.", False)
        try:
            printDebug("Attempting bonjour lookup on _plexmediasvr._tcp")
            bonjourServer = bonjourFind("_plexmediasvr._tcp")
                                                
            if bonjourServer.complete:
                printDebug("Bonjour discovery completed")
                #Add the first found server to the list - we will find rest from here
                
                bj_server_name = bonjourServer.bonjourName[0].encode('utf-8')
                
                g_serverDict.append({'name'      : bj_server_name.split('.')[0] ,
                                     'address'   : bonjourServer.bonjourIP[0]+":"+bonjourServer.bonjourPort[0] ,
                                     'discovery' : 'bonjour' , 
                                     'token'     : None ,
                                     'uuid'      : None })
                                     
                                     
            else:
                printDebug("BonjourFind was not able to discovery any servers")

        except:
            print "PleXBMC -> Bonjour Issue.  Possibly not installed on system"
            xbmcgui.Dialog().ok("Bonjour Error","Is Bonojur installed on this system?")
    else:
        g_host = __settings__.getSetting('ipaddress')
        g_port=__settings__.getSetting('port')
        
        if not g_host:
            g_host=None
        elif not g_port:
            printDebug( "PleXBMC -> No port defined.  Using default of " + DEFAULT_PORT, False)
            g_host=g_host+":"+DEFAULT_PORT
        else:
            g_host=g_host+":"+g_port
            printDebug( "PleXBMC -> Settings hostname and port: " + g_host, False)
    
    #Set to Assisted
    if g_bonjour == "2":
        printDebug("PleXBMC -> Assisted Bonjour discovery setting enabled.", False)
        if g_host is not None:
            g_serverDict.append({'serverName': 'unknown' ,
                                 'address'   : g_host ,
                                 'discovery' : 'bonjour' , 
                                 'token'     : None ,
                                 'uuid'      : None ,
                                 'role'      : 'master' })

    #Set to Disabled       
    elif g_bonjour == "0":
        if g_host is not None:
            g_serverDict.append({'serverName': 'unknown' ,
                                 'address'   : g_host ,
                                 'discovery' : 'local' , 
                                 'token'     : None ,
                                 'uuid'      : None ,
                                 'role'      : 'master' })    
        
    if __settings__.getSetting('myplex_user') != "":
        printDebug( "PleXBMC -> Adding myplex as a server location", False)
        g_serverDict.append({'serverName': 'MYPLEX' ,
                             'address'   : "my.plex.app" ,
                             'discovery' : 'myplex' , 
                             'token'     : None ,
                             'uuid'      : None ,
                             'role'      : 'master' })
    
    
    printDebug("PleXBMC -> serverList is " + str(g_serverDict), False)

def resolveAllServers():
    '''
      Return list of all media sections configured
      within PleXBMC
      @input: None
      @Return: unique list of media sections
    '''
    printDebug("== ENTER: resolveAllServers ==", False)
    localServers=[]
      
    for servers in g_serverDict:
    
        if ( servers['discovery'] == 'local' ) or ( servers['discovery'] == 'bonjour' ):
            localServers+=getLocalServers()
        elif servers['discovery'] == 'myplex':
            localServers+=getMyPlexServers()
    
    printDebug ("Resolved server List: " + str(localServers))
    
    '''If we have more than one server source, then
       we need to ensure uniqueness amonst the
       seperate servers.
       
       If we have only one server source, then the assumption
       is that Plex will deal with this for us.
    '''
    
    if len(g_serverDict) > 1:
        oneCount=0
        for onedevice in localServers:
        
            twoCount=0
            for twodevice in localServers:

                printDebug( "["+str(oneCount)+":"+str(twoCount)+"] Checking " + onedevice['uuid'] + " and " + twodevice['uuid'])

                if oneCount == twoCount:
                    printDebug( "skip" )
                    twoCount+=1
                    continue
                    
                if onedevice['uuid'] == twodevice['uuid']:
                    printDebug ( "match" )
                    if onedevice['discovery'] == "local":
                        localServers.pop(twoCount)
                    else:
                        localServers.pop(oneCount)
                else:
                    printDebug( "no match" )
                
                twoCount+=1
             
            oneCount+=1
    
    printDebug ("Unique server List: " + str(localServers))
    return localServers     
            
def getAllSections():
    '''
        from g_serverDict, get a list of all the available sections
        and deduplicate the sections list
        @input: None
        @return: None (alters the global value g_sectionList)
    '''
    printDebug("== ENTER: getAllSections ==", False)
    printDebug("Using servers list: " + str(g_serverDict))

    for server in g_serverDict:
                                                                        
        if server['discovery'] == "local" or server['discovery'] == "bonjour":                                                
            html=getURL('http://'+server['address']+'/system/library/sections')
        elif server['discovery'] == "myplex":
            html=getMyPlexURL('/pms/system/library/sections')
            
        if html is False:
            continue
                
        tree = etree.fromstring(html).getiterator("Directory")
        
        for sections in tree:
                                
            g_sections.append({'title':sections.get('title').encode('utf-8'), 
                               'address': sections.get('host')+":"+sections.get('port'),
                               'serverName' : sections.get('serverName').encode('utf-8'),
                               'uuid' : sections.get('machineIdentifier') ,
                               'path' : sections.get('path') ,
                               'token' : sections.get('accessToken',None) ,
                               'location' : server['discovery'] ,
                               'art' : sections.get('art') ,
                               'local' : sections.get('local') ,
                               'type' : sections.get('type') })
    
    '''If we have more than one server source, then
       we need to ensure uniqueness amonst the
       seperate sections.
       
       If we have only one server source, then the assumption
       is that Plex will deal with this for us
    '''
    if len(g_serverDict) > 1:    
        oneCount=0
        for onedevice in g_sections:
        
            twoCount=0
            for twodevice in g_sections:

                printDebug( "["+str(oneCount)+":"+str(twoCount)+"] Checking " + str(onedevice['title']) + " and " + str(twodevice['title']))
                printDebug( "and "+ onedevice['uuid'] + " is equal " + twodevice['uuid'])

                if oneCount == twoCount:
                    printDebug( "skip" )
                    twoCount+=1
                    continue
                    
                if ( str(onedevice['title']) == str(twodevice['title']) ) and ( onedevice['uuid'] == twodevice['uuid'] ):
                    printDebug( "match")
                    if onedevice['local'] == "1":
                        printDebug ( "popping 2 " + str(g_sections.pop(twoCount)))
                    else:
                        printDebug ( "popping 1 " + str(g_sections.pop(oneCount)))
                else:
                    printDebug( "no match")
                
                twoCount+=1
             
            oneCount+=1
    
def getAuthDetails(details, url_format=True, prefix="&"):
    '''
        Takes the token and creates the required arguments to allow
        authentication.  This is really just a formatting tools
        @input: token as dict, style of output [opt] and prefix style [opt]
        @return: header string or header dict
    '''
    token = details.get('token', None)
        
    if url_format:
        if token:
            return prefix+"X-Plex-Token="+str(token)
        else:
            return ""
    else:
        if token:
            return {'X-Plex-Token' : token }
        else:
            return {}
            
def getMyPlexServers():
    printDebug("== ENTER: getMyPlexServers ==", False)
    
    tempServers=[]
    url_path="/pms/servers"
    
    html = getMyPlexURL(url_path)
    
    if html is False:
        return
        
    server=etree.fromstring(html).findall('Server')
    for servers in server:
        data=dict(servers.items())
        
        if data.get('owned',None) == "1":
            accessToken=getMyPlexToken()
        else:
            accessToken=data.get('accessToken',None)
        
        tempServers.append({'serverName': data['name'].encode('utf-8') ,
                            'address'   : data['address']+":"+data['port'] ,
                            'discovery' : 'myplex' , 
                            'token'     : accessToken ,
                            'uuid'      : data['machineIdentifier'] })    
    return tempServers                         
    
def getLocalServers():
    printDebug("== ENTER: getLocalServers ==", False)

    tempServers=[]
    url_path="/servers"
    html=False
    
    for local in g_serverDict:
    
        if local.get('discovery') == "local" or local.get('discovery') == "bonjour":
            html = getURL(local['address']+url_path)
            break
        
    if html is False:
         return tempServers
             
    server=etree.fromstring(html).findall('Server')
    for servers in server:
        data=dict(servers.items())
        tempServers.append({'serverName': data['name'].encode('utf-8') ,
                            'address'   : data['address']+":"+data['port'] ,
                            'discovery' : 'local' , 
                            'token'     : data.get('accessToken',None) ,
                            'uuid'      : data['machineIdentifier'] })

    return tempServers                         
                             
def getMyPlexURL(url_path,renew=False,suppress=True):
    printDebug("== ENTER: getMyPlexURL ==", False)                    
    printDebug("url = "+MYPLEX_SERVER+url_path)

    try:
        conn = httplib.HTTPSConnection(MYPLEX_SERVER) 
        conn.request("GET", url_path+"?X-Plex-Token="+getMyPlexToken(renew)) 
        data = conn.getresponse() 
        if ( int(data.status) == 401 )  and not ( renew ):
            return getMyPlexURL(url_path,True)
            
        if int(data.status) >= 400:
            error = "HTTP response error: " + str(data.status) + " " + str(data.reason)
            if suppress is False:
                xbmcgui.Dialog().ok("Error",error)
            print error
            return False
        elif int(data.status) == 301 and type == "HEAD":
            return str(data.status)+"@"+data.getheader('Location')
        else:      
            link=data.read()
            printDebug("====== XML returned =======")
            printDebug(link, False)
            printDebug("====== XML finished ======")
    except socket.gaierror :
        error = 'Unable to lookup host: ' + MYPLEX_SERVER + "\nCheck host name is correct"
        if suppress is False:
            xbmcgui.Dialog().ok("Error",error)
        print error
        return False
    except socket.error, msg : 
        error="Unable to connect to " + MYPLEX_SERVER +"\nReason: " + str(msg)
        if suppress is False:
            xbmcgui.Dialog().ok("Error",error)
        print error
        return False
    else:
        return link

def getMyPlexToken(renew=False):
    printDebug("== ENTER: getMyPlexToken ==", False)
    
    token=__settings__.getSetting('myplex_token')
    
    if ( token == "" ) or (renew):
        token = getNewMyPlexToken()
    
    printDebug("Using token: " + str(token) + "[Renew: " + str(renew) + "]")
    return token
 
def getNewMyPlexToken():
    printDebug("== ENTER: getNewMyPlexToken ==", False)

    printDebug("Getting New token")
    myplex_username = __settings__.getSetting('myplex_user')
    myplex_password = __settings__.getSetting('myplex_pass')
        
    if ( myplex_username or myplex_password ) == "":
        printDebug("No myplex details in config..")
        return False
    
    base64string = base64.encodestring('%s:%s' % (myplex_username, myplex_password)).replace('\n', '')
    txdata=""
    token=False
    
    myplex_headers={'X-Plex-Platform': "XBMC",
                    'X-Plex-Platform-Version': "11.00",
                    'X-Plex-Provides': "player",
                    'X-Plex-Product': "PleXBMC",
                    'X-Plex-Version': "2.0b",
                    'X-Plex-Device': "Not Known",
                    'X-Plex-Client-Identifier': "PleXBMC",
                    'Authorization': "Basic %s" % base64string }
    
    try:
        conn = httplib.HTTPSConnection(MYPLEX_SERVER)
        conn.request("POST", "/users/sign_in.xml", txdata, myplex_headers) 
        data = conn.getresponse() 
   
        if int(data.status) == 201:      
            link=data.read()
            printDebug("====== XML returned =======")

            try:
                token=etree.fromstring(link).findtext('authentication-token')
                __settings__.setSetting('myplex_token',token)
            except:
                printDebug(link)
            
            printDebug("====== XML finished ======")
        else:
            error = "HTTP response error: " + str(data.status) + " " + str(data.reason)
            if suppress is False:
                xbmcgui.Dialog().ok(title,error)
            print error
            return False
    except socket.gaierror :
        error = 'Unable to lookup host: ' + server + "\nCheck host name is correct"
        if suppress is False:
            xbmcgui.Dialog().ok(title,error)
        print error
        return False
    except socket.error, msg : 
        error="Unable to connect to " + server +"\nReason: " + str(msg)
        if suppress is False:
            xbmcgui.Dialog().ok(title,error)
        print error
        return False
    
    return token

def getURL( url ,title="Error", suppress=True, type="GET"):
    printDebug("== ENTER: getURL ==", False)
    try:        
        if url[0:4] == "http":
            serversplit=2
            urlsplit=3
        else:
            serversplit=0
            urlsplit=1
            
        server=url.split('/')[serversplit]
        urlPath="/"+"/".join(url.split('/')[urlsplit:])
            
        authHeader=getAuthDetails({'token':_PARAM_TOKEN}, False)
            
        printDebug("url = "+url)
        printDebug("header = "+str(authHeader))
        conn = httplib.HTTPConnection(server) 
        conn.request(type, urlPath, headers=authHeader) 
        data = conn.getresponse() 
        if int(data.status) >= 400:
            error = "HTTP response error: " + str(data.status) + " " + str(data.reason)
            if suppress is False:
                xbmcgui.Dialog().ok(title,error)
            print error 
            return False
        elif ( int(data.status) == 301 ) or ( int(data.status) == 302 ): 
            return data.getheader('Location')
        else:      
            link=data.read()
            printDebug("====== XML returned =======")
            printDebug(link, False)
            printDebug("====== XML finished ======")
    except socket.gaierror :
        error = 'Unable to lookup host: ' + server + "\nCheck host name is correct"
        if suppress is False:
            xbmcgui.Dialog().ok(title,error)
        print error
        return False
    except socket.error, msg : 
        error="Unable to connect to " + server +"\nReason: " + str(msg)
        if suppress is False:
            xbmcgui.Dialog().ok(title,error)
        print error
        return False
    else:
        return link
      
def mediaType(partproperties, server, dvdplayback=False):
    printDebug("== ENTER: mediaType ==", False)
    
    #Passed a list of <Part /> tag attributes, select the appropriate media to play
    
    stream=partproperties['key']
    file=partproperties['file']
    
    #First determine what sort of 'file' file is
        
    if file[0:2] == "\\\\":
        printDebug("Looks like a UNC")
        type="UNC"
    elif file[0:1] == "/" or file[0:1] == "\\":
        printDebug("looks like a unix file")
        type="nixfile"
    elif file[1:3] == ":\\" or file[1:2] == ":/":
        printDebug("looks like a windows file")
        type="winfile"
    else:
        printDebug("looks like nuttin' i aint ever seen")
        printDebug(str(file))
        type="notsure"
    
    # 0 is auto select.  basically check for local file first, then stream if not found
    if g_stream == "0":
        #check if the file can be found locally
        if type == "nixfile" or type == "winfile":
            try:
                printDebug("Checking for local file")
                exists = open(file, 'r')
                printDebug("Local file found, will use this")
                exists.close()
                return "file:"+file
            except: pass
                
        printDebug("No local file")
        global g_stream
        if dvdplayback:
            printDebug("Forcing SMB for DVD playback")
            g_stream="2"
        else:
            g_stream="1"
        
    # 1 is stream no matter what
    if g_stream == "1":
        printDebug( "Selecting stream")
        return "http://"+server+stream
    # 2 is use SMB 
    elif g_stream == "2" or g_stream == "3":
        if g_stream == "2":
            protocol="smb"
        else:
            protocol="afp"
            
        printDebug( "Selecting smb/unc")
        if type=="UNC":
            filelocation=protocol+":"+file.replace("\\","/")
        else:
            #Might be OSX type, in which case, remove Volumes and replace with server
            server=server.split(':')[0]
            loginstring=""

            if g_nasoverride == "true":
                if not g_nasoverrideip == "":
                    server=g_nasoverrideip
                    printDebug("Overriding server with: " + server)
                    
                nasuser=__settings__.getSetting('nasuserid')
                if not nasuser == "":
                    loginstring=__settings__.getSetting('nasuserid')+":"+__settings__.getSetting('naspass')+"@"
                    printDebug("Adding AFP/SMB login info for user " + nasuser)
                
                
            if file.find('Volumes') > 0:
                filelocation=protocol+":/"+file.replace("Volumes",loginstring+server)
            else:
                if type == "winfile":
                    filelocation=protocol+"://"+loginstring+server+"/"+file[3:]
                else:
                    #else assume its a file local to server available over smb/samba (now we have linux PMS).  Add server name to file path.
                    filelocation=protocol+"://"+loginstring+server+file
                    
        if g_nasoverride == "true" and g_nasroot != "":
            #Re-root the file path
            printDebug("Altering path " + filelocation + " so root is: " +  g_nasroot)
            if '/'+g_nasroot+'/' in filelocation:
                components = filelocation.split('/')
                index = components.index(g_nasroot)
                for i in range(3,index):
                    components.pop(3)
                filelocation='/'.join(components)
    else:
        printDebug( "No option detected, streaming is safest to choose" )       
        filelocation="http://"+server+stream
    
    printDebug("Returning URL: " + filelocation)
    return filelocation
     
def addLink(url,properties,arguments,context=None):
        printDebug("== ENTER: addLink ==", False)
        printDebug("Adding link for [" + properties.get('title','unknown') + "]")

        printDebug("Passed arguments are " + str(arguments))
        printDebug("Passed properties are " + str(properties))
        
        if (arguments.get('token',None) is None) and _PARAM_TOKEN:
            arguments['token']=_PARAM_TOKEN
        
        type=arguments.get('type','Video')
            
        if type =="Picture":
             u=url+getAuthDetails(arguments,prefix="?")
        else:
            u=sys.argv[0]+"?url="+str(url)+getAuthDetails(arguments)
        
        ok=True
                
        printDebug("URL to use for listing: " + u)
        #Create ListItem object, which is what is displayed on screen
        thumbnail=arguments.get('thumb','')
        if '?' in thumbnail :
            liz=xbmcgui.ListItem(properties['title'], iconImage=thumbnail+getAuthDetails(arguments), thumbnailImage=thumbnail+getAuthDetails(arguments))
        else:
            liz=xbmcgui.ListItem(properties['title'], iconImage=thumbnail+getAuthDetails(arguments,prefix="?"), thumbnailImage=thumbnail+getAuthDetails(arguments,prefix="?"))

        printDebug("Setting thumbnail as " + thumbnail)              
            
        #Set properties of the listitem object, such as name, plot, rating, content type, etc
        liz.setInfo( type=type, infoLabels=properties ) 
        
        liz.setProperty('Artist_Genre', properties.get('genre',''))
        liz.setProperty('Artist_Description', properties.get('plot',''))

        #Set media flag properties for the skin
        if g_skipmediaflags == "false":
            liz.setProperty('VideoResolution', arguments.get('VideoResolution',''))
            liz.setProperty('VideoCodec', arguments.get('VideoCodec',''))
            liz.setProperty('AudioCodec', arguments.get('AudioCodec',''))
            liz.setProperty('AudioChannels', arguments.get('AudioChannels',''))
            liz.setProperty('VideoAspect', arguments.get('VideoAspect',''))
              
        #Set the file as playable, otherwise setresolvedurl will fail
        liz.setProperty('IsPlayable', 'true')
                      
        #Set the fanart image if it has been enabled
        fanart=arguments.get('fanart_image','')
        if '?' in fanart:
            liz.setProperty('fanart_image', fanart + getAuthDetails(arguments))
        else:
            liz.setProperty('fanart_image', fanart + getAuthDetails(arguments,prefix="?"))  
        
        printDebug( "Setting fan art as " + fanart +" with headers: "+ getAuthDetails(arguments))
        
        if context is not None:
            printDebug("Building Context Menus")
            #transcodeURL="XBMC.RunPlugin("+u+"&transcode=1)"
            #transcodeURL="XBMC.RunScript("+PLUGINPATH+"/default.py, 0, ?url="+url+"&transcode=1)"
            #print transcodeURL
            #transcode="Container.Update("+u+"&transcode=1)"
            #context.append(("Play trancoded", transcodeURL, ))
            #cm_url_download = sys.argv[0] + '?url='+url+'&mode=23'
            #context.append(("Play with Transcoder" , "XBMC.RunPlugin(%s)" % (cm_url_download)))
            liz.addContextMenuItems(context, g_contextReplace)
        
        #Finally add the item to the on screen list, with url created above
        ok=xbmcplugin.addDirectoryItem(handle=pluginhandle,url=u,listitem=liz)
        
        return ok

def addDir(url,properties,arguments,context=None):
        printDebug("== ENTER: addDir ==", False)
        try:
            printDebug("Adding Dir for [" + properties['title'].encode('utf-8') + "]")
        except: pass

        printDebug("Passed arguments are " + str(arguments))
        printDebug("Passed properties are " + str(properties))
        
        if (arguments.get('token',None) is None) and _PARAM_TOKEN:
            arguments['token']=_PARAM_TOKEN

        
        #Create the URL to pass to the item
        u=sys.argv[0]+"?url="+str(url)+getAuthDetails(arguments)
        ok=True
                
        #Create the ListItem that will be displayed
        try:
            if '?' in arguments['thumb']:
                liz=xbmcgui.ListItem(properties['title'], iconImage=arguments['thumb']+getAuthDetails(arguments), thumbnailImage=arguments['thumb']+getAuthDetails(arguments))
            else:
                liz=xbmcgui.ListItem(properties['title'], iconImage=arguments['thumb']+getAuthDetails(arguments,prefix="?"), thumbnailImage=arguments['thumb']+getAuthDetails(arguments,prefix="?"))
            printDebug("Setting thumbnail as " + arguments['thumb']+getAuthDetails(arguments,prefix="?"))
        except:
            liz=xbmcgui.ListItem(properties['title'], iconImage='', thumbnailImage='')
        
            
        #Set the properties of the item, such as summary, name, season, etc
        try:
            liz.setInfo( type=arguments['type'], infoLabels=properties ) 
        except:
            liz.setInfo(type='Video', infoLabels=properties ) 

        printDebug("URL to use for listing: " + u)
        
        try:
            liz.setProperty('Artist_Genre', properties['genre'])
            liz.setProperty('Artist_Description', properties['plot'])
        except: pass
        
        #If we have set a number of watched episodes per season
        try:
            #Then set the number of watched and unwatched, which will be displayed per season
            liz.setProperty('WatchedEpisodes', str(arguments['WatchedEpisodes']))
            liz.setProperty('UnWatchedEpisodes', str(arguments['UnWatchedEpisodes']))
        except: pass
        
        #Set the fanart image if it has been enabled
        try:
            if '?' in arguments['fanart_image']:
                liz.setProperty('fanart_image', str(arguments['fanart_image']+getAuthDetails(arguments)))
            else:
                liz.setProperty('fanart_image', str(arguments['fanart_image']+getAuthDetails(arguments,prefix="?")))
            
            printDebug( "Setting fan art as " + str(arguments['fanart_image'])+" with headers: "+ getAuthDetails(arguments))
        except: pass

        try:
            liz.setProperty('bannerArt', arguments['banner']+getAuthDetails(arguments,prefix="?"))
            printDebug( "Setting banner art as " + str(arguments['banner']))
        except:
            pass

        if context is not None:
            printDebug("Building Context Menus")
            liz.addContextMenuItems( context, g_contextReplace )
       
        #Finally add the item to the on screen list, with url created above
        ok=xbmcplugin.addDirectoryItem(handle=pluginhandle,url=u,listitem=liz,isFolder=True)
        return ok
        
def displaySections(filter=None):
        printDebug("== ENTER: displaySections() ==", False)
        xbmcplugin.setContent(pluginhandle, 'movies')

        #Get the global host variable set in settings        
        numOfServers=len(g_serverDict)
                
        printDebug( "Using list of "+str(numOfServers)+" servers: " +  str(g_serverDict))
        
        getAllSections()
        
        for arguments in g_sections:
                
                properties={}
                #Check if we are to display all or just local sections (all for bonjour)
                
                if g_skipimages == "false":
                    try:
                        if arguments['art'][0] == "/":
                            arguments['fanart_image']="http://"+arguments['address']+arguments['art']
                        else:
                            arguments['fanart_image']=arguments['art']
                    
                    except: 
                        arguments['fanart_image']=""
                        
                    try:
                        if arguments['thumb'][0] == "/":
                            arguments['thumb']="http://"+arguments['address']+arguments['thumb'].split('?')[0]
                        else:
                            arguments['thumb']="http://"+arguments['address']+"/library/sections/"+arguments['thumb'].split('?')[0]
                    except:
                            arguments['thumb']=arguments['fanart_image']
                    
                #Start pulling out information from the parsed XML output. Assign to various variables
                try:
                    if len(g_serverDict) == 1:
                        properties['title']=arguments['title']
                    else:
                        properties['title']=arguments['serverName']+": "+arguments['title']
                except:
                    properties['title']="unknown"
                
                
                #Determine what we are going to do process after a link is selected by the user, based on the content we find
                if arguments['type'] == 'show':
                    mode=1
                    if (filter is not None) and (filter != "tvshows"):
                        continue
                        
                elif  arguments['type'] == 'movie':
                    mode=2
                    if (filter is not None) and (filter != "movies"):
                        continue

                elif  arguments['type'] == 'artist':
                    mode=3
                    if (filter is not None) and (filter != "music"):
                        continue

                elif  arguments['type'] == 'photo':
                    mode=16
                    if (filter is not None) and (filter != "photos"):
                        continue

                else:
                    printDebug("Ignoring section "+properties['title']+" of type " + arguments['type'] + " as unable to process")
                    continue
                
                arguments['type']="Video"
                
                if g_secondary == "true":
                    s_url='http://'+arguments['address']+arguments['path']+"&mode=0"
                else:
                    #Build URL with the mode to use and key to further XML data in the library
                    s_url='http://'+arguments['address']+arguments['path']+'/all'+"&mode="+str(mode)
                

                if g_skipcontext == "false":
                    context=[]
                    refreshURL="http://"+arguments['address']+arguments['path']+"/refresh"
                    libraryRefresh = "XBMC.RunScript("+g_loc+"/default.py, update ," + refreshURL + ")"
                    context.append(('Refresh library section', libraryRefresh , ))
                else:
                    context=None
                
                #Build that listing..
                addDir(s_url, properties,arguments, context)
       
        #For each of the servers we have identified
        allservers=resolveAllServers()
        numOfServers=len(allservers)
        
        for server in allservers:
                                                                                              
            #Plex plugin handling 
            if (filter is not None) and (filter != "plugins"):
                continue 
            
            arguments={}
            properties={}
          
            if numOfServers > 1:
                prefix=server['serverName']+": "
            else:
                prefix=""
                    
            properties['title']=prefix+"Channels"
                
            arguments['type']="video"
            mode=21
            u="http://"+server['address']+"/system/plugins/all&mode="+str(mode)
            addDir(u,properties,arguments)
                    
            #Create plexonline link
            properties['title']=prefix+"Plex Online"
            arguments['type']="file"
            mode=19
            u="http://"+server['address']+"/system/plexonline&mode="+str(mode)
            addDir(u,properties,arguments)
          
        #All XML entries have been parsed and we are ready to allow the user to browse around.  So end the screen listing.
        xbmcplugin.endOfDirectory(pluginhandle)  

def Movies(url,tree=None):
        printDebug("== ENTER: Movies() ==", False)
        xbmcplugin.setContent(pluginhandle, 'movies')
                
        #get the server name from the URL, which was passed via the on screen listing..
        if tree is None:
            #Get some XML and parse it
            html=getURL(url)
            
            if html is False:
                return
                
            tree = etree.fromstring(html)

        server=getServerFromURL(url)
                        
        ramdonNumber=str(random.randint(1000000000,9999999999))   
        #Find all the video tags, as they contain the data we need to link to a file.
        MovieTags=tree.findall('Video')
        fullList=[]
        for movie in MovieTags:
            
            printDebug("---New Item---")
            tempgenre=[]
            tempcast=[]
            tempdir=[]
            tempwriter=[]
            
            #Lets grab all the info we can quickly through either a dictionary, or assignment to a list
            #We'll process it later
            for child in movie:
                if child.tag == "Media":
                    mediaarguments = dict(child.items())
                elif child.tag == "Genre" and g_skipmetadata == "false":
                    tempgenre.append(child.get('tag'))
                elif child.tag == "Writer"  and g_skipmetadata == "false":
                    tempwriter.append(child.get('tag'))
                elif child.tag == "Director"  and g_skipmetadata == "false":
                    tempdir.append(child.get('tag'))
                elif child.tag == "Role"  and g_skipmetadata == "false":
                    tempcast.append(child.get('tag'))
            
            printDebug("Media attributes are " + str(mediaarguments))
                                        
            #Gather some data 
            view_offset=movie.get('viewOffset',0)
            duration=int(mediaarguments.get('duration',movie.get('duration',0)))/1000
                                   
            #Required listItem entries for XBMC
            details={'plot'      : movie.get('summary','') ,
                     'title'     : movie.get('title','Unknown').encode('utf-8') ,
                     'playcount' : int(movie.get('viewCount',0)) ,
                     'rating'    : float(movie.get('rating',0)) ,
                     'studio'    : movie.get('studio','') ,
                     'mpaa'      : "Rated " + movie.get('contentRating', 'unknown') ,
                     'year'      : int(movie.get('year',0)) ,
                     'tagline'   : movie.get('tagline','') ,
                     'duration'  : str(datetime.timedelta(seconds=duration)) ,
                     'overlay'   : 6 }
            
            #Extra data required to manage other properties
            extraData={'type'         : "Video" ,
                       'thumb'        : getThumb(movie, server) ,
                       'fanart_image' : getFanart(movie,server) ,
                       'token'        : _PARAM_TOKEN ,
                       'key'          : movie.get('key',''),
                       'ratingKey'    : str(movie.get('ratingKey',0)) }

            #Determine what tupe of watched flag [overlay] to use
            if details['playcount'] > 0:
                if g_skinwatched == "xbmc":          #WATCHED
                    details['overlay']=7   #Tick ICON  in XBMC
                elif g_skinwatched == "plexbmc":
                    details['overlay']=0   #Blank entry in Plex
            elif details['playcount'] == 0: 
                if g_skinwatched == "plexbmc":
                    details['overlay']=4   #PLEX shows dot (using overlayhastrainer)
            
            if g_skinwatched == "plexbmc" and int(view_offset) > 0:
                details['overlay'] = 5     #PLEX show partial viewing (using overlaytrained)            
            
            #Extended Metadata
            if g_skipmetadata == "false":
                details['cast']     = tempcast
                details['director'] = " / ".join(tempdir)
                details['writer']   = " / ".join(tempwriter)
                details['genre']    = " / ".join(tempgenre)
                 
            #Add extra media flag data
            if g_skipmediaflags == "false":
                extraData['VideoResolution'] = mediaarguments.get('videoResolution','')
                extraData['VideoCodec']      = mediaarguments.get('videoCodec','')
                extraData['AudioCodec']      = mediaarguments.get('audioCodec','')
                extraData['AudioChannels']   = mediaarguments.get('audioChannels','')
                extraData['VideoAspect']     = mediaarguments.get('aspectRatio','')

            #Build any specific context menu entries
            if g_skipcontext == "false":
                context=buildContextMenu(url, extraData)    
            else:
                context=None
            # http:// <server> <path> &mode=<mode> &id=<media_id> &t=<rnd>
            u="http://%s%s&mode=%s&id=%s&t%s" % (server, extraData['key'], _MODE_PLAYLIBRARY, extraData['ratingKey'], ramdonNumber)
          
            #Right, add that link...and loop around for another entry
            addLink(u,details,extraData,context)        
        
        #If we get here, then we've been through the XML and it's time to finish.
        xbmcplugin.endOfDirectory(pluginhandle)
 
def buildContextMenu(url, arguments):
    context=[]
    server=getServerFromURL(url)
    refreshURL=url.replace("/all", "/refresh")
    plugin_url="XBMC.RunScript("+g_loc+"/default.py, "
    ID=arguments.get('ratingKey','0')

    #Initiate Library refresh 
    libraryRefresh = plugin_url+"update, " + refreshURL.split('?')[0]+getAuthDetails(arguments,prefix="?") + ")"
    context.append(('Rescan library section', libraryRefresh , ))
    
    #Mark media unwatched
    unwatchURL="http://"+server+"/:/unscrobble?key="+ID+"&identifier=com.plexapp.plugins.library"+getAuthDetails(arguments)
    unwatched=plugin_url+"watch, " + unwatchURL + ")"
    context.append(('Mark as Unwatched', unwatched , ))
            
    #Mark media watched        
    watchURL="http://"+server+"/:/scrobble?key="+ID+"&identifier=com.plexapp.plugins.library"+getAuthDetails(arguments)
    watched=plugin_url+"watch, " + watchURL + ")"
    context.append(('Mark as Watched', watched , ))

    #Delete media from Library
    deleteURL="http://"+server+"/library/metadata/"+ID+getAuthDetails(arguments)
    removed=plugin_url+"delete, " + deleteURL + ")"
    context.append(('Delete media', removed , ))

    #Display plugin setting menu
    settingDisplay=plugin_url+"setting)"
    context.append(('PleXBMC settings', settingDisplay , ))

    #Reload media section
    listingRefresh=plugin_url+", refresh)"
    context.append(('Reload Section', listingRefresh , ))

    printDebug("Using context menus " + str(context))
    
    return context
    
def SHOWS(url,tree=None):
        printDebug("== ENTER: SHOWS() ==", False)
        xbmcplugin.setContent(pluginhandle, 'tvshows')

        #xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
                
        #Get the URL and server name.  Get the XML and parse
        if tree is None:
            html=getURL(url)
        
            if html is False:
                return

            tree=etree.fromstring(html)
 
        server=getServerFromURL(url)
 
        #For each directory tag we find
        ShowTags=tree.findall('Directory') # These type of calls seriously slow down plugins
        for show in ShowTags:

            arguments=dict(show.items())
            tempgenre=[]
            
            #Lets grab all the info we can quickly through either a dictionary, or assignment to a list
            #We'll process it later
            for child in show:
                try:
                    tempgenre.append(child.get('tag'))
                except:pass
                
            #Create the basic data structures to pass up
            properties={'overlay': 6, 'playcount': 0, 'season' : 0 , 'episode':0 }   #Create a dictionary for properties with some defaults(i.e. ListItem properties)
            
            #Get name
            try:
                properties['title']=properties['tvshowname']=arguments['title'].encode('utf-8')
            except: pass
            
            #Get the studio
            try:
                properties['studio']=arguments['studio']
            except:pass
            
            #Get the Plot          
            try:
                properties['plot']=arguments['summary']
            except: pass

            #Get the certificate to see how scary it is..
            try:
                properties['mpaa']=arguments['contentrating']
            except:pass
                
            #Get number of episodes in season
            try:
                 properties['episode']=int(arguments['leafCount'])
            except:pass
            
            #Get number of watched episodes
            try:
                watched=arguments['viewedLeafCount']
                arguments['WatchedEpisodes']=int(watched)
                arguments['UnWatchedEpisodes']=properties['episode']-arguments['WatchedEpisodes']
            except:
                arguments['WatchedEpisodes']=0
                arguments['UnWatchedEpisodes']=0
    
            #banner art
            try:
                arguments['banner']='http://'+server+arguments['banner'].split('?')[0]+"/banner.jpg"
            except:
                pass
                
            if arguments['WatchedEpisodes'] == 0:
                if g_skinwatched == "xbmc":          #UNWATCHED
                    properties['overlay']=6   #XBMC shows blank
                elif g_skinwatched == "plexbmc":
                    properties['overlay']=4   #PLEX shows dot (using overlayhastrainer)
            elif arguments['UnWatchedEpisodes'] == 0: 
                if g_skinwatched == "xbmc":          #WATCHED
                    properties['overlay']=7   #Tick ICON  in XBMC
                elif g_skinwatched == "plexbmc":
                    properties['overlay']=0   #Blank entry in Plex
            else:
                if g_skinwatched == "plexbmc":
                    properties['overlay'] = 5     #PLEX show partial viewing (using overlaytrained)
                elif g_skinwatched == "xbmc":
                    properties['overlay']=6
            
            #get Genre
            try:
                properties['genre']=" / ".join(tempgenre)
            except:pass
                
            #get the air date
            try:
                properties['aired']=arguments['originallyAvailableAt']
            except:pass

            if g_skipimages == "false":            
                #Get the picture to use 
                arguments['thumb']=getThumb(arguments, server)
                   
                #Get a nice big picture  
                arguments['fanart_image']=getFanart(arguments,server)
           
            #Set type
            arguments['type']="Video"

            if g_flatten == "2":
                printDebug("Flattening all shows")
                mode=6 # go straight to episodes
                arguments['key']=arguments['key'].replace("children","allLeaves")
                u='http://'+server+arguments['key']+"&mode="+str(mode)
            else:
                mode=4 # grab season details
                u='http://'+server+arguments['key']+"&mode="+str(mode)
            
            if g_skipcontext == "false":
                context=buildContextMenu(url, arguments)
            else:
                context=None
                
            addDir(u,properties,arguments, context) 
            
        #End the listing    
        xbmcplugin.endOfDirectory(pluginhandle)
 
def Seasons(url):
        printDebug("== ENTER: season() ==", False)
        xbmcplugin.setContent(pluginhandle, 'seasons')

        #xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)

        
        #Get URL, XML and parse
        server=getServerFromURL(url)
        html=getURL(url)
        
        if html is False:
            return
       
        tree=etree.fromstring(html)
        
        willFlatten=False
        if g_flatten == "1":
            #check for a single season
            if int(tree.get('size')) == 1:
                printDebug("Flattening single season show")
                willFlatten=True
        sectionart=getFanart(dict(tree.items()), server)
       
        #if g_playtheme == "true":
        #    try:
        #        theme = tree.get('theme').split('?')[0]
        #        xbmc.Player().play('http://'+server+theme+'/theme.mp3')
        #    except:
        #        printDebug("No Theme music to play")
        #        pass
                
       
        #For all the directory tags
        ShowTags=tree.findall('Directory')
        for show in ShowTags:

            if willFlatten:
                url='http://'+server+show.get('key')
                EPISODES(url)
                return
        
            arguments=dict(show.items());
            arguments['token']=_PARAM_TOKEN

            #Build basic data structures
            properties={'playcount': 0, 'season' : 0 , 'episode':0 }   #Create a dictionary for properties with some defaults(i.e. ListItem properties)
 
            #Get name
            try:
                properties['tvshowtitle']=properties['title']=arguments['title'].encode('utf-8')
            except: pass
       
            if g_skipimages == "false":

                #Get the picture to use 
                arguments['thumb']=getThumb(arguments, server)
                   
                #Get a nice big picture  
                arguments['fanart_image']=getFanart(arguments, server)
                try:
                    if arguments['fanart_image'] == "":
                        arguments['fanart_image']=sectionart
                except:
                    pass

            #Get number of episodes in season
            try:
                 properties['episode']=int(arguments['leafCount'])
            except:pass
            
            #Get number of watched episodes
            try:
                watched=arguments['viewedLeafCount']
                arguments['WatchedEpisodes']=int(watched)
                arguments['UnWatchedEpisodes']=properties['episode']-arguments['WatchedEpisodes']
            except:
                arguments['WatchedEpisodes']=0
                arguments['UnWatchedEpisodes']=0
    
                
            if arguments['WatchedEpisodes'] == 0:
                if g_skinwatched == "xbmc":          #UNWATCHED
                    properties['overlay']=6   #XBMC shows blank
                elif g_skinwatched == "plexbmc":
                    properties['overlay']=4   #PLEX shows dot (using overlayhastrainer)
            elif arguments['UnWatchedEpisodes'] == 0: 
                if g_skinwatched == "xbmc":          #WATCHED
                    properties['overlay']=7   #Tick ICON  in XBMC
                elif g_skinwatched == "plexbmc":
                    properties['overlay']=0   #Blank entry in Plex
            else:
                if g_skinwatched == "plexbmc" :
                    properties['overlay'] = 5     #PLEX show partial viewing (using overlaytrained)
                elif g_skinwatched == "xbmc":
                    properties['overlay']=6

    
            #Get the Plot          
            try:
                properties['plot']=arguments['summary']
            except: pass

            #Set type
            arguments['type']="Video"

            #Set the mode to episodes, as that is what's next     
            mode=6
            
            url='http://'+server+arguments['key']+"&mode="+str(mode)

            if g_skipcontext == "false":
                context=buildContextMenu(url, arguments)
            else:
                context=None
                
            #Build the screen directory listing
            addDir(url,properties,arguments, context) 
            
        #All done, so end the listing
        xbmcplugin.endOfDirectory(pluginhandle)
 
def EPISODES(url,tree=None):
        printDebug("== ENTER: EPISODES() ==", False)
        xbmcplugin.setContent(pluginhandle, 'episodes')
        
        #xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_EPISODE)
                
        if tree is None:
            #Get URL, XML and Parse
            html=getURL(url)
            
            if html is False:
                return
            
            tree=etree.fromstring(html)
        
        ShowTags=tree.findall('Video')
            
        server=getServerFromURL(url)
        
        #Get the end part of the URL, as we need to get different data if parsing "All Episodes"

        target=url.split('/')[-1]

        printDebug("target URL is " + target)

        try:
            displayShow = tree.get('mixedParents')
            printDebug("TV listing contains mixed shows")
        except: 
            displayShow = "0"
                        
        if displayShow == "0" or displayShow is None:
            #Name of the show
            try:
                showname=tree.get('grandparentTitle')
            except:
                showname=None
            
            #the kiddie rating
            try:
                certificate = tree.get('grandparentContentRating')
            except:
                certificate=None
            
            #the studio
            try:
                studio = tree.get('grandparentStudio')
            except:
                studio = None
              
              
            #If we are processing individual season, then get the season number, else we'll get it later
            try:
                season=tree.get('parentIndex')
            except:pass

        if g_skipimages == "false":        
            sectionart=getFanart(dict(tree.items()), server)
        
         
        #right, not for each show we find
        for show in ShowTags:
            
            arguments=dict(show.items())
            arguments['token']=_PARAM_TOKEN            
            tempgenre=[]
            tempcast=[]
            tempdir=[]
            tempwriter=[]
            
            #Lets grab all the info we can quickly through either a dictionary, or assignment to a list
            #We'll process it later
            for child in show:
                if child.tag == "Media":
                    mediaarguments = dict(child.items())
                elif child.tag == "Genre" and g_skipmetadata == "false":
                    tempgenre.append(child.get('tag'))
                elif child.tag == "Writer" and g_skipmetadata == "false":
                    tempwriter.append(child.get('tag'))
                elif child.tag == "Director" and g_skipmetadata == "false":
                    tempdir.append(child.get('tag'))
                elif child.tag == "Role" and g_skipmetadata == "false":
                    tempcast.append(child.get('tag'))
            
            #required to grab to check if file is a .strm file
           
            printDebug("Media attributes are " + str(mediaarguments))
            printDebug( "Extra info is " + str(tempgenre) + str(tempwriter) + str(tempcast) + str(tempdir))
            
            #Set basic structure with some defaults.  Overlay 6 is unwatched
            properties={'playcount': 0, 'season' : 0}   #Create a dictionary for properties with some defaults(i.e. ListItem properties)
            #arguments={'type': "tvshows", 'viewoffset': 0, 'duration': 0, 'thumb':''}    #Create a dictionary for file arguments (i.e. stuff you need, but are no listitems)
            
            #Get the episode number
            try:
                properties['episode']=int(arguments['index'])
            except: pass

            #Get name
            try:
                properties['title']=str(properties['episode']).zfill(2)+". "+arguments['title'].encode('utf-8')
            except: 
                properties['title']="Unknown"
                       
            #Get the Plot          
            try:
                properties['plot']=arguments['summary']
            except: pass
            
            #Get the watched status
            try:
                properties['playcount']=int(arguments['viewCount'])
            except:
                properties['playcount']=0
                
            try:
                arguments['viewOffset']
            except:
                arguments['viewOffset']=0

            
            if properties['playcount'] > 0:
                if g_skinwatched == "xbmc":          #WATCHED
                    properties['overlay']=7   #Tick ICON  in XBMC
                elif g_skinwatched == "plexbmc":
                    properties['overlay']=0   #Blank entry in Plex
            elif properties['playcount'] == 0: 
                if g_skinwatched == "xbmc":          #UNWATCHED
                    properties['overlay']=6   #XBMC shows blank
                elif g_skinwatched == "plexbmc":
                    properties['overlay']=4   #PLEX shows dot (using overlayhastrainer)
            
            if g_skinwatched == "plexbmc" and int(arguments['viewOffset']) > 0:
                properties['overlay'] = 5     #PLEX show partial viewing (using overlaytrained)
            
            #Get how good it is, based on your votes...
            try:
                properties['rating']=float(arguments['rating'])
            except: pass
                        
            #If we are processing an "All Episodes" directory, then get the season from the video tag
            
            try:
                if season:
                    properties['season']=int(season)
            except:
                try:
                    properties['season']=int(arguments['parentIndex'])
                except: pass
                
            #check if we got the kiddie rating from the main tag
            try:
                if certificate:
                    properties['mpaa']=certificate
            except:
                try:
                    properties['mpaa']=arguments['contentRating']
                except:pass    
                    
            #Check if we got the showname from the main tag        
            try:
                if showname:
                    properties['tvshowtitle']=showname
            except:
                try:
                    properties['tvshowtitle']=arguments['grandparentTitle']
                except: pass
            
            try:
                if displayShow == "1":
                    properties['title']=properties['tvshowtitle']+": "+properties['title']
            except: pass
            
            #check if we got the studio from the main tag.
            try:
                if studio:
                    properties['studio']=studio
            except:
                try:
                    properties['studio']=arguments['studio']
                except: pass
              
            if g_skipimages == "false":
                  
                #Get the picture to use
                arguments['thumb']=getThumb(arguments, server)
                   
                #Get a nice big picture  
                arguments['fanart_image']=getFanart(arguments, server)
                try:
                    if arguments['fanart_image'] == "":
                        arguments['fanart_image']=sectionart
                except:
                    pass

            #Set type
            arguments['type']="Video"

            
            if g_skipmetadata == "false":
                #Cast
                properties['cast']=tempcast
                
                #director
                properties['director']=" / ".join(tempdir)
                
                #Writer
                properties['writer']=" / ".join(tempwriter)
                
                #Genre        
                properties['genre']=" / ".join(tempgenre) 
            
            #get the air date
            try:
                properties['aired']=arguments['originallyAvailableAt']
            except:pass
            
            #Set the film duration 
            try:
                arguments['duration']=mediaarguments['duration']
            except KeyError:
                try:
                    arguments['duration']
                except:
                    arguments['duration']=0
             
            arguments['duration']=int(arguments['duration'])/1000
            properties['duration']=str(datetime.timedelta(seconds=int(arguments['duration'])))
            
            #If we are streaming, then get the virtual location
            #url=
            #Set mode 5, which is play            
            mode=5

            u='http://'+server+arguments['key']+"&mode="+str(mode)+"&id="+str(arguments['ratingKey'])
            
            if g_skipcontext == "false":
                context=buildContextMenu(url, arguments)
            else:
                context=None
             
            if g_skipmediaflags == "false":
                ### MEDIA FLAG STUFF ###
                try:
                    arguments['VideoResolution']=mediaarguments['videoResolution']
                except: pass
                try:
                    arguments['VideoCodec']=mediaarguments['videoCodec']
                except: pass
                try:
                    arguments['AudioCodec']=mediaarguments['audioCodec']
                except: pass
                
                try:
                    arguments['AudioChannels']=mediaarguments['audioChannels']
                except: pass
                try:
                    arguments['VideoAspect']=mediaarguments['aspectRatio']
                except: pass

            
            #Build a file link and loop
            addLink(u,properties,arguments, context)        
        
        #End the listing
        xbmcplugin.endOfDirectory(pluginhandle)

def getAudioSubtitlesMedia(server,id):
    printDebug("== ENTER: getAudioSubtitlesMedia ==", False)
    printDebug("Gather media stream info" ) 
    #Using PMS settings for audio and subtitle display
            
    #get metadata for audio and subtitle
    suburl="http://"+server+"/library/metadata/"+id
            
    html=getURL(suburl)
    tree=etree.fromstring(html)

    parts=[]
    partsCount=0
    subtitle={}
    subCount=0
    audio={}
    audioCount=0
    external={}
    media={}
    subOffset=-1
    audioOffset=-1
    selectedSubOffset=-1
    selectedAudioOffset=-1
    
    timings = tree.find('Video')
    try:
        media['viewOffset']=timings.get('viewOffset')
    except:
        media['viewOffset']=0
        
    try:    
        media['duration']=timings.get('duration')
    except:
        media['duration']=0
    
    options = tree.getiterator('Part')    
    
    contents="type"
    
    #Get the Parts info for media type and source selection 
    for stuff in options:
        try:
            bits=stuff.get('key'), stuff.get('file')
            parts.append(bits)
            partsCount += 1
        except: pass
        
    if g_streamControl == "1" or g_streamControl == "2":

        contents="all"
        tags=tree.getiterator('Stream')
        
        
        for bits in tags:
            stream=dict(bits.items())
            if stream['streamType'] == '2':
                audioCount += 1
                audioOffset += 1
                try:
                    if stream['selected'] == "1":
                        printDebug("Found preferred audio id: " + str(stream['id']) ) 
                        audio=stream
                        selectedAudioOffset=audioOffset
                except: pass
                     
            elif stream['streamType'] == '3':
                subOffset += 1
                try:
                    if stream['key']:
                        printDebug( "Found external subtitles id : " + str(stream['id']))
                        external=stream
                        external['key']='http://'+server+external['key']
                except: 
                    #Otherwise it's probably embedded
                    try:
                        if stream['selected'] == "1":
                            printDebug( "Found preferred subtitles id : " + str(stream['id']))
                            subCount += 1
                            subtitle=stream
                            selectedSubOffset=subOffset
                    except: pass
          
    else:
            printDebug( "Stream selection is set OFF")
              
    
    printDebug( {'contents':contents,'audio':audio, 'audioCount': audioCount, 'subtitle':subtitle, 'subCount':subCount ,'external':external, 'parts':parts, 'partsCount':partsCount, 'media':media, 'subOffset':selectedSubOffset, 'audioOffset':selectedAudioOffset})
    return {'contents':contents,'audio':audio, 'audioCount': audioCount, 'subtitle':subtitle, 'subCount':subCount ,'external':external, 'parts':parts, 'partsCount':partsCount, 'media':media, 'subOffset':selectedSubOffset, 'audioOffset':selectedAudioOffset}
   
def PLAYEPISODE(id,vids,override=False):
        printDebug("== ENTER: PLAYEPISODE ==", False)
        #Use this to play PMS library items that you want updated (Movies, TV shows)
        
        getTranscodeSettings(override)
      
        server=getServerFromURL(vids)
        
        streams=getAudioSubtitlesMedia(server,id)     
        url=selectMedia(streams['partsCount'],streams['parts'], server)

        if url is None:
            return
            
        protocol=url.split(':',1)[0]
  
        if protocol == "file":
            printDebug( "We are playing a local file")
            #Split out the path from the URL
            playurl=url.split(':',1)[1]
        elif protocol == "http":
            printDebug( "We are playing a stream")
            if g_transcode == "true":
                printDebug( "We will be transcoding the stream")
                playurl=transcode(id,url)+getAuthDetails({'token':_PARAM_TOKEN})

            else:
                playurl=url+getAuthDetails({'token':_PARAM_TOKEN},prefix="?")
        else:
            playurl=url
   
        
        try:
            resume=int(int(streams['media']['viewOffset'])/1000)
        except:
            resume=0
        
        printDebug("Resume has been set to " + str(resume))
        
        #Build a listitem, based on the url of the file
        item = xbmcgui.ListItem(path=playurl)
        result=1
            
        #If we passed a positive resume time, then we need to display the dialog box to ask the user what they want to do    
        if resume > 0:
            
            #Human readable time
            displayTime = str(datetime.timedelta(seconds=int(resume)))
            
            #Build the dialog text
            dialogOptions = [ "Resume from " + str(displayTime) , "Start from beginning"]
            printDebug( "We have part way through video.  Display resume dialog")
            
            #Create a dialog object
            startTime = xbmcgui.Dialog()
            
            #Box displaying resume time or start at beginning
            result = startTime.select('Resuming playback..',dialogOptions)
            
            #result contains an integer based on the selected text.
            if result == -1:
                #-1 is an exit without choosing, so end the function and start again when the user selects a new file.
                return
        
        printDebug("handle is " + str(pluginhandle))
        #ok - this will start playback for the file pointed to by the url
        if override:
            start=xbmc.Player().play(listitem=item)
        else:
            start = xbmcplugin.setResolvedUrl(pluginhandle, True, item)
        
        #Set a loop to wait for positive confirmation of playback
        count = 0
        while not xbmc.Player().isPlaying():
            printDebug( "Not playing yet...sleep for 2")
            count = count + 2
            if count >= 20:
                #Waited 20 seconds and still no movie playing - assume it isn't going to..
                return
            else:
                time.sleep(2)
                   
        #If we get this far, then XBMC must be playing
        
        #If the user chose to resume...
        if result == 0:
            #Need to skip forward (seconds)
            printDebug("Seeking to " + str(resume))
            xbmc.Player().pause()
            xbmc.Player().seekTime((resume)) 
            time.sleep(1)
            seek=xbmc.Player().getTime()

            while not ((seek-10) < resume < (seek + 10)):
                printDebug( "Do not appear to have seeked correctly. Try again")
                xbmc.Player().seekTime((resume)) 
                time.sleep(1)
                seek=xbmc.Player().getTime()
            
            xbmc.Player().pause()
    
        if not (g_transcode == "true" ): 
            #Next Set audio and subs
            setAudioSubtitles(streams)
     
            #OK, we have a file, playing at the correct stop.  Now we need to monitor the file playback to allow updates into PMS
        monitorPlayback(id,server)
        
        return

def setAudioSubtitles(stream):
    printDebug("== ENTER: setAudioSubtitles ==", False)
    #printDebug ("Found " + str(audioCount) + " audio streams")
        
    if stream['contents'] == "type":
        printDebug ("No streams to process.")
        
        if g_streamControl == "3":
            xbmc.Player().showSubtitles(False)    
            printDebug ("All subs disabled")

        return True

    if g_streamControl == "1" or  g_streamControl == "2":
        audio=stream['audio']
        printDebug("Attempting to set Audio Stream")
        #Audio Stream first        
        if stream['audioCount'] == 1:
            printDebug ("Only one audio stream present - will leave as default")
        elif stream['audioCount'] > 1:
            printDebug ("Multiple audio stream. Attempting to set to local language")
            try:
                if audio['selected'] == "1":
                    printDebug ("Found preferred language at index " + str(stream['audioOffset']))
                    xbmc.Player().setAudioStream(stream['audioOffset'])
                    printDebug ("Audio set")
            except: pass
      
    #Try and set embedded subtitles
    if g_streamControl == "1":
        subtitle=stream['subtitle']
        printDebug("Attempting to set subtitle Stream", True)
        try:
            if stream['subCount'] > 0 and subtitle['languageCode']:
                printDebug ("Found embedded subtitle for local language" )
                printDebug ("Enabling embedded subtitles")
                xbmc.Player().showSubtitles(False)
                xbmc.Player().setSubtitleStream(stream['subOffset'])
                return True
            else:
                printDebug ("No embedded subtitles to set")
        except:
            printDebug("Unable to set subtitles")
  
    if g_streamControl == "1" or g_streamControl == "2":
        external=stream['external']
        printDebug("Attempting to set external subtitle stream")
    
        try:   
            if external:
                try:
                    printDebug ("External of type ["+external['codec']+"]")
                    if external['codec'] == "idx" or external['codec'] =="sub":
                        printDebug ("Skipping IDX/SUB pair - not supported yet")
                    else:    
                        xbmc.Player().setSubtitles(external['key'])
                        return True
                except: pass                    
            else:
                printDebug ("No external subtitles available. Will turn off subs")
        except:
            printDebug ("No External subs to set")
            
    xbmc.Player().showSubtitles(False)    
    return False
        
def codeToCountry( id ):
  languages = { 
  	"None": "none",
    "alb" : "Albanian",
    "ara" : "Arabic"            ,
    "arm" : "Belarusian"        ,
    "bos" : "Bosnian"           ,
    "bul" : "Bulgarian"         ,
    "cat" : "Catalan"           ,
    "chi" : "Chinese"           ,
    "hrv" : "Croatian"          ,
    "cze" : "Czech"             ,
    "dan" : "Danish"            ,
    "dut" : "Dutch"             ,
    "eng" : "English"           ,
    "epo" : "Esperanto"         ,
    "est" : "Estonian"          ,
    "per" : "Farsi"             ,
    "fin" : "Finnish"           ,
    "fre" : "French"            ,
    "glg" : "Galician"          ,
    "geo" : "Georgian"          ,
    "ger" : "German"            ,
    "ell" : "Greek"             ,
    "heb" : "Hebrew"            ,
    "hin" : "Hindi"             ,
    "hun" : "Hungarian"         ,
    "ice" : "Icelandic"         ,
    "ind" : "Indonesian"        ,
    "ita" : "Italian"           ,
    "jpn" : "Japanese"          ,
    "kaz" : "Kazakh"            ,
    "kor" : "Korean"            ,
    "lav" : "Latvian"           ,
    "lit" : "Lithuanian"        ,
    "ltz" : "Luxembourgish"     ,
    "mac" : "Macedonian"        ,
    "may" : "Malay"             ,
    "nor" : "Norwegian"         ,
    "oci" : "Occitan"           ,
    "pol" : "Polish"            ,
    "por" : "Portuguese"        ,
    "pob" : "Portuguese (Brazil)" ,
    "rum" : "Romanian"          ,
    "rus" : "Russian"           ,
    "scc" : "SerbianLatin"      ,
    "scc" : "Serbian"           ,
    "slo" : "Slovak"            ,
    "slv" : "Slovenian"         ,
    "spa" : "Spanish"           ,
    "swe" : "Swedish"           ,
    "syr" : "Syriac"            ,
    "tha" : "Thai"              ,
    "tur" : "Turkish"           ,
    "ukr" : "Ukrainian"         ,
    "urd" : "Urdu"              ,
    "vie" : "Vietnamese"        ,
    "all" : "All"
  }
  return languages[ id ]        
                 
def selectMedia(count, options, server):   
    printDebug("== ENTER: selectMedia ==", False)
    #if we have two or more files for the same movie, then present a screen
    result=0
    dvdplayback=False
    
    if count > 1:
        
        dialogOptions=[]
        dvdIndex=[]
        indexCount=0
        for items in options:

            name=items[1].split('/')[-1]
        
            if g_forcedvd == "true":
                if '.ifo' in name.lower():
                    printDebug( "Found IFO DVD file in " + name )
                    name="DVD Image"
                    dvdIndex.append(indexCount)
                    
            dialogOptions.append(name)
            indexCount+=1
    
        #Build the dialog text
        printDebug("Create selection dialog box - we have a decision to make!")
            
        #Create a dialog object
        startTime = xbmcgui.Dialog()
            
        #Box displaying media selecttion screen
        result = startTime.select('Select media to play',dialogOptions)
            
        #result contains an integer based on the selected text.
        if result == -1:
            #-1 is an exit without choosing, so end the function and start again when the user selects a new file.
            return None
        
        if result in dvdIndex:
            printDebug( "DVD Media selected")
            dvdplayback=True
     
    else:
        if g_forcedvd == "true":
            if '.ifo' in options[result]:
                dvdplayback=True
   
    newurl=mediaType({'key': options[result][0] , 'file' : options[result][1]},server,dvdplayback)
   
    printDebug("We have selected media at " + newurl)
    return newurl
           
def remove_html_tags(data):
    p = re.compile(r'<.*?>')
    return p.sub('', data)

def monitorPlayback(id, server):
    printDebug("== ENTER: monitorPlayback ==", False)
    #Need to monitor the running playback, so we can determine a few things:
    #1. If the file has completed normally (i.e. the movie has finished)
    #2. If the file has been stopped halfway through - need to record the stop time.
    
    #Get the server name to update
    if len(server.split(':')) == 1:
        server=server
        
    monitorCount=0
    progress = 0
    complete = 0
    #Whilst the file is playing back
    while xbmc.Player().isPlaying():
        #Get the current playback time
        currentTime = int(xbmc.Player().getTime())
        #Try to get the progress, if not revert to previous progress (which should be near enough)
        try:
            progress = int(remove_html_tags(xbmc.executehttpapi("GetPercentage")))             
        except: pass
                               
        if progress < 95:
            #we are less then 95% of the way through, store the resume time
            printDebug( "Movies played time: " + str(currentTime)+ " seconds @ " + str(progress) + "%")
            getURL("http://"+server+"/:/progress?key="+id+"&identifier=com.plexapp.plugins.library&time="+str(currentTime*1000),suppress=True)
            complete=0
        else:
            #Then we were 95% of the way through, so we mark the file as watched
            if complete == 0:
                printDebug( "Movie marked as watched. Over 95% complete")
                getURL("http://"+server+"/:/scrobble?key="+id+"&identifier=com.plexapp.plugins.library",suppress=True)
                complete=1

        #Now sleep for 5 seconds
        time.sleep(5)
          
    #If we get this far, playback has stopped
    printDebug("Playback Stopped")
    
    if g_sessionID is not None:
        printDebug("Stopping PMS transcode job with session " + g_sessionID)
        stopURL='http://'+server+'/video/:/transcode/segmented/stop?session='+g_sessionID          
        html=getURL(stopURL)
        
    return
    
def PLAY(url):
        printDebug("== ENTER: PLAY ==", False)
        
        protocol=url[0:4]
  
        if protocol == "file":
            printDebug( "We are playing a local file")
            #Split out the path from the URL
            playurl=url.split(':',1)[1]
        elif protocol == "http":
            printDebug( "We are playing a stream")
            if '?' in url:
                playurl=url+getAuthDetails({'token':_PARAM_TOKEN})
            else:
                playurl=url+getAuthDetails({'token':_PARAM_TOKEN},prefix="?")
        else:
            playurl=url
   
       
        #This is for playing standard non-PMS library files (such as Plugins)
        item = xbmcgui.ListItem(path=playurl)
        return xbmcplugin.setResolvedUrl(pluginhandle, True, item)

def videoPluginPlay(vids, prefix=None):
    '''
        Plays Plugin Videos, which do not require library feedback 
        but require further processing
        @input: url of video, plugin identifier
        @return: nothing. End of Script
    '''

    printDebug("== ENTER: videopluginplay ==", False)
           
    server=getServerFromURL(vids)
    
    #If we find the url lookup service, then we probably have a standard plugin, but possibly with resolution choices
    if '/system/services/url/lookup' in vids:
        printDebug("URL Lookup service")
        html=getURL(vids)
        tree=etree.fromstring(html)
        
        mediaCount=0
        mediaDetails=[]
        for media in tree.getiterator('Media'):
            mediaCount+=1
            tempDict={}
            tempDict['videoResolution']=media.get('videoResolution',"Unknown")
            
            for child in media:
                tempDict['key']=child.get('key','')
            
            mediaDetails.append(tempDict)
                    
        printDebug( str(mediaDetails) )            
                    
        #If we have options, create a dialog menu
        if mediaCount > 1:
            printDebug ("Select from plugin video sources")
            dialogOptions=[x['videoResolution'] for x in mediaDetails ]
            videoResolution = xbmcgui.Dialog()
            
            #Box displaying resume time or start at beginning
            result = videoResolution.select('Select resolution..',dialogOptions)
            
            #result contains an integer based on the selected text.
            if result == -1:
                #-1 is an exit without choosing, so end the function and start again when the user selects a new file.
                return
            else:
                vids=getLinkURL('',mediaDetails[result],server)
        else:
            vids=getLinkURL('',mediaDetails[0],server)

    
    #If URL is a PlayVideo URL, then will probably redirect to another source (either 301 or indirectly).
    #if vids.find('PlayVideo?') > 0:
    #    printDebug("PlayVideo url detected")
        
    #Check if there is a further level of XML required
    if '&indirect=1' in vids:
        printDebug("Indirect link")
        html=getURL(vids)
        tree=etree.fromstring(html)
        
        for bits in tree.getiterator('Part'):
            vids=bits.get('key')
        
    #Check for a 301/2 redirect, which XBMC doesn't handle will sometimes.               
    else:
        printDebug("Direct link")
        output=getURL(vids, type="HEAD")
        printDebug(str(output))
        if ( output[0:4] == "http" ) or ( output[0:4] == "plex" ):
            printDebug("Redirect.  Getting new URL")
            vids=output
            printDebug("New URL is: "+ vids)
            parameters=get_params(vids)
            
            arguments={}
            try:
                    prefix=parameters["prefix"]
            except:
                    pass     
            arguments['key']=vids
            arguments['identifier']=prefix

            vids=getLinkURL(vids, arguments ,server)  
    
    printDebug("URL to Play: " + vids)
    printDebug("Prefix is: " + str(prefix))
    
    #If there is no prefix, we are not transcoding video
    if prefix is None:
        prefix=""
    else:
        getTranscodeSettings(True)
        vids=transcode(0, vids, prefix)
        session=vids
    
    #If this is an Apple movie trailer, add User Agent to allow access
    if 'trailers.apple.com' in vids:
        url=vids+"|User-Agent=QuickTime/7.6.5 (qtver=7.6.5;os=Windows NT 5.1Service Pack 3)"
    elif server in vids:
        url=vids+getAuthDetails({'token': _PARAM_TOKEN})
    else:
        url=vids
   
    printDebug("Final URL is : " + url)
    
    item = xbmcgui.ListItem(path=url)
    start = xbmcplugin.setResolvedUrl(pluginhandle, True, item)        
    
    
    if 'transcode' in url:
        try:
            pluginTranscodeMonitor(g_sessionID,server)
        except: 
            printDebug("Unable to start transcode monitor")
    else:
        printDebug("Not starting monitor")
        
    return

def pluginTranscodeMonitor(sessionID,server):
        printDebug("== ENTER: pluginTranscodeMonitor ==", False)

        #Logic may appear backward, but this does allow for a failed start to be detected
        #First while loop waiting for start

        count=0
        while not xbmc.Player().isPlaying():
            printDebug( "Not playing yet...sleep for 2")
            count = count + 2
            if count >= 40:
                #Waited 20 seconds and still no movie playing - assume it isn't going to..
                return
            else:
                time.sleep(2)

        while xbmc.Player().isPlaying():
            printDebug("Waiting for playback to finish")
            time.sleep(4)
        
        printDebug("Playback Stopped")
        printDebug("Stopping PMS transcode job with session: " + sessionID)
        #server=getServerFromURL(sessionID)
        stopURL='http://'+server+'/video/:/transcode/segmented/stop?session='+sessionID
            
        html=getURL(stopURL)

        return
                
def get_params(paramstring):
        printDebug("== ENTER: get_params ==", False)
        printDebug("Parameter string: " + paramstring)
        param={}
        if len(paramstring)>=2:
                params=paramstring
                
                if params[0] == "?":
                    cleanedparams=params[1:] 
                else:
                    cleanedparams=params
                    
                if (params[len(params)-1]=='/'):
                        params=params[0:len(params)-2]
                pairsofparams=cleanedparams.split('&')
                for i in range(len(pairsofparams)):
                        splitparams={}
                        #Right, extended urls that contain = do not parse correctly and this tops plugins from working
                        #Need to think of a better way to do the split, at the moment i'm hacking this by gluing the
                        #two bits back togethers.. nasty...
                        splitparams=pairsofparams[i].split('=')
                        if (len(splitparams))==2:
                                param[splitparams[0]]=splitparams[1]
                        elif (len(splitparams))==3:
                                param[splitparams[0]]=splitparams[1]+"="+splitparams[2]
        printDebug("Returning: " + str(param))                        
        return param

def getContent(url):  
    printDebug("== ENTER: getContent ==", False)
    #We've been called at mode 0, by ROOT becuase we are going to traverse the secondary menus
        
    #First we need to peek at the XML, to see if we've hit any video links yet.
        
    server=url.split('/')[2]
    lastbit=url.split('/')[-1]
    secondtolast=url.split('/')[-2]
    printDebug("URL suffix: " + str(lastbit))
    
    if lastbit.startswith('search'):
        #Found search URL.  Bring up keyboard and get input for query string
        printDebug("This is a search URL.  Bringing up keyboard")
        kb = xbmc.Keyboard('', 'heading')
        kb.setHeading('Enter search term') # optional
        kb.doModal()
        if (kb.isConfirmed()):
            text = kb.getText()
            printDebug("Search term input: "+ text)
            url=url+'&query='+text
        else:
            return
     
    html=getURL(url)
    
    if html is False:
        return
        
    tree=etree.fromstring(html)
 
    if lastbit == "folder":
        PlexPlugins(url,tree)
        return
 
    arguments=dict(tree.items())
    view_group=arguments.get('viewGroup',None)

    if view_group == "movie":
        printDebug( "This is movie XML, passing to Movies")
        if not (lastbit.startswith('recently') or lastbit.startswith('newest')):
            xbmcplugin.addSortMethod(pluginhandle,xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
        Movies(url, tree)
    elif view_group == "show":
        printDebug( "This is tv show XML")
        SHOWS(url,tree)
    elif view_group == "episode":
        printDebug("This is TV episode XML")
        EPISODES(url,tree)
    elif view_group == 'artist':
        printDebug( "This is music XML")
        artist(url, tree)
    elif view_group== 'album' or view_group == 'albums':
        albums(url,tree)
    elif view_group == "track":
        printDebug("This is track XML")
        tracks(url, tree)
    elif view_group =="photo":
        printDebug("This is a photo XML")
        photo(url,tree)
    else:
        processDirectory(url,tree)
        
    return

def processDirectory(url,tree=None):
    printDebug("== ENTER: processDirectory ==", False)
    #else we have a secondary, which we'll process here
    printDebug("Processing secondary menus")
    xbmcplugin.setContent(pluginhandle, 'movies')

    server=getServerFromURL(url)
    
    try:
        fanart=tree.get('art').split('?')[0] #drops the guid from the fanart image
        art_url='http://'+server+fanart#.encode('utf-8')
        #art_url='http://'+server+g_port+'/photo/:/transcode?url='+art_url+'&width=1280&height=720'
    except:  
        art_url=None 

    
    for apple in tree:
        arguments=dict(apple.items())
        properties={}
        properties['title']=arguments['title']
        
        try:
            arguments['thumb']=art_url
            arguments['fanart_image']=arguments['thumb']
        except:
            arguments['thumb']=""

        try:
            if arguments['key'].split('/')[0] == "http:":
                p_url=arguments['key']
            elif arguments['key'][0] == '/':
                #The key begins with a slash, there is absolute
                p_url='http://'+server+str(arguments['key'])
            else:
                #Build the next level URL and add the link on screen
                p_url=url+'/'+str(arguments['key'])
        except: continue    
        #If we have a key error - then we don't add to the list.
        
        n_url=p_url+'&mode=0'

        addDir(n_url,properties,arguments, )
        
    xbmcplugin.endOfDirectory(pluginhandle)

def transcode(id,url,identifier=None):
    printDebug("== ENTER: transcode ==", False)
    # First get the time since Epoch
        
    #Had to use some customised modules to get hmac sha256 working on python 2.4
    import base64
    
    server=url.split('/')[2]
    filestream=urllib.quote_plus("/"+"/".join(url.split('/')[3:]))
  
    if identifier is not None:
        baseurl=url.split('url=')[1]
        myurl="/video/:/transcode/segmented/start.m3u8?url="+baseurl+"&webkit=1&3g=0&offset=0&quality="+g_quality+"&session="+g_sessionID+"&identifier="+identifier
    else:
  
        if g_transcodefmt == "m3u8":
            myurl = "/video/:/transcode/segmented/start.m3u8?identifier=com.plexapp.plugins.library&ratingKey=" + id + "&offset=0&quality="+g_quality+"&url=http%3A%2F%2Flocalhost%3A32400" + filestream + "&3g=0&httpCookies=&userAgent=&session="+g_sessionID
        elif g_transcodefmt == "flv":
            myurl="/video/:/transcode/generic.flv?format=flv&videoCodec=libx264&vpre=video-embedded-h264&videoBitrate=5000&audioCodec=libfaac&apre=audio-embedded-aac&audioBitrate=128&size=640x480&fakeContentLength=2000000000&url=http%3A%2F%2Flocalhost%3A32400"  + filestream + "&3g=0&httpCookies=&userAgent="
        else:
            printDebug( "Woah!!  Barmey settings error....Bale.....")
            return url

            
    now=str(int(round(time.time(),0)))
    
    msg = myurl+"@"+now
    printDebug("Message to hash is " + msg)
    
    #These are the DEV API keys - may need to change them on release
    publicKey="KQMIY6GATPC63AIMC4R2"
    privateKey = base64.decodestring("k3U6GLkZOoNIoSgjDshPErvqMIFdE0xMTx8kgsrhnC0=")
       
    #If python is > 2.4 then do this
    import hashlib, hmac
    hash=hmac.new(privateKey,msg,digestmod=hashlib.sha256)
    
    printDebug("HMAC after hash is " + hash.hexdigest())
    
    #Encode the binary hash in base64 for transmission
    token=base64.b64encode(hash.digest())
    
    #Send as part of URL to avoid the case sensitive header issue.
    fullURL="http://"+server+myurl+"&X-Plex-Access-Key="+publicKey+"&X-Plex-Access-Time="+str(now)+"&X-Plex-Access-Code="+urllib.quote_plus(token)+"&"+capability
       
    printDebug("Transcoded media location URL " + fullURL)
    
    return fullURL
     
def artist(url,tree=None):
        printDebug("== ENTER: artist ==", False)
        xbmcplugin.setContent(pluginhandle, 'artists')

        #xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
        
        #Get the URL and server name.  Get the XML and parse
        if tree is None:
        
            html=getURL(url)
            
            if html is False:
                return
       
            tree=etree.fromstring(html)
        
        server=getServerFromURL(url)
        
        #For each directory tag we find
        ShowTags=tree.findall('Directory') # These type of calls seriously slow down plugins
        for show in ShowTags:

            arguments=dict(show.items())
        
            #tempgenre=[]
            
            #Lets grab all the info we can quickly through either a dictionary, or assignment to a list
            #We'll process it later
            #for child in show:
            #    try:
            #        tempgenre.append(child.get('tag'))
            #    except:pass
                
            #Create the basic data structures to pass up
            properties={}  #Create a dictionary for properties with some defaults(i.e. ListItem properties)
            
            #Get name
            try:
                properties['title']=properties['artist']=arguments['title'].encode('utf-8')
            except: pass
                        
            #Get the Plot          
            try:
                properties['plot']=arguments['summary']
            except: pass
                                        
            #get Genre
            #try:
            #    properties['genre']=" / ".join(tempgenre)
            #except:pass
                
            #Get the picture to use
            arguments['thumb']=getThumb(arguments, server)
               
            #Get a nice big picture  

            arguments['fanart_image']=getFanart(arguments, server)
           
            arguments['type']="Music"

            mode=14 
            url='http://'+server+'/library/metadata/'+arguments['ratingKey']+'/children'+"&mode="+str(mode)
            
            addDir(url,properties,arguments) 
            
        #End the listing    
        xbmcplugin.endOfDirectory(pluginhandle)

def albums(url, tree=None):
        printDebug("== ENTER: albums ==", False)
        xbmcplugin.setContent(pluginhandle, 'albums')

        #xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
       
        #Get the URL and server name.  Get the XML and parse
        if tree is None:
        
            html=getURL(url)
            
            if html is False:
                return
       
            tree=etree.fromstring(html)
        
        server=getServerFromURL(url)
        
        try:
            treeargs=dict(tree.items())
            artist=treeargs['parentTitle']
        except: pass
        
        sectionart=getFanart(treeargs, server)
        
        #For all the directory tags
        ShowTags=tree.findall('Directory')
        for show in ShowTags:
        
            arguments=dict(show.items())
            #Build basic data structures
            properties={}   #Create a dictionary for properties with some defaults(i.e. ListItem properties)
 
            #Get name
            try:
                properties['title']=properties['album']=arguments['title'].encode('utf-8')
            except: pass
       
            #Get the picture to use
            arguments['thumb']=getThumb(arguments, server)
               
            #Get a nice big picture  

            arguments['fanart_image']=getFanart(arguments, server)
            try:
                if arguments['fanart_image'] == "":
                    arguments['fanart_image']=sectionart
            except:
                pass

            try:
                properties['artist']=artist
            except: 
                try:
                    properties['artist']=arguments['parentTitle']
                except:
                    pass
                            
            arguments['type']="Music"
            mode=15
            
            try:
                properties['year']=int(arguments['year'])
            except: pass
            
            url='http://'+server+arguments['key']+"&mode="+str(mode)
            #Set the mode to episodes, as that is what's next 

            #Build the screen directory listing
            addDir(url,properties,arguments) 
            
        #All done, so end the listing
        xbmcplugin.endOfDirectory(pluginhandle)

def tracks(url,tree=None):
        printDebug("== ENTER: tracks ==", False)
        xbmcplugin.setContent(pluginhandle, 'songs')
        
        #xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_TRACKNUM)
        
        #Get the server
        target=url.split('/')[-1]
        
        #Get the URL and server name.  Get the XML and parse
        if tree is None:
        
            html=getURL(url)
            
            if html is False:
                return

        
            tree=etree.fromstring(html)
        
        ShowTags=tree.findall('Track')      
        server=getServerFromURL(url)           
        treeargs=dict(tree.items()) 
 
        try: 
            if not target == "allLeaves":
                #Name of the show
                try:
                    artistname=tree.get('grandparentTitle')
                except: pass
                
                #the album
                try:
                    albumname = tree.get('parentTitle')
                except: pass
            
                try:
                    sectionthumb=getThumb(treeargs, server)
                except: pass
                
        except: pass
         
        sectionart=getFanart(treeargs,server) 
         
        #right, not for each show we find
        for show in ShowTags:
            #print show
            
            arguments=dict(show.items())
            tempgenre=[]
            
            #Lets grab all the info we can quickly through either a dictionary, or assignment to a list
            #We'll process it later
            for child in show:
                if child.tag == "Media":
                    mediaarguments = dict(child.items())
                        
                    for babies in child:
                        if babies.tag == "Part":
                            partarguments=(dict(babies.items()))
                elif child.tag == "Genre":
                    tempgenre.append(child.get('tag'))
            
            #required to grab to check if file is a .strm file
            #Can't play strm files, so lets not bother listing them. 
           
            printDebug( "args is " + str(arguments))
            printDebug( "Media is " + str(mediaarguments))
            printDebug( "Part is " + str(partarguments))
            
            #Set basic structure with some defaults.  Overlay 6 is unwatched
            properties={}   #Create a dictionary for properties with some defaults(i.e. ListItem properties)
            
            #Get the tracknumber number
            properties['TrackNumber']=int(arguments.get('index',0))

            #Get name
            try:
                properties['title']=str(properties['TrackNumber']).zfill(2)+". "+arguments['title'].encode('utf-8')
            except: pass
                                    
            #Get how good it is, based on your votes...
            try:
                properties['rating']=float(arguments['rating'])
            except: pass
            
            #Get the last played position  
            try:
                arguments['viewOffset']=int(arguments['viewOffset'])/1000
            except:
                arguments['viewOffset']=0

                        
            #If we are processing an "All Episodes" directory, then get the season from the video tag
            
            try:
                properties['album']=albumname
            except: 
                properties['album']=arguments['parentTitle']
            
                    
            #Check if we got the showname from the main tag        
            try:
                properties['artist']=artistname
            except:
                properties['artist']=arguments['grandparentTitle']
                
            #Get the picture to use
            arguments['thumb']=getThumb(arguments, server)
            try:
                if arguments['thumb'].find('/resources/movie.png') > 0:
                    arguments['thumb']=sectionthumb
            except: pass
                
             

            #Get a nice big picture  
            arguments['fanart_image']=getFanart(arguments, server)  
            try:
                if arguments['fanart_image'] == "":
                    arguments['fanart_image']=sectionart
            except:
                pass
                
            #Assign standard metadata
            #Genre        
            properties['genre']=" / ".join(tempgenre) 
            
            
            #Set the track duration 
            try:
                arguments['duration']=mediaarguments['duration']
            except KeyError:
                try:
                    arguments['duration']
                except:
                    arguments['duration']=0
             
            arguments['duration']=int(arguments['duration'])/1000
            properties['duration']=arguments['duration']
            
            #set type
            arguments['type']="Music"
            
            #If we are streaming, then get the virtual location
            url=mediaType(partarguments,server)
            #Set mode 5, which is play            
            mode=12

            u=str(url)+"&mode="+str(mode)+"&resume="+str(arguments['viewOffset'])+"&id="+str(arguments['ratingKey'])+"&duration="+str(arguments['duration'])
                
            #Build a file link and loop
            addLink(u,properties,arguments)        
        
        #End the listing
        xbmcplugin.endOfDirectory(pluginhandle)

def PlexPlugins(url, tree=None):
    '''
        Main function to parse plugin XML from PMS
        Will create dir or item links depending on what the 
        main tag is.
        @input: plugin page URL
        @return: nothing, creates XBMC GUI listing
    '''

    printDebug("== ENTER: PlexPlugins ==", False)
    xbmcplugin.setContent(pluginhandle, 'movies')
    server=getServerFromURL(url)
    if tree is None:

        html=getURL(url)
    
        if html is False:
            return

        tree=etree.fromstring(html)
    
    try:
        sectionArt=getFanart(dict(tree.items()),server)
    except: pass
    
    try:
        identifier=tree.get('identifier')
    except: pass
    
    for orange in tree:
           
        arguments=dict(orange.items())

        #Set up the basic structures
        properties={'overlay':6}
                    
        try: 
            properties['title']=arguments['title'].encode('utf-8')
        except:
            try:
                properties['title']=arguments['name'].encode('utf-8')
            except:
                properties['title']="unknown"
                
        arguments['thumb']=getThumb(arguments, server)
        
        arguments['fanart_image']=getFanart(arguments, server)
        try:
            if arguments['fanart_image'] == "":
                arguments['fanart_image']=sectionArt
        except:
            pass
            
        try:    
            arguments['identifier']=identifier    
        except:
            arguments['identifier']=""
            
        p_url=getLinkURL(url, arguments, server)

        
        if orange.tag == "Directory" or orange.tag == "Podcast":
            #We have a directory tag, so come back into this function

            s_url=p_url+"&mode="+str(_MODE_PLEXPLUGINS)
            
            #Set type
            arguments['type']="Video"
            
            addDir(s_url, properties, arguments)
                
        #If we have some video links as well
        elif orange.tag == "Video":
         
            #Set the mode to play them this time
                
            #Build the URl and add a link to the file
            v_url=p_url+"&mode="+str(_MODE_VIDEOPLUGINPLAY) 
            
            #Set type
            arguments['type']="Video"
           
            addLink(v_url, properties, arguments)

    xbmcplugin.endOfDirectory(pluginhandle)        

def processXML(url, tree=None):
    '''
        Main function to parse plugin XML from PMS
        Will create dir or item links depending on what the 
        main tag is.
        @input: plugin page URL
        @return: nothing, creates XBMC GUI listing
    '''

    printDebug("== ENTER: processXML ==", False)
    xbmcplugin.setContent(pluginhandle, 'movies')
    server=getServerFromURL(url)
    if tree is None:

        html=getURL(url)
    
        if html is False:
            return

        tree=etree.fromstring(html)
    
    try:
        sectionArt=getFanart(dict(tree.items()),server)
    except: pass
    
    try:
        identifier=tree.get('identifier')
    except: pass
    
    for orange in tree:
           
        properties={'overlay':6}
                    
        try: 
            properties['title']=arguments['title'].encode('utf-8')
        except:
            try:
                properties['title']=arguments['name'].encode('utf-8')
            except:
                properties['title']="unknown"
                
        arguments['thumb']=getThumb(arguments, server)
        
        arguments['fanart_image']=getFanart(arguments, server)
        try:
            if arguments['fanart_image'] == "":
                arguments['fanart_image']=sectionArt
        except:
            pass
            
        try:    
            arguments['identifier']=identifier    
        except:
            arguments['identifier']=""
            
        p_url=getLinkURL(url, arguments, server)

        
        #These are intermediate items and point to further objects
        if orange.tag == "Directory" or orange.tag == "Podcast":
            #We have a directory tag, so come back into this function

            s_url=p_url+"&mode="+str(_MODE_PLEXPLUGINS)
            
            #Set type
            arguments['type']="Video"
            
            addDir(s_url, properties, arguments)
                
        #These are media end points
        elif orange.tag == "Video" or orange.tag == "Track":
         
            #Set the mode to play them this time
                
            #Build the URl and add a link to the file
            v_url=p_url+"&mode="+str(_MODE_VIDEOPLUGINPLAY) 
            
            #Set type
            arguments['type']="Video"
           
            addLink(v_url, properties, arguments)

    xbmcplugin.endOfDirectory(pluginhandle)        
        
def photo(url,tree=None):
    printDebug("== ENTER: photos ==", False)
    server=url.split('/')[2]
    
    if tree is None:
        html=getURL(url)
        
        if html is False:
            return
        
        tree=etree.fromstring(html)
    
    try:
        sectionArt=getFanart(dict(tree.items()),server)
    except: pass
 
    for banana in tree:
        
        arguments=dict(banana.items())
        properties={}
        
        try:
            properties['title']=properties['name']=arguments['title'].encode('utf-8')
        except:
            properties['title']=properties['name']="Unknown"
            
        try: 
            properties['title']=arguments['title'].encode('utf-8')
        except:
            try:
                properties['title']=arguments['name'].encode('utf-8')
            except:
                properties['title']="unknown"
                 
        arguments['thumb']=getThumb(arguments, server)
        
        arguments['fanart_image']=getFanart(arguments, server)
        try:
            if arguments['fanart_image'] == "":
                arguments['fanart_image']=sectionArt
        except:
            pass

        u=getLinkURL(url, arguments, server)   
                
        if banana.tag == "Directory":
            mode=16
            u=u+"&mode="+str(mode)
            addDir(u,properties,arguments)
    
        elif banana.tag == "Photo":
        
            try:
                if arguments['ratingKey']:
                               
                    for child in banana:
                        if child.tag == "Media":
                            for images in child:
                                if images.tag == "Part":
                                    arguments['thumb']="http://"+server+images.get('key')
                                    u=arguments['thumb']
            except:
                pass
            
            arguments['type']="Picture"
            addLink(u,properties,arguments)

    xbmcplugin.endOfDirectory(pluginhandle)

def music(url, tree=None):
    printDebug("== ENTER: music ==", False)
    xbmcplugin.setContent(pluginhandle, 'artists')

    server=getServerFromURL(url)
    
    if tree is None:
        html=getURL(url)
    
        if html is False:
            return
   
        tree=etree.fromstring(html)
 
    try:
        sectionArt=getFanart(dict(tree.items()),server)
    except: pass
 
    for grapes in tree:
       
        arguments=dict(grapes.items())
        arguments['type']="Music"        
        properties={}
        
        try:
            if arguments['key'] == "":
                continue
        except: pass
                          
        arguments['thumb']=getThumb(arguments, server)

        arguments['fanart_image']=getFanart(arguments, server)
        try:
            if arguments['fanart_image'] == "":
                arguments['fanart_image']=sectionArt
        except:
            pass
        
        try:
            properties['genre']=arguments['genre']
        except: pass

        try:
            properties['artist']=arguments['artist']
        except:pass
                
        try:
            properties['year']=int(arguments['year'])
        except:pass

        try:
            properties['album']=arguments['album']
        except:pass
        
        try: 
            properties['tracknumber']=int(arguments['index'])
        except:pass
        
        properties['title']="Unknown"
   
        u=getLinkURL(url, arguments, server)
        
        if grapes.tag == "Track":
            printDebug("Track Tag")
            xbmcplugin.setContent(pluginhandle, 'songs')
            #xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_TRACKNUM)
            
            try:
                properties['title']=arguments['track'].encode('utf-8')
            except: pass
            
                         
            #Set the track length 
            try:
                arguments['totalTime']=int(arguments['totalTime'])/1000
                properties['duration']=arguments['totalTime']
            except: pass
           
            mode=12
            u=u+"&mode="+str(mode)
            addLink(u,properties,arguments)

        else: 
        
            if grapes.tag == "Artist":
                printDebug("Artist Tag")
                xbmcplugin.setContent(pluginhandle, 'artists')
                try:
                    properties['title']=arguments['artist']
                except: 
                    properties['title']="Unknown"
             
            elif grapes.tag == "Album":
                printDebug("Album Tag")
                xbmcplugin.setContent(pluginhandle, 'albums')
                try:    
                    properties['title']=arguments['album']
                except: pass
            elif grapes.tag == "Genre":
                try:    
                    properties['title']=arguments['genre']
                except: pass
            
            else:
                printDebug("Generic Tag: " + grapes.tag)
                try:
                    properties['title']=arguments['title']
                except: pass
            
            mode=17
            u=u+"&mode="+str(mode)
            addDir(u,properties,arguments)
        
    xbmcplugin.endOfDirectory(pluginhandle)    

def getThumb(arguments, server):
    '''
        Simply take a URL or path and determine how to format for images
        @ input: elementTree element, server name
        @ return formatted URL
    '''
    thumbnail=arguments.get('thumb','').split('?t')[0]
    
    if thumbnail == '':
        return ''
        
    elif thumbnail[0:4] == "http" :
        return thumbnail
    
    elif thumbnail[0] == '/':
        return 'http://'+server+thumbnail
    
    else: 
        return g_loc+'/resources/movie.png'

def getFanart(arguments, server):
    '''
        Simply take a URL or path and determine how to format for fanart
        @ input: elementTree element, server name
        @ return formatted URL for photo resizing
    '''

    fanart=arguments.get('art','')
    
    if fanart == '':
        return ''

    elif fanart[0:4] == "http" :
        return fanart
        
    elif fanart[0] == '/':
        return photoTranscode(server,'http://localhost:32400'+fanart)
        
    else:  
        return ''

def getServerFromURL(url):
    '''
    Simply split the URL up and get the server portion, sans port
    @ input: url, woth or without protocol
    @ return: the URL server
    '''
    if url[0:4] == "http":
        return url.split('/')[2]
    else:
        return url.split('/')[0]

def getLinkURL(url, arguments, server):
    '''
        Investigate the passed URL and determine what is required to 
        turn it into a usable URL
        @ input: url, XML data and PM server address
        @ return: Usable http URL
    '''
    
    printDebug("== ENTER: getLinkURL ==")
    try:
        #If key starts with http, then return it
        if arguments['key'][0:4] == "http":
            printDebug("Detected http link")
            return arguments['key']
            
        #If key starts with a / then prefix with server address    
        elif arguments['key'][0] == '/':
            printDebug("Detected base path link")
            return 'http://'+server+str(arguments['key'])

        #If key starts with plex:// then it requires transcoding 
        elif arguments['key'][0:5] == "plex:":
            printDebug("Detected plex link")    
            components=arguments['key'].split('&')
            for i in components:
                if 'prefix=' in i:
                    del components[components.index(i)]
                    break
            try:
                if arguments['identifier']:
                    components.append('identifier='+arguments['identifier'])
            except: pass
            
            arguments['key']='&'.join(components)        
            newUrl='http://'+server+'/'+'/'.join(arguments['key'].split('/')[3:])
            return newUrl
            
        #Any thing else is assumed to be a relative path and is built on existing url        
        else:
            printDebug("Detected relative link")
            return url+'/'+str(arguments['key'])
    except:pass
     
    return url
    
def plexOnline(url):
    printDebug("== ENTER: plexOnline ==")
    xbmcplugin.setContent(pluginhandle, 'files')

    server=url.split('/')[2]
    
    html=getURL(url)
    
    if html is False:
        return
    
    tree=etree.fromstring(html)
        
    for lemons in tree:
       
        arguments=dict(lemons.items())
        arguments['type']="Video"        
        properties={}
        
        try:
            if arguments['key'] == "":
                continue
        except: pass
        
        try:
            properties['title']=arguments['title']
        except:
            try:
                properties['title']=arguments['name']
            except:
                properties['title']="Unknown"
        
        mode=19
        
        if arguments['key'][0] == '/':
            #The key begins with a slah, there is absolute
            u='http://'+server+str(arguments['key'])
        else:
            #Build the next level URL and add the link on screen
            u=url+'/'+str(arguments['key'])

        
        try:
            if arguments['installed'] == "1":
                properties['title']=properties['title']+" (installed)"
                mode=20
            elif arguments['installed'] == "0":
                mode=20
                
        except:pass 
        
        try:
            if not arguments['thumb'].split('/')[0] == "http:":
                arguments['thumb']='http://'+server+arguments['thumb'].encode('utf-8')
        except:
            thumb=g_loc+'/resources/movie.png'  
            arguments['thumb']=thumb

        properties['title']=properties['title'].encode('utf-8')    
            
        u=u+"&mode="+str(mode)+"&name="+urllib.quote_plus(properties['title'])
        addDir(u, properties, arguments)

    xbmcplugin.endOfDirectory(pluginhandle)    
   
def install(url, name):
    printDebug("== ENTER: install ==", False)
    html=getURL(url)
    if html is False:
        return
    tree = etree.fromstring(html)
    
    if tree.get('size') == "1":
        #This plugin is probably not install
        printDebug("Not installed.  Print dialog")
        ret = xbmcgui.Dialog().yesno("Plex Online","About to install " + name)

        if ret:
            printDebug("Installing....")
            installed = getURL(url+"/install")
            tree = etree.fromstring(installed)
    
            msg=tree.get('message')
            printDebug(msg)
            xbmcgui.Dialog().ok("Plex Online",msg)

    else:
        #This plugin is already installed
        printDebug("Already installed")
        operations={}
        i=0
        for plums in tree.findall('Directory'):
            operations[i]=plums.get('key').split('/')[-1]
            i+=1
        
        options=operations.values()
        
        ret = xbmcgui.Dialog().select("This plugin is already installed..",options)
        
        if ret == -1:
            printDebug("No option selected, cancelling")
            return
        
        printDebug("Option " + str(ret) + " selected.  Operation is " + operations[ret])
        u=url+"/"+operations[ret]

        action = getURL(u)
        tree = etree.fromstring(action)
    
        msg=tree.get('message')
        printDebug(msg)
        xbmcgui.Dialog().ok("Plex Online",msg)
   
    return   

def channelView(url):

    printDebug("== ENTER: channelView ==", False)
    html=getURL(url)
    if html is False:
        return
    tree = etree.fromstring(html)
    
    server=getServerFromURL(url)
    
    for channels in tree.getiterator('Directory'):
    
        try:
            if channels.get('local') == "0":
                continue
        except: pass
            
        arguments=dict(channels.items())

    
        arguments['fanart_image']=getFanart(arguments, server)

        arguments['thumb']=getThumb(arguments, server)
        
        properties={}
        properties['title']=arguments['title']

        suffix=arguments['path'].split('/')[1]
        
        try:
            if arguments['unique']=='0':
                properties['title']=properties['title']+" ("+suffix+")"
        except:
            pass
               
        try:
            if arguments['path'].split('/')[0] == "http:":
                p_url=arguments['path']
            elif arguments['path'][0] == '/':
                #The path begins with a slah, there is absolute
                p_url='http://'+server+str(arguments['path'])
            else:
                #Build the next level URL and add the link on screen
                p_url=url+'/'+str(arguments['path'])
        except: continue    
        #If we have a path error - then we don't add to the list.
        
        if suffix == "photos":
            mode=16
        elif suffix == "video":
            mode=7
        elif suffix == "music":
            mode=17
        else:
            mode=0
        
        n_url=p_url+'&mode='+str(mode)

        addDir(n_url,properties,arguments)
        
    xbmcplugin.endOfDirectory(pluginhandle)

def photoTranscode(server, url):
        return 'http://'+server+'/photo/:/transcode?url='+urllib.quote_plus(url)+'&width=1280&height=720'
              
def skin():
        #Gather some data and set the window properties
        printDebug("== ENTER: skin() ==", False)
        #Get the global host variable set in settings
        WINDOW = xbmcgui.Window( 10000 )
         
         
        #Get the global host variable set in settings        
        numOfServers=len(g_serverDict)
                
        printDebug( "Using list of "+str(numOfServers)+" servers: " +  str(g_serverDict))
        
        getAllSections()
        
         
        sectionCount=0
        serverCount=0
        
        #For each of the servers we have identified
        for arguments in g_sections:
                                                                       
                if g_skipimages == "false":
                    try:
                        if arguments['art'][0] == "/":
                            arguments['fanart_image']="http://"+arguments['address']+arguments['art']
                        else:
                            arguments['fanart_image']="http://"+arguments['address']+"/library/sections/"+arguments['art']
                    except: 
                            arguments['fanart_image']=""
                        
                    try:
                        if arguments['thumb'][0] == "/":
                            arguments['thumb']="http://"+arguments['address']+arguments['thumb'].split('?')[0]
                        else:
                            arguments['thumb']="http://"+arguments['address']+"/library/sections/"+arguments['thumb'].split('?')[0]
                    except: 
                        arguments['thumb']=arguments['fanart_image']
                    
                    
                #Set up some dictionaries with defaults that we are going to pass to addDir/addLink
                properties={}

                #Start pulling out information from the parsed XML output. Assign to various variables
                try:
                    if numOfServers == 1:
                        properties['title']=arguments['title']
                    else:
                        properties['title']=arguments['serverName']+": "+arguments['title']
                except:
                    properties['title']="unknown"
                
                #Determine what we are going to do process after a link is selected by the user, based on the content we find
                if arguments['type'] == 'show':
                    window="VideoLibrary"
                    mode=1
                if  arguments['type'] == 'movie':
                    window="VideoLibrary"
                    mode=2
                if  arguments['type'] == 'artist':
                    window="MusicFiles"
                    mode=3
                if  arguments['type'] == 'photo':
                    window="Pictures"
                    mode=16

                    #arguments['type']="Video"
                
                if g_secondary == "true":
                    s_url='http://'+arguments['address']+arguments['path']+"&mode=0"
                else:
                    #Build URL with the mode to use and key to further XML data in the library
                    s_url='http://'+arguments['address']+arguments['path']+'/all'+"&mode="+str(mode)
                

                
                #Build that listing..
                WINDOW.setProperty("plexbmc.%d.title" % (sectionCount) , arguments['title'])
                WINDOW.setProperty("plexbmc.%d.subtitle" % (sectionCount), arguments['serverName'])
                WINDOW.setProperty("plexbmc.%d.path" % (sectionCount), "ActivateWindow("+window+",plugin://plugin.video.plexbmc/?url="+s_url+getAuthDetails(arguments)+",return)")
                WINDOW.setProperty("plexbmc.%d.art" % (sectionCount), photoTranscode(arguments['address'],arguments['fanart_image'])+getAuthDetails(arguments,prefix="?"))
                WINDOW.setProperty("plexbmc.%d.type" % (sectionCount) , arguments['type'])
                WINDOW.setProperty("plexbmc.%d.icon" % (sectionCount) , arguments['thumb'].split('?')[0]+getAuthDetails(arguments,prefix="?"))
                WINDOW.setProperty("plexbmc.%d.thumb" % (sectionCount) , arguments['thumb'].split('?')[0]+getAuthDetails(arguments,prefix="?"))
                WINDOW.setProperty("plexbmc.%d.partialpath" % (sectionCount) , "ActivateWindow("+window+",plugin://plugin.video.plexbmc/?url=http://"+arguments['address']+arguments['path'])

                
                printDebug("Building window properties index [" + str(sectionCount) + "] which is [" + arguments['title'] + "]")
                printDebug("PATH in use is: ActivateWindow("+window+",plugin://plugin.video.plexbmc/?url="+s_url+getAuthDetails(arguments)+",return)")
                sectionCount += 1
        
        #For each of the servers we have identified
        allservers=resolveAllServers()
        numOfServers=len(allservers)
        
        for server in allservers:
        
            if g_channelview == "true":
                WINDOW.setProperty("plexbmc.channel", "1")
                WINDOW.setProperty("plexbmc.%d.server.channel" % (serverCount) , "ActivateWindow(VideoLibrary,plugin://plugin.video.plexbmc/?url=http://"+server['address']+"/system/plugins/all&mode=21"+getAuthDetails(server)+",return)")
            else:
                WINDOW.clearProperty("plexbmc.channel")
                WINDOW.setProperty("plexbmc.%d.server.video" % (serverCount) , "http://"+server['address']+"/video&mode=7"+getAuthDetails(server))
                WINDOW.setProperty("plexbmc.%d.server.music" % (serverCount) , "http://"+server['address']+"/music&mode=17"+getAuthDetails(server))
                WINDOW.setProperty("plexbmc.%d.server.photo" % (serverCount) , "http://"+server['address']+"/photos&mode=16"+getAuthDetails(server))
                    
            WINDOW.setProperty("plexbmc.%d.server.online" % (serverCount) , "http://"+server['address']+"/system/plexonline&mode=19"+getAuthDetails(server))
    
            printDebug ("server hostname is : " + str(server['address']))
            try:
                WINDOW.setProperty("plexbmc.%d.server" % (serverCount) , server['serverName'])
                printDebug ("Name mapping is :" + server['serverName'])
            except:
                printDebug ("Falling back to server hostname")
                WINDOW.setProperty("plexbmc.%d.server" % (serverCount) , server['address'].split(':')[0])
                
            serverCount+=1
                
            
        #Clear out old data
        try:
            printDebug("Clearing properties from [" + str(sectionCount) + "] to [" + WINDOW.getProperty("plexbmc.sectionCount") + "]")

            for i in range(sectionCount, int(WINDOW.getProperty("plexbmc.sectionCount"))+1):
                WINDOW.clearProperty("plexbmc.%d.title" % ( i ) )
                WINDOW.clearProperty("plexbmc.%d.subtitle" % ( i ) )
                WINDOW.clearProperty("plexbmc.%d.url" % ( i ) )
                WINDOW.clearProperty("plexbmc.%d.path" % (i) )
                WINDOW.clearProperty("plexbmc.%d.window" % ( i ) )
                WINDOW.clearProperty("plexbmc.%d.art" % ( i ) )
                WINDOW.clearProperty("plexbmc.%d.type" % ( i ) )
                WINDOW.clearProperty("plexbmc.%d.icon" % ( i ) )
                WINDOW.clearProperty("plexbmc.%d.thumb" % ( i ) )
        except:
            pass

        printDebug("Total number of skin sections is [" + str(sectionCount) + "]")
        printDebug("Total number of servers is ["+str(numOfServers)+"]")
        WINDOW.setProperty("plexbmc.sectionCount", str(sectionCount))
        WINDOW.setProperty("plexbmc.numServers", str(numOfServers))

def libraryRefresh(url):
    printDebug("== ENTER: libraryRefresh ==", False)
    #Refreshing the library
    html=getURL(url)
    printDebug ("Library refresh requested")
    xbmc.executebuiltin("XBMC.Notification(\"PleXBMC\",Library Refresh started,100)")
    return

def watched(url):
    printDebug("== ENTER: watched ==", False)

    if url.find("unscrobble") > 0:
        printDebug ("Marking as unwatched with: " + url)
        string="Marked as unwatched"
    else:
        printDebug ("Marking as watched with: " + url)
        string="Marked as watched"
    
    html=getURL(url)
    xbmc.executebuiltin("Container.Refresh")
    
    return
 
def displayServers(url):
    printDebug("== ENTER: displayServers ==", False)
    type=url.split('/')[2]
    printDebug("Displaying entries for " + type)
    Servers = resolveAllServers()
    numOfServers=len(Servers)

    printDebug( "Using list of "+str(numOfServers)+" servers: " +  str(Servers))
     
    #For each of the servers we have identified
    for arguments in Servers:
    
        properties={}
         
        try:
            properties['title']=arguments['serverName']
        except:
            properties['title']="unknown"

        if type == "video":
            s_url='http://'+arguments['address']+"/video&mode=7"
            
        elif type == "online":
            s_url='http://'+arguments['address']+"/system/plexonline&mode=19"
            
        elif type == "music":
            s_url='http://'+arguments['address']+"/music&mode=17"
            
        elif type == "photo":
            s_url='http://'+arguments['address']+"/photos&mode=16"
                
        #Build that listing..
        addDir(s_url, properties,arguments)

                
    #All XML entries have been parsed and we are ready to allow the user to browse around.  So end the screen listing.
    xbmcplugin.endOfDirectory(pluginhandle)  
   
def getTranscodeSettings(override=False):
    global g_transcode 
    g_transcode = __settings__.getSetting('transcode')

    if override is True:
            printDebug( "Transcode override.  Will play media with addon transcoding settings")
            g_transcode="true"

    if g_transcode == "true":
        #If transcode is set, ignore the stream setting for file and smb:
        global g_stream
        g_stream = "1"
        printDebug( "We are set to Transcode, overriding stream selection")
        global g_transcodetype 
        global g_transcodefmt
        g_transcodetype = __settings__.getSetting('transcodefmt')
        if g_transcodetype == "0":
            g_transcodefmt="m3u8"
        elif g_transcodetype == "1":
            g_transcodefmt="flv"
        
        global g_quality
        g_quality = str(int(__settings__.getSetting('quality'))+3)
        printDebug( "Transcode format is " + g_transcodefmt)
        printDebug( "Transcode quality is " + g_quality)
        
        baseCapability="http-live-streaming,http-mp4-streaming,http-streaming-video,http-mp4-video"
        if int(g_quality) >= 3:
            baseCapability+=",http-streaming-video-240p,http-mp4-video-240p"
        if int(g_quality) >= 4:
            baseCapability+=",http-streaming-video-320p,http-mp4-video-320p"
        if int(g_quality) >= 5:
            baseCapability+=",http-streaming-video-480p,http-mp4-video-480p"
        if int(g_quality) >= 6:
            baseCapability+=",http-streaming-video-720p,http-mp4-video-720p"
        if int(g_quality) >= 9:
            baseCapability+=",http-streaming-video-1080p,http-mp4-video-1080p"
            
        g_audioOutput=__settings__.getSetting("audiotype")         
        if g_audioOutput == "0":
            audio="mp3,aac"
        elif g_audioOutput == "1":
            audio="mp3,aac,ac3"
        elif g_audioOutput == "2":
            audio="mp3,aac,ac3,dts"
    
        global capability   
        capability="X-Plex-Client-Capabilities="+urllib.quote_plus("protocols="+baseCapability+";videoDecoders=h264{profile:high&resolution:1080&level:51};audioDecoders="+audio)              
        printDebug("Plex Client Capability = " + capability)
        
        import uuid
        global g_sessionID
        g_sessionID=str(uuid.uuid4())
    
def deleteMedia(url):
    printDebug("== ENTER: deleteMedia ==", False)

    printDebug ("deleteing media at: " + url)
    
    ret = xbmcgui.Dialog().yesno("Confirm file delete?","Delete this item? This action will delete media and associated data files.")

    if ret:
        printDebug("Deleting....")
        installed = getURL(url,type="DELETE")    
    
        xbmc.executebuiltin("Container.Refresh")
    
    return

            
##So this is where we really start the plugin.
printDebug( "PleXBMC -> Script argument is " + str(sys.argv[1]), False)

try:
    params=get_params(sys.argv[2])
except:
    params={}
        
#Now try and assign some data to them
param_url=params.get('url',None)
param_name=urllib.unquote_plus(params.get('name',""))
mode=int(params.get('mode',-1))
param_id=params.get('id',None)
param_transcodeOverride=int(params.get('transcode',0))
param_identifier=params.get('identifier',None)
_PARAM_TOKEN=params.get('X-Plex-Token',None)

if str(sys.argv[1]) == "skin":
    discoverAllServers()
    skin()
elif sys.argv[1] == "update":
    url=sys.argv[2]
    libraryRefresh(url)
elif sys.argv[1] == "watch":
    url=sys.argv[2]
    watched(url)
elif sys.argv[1] == "setting":
    __settings__.openSettings()
elif sys.argv[1] == "delete":
    url=sys.argv[2]
    deleteMedia(url)
elif sys.argv[1] == "refresh":
    xbmc.executebuiltin("Container.Refresh")
else:
   
    pluginhandle = int(sys.argv[1])
                    
    if g_debug == "true":
        print "PleXBMC -> Mode: "+str(mode)
        print "PleXBMC -> URL: "+str(param_url)
        print "PleXBMC -> Name: "+str(param_name)
        print "PleXBMC -> ID: "+ str(param_id)
        print "PleXBMC -> token: " + str(_PARAM_TOKEN)

    #Run a function based on the mode variable that was passed in the URL
        
        
    if mode==None or param_url==None or len(param_url)<1:
        discoverAllServers()
        displaySections()
    elif mode == 0:
        getContent(param_url)
    elif mode==1:
        SHOWS(param_url)
    elif mode==2:
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
        Movies(param_url)
    elif mode==3:
        artist(param_url)
    elif mode==4:
        Seasons(param_url)
    elif mode==5:
        PLAYEPISODE(param_id,param_url)
    elif mode==6:
        EPISODES(param_url)
    elif mode==7:
        PlexPlugins(param_url)
    elif mode==12:
        PLAY(param_url)
    elif mode ==14:
        albums(param_url)
    elif mode == 15:
        tracks(param_url)
    elif mode==16:
        photo(param_url)
    elif mode==17:
        music(param_url)
    elif mode==18:
        videoPluginPlay(param_url,param_identifier)
    elif mode==19:
        plexOnline(param_url)
    elif mode==20:
        install(param_url,param_name)
    elif mode==21:
        channelView(param_url)
    elif mode==22:
        discoverAllServers()
        displayServers(param_url)
    elif mode==23:
        PLAYEPISODE(param_id,param_url,override=True)

print "===== PLEXBMC STOP ====="
   
#clear done and exit.        
sys.modules.clear()
