import socket
# import sys
import threading
import time
import re
import struct
import json

import logging
logging.basicConfig(level=logging.DEBUG)

# We can't customize
# try:
	# from cStringIO import StringIO
# except:
from StringIO import StringIO

class NoMoreToReadException(Exception):
	pass
def readOrException(self, c=-1):
	d = self.read(c)
	if c != -1 and len(d) != c:
		raise NoMoreToReadException("Couldn't read desired amount of bytes")
	return d
StringIO.readE = readOrException


from base64 import b64encode
from hashlib import sha1

class Event(object):
	def __init__(self, name, data):
		self.name = name
		self.data = data
		self.source = None
	def __str__(self):
		return "<Event '{}' {}>".format(self.name, self.data)

class EventDispatcher(object):
	def _createDictIfNot(self):
		if not hasattr(self, "eventListeners"):
			self.eventListeners = {}
	def dispatchEvent(self, nameOrEvent, data=None):
		self._createDictIfNot()
		
		e = Event(nameOrEvent, data) if isinstance(nameOrEvent, basestring) else nameOrEvent
		
		if not e.source:
			e.source = self

		if e.name in self.eventListeners:
			for el in self.eventListeners[e.name]:
				if el(e):
					break

	def addEventListener(self, name, function):
		self._createDictIfNot()

		if not name in self.eventListeners:
			self.eventListeners[name] = []
		self.eventListeners[name].append(function)
	
	def removeEventListener(self, name, function):
		self._createDictIfNot()

		if name in self.eventListeners and function in self.eventListeners[name]:
			self.eventListeners[name].remove(function)


class WebSocketThread(threading.Thread, EventDispatcher):
	PROTOCOL_SWITCH_HEADERS = 'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {key}\r\n\r\n'
	WEBSOCKET_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
	websocketKeyRegex = re.compile(r'(?im)Sec-WebSocket-Key:\s*(.{24})$')
	websocketPathRegex = re.compile(r'(?im)^GET /([a-zA-Z0-9_]+)/([a-zA-Z0-9_]+) HTTP/1.\d$')

	daemon = True

	def __init__(self, conn):
		threading.Thread.__init__(self)
		self.logger = logging.getLogger(self.__class__.__name__)
		
		# self.server = server
		self.conn = conn

		self.rhost, self.rport = self.conn.getpeername()
		self.lhost, self.lport = self.conn.getsockname()

		self.path = None
		self.uuid = None

		self.prevData = ''
		self.fragment = ''

		self.running = False
		self.handshaked = False
		self.pendingReplies = {}
	
	def die(self):
		self.running = False
		self.dispatchEvent("die", self)

	def process(self, d):
		try:
			j = json.loads(d)
			self.logger.info(j)
			if "rid" in j and j["rid"] in self.pendingReplies:
				callback = self.pendingReplies.pop(j["rid"])
				callback[0](j, *callback[1], **callback[2])
			self.dispatchEvent("message", j)
		except ValueError:
			self.logger.warning("Got a bad message from {}:{}".format(self.rhost, self.rport))
			print d

	def sendReply(self, j):
		rid = str(hash(j)) + str(hash(self))
		j["rid"] = rid
		self.send( j )
		return rid
	def sendReplyCallback(self, j, callback, *args, **kwargs):
		rid = self.sendReply(j)
		self.pendingReplies[rid] = (callback, args, kwargs)
		return rid

	def send(self, j):
		self.sendRaw(json.dumps(j))
	def sendRaw(self, data):
		try:
			msg = chr(129)
			length = len(data)
			
			if length < 126:
				msg += chr(length)
			elif length < 65536:
				msg += chr(126) + struct.pack(">H", length)
			else:
				msg += chr(127) + struct.pack(">Q", length)
			
			msg += data
			self.conn.sendall(msg)
		except Exception as e:
			self.logger.error(e)

	def doHandshake(self, key):
		digest = b64encode(sha1(key + self.WEBSOCKET_GUID).hexdigest().decode('hex'))
		r = self.PROTOCOL_SWITCH_HEADERS.format(key=digest)
		self.logger.info("Handshaking with "+ str(digest))
		self.conn.send(r)
		self.handshaked = True

		self.dispatchEvent("connection", self)


	def handle(self, data):
		# How many bytes of data we've got
		dataLength = len(data)
		# The first two bytes determine the length, and if we don't have those, abort
		if dataLength < 2: return data, False

		# Wrapping the bytes into a StringIO makes reading them easier, when we don't have to worry about the position in the stream
		sio = StringIO(data)
		try: 
			# Read a byte, note that the custom .readE() throws an exception if we can't read enough
			rc = ord(sio.readE(1))
			fin, opcode = rc >> 4+3, rc & 0xF # FIN, (RSVP1-3) and opcode
			rc = ord(sio.readE(1))
			masked, plen = rc >> 7, rc & 0x7f # MASKED (always 1) and payload length
			
			if opcode == 0x8: # 0x8: close connection
				self.die()
				return '', False
			elif opcode in [0x0, 0x1, 0x2]: # Continuation-, Text-, Binary frame
				
				# Unpack the length if it's not < 126
				if plen == 126:
					plen = struct.unpack(">H", sio.readE(2))[0]
				elif plen == 127:
					plen = struct.unpack(">Q", sio.readE(8))[0]
				
				# The data is masked with XOR
				masks = [ord(b) for b in sio.readE(4) ]
				decoded = ''
				for c in sio.readE(plen):
					decoded += chr( ord(c) ^ masks[len(decoded) % 4] )

				self.fragment += decoded
				if fin: # Is this the final packet in this sequence?
					self.process(self.fragment)
					self.fragment = ''
				
				# Return the rest of the data
				return sio.read(), True
		except NoMoreToReadException as e:
			return data, False

	def run(self):
		self.running = True

		# The socket will not block on read, but throw an exception when it can't be read from.
		self.conn.setblocking(0)
		while self.running:
			# Receiving from client
			try:
				data = self.conn.recv(1024*4)
				if not data: break 
				
				self.prevData += data

				if not self.handshaked:
					d = self.prevData.replace("\r", '')
					m = self.websocketKeyRegex.search(d)
					p = self.websocketPathRegex.search(d)
					if m:
						self.path, self.uuid = p.groups()
						self.prevData = ''
						self.doHandshake(m.group(1))
				
				else:
					moreData = True
					while moreData:
						self.prevData, moreData = self.handle(self.prevData)
			except socket.error as e:
				if e.errno != 11:
					self.logger.error(e)
		self.conn.close()
		# print "WebSocketThread out of loop"
		# self.die()

