

import unittest

from zerobot import *

import zmq
import time



from test_ioadapter import IOAdapterTest


class ArduinoAdapterTest(IOAdapterTest, unittest.TestCase):
	KLASS = ArduinoAdapter
	ARGS = (
		"/dev/ttyACM0",
		{'echo': ArduinoFunction("echo", 12345, "some doc", {"a": 42})}
	)
		
	def test_basic(self):
		server = self.server
		request = Request("42", "help", args=["echo",])
		server.send_multipart([
			self.ioadapter.identity.encode(),
			server.identity,
			request.pack()
		])

		time.sleep(0.05)
		
		msg = self.server.recv_multipart()
		response = Response("42", "some doc", None)
		self.assertEqual(msg,[self.ioadapter.identity.encode(), server.identity, response.pack()])


if __name__ == '__main__':
    unittest.main()
