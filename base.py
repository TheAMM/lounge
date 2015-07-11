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
	def __init__(self, app):
		self.app = app

	def on_identify(self, j, ws):
		u = Lounger.fromIdentify(j, ws)
		self.app.r.rooms[u.roomKey].addUser(u)
		# ws.uuid = j["uuid"]
		# ws.uuid = j["uuid"]
		# ws.send({"type":"ping", "time":time.time()})
		# print ws.uuid, "identified"
		# print j, ws
	
	def on_pingall(self, j, ws):
		self.app.r.rooms[j["room"]].pingAll()

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


class Lounger(WebSocket.EventDispatcher):
	def __init__(self, websocket, name="Nameless Lounger"):
		self.ws = websocket
		self.ws.addEventListener("die", self.die)
		self.name = name
		# self.uuid = uuid
		self.roomKey = None
		self.ping = -1
		# self.room =

	def die(self, event=None):
		self.dispatchEvent("die", self)
	
	@staticmethod
	def fromIdentify(j, ws):
		l = Lounger(ws)
		l.uuid = j["uuid"]
		l.roomKey = j["room"]
		return l
		# l.uuid = j["uuid"]


class LoungeRoom(object):
	def __init__(self, key, name="Unnamed Lounge"):
		self.key = key
		self.name = name

		self.users = []
	def changeName(self, newName):
		self.name = newName
		
		self.sendAll( {"type":"roomname", "room":self.key, "name":self.name})

	def pingAll(self):
		for u in this.users:
			u.ping = -1
		self.sendAll( {"type":"ping", "time":time.time()} )

	def addUser(self, user):
		if not user in self.users:
			self.sendAll( {"type":"join", "user":user.uuid} )
			
			self.users.append(user)
			user.room = self
			user.addEventListener("die", self.removeUser)
			
			user.ws.send( {"type":"users", "users":[u.uuid for u in self.users]} )
	
	def removeUser(self, user):
		if isinstance(user, WebSocket.Event):
			user = user.data
		try:
			self.users.remove(user)
			self.sendAll( {"type":"left", "user":user.uuid} )
			user.room = None
		except:
			pass
	def sendAll(self, jsonData):
		for u in self.users:
			u.ws.send(jsonData)




# Socket

class Rooms(object):
	def __init__(self):
		self.rooms = {}

	@cherrypy.expose
	def index(self):
		raise cherrypy.HTTPRedirect("/")
	
	@cherrypy.expose
	def default(self, roomKey=None, **kwargs):
		if not roomKey in self.rooms:
			roomName = kwargs.pop("name", None) or "Unnamed Lounge"
			room = LoungeRoom(roomKey)
			self.rooms[roomKey] = room
		else:
			room = self.rooms[roomKey]
		print self.rooms

		tmpl = tmplLookup.get_template("room.mako.html")
		context = { 
					"wshost" : re.match(r'https?:\/\/(.*?)(?::\d+)$', cherrypy.request.base).group(1),
					"wsport" : 8088,
					"port" : 8088,
					"base" : cherrypy.request.base,
					"roomKey" : room.key,
					"roomName" : room.name,
				  }
		return tmpl.render(**context)

# SQLITE_DATABASE = "database.sqlite3"

# Our CherryPy application
tmplLookup = TemplateLookup(directories=['templates'], module_directory='tmp/mako')
class Root(object):
	
	def __init__(self):
		self.r = Rooms()
		self.cl = CouchListener(self)
		pass

	@cherrypy.expose
	def index(self):
		# tmpl = tmplLookup.get_template("testing.mako.html")
		tmpl = tmplLookup.get_template("index.mako.html")
		context = { 
					# "wshost" : re.match(r'https?:\/\/(.*?)(?::\d+)$', cherrypy.request.base).group(1),
					# "wsport" : 8088,
					# "port" : 8088,
					# "base" : cherrypy.request.base,
					"rooms":self.r.rooms.values()
				  }
		return tmpl.render(**context)

	# @cherrypy.expose
	# def default(self, key=None, **kwargs):
	# 	raise cherrypy.HTTPRedirect("/") 


# cherrypy.engine.subscribe('start', dbHandler.setup_database)

# cherrypy.engine.subscribe('start', dbHandler.setup_database)
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

root = Root()
wsgiapp = cherrypy.tree.mount(root, config=config)

wss = WebSocket.WebSocketServer( ('', 8088) , client=root.cl)
cherrypy.engine.subscribe('stop', wss.die)

wss.start()


if __name__ != "__main__":
	cherrypy.config.update({'engine.autoreload.on': False})
	cherrypy.server.unsubscribe()
	cherrypy.engine.start()
else:
	cherrypy.config.update({ 'server.socket_port': 8090, 'server.socket_host': "0.0.0.0"})
	cherrypy.quickstart(wsgiapp)