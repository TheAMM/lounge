import socket
# import sys
import threading
import time
import re
import struct
import json

import logging
logging.basicConfig(level=logging.DEBUG)

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

logging

HOST = ''   # Symbolic name meaning all available interfaces
PORT = 8088 # Arbitrary non-privileged port



class WebSocketThread(threading.Thread):
	PROTOCOL_SWITCH_HEADERS = 'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {key}\r\n\r\n'
	WEBSOCKET_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
	websocketKeyRegex = re.compile(r'(?im)Sec-WebSocket-Key:\s*(.{24})$')

	daemon = True

	def __init__(self, server, conn):
		threading.Thread.__init__(self)
		self.logger = logging.getLogger(self.__class__.__name__)
		# self.logger.setLevel(50)
		self.logger.info("Created WebSocketThread")
		
		self.server = server
		self.conn = conn
		# self.state = state

		self.running = False
		self.uuid = None
		self.prevData = ''
		self.handshaked = False
	
	def die(self):
		self.server.removeThread(self)
		self.running = False
		self.conn.close()

	def process(self, d):
		j = json.loads(d)
		self.logger.info(j)

		# if j["type"] == "identify":
			# self.uuid = j["data"]["uuid"]

		self.server.processEvent(j, self)

		# key = d.split(" ")[0]
		# if key == "join":
			# self.uuid = d.split(" ")[1]
		# elif key in ["play", "pause"]:
			# event, timeStamp = d.split(" ")
			# self.state["event"] = event
			# self.state["time"] = timeStamp
		# self.logger.info( "[{}] <<".format(self.uuid, str(d)) )
		# self.send("Echo: " + d)
	def send(self, j):
		self.sendRaw(json.dumps(j))
	def sendRaw(self, data):
		# print "Trying to send"
		try:
			msg = chr(129)
			length = len(data)
			if length <= 125:
				msg += chr(length)
			elif length >= 126 and length <= 65535:
				msg += chr(126) + struct.pack(">H", length)
			else:
				msg += chr(127) + struct.pack(">Q", length)
			msg += data
			self.conn.sendall(msg)
		except Exception as e:
			self.logger.error(e)
			# pass
	def doHandshake(self, key):
		digest = b64encode(sha1(key + self.WEBSOCKET_GUID).hexdigest().decode('hex'))
		r = self.PROTOCOL_SWITCH_HEADERS.format(key=digest)
		self.logger.info("Handshaking with "+ str(digest))
		self.conn.send(r)
		self.handshaked = True


	def handle(self, data):
		dataLength = len(data)
		if dataLength < 2: return data, False
		sio = StringIO(data)
		try: 
			rc = sio.readE(1)
			if rc == chr(136):
				self.die()
				return '', False
			elif rc == chr(129):
				length = ord(sio.readE(1)) & 127
				# p = 2 # ugly, but who cares, push into production
				
				if length == 126:
					# if dataLength < 2+2: return data, False
					# length = struct.unpack(">H", data[p:p+2])[0]
					length = struct.unpack(">H", sio.readE(2))[0]
					# p+=2
				elif length == 127:
					# if dataLength < 2+8: return data, False
					# length = struct.unpack(">Q", data[p:p+8])[0]
					length = struct.unpack(">Q", sio.readE(8))[0]
					# p+=8
				
				# if len(data[p:]) < length+4: return data, False
				
				# masks = [ord(b) for b in data[p:p+4] ]
				masks = [ord(b) for b in sio.readE(4) ]
				# p += 4
				decoded = ''
				# for c in data[p:p+length]:
				for c in sio.readE(length):
					decoded += chr( ord(c) ^ masks[len(decoded) % 4] )
				# p += length

				self.process(decoded)
			
				# return data[p:], True
				return sio.read(), True
		except NoMoreToReadException as e:
			return data, False

	def run(self):
		self.running = True
		self.logger.info("WebSocketThread running")
		# The socket will not block on read, but throw an exception when it can't be read from.
		self.conn.setblocking(0)
		while self.running:
			# Receiving from client
			try:
				data = self.conn.recv(1024*4)
				if not data: break
				
				self.prevData += data
			except socket.error as e:
				if e.errno != 11:
					self.logger.error(e)

			if not self.handshaked:
				# self.logger.info(self.prevData)
				m = self.websocketKeyRegex.search(self.prevData.replace("\r", ''))
				# m = self.websocketKeyRegex.search(self.prevData)
				if m:
					self.doHandshake(m.group(1))
					self.prevData = ''
			else:
				moreData = True
				while moreData:
					self.prevData, moreData = self.handle(self.prevData)
			
		# self.conn.close()
		print "WebSocketThread out of loop"
		self.die()

