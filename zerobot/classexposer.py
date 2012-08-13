
from .core import *
from .proxy import Proxy

import queue
import traceback
import inspect

#signal.signal(signal.SIGINT, signal_handler)
class ClassExposer(Client):
	"""
	Permet d'exposer les méthodes d'une classe à distance. Les requêtes sont
	traitées séquentiellement, pour un traitement de requêtes en parallèle
	voir la class AsyncClassExposer.
	"""
	def __init__(self, identity, conn_addr, exposed_obj, ctx=None):
		Client.__init__(self, identity, conn_addr, ctx)
		self.exposed_obj = exposed_obj

	def _process(self, fd, _ev):
		"""
		Le message reçu est en 2 parties :
		1. remote_id
		2. packed request
		
		Une Request est un dictionnaire:
		{@code
			{
				uid: 	{str} unique id qu'il faudra renvoyer
				fct:	{str} la fonction à appeller
				args:	{list} les arguments
				kwargs:	{dict} les arguments només
			}
		}
		La fonction va unpack le message et la request pour extraire la fonction à appeller.
		"""
		msg = fd.recv_multipart()
		self.logger.debug("worker %s recv %s", self.identity, msg)
		remote_id, packed_request = msg
		request = Request.unpack(packed_request)
		err = None
		r = None
		try:
			if request.fct=='help':
				f = self.help
			elif request.fct=='stop':
				f = self.stop
			else:
				f = getattr(self.exposed_obj, request.fct)
				if request.fct.startswith('_'):
					raise Exception("Method %s is protected" % request.fct)
			args,kwargs = request.args, request.kwargs
			if args and kwargs:
				r = f(*args, **kwargs)
			elif kwargs:
				r = f(**kwargs)
			else:
				r = f(*args)
		except Exception as ex:
			err = {}
			err['tb'] = traceback.format_exc()
			err['error'] = str(ex)
		response = Response(request.uid, r, err)
		self.send_multipart([remote_id, response.pack()])

	def __repr__(self):
		return "ClassExposerWorker(%s,%s,%s,..)" % (self.identity, self.conn_addr, self.exposed_obj)
		

