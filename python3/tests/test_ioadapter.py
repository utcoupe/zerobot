
import unittest

from zerobot import *

import zmq
import time

class IOAdapterTest:
	
	def setUp(self):
		self.ctx = zmq.Context()
		self.server = self.ctx.socket(zmq.ROUTER)
		self.server.identity = b'Server'
		self.server.bind("inproc://server")
		time.sleep(0.05)
		self.ioadapter = self.KLASS("IoAdapter", "inproc://server", *self.ARGS, ctx=self.ctx)
		self.ioadapter.start(False)
		
	def tearDown(self):
		self.ioadapter.close()
		self.server.close()
		self.ctx.term()
		time.sleep(0.1)

class SubProcessAdapterTest(IOAdapterTest, unittest.TestCase):
	KLASS = SubProcessAdapter
	ARGS = (["echo","coucou"],)
	def test_basic(self):
		msg = self.server.recv_multipart()
		self.assertEqual(msg,[self.ioadapter.identity.encode(), b"coucou\n"])

if __name__ == '__main__':
    unittest.main()
