
import unittest

import time

from zerobot import *


class RequestTestCase(unittest.TestCase):
	def setUp(self):
		self.uuid = 42
		self.fct = 'fct_test'
		self.args = [1,2,3]
		self.kwargs = {'a':1}
		self.r = Request(self.uuid, self.fct, self.args, self.kwargs)
		
	def test_attrs(self):
		self.assertEqual(self.r.uid, self.uuid)
		self.assertEqual(self.r.fct, self.fct)
		self.assertEqual(self.r.args, self.args)
		self.assertEqual(self.r.kwargs, self.kwargs)
		
	def test_pack_unpack(self):
		pack = self.r.pack()
		unpack = Request.unpack(pack)
		self.assertEqual(self.r, unpack)
		

class ResponseTestCase(unittest.TestCase):
	def setUp(self):
		self.uuid = 42
		self.data = {'a': 1, 'b': [1,2,'hey'], 'c': {'hello': 'world'}}
		self.error = {'error': 'Une erreur', 'tb': 'La traceback'}
		self.r = Response(self.uuid, self.data, self.error)

	def test_attrs(self):
		self.assertEqual(self.r.uid, self.uuid)
		self.assertEqual(self.r.data, self.data)
		self.assertEqual(self.r.error, self.error)

	def test_unpack_pack(self):
		pack = self.r.pack()
		unpack = Response.unpack(pack)
		self.assertEqual(self.r, unpack)

class RemoteTestCase(unittest.TestCase):
	class Abc:
		def ping(self, num):
			return num+42

		def hello(self):
			return "world"

		def hard_one(self, a=3, b=4, c=5):
			return a,b,c

		def sleep(self, n):
			time.sleep(n)
	FRONTEND_PORT	= 5010
	BACKEND_PORT	= 5011
	LOG_PORT		= 5012
	
	def setUp(self):
		self.server = Server("tcp://*:%s"%self.FRONTEND_PORT,"tcp://*:%s"%self.BACKEND_PORT,"tcp://*:%s"%self.LOG_PORT)
		self.server.start()

		self.abc = ClassExposer("abc", "tcp://localhost:%s"%self.BACKEND_PORT, self.Abc())
		self.abc.start()
		time.sleep(0.2)
		
		self.client = RemoteClient("client", "tcp://localhost:%s"%self.FRONTEND_PORT, "abc")
		self.client.start()
		time.sleep(0.2)

	def test_block(self):
		self.assertEqual(self.client.ping(56,block=True), 56+42)
		self.assertEqual(self.client.hello(block=True), "world")
		self.assertEqual(self.client.hard_one(c=1,b=42,block=True), [3,42,1])

	def test_async(self):
		self._setup_cb()
		ev = self.client.ping(56, block=False, cb_fct=self._cb)
		ev.wait()
		self.assertIsNotNone(self.response_cb)
		self.assertEqual(self.response_cb.data, 56+42)

	def test_timeout(self):
		self.assertRaises(ZeroBotTimeout, self.client.sleep, 100, timeout=0.5, block=True)
		self._setup_cb()
		ev = self.client.sleep(100, block=False, timeout=0.5, cb_fct=self._cb)
		ev.wait()
		self.assertTrue(self.response_cb.error_is_set())
		self.assertEqual(self.response_cb.error['error'], 'timeout')


	def _setup_cb(self):
		self.response_cb = None
	
	def _cb(self, response):
		self.response_cb = response
	
	def tearDown(self):
		self.server.stop()
		self.abc.stop()
		self.client.stop()
		time.sleep(1)
		
