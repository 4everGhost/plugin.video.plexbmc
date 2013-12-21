import re
import socket
import traceback
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from urlparse import urlparse, parse_qs
from settings import settings
from functions import *
from subscribers import subMgr

class MyHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def do_HEAD(s):
        printDebug( "Serving HEAD request..." )
        s.answer_request(0)

    def do_GET(s):
        printDebug( "Serving GET request..." )
        s.answer_request(1)

    def response(s, body, headers = {}, code = 200):
        try:
            s.send_response(code)
            for key in headers:
                s.send_header(key, headers[key])
            s.send_header('Content-Length', len(body))
            s.send_header('Connection', "close")
            s.end_headers()
            s.wfile.write(body)
            s.wfile.close()
        except:
            pass

    def answer_request(s, sendData):
        try:
            request_path=s.path[1:]
            request_path=re.sub(r"\?.*","",request_path)
            url = urlparse(s.path)
            paramarrays = parse_qs(url.query)
            params = {}
            for key in paramarrays:
                params[key] = paramarrays[key][0]
            printDebug ( "request path is: [%s]" % ( request_path,) )
            printDebug ( "params are: %s" % params )
            subMgr.updateCommandID(s.headers.get('X-Plex-Client-Identifier', s.client_address[0]), params.get('commandID', False))
            if request_path=="version":
                s.response("PleXBMC Helper Remote Redirector: Running\r\nVersion: %s" % settings['version'])
            elif request_path=="verify":
                result=jsonrpc("ping")
                s.response("XBMC JSON connection test:\r\n"+result)
            elif "resources" == request_path:
                resp = getXMLHeader()
                resp += "<MediaContainer>"
                resp += "<Player"
                resp += ' title="%s"' % settings['client_name']
                resp += ' protocol="plex"'
                resp += ' protocolVersion="1"'
                resp += ' protocolCapabilities="navigation,playback,timeline"'
                resp += ' machineIdentifier="%s"' % settings['uuid']
                resp += ' product="PleXBMC"'
                resp += ' platform="%s"' % getPlatform()
                resp += ' platformVersion="%s"' % settings['plexbmc_version']
                resp += ' deviceClass="pc"'
                resp += "/>"
                resp += "</MediaContainer>"
                printDebug("crafted resources response: %s" % resp)
                s.response(resp, getPlexHeaders())
            elif "/subscribe" in request_path:
                s.response(getOKMsg(), getPlexHeaders())
                protocol = params.get('protocol', False)
                host = s.client_address[0]
                port = params.get('port', False)
                uuid = s.headers.get('X-Plex-Client-Identifier', "")
                commandID = params.get('commandID', 0)
                subMgr.addSubscriber(protocol, host, port, uuid, commandID)
            elif "/unsubscribe" in request_path:
                s.response(getOKMsg(), getPlexHeaders())
                uuid = s.headers.get('X-Plex-Client-Identifier', False) or s.client_address[0]
                subMgr.removeSubscriber(uuid)
            elif request_path == "player/playback/setParameters":
                s.response(getOKMsg(), getPlexHeaders())
                if 'volume' in params:
                    volume = int(params['volume'])
                    printDebug("adjusting the volume to %s%%" % volume)
                    jsonrpc("Application.SetVolume", {"volume": volume})
            elif "/playMedia" in request_path:
                s.response(getOKMsg(), getPlexHeaders())
                resume = params.get('viewOffset', params.get('offset', "0"))
                protocol = params.get('protocol', "http")
                address = params.get('address', s.client_address[0])
                server = getServerByHost(address)
                port = params.get('port', server.get('port', '32400'))
                fullurl = protocol+"://"+address+":"+port+params['key']
                printDebug("playMedia command -> fullurl: %s" % fullurl)
                jsonrpc("playmedia", [fullurl, resume])
                subMgr.lastkey = params['key']
                subMgr.lookup(address, port)
            elif request_path == "player/playback/play":
                s.response(getOKMsg(), getPlexHeaders())
                for playerid in getPlayerIds():
                    jsonrpc("Player.PlayPause", {"playerid" : playerid, "play": True})
            elif request_path == "player/playback/pause":
                s.response(getOKMsg(), getPlexHeaders())
                for playerid in getPlayerIds():
                    jsonrpc("Player.PlayPause", {"playerid" : playerid, "play": False})
            elif request_path == "player/playback/stop":
                s.response(getOKMsg(), getPlexHeaders())
                for playerid in getPlayerIds():
                    jsonrpc("Player.Stop", {"playerid" : playerid})
            elif request_path == "player/playback/seekTo":
                s.response(getOKMsg(), getPlexHeaders())
                for playerid in getPlayerIds():
                    jsonrpc("Player.Seek", {"playerid":playerid, "value":millisToTime(params.get('offset', 0))})
            elif request_path == "player/playback/stepForward":
                s.response(getOKMsg(), getPlexHeaders())
                for playerid in getPlayerIds():
                    jsonrpc("Player.Seek", {"playerid":playerid, "value":"smallforward"})
            elif request_path == "player/playback/stepBack":
                s.response(getOKMsg(), getPlexHeaders())
                for playerid in getPlayerIds():
                    jsonrpc("Player.Seek", {"playerid":playerid, "value":"smallbackward"})
            elif request_path == "player/playback/skipNext":
                s.response(getOKMsg(), getPlexHeaders())
                for playerid in getPlayerIds():
                    jsonrpc("Player.Seek", {"playerid":playerid, "value":"bigforward"})
            elif request_path == "player/playback/skipPrevious":
                s.response(getOKMsg(), getPlexHeaders())
                for playerid in getPlayerIds():
                    jsonrpc("Player.Seek", {"playerid":playerid, "value":"bigbackward"})
            elif request_path == "player/navigation/moveUp":
                s.response(getOKMsg(), getPlexHeaders())
                jsonrpc("Input.Up")
            elif request_path == "player/navigation/moveDown":
                s.response(getOKMsg(), getPlexHeaders())
                jsonrpc("Input.Down")
            elif request_path == "player/navigation/moveLeft":
                s.response(getOKMsg(), getPlexHeaders())
                jsonrpc("Input.Left")
            elif request_path == "player/navigation/moveRight":
                s.response(getOKMsg(), getPlexHeaders())
                jsonrpc("Input.Right")
            elif request_path == "player/navigation/select":
                s.response(getOKMsg(), getPlexHeaders())
                jsonrpc("Input.Select")
            elif request_path == "player/navigation/home":
                s.response(getOKMsg(), getPlexHeaders())
                jsonrpc("Input.Home")
            elif request_path == "player/navigation/back":
                s.response(getOKMsg(), getPlexHeaders())
                jsonrpc("Input.Back")
        except:
            traceback.print_exc()
    
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True