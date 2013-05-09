
from .proxy import Proxy
import zmq

import logging
from zmq.eventloop import ioloop


class Server(Proxy):
	def __init__(self, ft_bind_addr="tcp://*:5000", bc_bind_addr="tcp://*:5001",
			pb_bind_addr="tcp://*:5002", ev_pl_bind_addr="tcp://*:5003", ev_pb_bind_addr="tcp://*:5004",
			ctx=None, identity="Server"):
		super(Server, self).__init__(identity, ft_bind_addr=ft_bind_addr, ft_type=zmq.ROUTER, bc_bind_addr=bc_bind_addr, bc_type=zmq.ROUTER, ctx=ctx)
		# création ds sockets
		self.publisher = self.ctx.socket(zmq.PUB)
		self.ev_puller = self.ctx.socket(zmq.ROUTER)
		self.ev_publisher = self.ctx.socket(zmq.PUB)
		# sauvegarde des adresses
		self._pb_addr = pb_bind_addr
		self._ev_pl_addr = ev_pl_bind_addr
		self._ev_pb_addr = ev_pb_bind_addr
		# binds
		self.publisher.bind(self._pb_addr)
		self.ev_puller.bind(self._ev_pl_addr)
		self.ev_publisher.bind(self._ev_pb_addr)
		self._to_close.append(self.publisher)
		self._to_close.append(self.ev_puller)
		self._to_close.append(self.ev_publisher)

	def create_poller(self):
		poller = super(Server, self).create_poller()
		poller.register(self.ev_puller, zmq.POLLIN)
		return poller
	
	def start(self, block=True):
		self.logger.info("Server start")
		self.logger.info("Listening\t%s", self._ft_addr)
		self.logger.info("Backend\t%s", self._bc_addr)
		self.logger.info("Publishing\t%s", self._pb_addr)
		self.logger.info("Event puller\t%s", self._ev_pl_addr)
		self.logger.info("Event publisher\t%s", self._ev_pb_addr)
		super(Server,self).start(block)

	def close(self):
		self.publisher.close()
		self.ev_puller.close()
		self.ev_publisher.close()
		super(Server,self).close()
	
	def _frontend_process_msg(self, msg):
		#print("frontend")
		self.publisher.send_multipart(msg)

		nb = len(msg)
		if nb ==2:
			id_from = msg[0]
			id_to = id_from.decode().split('-')[-1].encode()
			msg = msg[1]
		elif nb==3:
			id_from = msg[0]
			id_to = msg[1]
			msg = msg[2]
		elif nb==4:
			id_from = msg[0]
			id_to = msg[2]
			msg = msg[3]
		#print('Frontend received %s' % ((id_from, id_to, msg),))
		return [id_to,id_from,msg]

	def _backend_process_msg(self, msg):
		#print("backend")
		self.publisher.send_multipart(msg)
		id_from, id_to, msg = msg
		#print('Backend received %s' % ((id_from, id_to, msg),))
		return [id_to,id_from,msg]

	def _ev_puller_handler(self, fd, _ev):
		msg = fd.recv_multipart()
		#print("ev_puller")
		#print('Event puller received %s' % (msg,))
		self.publisher.send_multipart(msg)
		id_from, key_event, msg = msg
		self.ev_publisher.send_multipart([key_event, id_from, msg])
	
	def _process_poll_items(self, items):
		"""
		On surcharge cette fonction pour pouvoir recuperer les events
		sur ev_puller et les renvoyer sur ev_publisher.
		"""
		ev_puller = self.ev_puller
		if ev_puller in items:
			self._ev_puller_handler(ev_puller, items[ev_puller])
	
	def __repr__(self):
		return "Server(%s,%s,%s)"%(self._ft_addr, self._bc_addr, self._pb_addr)

