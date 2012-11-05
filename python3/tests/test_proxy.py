
import unittest


from zerobot import *

import time

class _ProxyTest:
	def socket_recv(self, s):
		time.sleep(0.05)
		msg = None
		try:
			msg = s.recv_multipart(zmq.NOBLOCK)
		except zmq.ZMQError:
			pass
		return msg
	
	def client_recv(self):
		return self.socket_recv(self.client)
		
	def server_recv(self):
		return self.socket_recv(self.server)
	
	def setUp(self):
		self.ctx = zmq.Context()
		# server
		self.server = self.ctx.socket(zmq.ROUTER)
		self.server.setsockopt(zmq.IDENTITY, b"server")
		self.server.bind("inproc://server")
		# proxy
		self.proxy = self.KLASS("proxy", ft_conn_addr="inproc://server", bc_bind_addr="inproc://proxy", ctx=self.ctx)
		self.proxy.start(False)
		# client
		self.client = self.ctx.socket(zmq.DEALER)
		self.client.setsockopt(zmq.IDENTITY, b"client")
		self.client.connect("inproc://proxy")
		time.sleep(0.1)

	def tearDown(self):
		self.proxy.close()
		self.server.close()
		self.client.close()
		self.ctx.term()
		time.sleep(0.1)

class ProxyTestCase(_ProxyTest):
	KLASS = Proxy
	
	def test_proxy(self):
		self.client.send_multipart([b"hello",b"world"])
		msg = self.server_recv()
		if not msg: self.fail("server doesn't received the msg")
		self.assertEqual(msg, [self.proxy.identity.encode(), b"hello", b"world"])

		self.server.send_multipart([b"proxy",b"bye",b"dude"])
		msg = self.client_recv()
		if not msg: self.fail("client doesn't received the msg")
		self.assertEqual(msg, [b"bye", b"dude"])

class RadioactivProxy(Proxy):
	def _frontend_process_msg(self, msg):
		return msg.append(b"<3 nuclear <3")

	def _backend_process_msg(self, msg):
		return msg.append(b"i'm a fool")

class ModifiedProxyTestCase(_ProxyTest):
	KLASS = RadioactivProxy
	
	def test_modified_proxy(self):
		self.client.send_multipart([b"hello",b"world"])
		msg = self.server_recv()
		if not msg: self.fail("server doesn't received the msg")
		self.assertEqual(msg, [self.proxy.identity.encode(), b"hello", b"world",b"i'm a fool"])

		self.server.send_multipart([b"proxy",b"bye",b"dude"])
		msg = self.client_recv()
		if not msg: self.fail("client doesn't received the msg")
		self.assertEqual(msg, [b"bye", b"dude", b"<3 nuclear <3"])
		
if __name__ == '__main__':
    unittest.main()
