
import unittest

from zerobot import *


class RequestTestCase(unittest.TestCase):
	def setUp(self):
		self.uuid = 42
		self.fct = 'fct_test'
		self.args = (1,2,3)
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
		print(unpack)
		self.assertEqual(self.r, unpack)
		
