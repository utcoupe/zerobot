
import unittest

from zerobot import *

import zmq
import time

class _IOAdapterTest:
	def setUp(self):
		self.ctx = zmq.Context()
		self.server = self.ctx.socket(zmq.DEALER)
		self.server.bind("inproc://server")
		time.sleep(0.05)
		self.client = self.KLASS("client", "inproc://server", *self.ARGS, ctx=self.ctx)
		self.client.start(False)
	def tearDown(self):
		self.client.close()
		self.server.close()
		self.ctx.term()
		time.sleep(0.1)

class SubProcessAdapterTest(_IOAdapterTest, unittest.TestCase):
	KLASS = SubProcessAdapter
	ARGS = (["echo","coucou"],)
	def test_basic(self):
		msg = self.server.recv_multipart()
		self.assertEqual(msg,[b"coucou\n"])
