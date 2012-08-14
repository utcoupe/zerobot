
from .proxy import Proxy
import zmq
import zhelpers

import logging
from zmq.eventloop import ioloop


class Server(Proxy):
	def __init__(self, ft_bind_addr="tcp://*:5000", bc_bind_addr="tcp://*:5001", pb_bind_addr="tcp://*:5002", ctx=None, identity="Server"):
		super(Server, self).__init__(identity, ft_bind_addr=ft_bind_addr, ft_type=zmq.ROUTER, bc_bind_addr=bc_bind_addr, bc_type=zmq.ROUTER, ctx=ctx)
		# création ds sockets
		self.publisher = self.ctx.socket(zmq.PUB)
		# sauvegarde des adresses
		self._pb_addr = pb_bind_addr
		# binds
		self.publisher.bind(self._pb_addr)
		self._to_close.append(self.publisher)

	def start(self, block=False):
		self.logger.info("Server start")
		self.logger.info("Listening\t%s", self._ft_addr)
		self.logger.info("Backend\t%s", self._bc_addr)
		self.logger.info("Publishing\t%s", self._pb_addr)
		super(Server,self).start(block)
	
	def frontend_process_msg(self, msg):
		#print("frontend")
		self.publisher.send_multipart(msg)
		id_from, id_to, msg = msg
		#print('Frontend received %s' % ((id_from, id_to, msg),))
		return [id_to,id_from,msg]

	def backend_process_msg(self, msg):
		#print("backend")
		self.publisher.send_multipart(msg)
		id_from, id_to, msg = msg
		#print('Backend received %s' % ((id_from, id_to, msg),))
		return [id_to,id_from,msg]

	def __repr__(self):
		return "Server(%s,%s,%s)"%(self._ft_addr, self._bc_addr, self._pb_addr)