# s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
# print '>> Socket created'

# #Bind socket to local host and port
# try:
# 	s.bind((HOST, PORT))
# except socket.error as msg:
# 	print '>> Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
# 	# sys.exit()

# print '>> Socket bind complete'

# #Start listening on socket
# s.listen(10)
# print '>> Socket now listening'
class WebSocketServerClient(object):
	eventListeners = {}
	
	def __init__(self):
		pass

	def addEventListener(self, name, function):
		if not name in self.eventListeners:
			self.eventListeners[name] = []
		self.eventListeners[name].append(function)
	
	def removeEventListener(self, name, function):
		if name in self.eventListeners and function in self.eventListeners[name]:
			self.eventListeners[name].remove(function)
	
	def processEvent(self, jsonData, ws):
		if not "type" in jsonData:
			return
		
		name = jsonData["type"].lower()
		funName = "on_"+name
		if hasattr(self, funName):
			getattr(self, funName)(jsonData, ws)
		if name in self.eventListeners:
			for func in self.eventListeners[name]:
				func(jsonData, ws)

class WebSocketServer(threading.Thread):
	daemon = True
	FPS = 60.0
	def __init__(self, hostPort=('', 8088), client=None):
		threading.Thread.__init__(self)
		self.logger = logging.getLogger(self.__class__.__name__)
		# self.logger.setLevel(50)

		# print "WebSocketServer, created logger", self.logger
		
		self.hostPort = hostPort
		self.client = client
		
		self.threads = []
		
		self.running = False
		self.sleepTime = 1.0 / self.FPS

		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow re-using the address. Handy when developing and restarting the server often

	

	def processEvent(self, data, ws):
		if self.client:
			self.client.processEvent(data, ws)
		# name = name.lower()
		# funName = "on_"+name
		# if hasattr(self.client, funName):
		# 	getattr(self.client, funName)(name, data, ws)
		# if name in self.eventListeners:
		# 	for func in self.eventListeners[name]:
		# 		func(name, data, ws)

	def sendAll(self, data):
		for t in self.threads:
			t.send(data)


	def die(self):
		self.logger.info("WebSocketServer shutting down")
		self.running = False
		for t in self.threads:
			t.die()
		for t in self.threads:
			t.join()
		self.logger.info("Done")

	def createThread(self, conn):
		newThread = WebSocketThread(self, conn)
		self.threads.append(newThread)
		newThread.start()
	
	# def hasChanged(self):
	# 	changed = False
	# 	for (k, v) in self.state.iteritems():
	# 		if self.oldState[k] != v:
	# 			changed = True
	# 		self.oldState[k] = v
	# 	return changed

	def removeThread(self, thread):
		try:
			self.threads.remove(thread)
		except:
			pass

	# def filterAliveThreads(self):
	# 	alive = []
	# 	for t in self.threads:
	# 		if t.isAlive():
	# 			alive.append(t)
	# 	self.threads = alive

	def run(self):
		self.running = True
		try:
			self.sock.bind(self.hostPort)
		except socket.error as msg:
			self.logger.error('Socket bind failed. Error Code : {} Message {}'.format(str(msg[0]), msg[1]))
			raise msg

		self.logger.info('Socket bind complete')
		# print 'Socket bind complete'
		self.sock.listen(10)
		self.logger.info('Socket now listening')

		while self.running:
			try:
				# Wait for a connection; blocks
				conn, addr = self.sock.accept()
				self.logger.info('Connected with {}:{}'.format(*addr))
				self.createThread(conn)
			# except KeyboardInterrupt, e:
				# self.logger.info("Quitting")
				# self.die()
				# break
			except Exception, e:
				self.logger.error("Error!")
				raise e
				self.die()
				break
		self.sock.close()
			# startTime = time.time()
			
			# self.filterAliveThreads()

			# if self.hasChanged():
			# 	m = '{event} {time}'.format(**self.state)
			# 	print "|{:02d}|".format(len(self.threads)), m
			# 	for t in self.threads:
			# 		t.send(m)

			# took = time.time() - startTime
			# time.sleep( max(0, self.sleepTime-took))
		print "MainThread out of loop"


# class ClientThread(threading.Thread):
	

# mt = MainThread()
# mt.start()

# while True:
# 	try:
# 		#wait to accept a connection - blocking call
# 		conn, addr = s.accept()
# 		print '>> Connected with {}:{}'.format(*addr)
# 		mt.createThread(conn)
# 	except KeyboardInterrupt, e:
# 		print "Quitting"
# 		mt.die()
# 		break
# 	except Exception, e:
# 		print "Error"
# 		raise e
# 		mt.die()
# 		break
# s.close()
# print "Socket closed"
