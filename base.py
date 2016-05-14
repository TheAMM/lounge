#!/usr/bin/python
import cherrypy
# import sqlite3
import os
import re
import time

import random
import math

from mako.template import Template
from mako.lookup import TemplateLookup

import WebSocket

import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("cherrypy.error").setLevel(logging.ERROR)
logging.getLogger("cherrypy.access").setLevel(logging.ERROR)

def generateKey(length=6):
	r = random.random()
	print length
	def baseN(num, b=62, numerals="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"):
		return ((num == 0) and numerals[0]) or (baseN(num // b, b, numerals).lstrip(numerals[0]) + numerals[num % b])
	return baseN( int(r*math.pow(62, length)), 62)

USER_KEY_LENGTH = 6
ROOM_KEY_LENGTH = 4

class SocketManager(object):
	def __init__(self, app):
		self.app = app

	def handleNewThread(self, e):
		e.data.addEventListener("connection", self.on_connection)
		# e.data.addEventListener("message", self.on_message)

	# def on_message(self, e):

	def on_connection(self, e):
		ws = e.data
		print ws, ws.path, ws.uuid, self.app.r.rooms
		
		if not ws.path in self.app.r.rooms:
			print "No room for WS, killing"
			ws.die()
			return

		print "Adding", ws
		self.app.r.rooms[ws.path].addUser(ws)

class CouchListener(WebSocket.WebSocketServerClient):
	def __init__(self, app):
		self.app = app

	def on_connection(self, ws):
		# u = Lounger.fromIdentify(j, ws)
		u = Lounger(ws)
		u.uuid = generateKey(USER_KEY_LENGTH)
		# self.app.r.rooms[u.roomKey].addUser(u)

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
		se.sendAll(j)
	on_pause = on_play
	on_seeked = on_play
	on_setvideo = on_play


class Lounger(WebSocket.EventDispatcher):
	def __init__(self, websocket, name="Nameless Lounger"):
		self.ws = websocket
		self.ws.addEventListener("die", self.die)
		self.ws.addEventListener("message", self._message)
		self.name = name
		self.uuid = websocket.uuid
		self.roomKey = websocket.path
		self.ping = -1
		self.time = None
		# self.room =

	def die(self, event=None):
		self.dispatchEvent("die", self)

	def _message(self, event):
		event.source = self
		self.dispatchEvent(event)
	
	@staticmethod
	def fromIdentify(j, ws):
		l = Lounger(ws)
		l.uuid = j["uuid"]
		l.roomKey = j["room"]
		return l
		# l.uuid = j["uuid"]

import threading
class LoungeRoom(object):
	def __init__(self, key, name="Unnamed Lounge"):
		self.key = key
		self.name = name

		self.users = []

		self._pendingReplies = {}

		# t = threading.Thread(target = self.sendUpdates)
		# t.start()

	# def sendUpdates(self):
	# 	while True:
	# 		t = {}
	# 		for l in self.users:
	# 			t[l.uuid] = l.time
	# 		t = {"type": "times", "times":t}
	# 		self.sendAll(t)
	# 		time.sleep(2)


	def _on_message(self, e):
		jsonData = e.data
		if jsonData is None or (not "type" in jsonData):
			return

		name = jsonData["type"].lower()
		if name == "reply":
			self._pendingReplies[jsonData["replyid"]](e)
		else:
			funName = "on_"+name
			if hasattr(self, funName):
				getattr(self, funName)(jsonData, e.source)

	def getTimes(self):
		self.sendAll( {"type":"gettime"} )

	def getPing(self):
		for l in self.users:
			l.ws.sendReplyCallback( {"type":"ping"})

	def on_time(self, j, l):
		l.time = j["time"]

	def on_pingall(self, j, l):
		self.pingAll()


	def on_ping(self, j, l):
		l.ws.send({"type":"pong", "time":j["time"]})
	def on_pong(self, j, l):
		delta = time.time() - j["time"]
		print "Ping to {} ({}) and back: {:0.1f}".format(l.ws.rhost, l.uuid, delta*1000)
	
	def on_play(self, j, l):
		self.sendAll(j)

	on_pause = on_play
	on_seeked = on_play
	on_setvideo = on_play


	def changeName(self, newName):
		self.name = newName
		
		self.sendAll( {"type":"roomname", "room":self.key, "name":self.name})

	def pingAll(self):
		for u in this.users:
			u.ping = -1
		self.sendAll( {"type":"ping", "time":time.time()} )

	def addUser(self, ws):
		user = Lounger(ws)
		
		self.sendAll( {"type":"join", "user":user.uuid} )
		
		self.users.append(user)
		user.room = self
		user.addEventListener("die", self.removeUser)
		user.addEventListener("message", self._on_message)
		
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
class RoomExistsException(Exception):
	pass
class RoomDoesNotExistException(Exception):
	pass

class Rooms(object):
	def __init__(self):
		self.rooms = {}

	@cherrypy.expose
	def index(self):
		raise cherrypy.HTTPRedirect("/")

	def createRoom(self, roomKey):
		if roomKey in self.rooms:
			raise RoomExistsException()
		room = LoungeRoom(roomKey)
		self.rooms[roomKey] = room
		return room

	def removeRoom(self, roomKey):
		if roomKey not in self.rooms:
			raise RoomDoesNotExistException()
		self.rooms.pop(roomKey, None)
	
	@cherrypy.expose
	def default(self, roomKey=None, **kwargs):
		if not roomKey in self.rooms:
			return 'No room found. <a href="/">Go back.</a>'
			# roomName = kwargs.pop("name", None) or "Unnamed Lounge"
			# room = LoungeRoom(roomKey)
			# self.rooms[roomKey] = room
		# else:
		room = self.rooms[roomKey]
		# print self.rooms

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

	def cleanName(self, name):
		allowed = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ _*"
		if name:
			return ''.join( c for c in name if c in allowed).replace(' ', '_').strip()
		return None

# SQLITE_DATABASE = "database.sqlite3"

# Our CherryPy application
tmplLookup = TemplateLookup(directories=['templates'], module_directory='tmp/mako')
class Root(object):
	
	def __init__(self):
		self.r = Rooms()
		# self.cl = CouchListener(self)
		self.sm = SocketManager(self)
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

	@cherrypy.expose
	def room(self, roomname=None, action=None):
		roomname = self.r.cleanName(roomname)
		if not roomname:
			return "No roomname, eh?"
		if not action:
			return "No action, eh?"
		
		if   action == "create":
			self.r.createRoom(roomname)
			raise cherrypy.HTTPRedirect("/r/"+roomname)
		elif action == "remove":
			self.r.removeRoom(roomname)
			raise cherrypy.HTTPRedirect("/")

		return roomname

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

# wss = WebSocket.WebSocketServer( ('', 8088) , client=root.cl)
wss = WebSocket.WebSocketServer( ('', 8088))
wss.addEventListener("newthread", root.sm.handleNewThread)
cherrypy.engine.subscribe('stop', wss.die)

wss.start()


if __name__ != "__main__":
	cherrypy.config.update({'engine.autoreload.on': False})
	cherrypy.server.unsubscribe()
	cherrypy.engine.start()
else:
	cherrypy.config.update({ 'server.socket_port': 8090, 'server.socket_host': "0.0.0.0"})
	cherrypy.quickstart(wsgiapp)