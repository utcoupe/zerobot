
import unittest

import time

from zerobot import *

#import logging; logging.basicConfig(level=0)

class _ServiceTest:
	
	class BasicClient(BaseClient):
		def _process(self, fd, _ev):
			self.msg = fd.recv_multipart()
	
	class Abc:
		def ping(self, num):
			return num+42

		def hard_one(self, a=1, b=2, c=3):
			return a,b,c

		def sleep(self, t):
			time.sleep(t)
			return t
	
	PORT	= 9050
	client_id = b"client"
	classexposer_id = b"classexposer"

	def setUp(self):
		
		# création d'un socket pour les échanges
		self.ctx = zmq.Context()
		self.socket = self.ctx.socket(zmq.ROUTER)
		self.socket.setsockopt(zmq.IDENTITY, self.client_id)
		self.socket.bind("tcp://*:%s"%self.PORT)
		
		# création du class exposer
		self.abc = self.KLASS(self.classexposer_id.decode(), "tcp://localhost:%s"%self.PORT, self.Abc())
		self.abc.start(False)

		# sleep pour être sûr que la connection soit établie
		time.sleep(0.1)

	def tearDown(self):
		self.abc.close()
		self.socket.close()
		self.ctx.term()
		time.sleep(0.1)

	def send_request(self, request):
		self.socket.send_multipart([self.classexposer_id, self.client_id, request.pack()])

	def whole_response(self, response):
		return [self.classexposer_id, self.client_id, response.pack()]
	
	def send_ping(self):
		request = Request("42", "hard_one", [56], {'c': 42})
		self.send_request(request)

	def response_ping(self):
		response = Response("42", [56,2,42])
		return self.whole_response(response)

	def send_hard_one(self):
		request = Request("43", "hard_one", [56], {'c': 42})
		self.send_request(request)

	def response_hard_one(self):
		response = Response("43", [56,2,42])
		return self.whole_response(response)

	def send_sleep(self, t, uuid="44"):
		request = Request(uuid, "sleep", [t])
		self.send_request(request)
		
	def response_sleep(self, t, uuid="44"):
		response = Response(uuid, t)
		return self.whole_response(response)
		

class ServiceTestCase(_ServiceTest, unittest.TestCase):

	KLASS = Service
	
	def test_basic(self):
		# test Abc.ping
		self.send_ping()
		msg = self.socket.recv_multipart()
		self.assertEqual(msg, self.response_ping())
		
		# test Abc.hard_one
		self.send_hard_one()
		msg = self.socket.recv_multipart()
		self.assertEqual(msg, self.response_hard_one())


class AsyncServiceTestCase(_ServiceTest, unittest.TestCase):
	KLASS = AsyncService

	def test_basic(self):
		self.abc.dynamic_workers = False
		# send sleep 1 sec and ping
		self.send_sleep(0.1)
		self.send_ping()
		# recv ping first
		msg = self.socket.recv_multipart()
		self.assertEqual(msg, self.response_ping())
		# then recv sleep
		msg = self.socket.recv_multipart()
		self.assertEqual(msg, self.response_sleep(0.1))

	def test_grow_workers(self):
		self.abc.dynamic_workers = True
		current_n_workers = len(self.abc._workers)
		# send pleins de sleeps
		for i in range(current_n_workers*4): self.send_sleep(0.3, "sleep-%s"%i)
		time.sleep(0.05)
		# on voit si le nombre de workers à augmenté
		self.assertGreaterEqual(len(self.abc._workers), current_n_workers*4)
		
if __name__ == '__main__':
    unittest.main()
