
from .core import *

'''
class Proxy(Base):
	def __init__(self, identity, ctx=None, *, ft_conn_addr=None, ft_bind_addr=None, ft_type=zmq.DEALER, bc_bind_addr=None, bc_conn_addr=None, bc_type=zmq.DEALER):
		"""
		Interface de base pour les device avec entrée/sortie.
		Il est possible de choisir le type des sockets ainsi que le type de connection (connect/bind).
		@param {str} identity identité du proxy
		@param {zmq.Context} ctx context zmq
		@param {str|None} ft_conn_addr connect frontend
		@param {str|None} ft_bind_addr bind frontend
		@param {zmq.*|zmq.DEALER} ft_type type du socket frontend
		@param {str|None} bc_conn_addr connect backend
		@param {str|None} ft_bind_addr bind backend
		@param {zmq.*|zmq.DEALER} bc_type type du socket backend
		"""
		# si aucune adresse pour le socket frontend n'est précisée
		if not (ft_conn_addr or ft_bind_addr):
			raise Exception("ft_bind_addr or ft_conn_addr must be precised")
		# si les deux adresses sont précisées
		if ft_conn_addr and ft_bind_addr:
			raise Exception("you can't use ft_bind_addr and ft_conn_addr")
		# si aucune adresse pour le socket backend n'est précisée
		if not (bc_conn_addr or bc_bind_addr):
			raise Exception("bc_bind_addr or bc_conn_addr must be precised")
		# si les deux adresses sont précisées
		if bc_conn_addr and bc_bind_addr:
			raise Exception("you can't use bc_bind_addr and bc_conn_addr")
		# appel du constructeur parent
		super(Proxy, self).__init__(ctx)
		# sauvegarde de l'identité
		self.identity = identity
		# création ds sockets
		self.frontend = self.ctx.socket(ft_type)
		self.frontend.setsockopt(zmq.IDENTITY, self.identity.encode())
		self.backend = self.ctx.socket(bc_type)
		self.backend.setsockopt(zmq.IDENTITY, self.identity.encode())
		self._to_close.append(self.frontend)
		self._to_close.append(self.backend)
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
		self.add_handler(self.frontend, self._frontend_handler, ioloop.IOLoop.READ)
		self.add_handler(self.backend, self._backend_handler, ioloop.IOLoop.READ)

	def _frontend_process_msg(self, msg):
		"""
		Fonction pouvant être surchargée pur changer le comportement du proxy.
		Cette fonctione est appellée lorsque le socket frontend reçoit un message.
		Le résultat de la fonction est envoyé à la socket backend.
		"""
		return msg
		
	def _frontend_handler(self, fd, _ev):
		"""
		Fonction pouvant être surchargée pur changer le comportement du proxy.
		"""
		msg = fd.recv_multipart()
		new_msg = self._frontend_process_msg(msg)
		if new_msg:
			#print("ft send", new_msg)
			self.backend.send_multipart(new_msg)

	def _backend_process_msg(self, msg):
		"""
		Fonction pouvant être surchargée pur changer le comportement du proxy.
		Cette fonctione est appellée lorsque le socket backend reçoit un message.
		Le résultat de la fonction est envoyé à la socket frontend.
		"""
		return msg

	def _backend_handler(self, fd, _ev):
		"""
		Fonction pouvant être surchargée pur changer le comportement du proxy.
		"""
		msg = fd.recv_multipart()
		new_msg = self._backend_process_msg(msg)
		if new_msg:
			#print("bc send", new_msg)
			self.frontend.send_multipart(new_msg)


'''
class Proxy(Base):
	def __init__(self, identity, ctx=None, *, ft_conn_addr=None, ft_bind_addr=None, ft_type=zmq.DEALER, bc_bind_addr=None, bc_conn_addr=None, bc_type=zmq.DEALER):
		"""
		Interface de base pour les device avec entrée/sortie.
		Il est possible de choisir le type des sockets ainsi que le type de connection (connect/bind).
		@param {str} identity identité du proxy
		@param {zmq.Context} ctx context zmq
		@param {str|None} ft_conn_addr connect frontend
		@param {str|None} ft_bind_addr bind frontend
		@param {zmq.*|zmq.DEALER} ft_type type du socket frontend
		@param {str|None} bc_conn_addr connect backend
		@param {str|None} ft_bind_addr bind backend
		@param {zmq.*|zmq.DEALER} bc_type type du socket backend
		"""
		self.ctx = ctx or zmq.Context()
		self._ctx_is_mine = ctx is None
		self.logger = logging.getLogger(__name__+'.'+self.__class__.__name__)
		# si aucune adresse pour le socket frontend n'est précisée
		if not (ft_conn_addr or ft_bind_addr):
			raise Exception("ft_bind_addr or ft_conn_addr must be precised")
		# si les deux adresses sont précisées
		if ft_conn_addr and ft_bind_addr:
			raise Exception("you can't use ft_bind_addr and ft_conn_addr")
		# si aucune adresse pour le socket backend n'est précisée
		if not (bc_conn_addr or bc_bind_addr):
			raise Exception("bc_bind_addr or bc_conn_addr must be precised")
		# si les deux adresses sont précisées
		if bc_conn_addr and bc_bind_addr:
			raise Exception("you can't use bc_bind_addr and bc_conn_addr")
		# appel du constructeur parent
		super(Proxy, self).__init__(ctx)
		# sauvegarde de l'identité
		self.identity = identity
		# création ds sockets
		self.frontend = self.ctx.socket(ft_type)
		self.frontend.setsockopt(zmq.IDENTITY, self.identity.encode())
		self.backend = self.ctx.socket(bc_type)
		self.backend.setsockopt(zmq.IDENTITY, self.identity.encode())
		self._to_close.append(self.frontend)
		self._to_close.append(self.backend)
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

		self._e_stop = threading.Event()


	def stop(self):
		self._e_stop.set()
		super(Proxy, self).stop()
	
	def start(self, block=False):
		if not block:
			t = threading.Thread(target=self.start, args=(True,))
			t.setDaemon(True)
			t.start()
		else:
			backend,frontend = self.backend,self.frontend
			poller = zmq.Poller()
			poller.register(backend, zmq.POLLIN)
			poller.register(frontend, zmq.POLLIN)
			while not self._e_stop.is_set():
				try:
					items = dict(poller.poll(500))
				except:
					break # Interrupted
				
				if frontend in items:
					#msg = frontend.recv_multipart()
					#new_msg = self._frontend_process_msg(msg)
					#self.backend.send_multipart(new_msg)
					self._frontend_handler(frontend, items[frontend])
				if backend in items:
					#msg = backend.recv_multipart()
					#new_msg = self._backend_process_msg(msg)
					#self.frontend.send_multipart(new_msg)
					self._backend_handler(backend, items[backend])
				
	
	def _frontend_process_msg(self, msg):
		"""
		Fonction pouvant être surchargée pur changer le comportement du proxy.
		Cette fonctione est appellée lorsque le socket frontend reçoit un message.
		Le résultat de la fonction est envoyé à la socket backend.
		"""
		return msg
		
	def _frontend_handler(self, fd, _ev):
		"""
		Fonction pouvant être surchargée pour changer le comportement du proxy.
		"""
		msg = fd.recv_multipart()
		new_msg = self._frontend_process_msg(msg)
		if new_msg:
			#print("ft send", new_msg)
			self.backend.send_multipart(new_msg)

	def _backend_process_msg(self, msg):
		"""
		Fonction pouvant être surchargée pur changer le comportement du proxy.
		Cette fonctione est appellée lorsque le socket backend reçoit un message.
		Le résultat de la fonction est envoyé à la socket frontend.
		"""
		return msg

	def _backend_handler(self, fd, _ev):
		"""
		Fonction pouvant être surchargée pur changer le comportement du proxy.
		"""
		msg = fd.recv_multipart()
		new_msg = self._backend_process_msg(msg)
		if new_msg:
			#print("bc send", new_msg)
			self.frontend.send_multipart(new_msg)

