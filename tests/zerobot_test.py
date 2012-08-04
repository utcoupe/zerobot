
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

class ZeroBotTestCase(unittest.TestCase):
	class Cool:
		def ping(self, num):
			return num+42

		def hello(self):
			return "world"

		def hard_one(self, a=3, b=4, c=5):
			return a,b,c

		def echo(self, m):
			return m
	
	def setUp(self):
		server = Server("tcp://*:8080","tcp://*:8081","tcp://*:8082")
		server.start()

		cool = ClassExposer("cool", "tcp://localhost:8081", ZeroBotTestCase.Cool())
		cool.start()

		time.sleep(0.2)

	def test_remote(self):
		remote_cool = RemoteClient("remote_cool", "tcp://localhost:8080", "cool")
		remote_cool.start()
		time.sleep(0.2)

		self.assertEqual(remote_cool.ping(56,block=True), 56+42)
		self.assertEqual(remote_cool.hello(block=True), "world")
		self.assertEqual(remote_cool.hard_one(c=1,b=42,block=True), [3,42,1])
