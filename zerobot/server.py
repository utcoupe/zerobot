
from .core import Base
import zmq
import zhelpers

import logging
from zmq.eventloop import ioloop


class Server(Base):
	def __init__(self, ft_bind_addr="tcp://*:5000", bc_bind_addr="tcp://*:5001", pb_bind_addr="tcp://*:5002", ctx=None, identity="Server"):
		super(Server, self).__init__(identity, ctx)
		# création ds sockets
		self.frontend = self.ctx.socket(zmq.ROUTER)
		self.backend = self.ctx.socket(zmq.ROUTER)
		self.publisher = self.ctx.socket(zmq.PUB)
		# sauvegarde des adresses
		self._ft_addr = ft_bind_addr
		self._bc_addr = bc_bind_addr
		self._pb_addr = pb_bind_addr
		# binds
		self.frontend.bind(self._ft_addr)
		self.backend.bind(self._bc_addr)
		self.publisher.bind(self._pb_addr)
		# handlers
		self.add_handler(self.frontend, self.frontend_handler, ioloop.IOLoop.READ)
		self.add_handler(self.backend, self.backend_handler, ioloop.IOLoop.READ)

	def start(self, block=False):
		self.logger.info("Server start")
		self.logger.info("Listening\t%s", self._ft_addr)
		self.logger.info("Backend\t%s", self._bc_addr)
		self.logger.info("Publishing\t%s", self._pb_addr)
		super(Server,self).start(block)
	
	def frontend_handler(self, _fd, _ev):
		#print("frontend")
		#id_from, id_to, msg = zhelpers.dump(frontend)
		id_from, id_to, msg = self.frontend.recv_multipart()
		#print('Frontend received %s' % ((id_from, id_to, msg),))
		self.backend.send_multipart([id_to,id_from,msg])
		self.publisher.send_multipart([id_from,id_to,msg])

	def backend_handler(self, _fd, _ev):
		#print("backend")
		#id_from, id_to, msg = zhelpers.dump(backend)
		id_from, id_to, msg = self.backend.recv_multipart()
		#print('Backend received %s' % (msg,))
		self.frontend.send_multipart([id_to,id_from,msg])
		self.publisher.send_multipart([id_from,id_to,msg])
	
	def close(self, all_fds=False):
		super(Server, self).close(all_fds)
		if not all_fds:
			self.frontend.close()
			self.backend.close()
		self.publisher.close()

	def __repr__(self):
		return "Server(%s,%s,%s)"%(self._ft_addr, self._bc_addr, self._pb_addr)
