#!/usr/bin/python
import cherrypy
# import sqlite3
import os
import re
import time

from mako.template import Template
from mako.lookup import TemplateLookup

import WebSocket

import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("cherrypy.error").setLevel(logging.ERROR)
logging.getLogger("cherrypy.access").setLevel(logging.ERROR)

class CouchListener(WebSocket.WebSocketServerClient):
	def on_identify(self, j, ws):
		ws.uuid = j["uuid"]
		ws.send({"type":"ping", "time":time.time()})
		# print ws.uuid, "identified"
		# print j, ws
	
	def on_ping(self, j, ws):
		ws.send({"type":"pong", "time":j["time"]})
	def on_pong(self, j, ws):
		delta = time.time() - j["time"]
		print "Ping to {} and back: {:0.1f}".format(ws.uuid, delta*1000)
	
	def on_play(self, j, ws):
		wss.sendAll(j)
	on_pause = on_play
	on_seeked = on_play
	on_setvideo = on_play
	



cl = CouchListener()
wss = WebSocket.WebSocketServer( ('', 8088) , client=cl)
wss.start()
# Socket



# SQLITE_DATABASE = "database.sqlite3"

# Our CherryPy application
tmplLookup = TemplateLookup(directories=['templates'], module_directory='tmp/mako')
class Root(object):
	
	def __init__(self):
		# self.api = API()
		pass

	@cherrypy.expose
	def index(self):
		tmpl = tmplLookup.get_template("testing.mako.html")
		context = { 
					"wshost" : re.match(r'https?:\/\/(.*?)(?::\d+)$', cherrypy.request.base).group(1),
					"wsport" : 8088,
					"port" : 8088,
					"base" : cherrypy.request.base,
				  }
		return tmpl.render(**context)

	# @cherrypy.expose
	# def default(self, key=None, **kwargs):
	# 	raise cherrypy.HTTPRedirect("/") 


# cherrypy.engine.subscribe('start', dbHandler.setup_database)

# cherrypy.engine.subscribe('start', dbHandler.setup_database)
cherrypy.engine.subscribe('stop', wss.die)
# cherrypy.engine.subscribe('stop', cleanup_database)
staticDir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "static")
staticIco = os.path.join(staticDir,  "favicon.ico")
config = {
	# "/favicon.ico": {
		# "tools.staticfile.on" : True,
		# "tools.staticfile.filename" : staticIco
	# },
	"/static": {
		"tools.staticdir.on" : True,
		"tools.staticdir.dir" : staticDir
	}
}

wsgiapp = cherrypy.tree.mount(Root(), config=config)

if __name__ != "__main__":
	cherrypy.config.update({'engine.autoreload.on': False})
	cherrypy.server.unsubscribe()
	cherrypy.engine.start()
else:
	cherrypy.config.update({ 'server.socket_port': 8090, 'server.socket_host': "0.0.0.0"})
	cherrypy.quickstart(wsgiapp)