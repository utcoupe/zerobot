
from .core import *


class Proxy(Base):
	def __init__(self, identity, ctx=None, *, ft_conn_addr=None, ft_bind_addr=None, ft_type=zmq.DEALER, bc_bind_addr=None, bc_conn_addr=None, bc_type=zmq.DEALER):
		if not (ft_conn_addr or ft_bind_addr):
			raise Exception("ft_bind_addr or ft_conn_addr must be precised")
		if not (bc_conn_addr or bc_bind_addr):
			raise Exception("bc_bind_addr or bc_conn_addr must be precised")
		super(Proxy, self).__init__(ctx)
		self.identity = identity
		# création ds sockets
		self.frontend = self.ctx.socket(ft_type)
		self.frontend.setsockopt(zmq.IDENTITY, self.identity.encode())
		self.backend = self.ctx.socket(bc_type)
		# sauvegarde des adresses
		self._ft_addr = ft_conn_addr if ft_conn_addr else ft_bind_addr
		self._bc_addr = bc_bind_addr if bc_bind_addr else bc_conn_addr
		# bind/connect
		if ft_conn_addr:
			self.frontend.connect(ft_conn_addr)
		else:
			self.frontend.bind(ft_bind_addr)
		if bc_conn_addr:
			self.backend.connect(bc_conn_addr)
		else:
			self.backend.bind(bc_bind_addr)
		# handlers
		self.add_handler(self.frontend, self.frontend_handler, ioloop.IOLoop.READ)
		self.add_handler(self.backend, self.backend_handler, ioloop.IOLoop.READ)

	def frontend_process_msg(self, msg):
		return msg
		
	def frontend_handler(self, fd, _ev):
		msg = fd.recv_multipart()
		new_msg = self.frontend_process_msg(msg)
		#print("ft send", msg)
		self.backend.send_multipart(msg)

	def backend_handler(self, fd, _ev):
		msg = fd.recv_multipart()
		new_msg = self.backend_process_msg(msg)
		#print("bc send", msg)
		self.frontend.send_multipart(msg)

	def backend_process_msg(self, msg):
		return msg
	
	def close(self, all_fds=False):
		super(Proxy, self).close(all_fds)
		if not all_fds:
			self.frontend.close()
			self.backend.close()
