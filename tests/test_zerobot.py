
import unittest

import time

from zerobot import *

import logging
#logging.basicConfig(level=-1000)

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

