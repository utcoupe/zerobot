
from .core import *
from .proxy import Proxy

import queue
import traceback
import inspect

#signal.signal(signal.SIGINT, signal_handler)
class Service(BaseClient):
	"""
	Permet d'exposer les méthodes d'une classe à distance. Les requêtes sont
	traitées séquentiellement, pour un traitement de requêtes en parallèle
	voir :class:`zerobot.service.AsyncService`.
	
	*identity* string representant le nom unique du client
	
	*conn_addr* l'adresse du backend du serveur
	
	*exposed_obj* une instance de l'objet à exposer
	
	*ctx* zmq context
	
	"""
	def __init__(self, identity, conn_addr, exposed_obj, ctx=None):
		super(Service,self).__init__(identity, conn_addr, ctx)
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

	def help(self, f=None):
		"""
		Renvoie l'help pour le client ou pour la fonction *f* si précisée.
		"""
		if not f:
			# aide globale
			return dir(self.exposed_obj)
		else:
			if hasattr(self.exposed_obj, f):
				doc = getattr(self.exposed_obj,f).__doc__
				if not doc:
					doc = 'No documentation available'
				return doc
			else:
				return str(self.exposed_obj)+' has no method '+f
	
	def __repr__(self):
		return "ServiceWorker(%s,%s,%s,..)" % (self.identity, self.conn_addr, self.exposed_obj)
		

class AsyncService(Proxy):
	"""
	Permet d'exposer les méthodes d'une classe à distance. Permet en plus
	de lancer plusieurs méthodes bloquantes de la classe simultanément.
	Des workers sont utilisés, chaque worker exécute une requête<=>méthode de la class exposée.

	*identity* string representant le nom unique du client
	
	*conn_addr* l'adresse du backend du serveur
	
	*exposed_obj* une instance de l'objet à exposer
	
	*ctx* zmq context
	
	*init_workers* le nombre initial de workers <=> requêtes simultanées possibles
	
	*max_workers* nombre maximum de requêtes simultanées
	
	*min_workers* si non précisé est égale à init_workers
	
	*dynamic_workers* autorisé l'ajout/suppression de workers automatiquement
	"""
	def __init__(self, identity, conn_addr, exposed_obj, ctx=None,
			init_workers=5, max_workers=50, min_workers=None, dynamic_workers=False):
		# sauvegarde des adresses
		super(AsyncService, self).__init__(
			identity, ctx,
			ft_conn_addr=conn_addr,
			ft_type=zmq.DEALER,
			bc_bind_addr="inproc://workers-%s"%identity,
			bc_type=zmq.ROUTER
		)
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

	def _frontend_handler(self, fd, ev):
		# poll on frontend only if workers are available
		if len(self._free_workers) > 0:
			super(AsyncService, self)._frontend_handler(fd, ev)
			if self.dynamic_workers and len(self._free_workers) > 0:
				self.ungrow()
		elif self.dynamic_workers:
			self.grow()
	
	def grow(self):
		"""
		Si le client est en galere, des workers seront ajoutés, sinon
		ne fait rien.

		Fonction appellée en interne lorsque *dynamic_workers* veut True.
		"""
		n_workers = len(self._workers)
		if n_workers != self.max_workers:
			for i in range(n_workers, min(self.max_workers,2*n_workers)):
				self.add_worker()
			self._timeout_can_reduce_workers = time.time()+10
			self.logger.info("%s grows to %s workers", self.identity, len(self._workers))

	def ungrow(self):
		"""
		Si le client n'est pas très occupé, des workers seront retirés,
		sinon ne fait rien.
		
		Fonction appellée en interne lorsque *dynamic_workers* veut True.
		"""
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

	def close(self):
		self.logger.info("close event received")
		for worker in self._workers.values():
			self.logger.info("close %s" % worker)
			worker.close()
		super(AsyncService, self).close()
		self.logger.info("closed")
	
	def add_worker(self):
		""" Ajoute un worker au client. """
		worker_id = "Worker-%s-%s" % (self.identity, uuid.uuid1())
		worker = Service(worker_id, self._bc_addr, self.exposed_obj, ctx=self.ctx)
		# démarage en mode non bloquant pour qu'ils soient dans des threads
		worker.start(False)
		self._free_workers.append(worker_id)
		self._workers[worker_id] = worker

	def _backend_process_msg(self, msg):
		self.logger.debug("backend recv %s", msg)
		worker_id, msg = msg[0], msg[1:]
		worker_id = worker_id.decode()
		self._free_workers.append(worker_id)
		return msg
			
	def _frontend_process_msg(self, msg):
		#print('Service %s received: %s' % (self.identity, msg))
		self.logger.debug("frontend recv %s", msg)
		worker_id = self._free_workers.pop()
		return [worker_id.encode()]+msg

	def __repr__(self):
		return "AsyncService(%s,%s,%s,..)" % (self.identity, self._ft_addr, self.exposed_obj)