class WebSocketServerClient(EventDispatcher):
	
	def processEvent(self, jsonData, ws):
		if not "type" in jsonData:
			return
		self._createDictIfNot()
		
		name = jsonData["type"].lower()
		funName = "on_"+name
		if hasattr(self, funName):
			getattr(self, funName)(jsonData, ws)
		if name in self.eventListeners:
			for func in self.eventListeners[name]:
				func(jsonData, ws)

class WebSocketServer(threading.Thread, EventDispatcher):
	daemon = True
	FPS = 60.0
	def __init__(self, hostPort=('', 8088), client=None):
		threading.Thread.__init__(self)
		self.logger = logging.getLogger(self.__class__.__name__)
		
		self.hostPort = hostPort
		self.client = client
		
		self.threads = []
		
		self.running = False
		self.sleepTime = 1.0 / self.FPS

		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allows re-using the address. Handy when developing and restarting the server often

	

	# def processEvent(self, data, ws):
		# if self.client:
			# self.client.processEvent(data, ws)

	def sendAll(self, data):
		for t in self.threads:
			t.send(data)


	def die(self):
		self.running = False
		for t in self.threads:
			t.die()
		
		self.logger.info("Threads killed - waiting...")
		for t in self.threads:
			t.join()
		self.logger.info("Done")

	def createThread(self, conn):
		newThread = WebSocketThread(conn)
		newThread.addEventListener("die", self.removeThread)
		self.threads.append(newThread)
		self.dispatchEvent("newthread", newThread)
		newThread.start()
	
	def removeThread(self, thread):
		if isinstance(thread, Event):
			thread = thread.data
		try:
			self.threads.remove(thread)
		except:
			pass

	def run(self):
		self.running = True
		try:
			self.sock.bind(self.hostPort)
		except socket.error as msg:
			self.logger.error('Socket bind failed. Error Code : {} Message {}'.format(str(msg[0]), msg[1]))
			raise msg

		self.logger.info('Socket bind complete')
		self.sock.listen(10)
		self.logger.info('Socket now listening')

		while self.running:
			try:
				# Wait for a connection; blocks
				conn, addr = self.sock.accept()
				self.logger.info('Connected with {} - {}:{}'.format(conn.getpeername(), *addr))
				self.createThread(conn)
			except Exception, e:
				self.logger.error("Error!")
				raise e
				self.die()
				break
		self.sock.close()

		print "MainThread out of loop"
