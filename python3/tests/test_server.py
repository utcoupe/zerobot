
import unittest

import time
import multiprocessing

from zerobot import *


#import logging; logging.basicConfig(level=0)

class BaseServerTestCase:
	PORT = 9000
	FRONTEND_PORT	= PORT + 1
	BACKEND_PORT	= PORT + 2
	LOG_PORT		= PORT + 3
	EV_PULLER		= PORT + 4
	EV_PUBLISHER	= PORT + 5
	
	class BasicClient(BaseClient):
		def _process(self, fd, _ev):
			self.msg = fd.recv_multipart()


	def setUp(self):
		def f():
			server = Server("tcp://*:%s"%self.FRONTEND_PORT,"tcp://*:%s"%self.BACKEND_PORT,
				"tcp://*:%s"%self.LOG_PORT, "tcp://*:%s"%self.EV_PULLER, "tcp://*:%s"%self.EV_PUBLISHER)
			server.start()
		self.p = multiprocessing.Process(target=f)
		self.p.daemon = True
		self.p.start()
		time.sleep(0.5)

	def tearDown(self):
		self.p.terminate()
		time.sleep(0.2)

class ServerTestCase(BaseServerTestCase, unittest.TestCase):
	
	def test_launch(self):
		pass

class BaseServerAndClientsTestCase(BaseServerTestCase):

	def setUp(self):
		client1 = self.BasicClient("Client-1", "tcp://*:%s"%self.FRONTEND_PORT,
						"tcp://*:%s"%self.EV_PUBLISHER)
		client2 = self.BasicClient("Client-2", "tcp://*:%s"%self.BACKEND_PORT,
						ev_push_addr="tcp://*:%s"%self.EV_PULLER)
		client3 = self.BasicClient("Client-3", "tcp://*:%s"%self.BACKEND_PORT)
		client1.start(False)
		client2.start(False)
		client3.start(False)
		self.client1 = client1
		self.client2 = client2
		self.client3 = client3
		super(BaseServerAndClientsTestCase, self).setUp()

	def tearDown(self):
		super(BaseServerAndClientsTestCase, self).tearDown()
		self.client1.close()
		self.client2.close()
		self.client3.close()
		del self.client1
		del self.client2
		del self.client3

class ServerAndClientsTestCase(BaseServerAndClientsTestCase, unittest.TestCase):
	
	def test_route(self):
		msg_content = b"coucou"
		client1 = self.client1
		client2 = self.client2
		client3 = self.client3

		# envoie d'un message
		client1.send_multipart([client2.identity.encode(), msg_content])

		# sleep
		time.sleep(0.05)

		# vérification de la réception
		self.assertTrue(hasattr(client2,'msg'))
		self.assertEqual([client1.identity.encode(), msg_content], client2.msg)
		self.assertFalse(hasattr(client1,'msg'))
		self.assertFalse(hasattr(client3,'msg'))

		# envoie d'un message dans l'autre sens
		client2.send_multipart([client1.identity.encode(), msg_content])

		# sleep
		time.sleep(0.05)

		# vérification de la reception
		self.assertTrue(hasattr(client1,'msg'))
		self.assertEqual([client2.identity.encode(), msg_content], client1.msg)


class BaseServerEventsTestCase(BaseServerAndClientsTestCase):

	def setUp(self):
		ctx = zmq.Context()
		logger = ctx.socket(zmq.SUB)
		logger.connect("tcp://localhost:%s"%self.LOG_PORT)
		logger.setsockopt(zmq.SUBSCRIBE, b"")
		self.logger = logger
		self.logger_ctx = ctx
		super(BaseServerEventsTestCase, self).setUp()

	def tearDown(self):
		super(BaseServerEventsTestCase, self).tearDown()
		self.logger.close()
		del self.logger
		del self.logger_ctx

class ServerEventsTestCase(BaseServerEventsTestCase, unittest.TestCase):
	
	def test_event(self):
		ev_key = "yo"
		ev_obj = ["coucou", "tout le monde"]
		client1 = self.client1
		client2 = self.client2
		logger = self.logger

		self.ev_recv = False
		# ecoute d'un event
		def cb(key, id_from, obj):
			self.ev_recv = True
			self.ev_key = key
			self.ev_id_from = id_from
			self.ev_obj = obj
		client1.add_callback(ev_key, cb)
		
		# envoie d'un event
		client2.send_event(ev_key, ev_obj)

		# sleep
		time.sleep(0.05)
		
		# vérification de la reception
		self.assertEqual(self.ev_recv, True)
		self.assertEqual(self.ev_key, ev_key)
		self.assertEqual(self.ev_id_from, client2.identity)
		self.assertEqual(self.ev_obj, ev_obj)

		# verification logger
		msg = logger.recv_multipart()
		self.assertEqual([client2.identity.encode(), ev_key.encode(), json.dumps(ev_obj).encode()], msg)

if __name__ == '__main__':
    unittest.main()
