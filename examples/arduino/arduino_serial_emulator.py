
import sys
import os

DIR = os.path.dirname(__file__)
ZEROBOT_DIR = os.path.join(DIR, '..', '..', 'python3')
sys.path.append(os.path.abspath(ZEROBOT_DIR))


import subprocess
import threading

from zerobot import *
from zerobot.ioadapters.arduino import *


class Emulator:
	def __init__(self, exe):
		#self.out = open('out', 'wb')
		#self.last_read = 0
		self.p = subprocess.Popen(exe, stdout=subprocess.PIPE,
					stdin=subprocess.PIPE, stderr=subprocess.PIPE)
		def f():
			buff = b""
			while self.p.returncode is None:
				c = self.p.stderr.read(1)
				if c == b'\n':
					print("stderr : %s" % buff.decode())
					buff = b""
				else:
					buff += c
		t = threading.Thread(target=f)
		t.daemon = True
		t.start()
		
	def read(self, l):
		#self.p.stdout.flush()
		b = self.p.stdout.read(l)
		return b
		'''
		while 1:
			buff = open('out', 'rb').read()
			if (len(buff) - self.last_read) >= l:
				break
			time.sleep(0.01)
		self.last_read += l
		return buff[self.last_read-l:self.last_read]
		'''

	def readline(self):
		return self.p.stdout.readline()

	def write(self, m):
		self.p.stdin.write(m)
		self.p.stdin.flush()

if __name__ == '__main__':
	import sys
	import time
	import zmq
	import optparse
	import logging

	parser = optparse.OptionParser()
	parser.add_option("-e", "--exe", dest="exe",
			help="executable to wrap")
	parser.add_option("-p", "--protocol", dest="protocol",
			help="protocol type ('txt' or 'bin')")
	parser.add_option("-d", "--debug",
			action="store_true", dest="debug", default=False,
			help="show debug")
	(options, args) = parser.parse_args()

	if options.debug:
		logging.basicConfig(level=0)
	else:
		logging.basicConfig(level='INFO')

	if not options.exe:
		print("Give an executable !")
		exit(1)
	if not options.protocol:
		print("Give a protocol type !")
		exit(1)

	ctx = zmq.Context()
	s = ctx.socket(zmq.ROUTER)
	s.bind('tcp://*:5000')
	
	ctx = zmq.Context()
	l = ctx.socket(zmq.ROUTER)
	l.bind('tcp://*:5001')
	
	e = Emulator(options.exe)

	args = OrderedDict()
	args['a'] = None
	args['b'] = None
	f = ArduinoFunction("hello", 1, "simple test", args)
	
	a = ArduinoAdapter('arduino-service', 'tcp://localhost:5000', e,
				functions={"hello": f}, event_keys={56: "event_hello"},
				ev_push_addr="tcp://localhost:5001",
				protocol=options.protocol)
	
	
	try:
		a.start(False)

		req = Request(4242, "hello", args=[3000,-3000])
		s.send_multipart([b"arduino-service", b"server", req.pack()])
		print("server received :",s.recv_multipart())
		print("logger received :",l.recv_multipart())
		
		req = Request(4243, "hello", args=[3000,-3000])
		s.send_multipart([b"arduino-service", b"server", req.pack()])
		print("server received :",s.recv_multipart())
		print("logger received :",l.recv_multipart())
		
	except:
		import traceback
		traceback.print_exc()
		pass
	finally:
		a.close()

	
