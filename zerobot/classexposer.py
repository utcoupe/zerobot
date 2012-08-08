

from .core import *

import queue
import traceback
import inspect

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
		super(AsyncClassExposer,self).__init__(ctx)
		self.identity = identity
		self.exposed_obj = exposed_obj
		self.min_workers = min_workers or init_workers
		self.max_workers = max_workers
		self.dynamic_workers = dynamic_workers
		# socket recevant les requetes
		self.frontend = self.ctx.socket(zmq.DEALER)
		self.frontend.setsockopt(zmq.IDENTITY, self.identity.encode())
		self.conn_addr = conn_addr
		self.frontend.connect(self.conn_addr)
		# socket pour les workers
		self.backend = self.ctx.socket(zmq.ROUTER)
		self.backend_addr = "inproc://"+self.identity
		self.backend.bind(self.backend_addr)
		# workers
		self._workers = {}
		self._free_workers = []
		for _ in range(init_workers):
			self.add_worker()
		self._timeout_can_reduce_workers = 0
		#self.loop = FdLoop({self.backend: self.backend_handler, self.frontend: self.frontend_handler})
		# msg queue
		self._unprocess_msg = queue.deque()
		# fd handlers
		self.add_handler(self.backend, self.backend_handler, ioloop.IOLoop.READ)
		self.add_handler(self.frontend, self.frontend_handler, ioloop.IOLoop.READ)

	def add_worker(self):
		worker_id = "Worker-%s-%s" % (self.identity, uuid.uuid1())
		worker = ClassExposer(worker_id, self.backend_addr, self.exposed_obj, ctx=self.ctx)
		# démarage en mode non bloquant pour qu'ils soient dans des threads
		worker.start(False)
		self._free_workers.append(worker_id)
		self._workers[worker_id] = worker

	def backend_handler(self, fd, _ev):
		msg = fd.recv_multipart()
		self.logger.debug("backend recv %s", msg)
		worker_id, msg = msg[0], msg[1:]
		worker_id = worker_id.decode()
		self._free_workers.append(worker_id)
		self.consume_unprocess_msg()
		self.logger.debug("send to frontend %s",msg)
		self.frontend.send_multipart(msg)

	def consume_unprocess_msg(self):
		# ajouter des workers si on galère trop
		if self.dynamic_workers:
			n_workers = len(self._workers)
			n_free_workers = len(self._free_workers)
			if len(self._unprocess_msg) < n_free_workers//4 and time.time()>self._timeout_can_reduce_workers:
				if n_workers>5:
					max_to_remove = n_workers-5
					for i in range(min(max_to_remove, n_free_workers//4)):
						worker_id = self._free_workers.pop()
						self._workers[worker_id].stop()
						self._workers[worker_id] = None
						del self._workers[worker_id]
					self.logger.info("%s reduce to %s workers", self.identity, len(self._workers))
					self._timeout_can_reduce_workers = time.time()+10

		# envoyer le plus de messages possible aux workers
		while self._unprocess_msg and self._free_workers:
			msg = self._unprocess_msg.popleft()
			worker_id = self._free_workers.pop()
			self.send_to_worker(worker_id, msg)

		# retirer des workers si on en a trop
		if self.dynamic_workers:
			n_workers = len(self._workers)
			if self._unprocess_msg:
				if n_workers != self.max_workers:
					for i in range(len(self._workers), min(self.max_workers,2*n_workers)):
						self.add_worker()
					self._timeout_can_reduce_workers = time.time()+10
					self.logger.info("%s go to %s workers", self.identity, len(self._workers))
	
	def send_to_worker(self, worker_id, msg):
		new_msg = [worker_id.encode()]+msg
		self.logger.debug("send to backend %s"% new_msg)
		self.backend.send_multipart(new_msg)
			
	def frontend_handler(self, fd, _ev):
		#print('ClassExposer %s received: %s' % (self.identity, msg))
		msg = fd.recv_multipart()
		self.logger.debug("frontend recv %s", msg)
		self._unprocess_msg.append(msg)
		self.consume_unprocess_msg()
		return

	def help(self, method=None):
		"""
		Permet d'afficher de l'aide sur la classe exposée, utilise la doc python du code source.
		"""
		if not method:
			methods = inspect.getmembers(self.exposed_obj, predicate=inspect.ismethod)
			r =  map(lambda x: x[0], methods)
			r = list(filter(lambda x: not x.startswith('_'), r))
		else:
			r = dict(inspect.getfullargspec(getattr(self.exposed_obj,method))._asdict())
		return r

	def __repr__(self):
		return "AsyncClassExposer(%s,%s,%s,..)" % (self.identity, self.conn_addr, self.exposed_obj)
