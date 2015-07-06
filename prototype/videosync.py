'''
	Simple socket server using threads
'''

import socket
import sys
# from thread import *
import threading
import time
import re
import struct
from base64 import b64encode
from hashlib import sha1


HOST = ''   # Symbolic name meaning all available interfaces
PORT = 8088 # Arbitrary non-privileged port

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
print '>> Socket created'

#Bind socket to local host and port
try:
	s.bind((HOST, PORT))
except socket.error as msg:
	print '>> Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
	sys.exit()

print '>> Socket bind complete'

#Start listening on socket
s.listen(10)
print '>> Socket now listening'

class MainThread(threading.Thread):
	daemon = True
	FPS = 60.0
	def __init__(self):
		threading.Thread.__init__(self)
		self.state = {"time":None, "event":None}
		self.oldState = {"time":None, "event":None}
		self.threads = []

		self.running = True

		self.sleepTime = 1.0 / self.FPS

	def die(self):
		self.running = False
		print "Not running"
		for t in self.threads:
			print "Killing", t
			t.die()
			print "Killed", t
		print "Done"

	def createThread(self, conn):
		newThread = ClientThread(conn, self.state)
		self.threads.append(newThread)
		newThread.start()
	
	def hasChanged(self):
		changed = False
		for (k, v) in self.state.iteritems():
			if self.oldState[k] != v:
				changed = True
			self.oldState[k] = v
		return changed

	def filterAliveThreads(self):
		alive = []
		for t in self.threads:
			if t.isAlive():
				alive.append(t)
		self.threads = alive

	def run(self):
		while self.running:
			startTime = time.time()
			
			self.filterAliveThreads()

			if self.hasChanged():
				m = '{event} {time}'.format(**self.state)
				print "|{:02d}|".format(len(self.threads)), m
				for t in self.threads:
					t.send(m)

			took = time.time() - startTime
			time.sleep( max(0, self.sleepTime-took))
		print "MainThread out of loop"


class ClientThread(threading.Thread):
	websocketGUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

	daemon = True
	changedLock = threading.Lock()
	def __init__(self, conn, state):
		threading.Thread.__init__(self)
		self.conn = conn
		self.state = state
		self.running = True
		self.uid = None
		self.prevData = ""
		self.handshaked = False
	
	def die(self):
		self.running = False
		self.conn.close()

	def process(self, d):
		key = d.split(" ")[0]
		if key == "join":
			self.uid = d.split(" ")[1]
		elif key in ["play", "pause"]:
			event, timeStamp = d.split(" ")
			self.state["event"] = event
			self.state["time"] = timeStamp
		print "[{}] <<".format(self.uid), d
		# self.send("Echo: " + d)

	def send(self, data):
		# print "Trying to send"
		try:
			if self.running:
				msg = chr(129)
				length = len(data)
				if length <= 125:
					msg += chr(length)
				elif length >= 126 and length <= 65535:
					msg += chr(126)
					msg += struct.pack(">H", length)
				else:
					msg += chr(127)
					msg += struct.pack(">Q", length)
				msg += data

				self.conn.sendall(msg)
		except Exception as e:
			print e
			pass
	def doHandshake(self, key):
		digest = b64encode(sha1(key + self.websocketGUID).hexdigest().decode('hex'))
		r = 'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {key}\r\n\r\n'.format(key=digest)
		print "Handshaking with", digest
		self.conn.send(r)
		self.handshaked = True


	def handle(self, data):
		dataLength = len(data)
		if dataLength < 2: return data, False
		length = ord(data[1]) & 127
		p = 2 # ugly, but who cares, push into production
		
		if length == 126:
			if dataLength < 2+2: return data, False
			length = struct.unpack(">H", data[p:p+2])[0]
			p+=2
		elif length == 127:
			if dataLength < 2+8: return data, False
			length = struct.unpack(">Q", data[p:p+8])[0]
			p+=8
		
		if len(data[p:]) < length+4: return data, False
		
		masks = [ord(b) for b in data[p:p+4] ]
		p += 4
		decoded = ''
		for c in data[p:p+length]:
			decoded += chr(ord(c) ^ masks[len(decoded) % 4])
		p += length

		self.process(decoded)
		
		return data[p:], True

	def run(self):
		self.conn.setblocking(0)
		while self.running:
			#Receiving from client
			try:
				data = self.conn.recv(1024*4)
				if not data: break
				
				self.prevData = self.prevData + data
			except socket.error as e:
				if e.errno == 11:
					pass
				else:
					print e

			if not self.handshaked:
				m = re.search(r'Sec-WebSocket-Key:\s+(.{24})$', self.prevData.replace("\r", ""), re.MULTILINE)
				if m:
					# print "Sec-WebSocket-Key", m.group(1)
					self.doHandshake(m.group(1))
					self.prevData = ''
			else:
				moreData = True
				while moreData:
					self.prevData, moreData = self.handle(self.prevData)
			
		self.conn.close()
		print "ClientThread out of loop"

mt = MainThread()
mt.start()

while True:
	try:
		#wait to accept a connection - blocking call
		conn, addr = s.accept()
		print '>> Connected with {}:{}'.format(*addr)
		mt.createThread(conn)
	except KeyboardInterrupt, e:
		print "Quitting"
		mt.die()
		break
	except Exception, e:
		print "Error"
		raise e
		mt.die()
		break
s.close()
print "Socket closed"