class AsyncClassExposer(Base):
	"""
	Permet d'exposer les méthodes d'une classe à distance. Permet en plus
	de lancer plusieurs méthodes bloquantes de la classe simultanément.
	Des workers sont utilisés, chaque worker exécute une requête<=>méthode de la class exposée.
	"""
	def __init__(self, identity, conn_addr, exposed_obj, ctx=None, init_workers=5, max_workers=50, min_workers=None, dynamic_workers=False):
		"""
		@param {str} identity nom unique du client
		@param {str} conn_addr l'adresse du backend du serveur
		@param {Object} une instance de l'objet à exposer
		@param {zmq.Context} zmq context
		@param {int|5} init_workers le nombre initial de workers <=> requêtes simultanées possibles
		@param {int|50} max_workers nombre maximum de requêtes simultanées
		@param {int} min_workers si non précisé est égale à init_workers
		@param {bool|False} dynamic_workers autorisé l'ajout/suppression de workers automatiquement
		"""
		# zmq context
		self.ctx = ctx or zmq.Context()
		self._ctx_is_mine = ctx is None
		# sauvegarde de l'identité
		self.identity = identity
		# création ds sockets
		self.frontend = self.ctx.socket(zmq.DEALER)
		self.frontend.setsockopt(zmq.IDENTITY, self.identity.encode())
		self.backend = self.ctx.socket(zmq.ROUTER)
		self.backend.setsockopt(zmq.IDENTITY, self.identity.encode())
		# sauvegarde des adresses
		self._ft_addr = conn_addr
		self._bc_addr = "inproc://workers-%s"%self.identity
		# bind/connect
		self.frontend.connect(self._ft_addr)
		self.backend.bind(self._bc_addr)
		# poller
		self.poller = zmq.Poller()
		self.poller.register(self.frontend, zmq.POLLIN)
		self.poller.register(self.backend, zmq.POLLIN)
		#
		self.exposed_obj = exposed_obj
		self.min_workers = min_workers or init_workers
		self.max_workers = max_workers
		self.dynamic_workers = dynamic_workers
		# workers
		self._workers = {}
		self._free_workers = []
		for _ in range(init_workers):
			self.add_worker()
		self._timeout_can_reduce_workers = 0
		#self.loop = FdLoop({self.backend: self.backend_handler, self.frontend: self.frontend_handler})
		# events
		self._e_stop = threading.Event()
		# logger
		self.logger = logging.getLogger(__name__+'.'+self.__class__.__name__)
	
	def _loop(self):
		while not self._e_stop.is_set():
			frontend,backend = self.frontend,self.backend
			try:
				socks = dict(self.poller.poll())
			except Exception as ex:
				if not self._e_stop.is_set():
					self.logger.error(ex, exc_info=True)
				else: continue

			# Handle worker activity on backend
			if (backend in socks and socks[backend] == zmq.POLLIN):
				msg = backend.recv_multipart()
				new_msg = self.backend_process_msg(msg)
				if new_msg:
					self.logger.debug("send to frontend %s",msg)
					self.frontend.send_multipart(new_msg)
			
			# poll on frontend only if workers are available
			if len(self._free_workers) > 0:
				if (frontend in socks and socks[frontend] == zmq.POLLIN):
					msg = frontend.recv_multipart()
					new_msg = self.frontend_process_msg(msg)
					if new_msg:
						self.logger.debug("send to backend %s",msg)
						self.backend.send_multipart(new_msg)
				if self.dynamic_workers and len(self._free_workers) > 0:
					self.ungrow()
			elif self.dynamic_workers:
				self.grow()
			
	def grow(self):
		# ajouter des workers si on galère trop
		n_workers = len(self._workers)
		if n_workers != self.max_workers:
			for i in range(n_workers, min(self.max_workers,2*n_workers)):
				self.add_worker()
			self._timeout_can_reduce_workers = time.time()+10
			self.logger.info("%s grows to %s workers", self.identity, len(self._workers))

	def ungrow(self):
		# retirer des workers si on en a trop
		n_free_workers = len(self._free_workers)
		n_workers = len(self._workers)
		if n_workers > self.min_workers and n_free_workers > n_workers//2 and time.time()>self._timeout_can_reduce_workers:
			max_to_remove = n_workers-self.min_workers
			for i in range(min(max_to_remove, n_free_workers//2)):
				worker_id = self._free_workers.pop()
				self._workers[worker_id].stop()
				self._workers[worker_id] = None
				del self._workers[worker_id]
			self.logger.info("%s ungrows %s workers", self.identity,len(self._workers))
			self._timeout_can_reduce_workers = time.time()+10
	
	def start(self, block=True):
		self.logger.info("%s started", self)
		if block:
			self._loop()
		else:
			t = threading.Thread(target=self._loop,name="%s._loop"%self)
			t.setDaemon(True)
			t.start()

	def stop(self):
		self.logger.info("stop event received")
		self._e_stop.set()

	def close(self):
		self.logger.info("close event received")
		self.stop()
		for worker in self._workers.values():
			worker.close()
		self.frontend.close()
		self.backend.close()
		if self._ctx_is_mine:
			self.ctx.term()
		self.logger.info("closed")
	
	def add_worker(self):
		worker_id = "Worker-%s-%s" % (self.identity, uuid.uuid1())
		worker = ClassExposer(worker_id, self._bc_addr, self.exposed_obj, ctx=self.ctx)
		# démarage en mode non bloquant pour qu'ils soient dans des threads
		worker.start(False)
		self._free_workers.append(worker_id)
		self._workers[worker_id] = worker

	def backend_process_msg(self, msg):
		self.logger.debug("backend recv %s", msg)
		worker_id, msg = msg[0], msg[1:]
		worker_id = worker_id.decode()
		self._free_workers.append(worker_id)
		return msg
			
	def frontend_process_msg(self, msg):
		#print('ClassExposer %s received: %s' % (self.identity, msg))
		self.logger.debug("frontend recv %s", msg)
		worker_id = self._free_workers.pop()
		return [worker_id.encode()]+msg

	def __repr__(self):
		return "AsyncClassExposer(%s,%s,%s,..)" % (self.identity, self._ft_addr, self.exposed_obj)
