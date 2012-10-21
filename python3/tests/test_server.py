
import unittest

import time

from zerobot import *


#import logging; logging.basicConfig(level=0)

class ServerTestCase(unittest.TestCase):
	FRONTEND_PORT	= 9000
	BACKEND_PORT	= 9001
	LOG_PORT		= 9002
	
	class BasicClient(BaseClient):
		def _process(self, fd, _ev):
			self.msg = fd.recv_multipart()

	def test_launch(self):
		server = Server("tcp://*:%s"%self.FRONTEND_PORT,"tcp://*:%s"%self.BACKEND_PORT,"tcp://*:%s"%self.LOG_PORT)
		server.start(False)
		time.sleep(0.5)
		server.close()
		time.sleep(0.1)

	def test_route(self):
		msg_content = b"coucou"
		# lancement du serveur
		server = Server("tcp://*:%s"%self.FRONTEND_PORT,"tcp://*:%s"%self.BACKEND_PORT,"tcp://*:%s"%self.LOG_PORT)
		server.start(False)
		# lancement des clients
		client1 = self.BasicClient("Client-1", "tcp://*:%s"%self.FRONTEND_PORT)
		client2 = self.BasicClient("Client-2", "tcp://*:%s"%self.BACKEND_PORT)
		client3 = self.BasicClient("Client-3", "tcp://*:%s"%self.BACKEND_PORT)
		client1.start(False)
		client2.start(False)
		client3.start(False)
		
		time.sleep(0.1)

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

		server.close()
		client1.close()
		client2.close()
		client3.close()
		time.sleep(0.1)

if __name__ == '__main__':
    unittest.main()
