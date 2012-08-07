import zmq
from zmq.eventloop import ioloop
import zhelpers
import threading
import time
import random
import json
import inspect
import traceback
import uuid
import logging
import queue



class ZeroBotException(Exception):
	def __init__(self, err):
		Exception.__init__(self, err['error'])
		self.tb = err['tb']

class ZeroBotTimeout(Exception):
	pass


class Request:
	def __init__(self, uid, fct, args=[], kwargs={}):
		self.uid = uid
		self.fct = fct
		self.args = args
		self.kwargs = kwargs

	def pack(self):
		#print('Request.pack')
		msg = {}
		msg['uid'] = self.uid
		msg['fct'] = self.fct
		msg['args'] = self.args
		msg['kwargs'] = self.kwargs
		#print(msg)
		return json.dumps(msg).encode()

	@staticmethod
	def unpack(msg):
		#print('Request.unpack', msg)
		d = json.loads(msg.decode())
		return Request(**d)

	def __eq__(self, o):
		return self.uid == o.uid and self.fct == o.fct and self.args == o.args and self.kwargs == o.kwargs

	def __repr__(self):
		return "Request(%s,%s,%s,%s)" % (self.uid, self.fct, self.args, self.kwargs)

class Response:
	def __init__(self, uid, data, error=None):
		self.uid = uid
		self.data = data
		self.error = error

	def pack(self):
		#print('Response.pack')
		msg = {}
		msg['uid'] = self.uid
		msg['data'] = self.data
		msg['error'] = self.error
		#print(msg)
		return json.dumps(msg).encode()

	def error_is_set(self):
		return bool(self.error)

	@staticmethod
	def unpack(msg):
		#print('Response.unpack', msg)
		d = json.loads(msg.decode())
		return Response(**d)

	def __eq__(self, o):
		return self.uid == o.uid and self.data == self.data and self.error == self.error

	def __repr__(self):
		return "Response(%s,%s,%s)" % (self.uid, self.data, self.error)

class ResponseEvent:
	def __init__(self, cb_fct=None):
		self._ev = threading.Event()
		self.response = None
		self.cb_fct = cb_fct

	def _nonblocking_set(self, response):
		t = threading.Thread(target=self.set, args=(response,True))
		t.setDaemon(True)
		t.start()
	
	def set(self, response, block=False):
		if block:
			self.response = response
			if self.cb_fct:
				self.cb_fct(response)
			self._ev.set()
		else:
			self._nonblocking_set(response)

	def wait(self, timeout=None):
		self._ev.wait(timeout)

	def is_set(self):
		return self._ev.is_set()

class Base(ioloop.IOLoop):
	def __init__(self, identity, ctx=None):
		ioloop.IOLoop.__init__(self)
		self.identity = identity
		self.ctx = ctx or zmq.Context()
		self._ctx_is_mine = ctx is None
		self.logger = logging.getLogger(__name__+'.'+self.__class__.__name__)

	def start(self, block=True):
		self.logger.info("%s started", self.identity)
		if block:
			super(Base,self).start()
		else:
			t = threading.Thread(target=super(Base,self).start, name=self.identity)
			t.setDaemon(True)
			t.start()

	def stop(self):
		self.logger.info("stop event received")
		super(Base,self).stop()

	def close(self, all_fds=False):
		self.stop()
		self.logger.info("close event received")
		time.sleep(0.05)
		super(Base,self).close(all_fds)

class Client(Base):
	def __init__(self, identity, conn_addr, ctx=None):
		"""
		@param {str} identity identité du client
		@param {str} conn_addr adresse sur laquelle se connecter
		@param {zmq.Context} zmq context
		"""
		super(Client, self).__init__(identity, ctx)
		self.conn_addr = conn_addr
		self.socket = self.ctx.socket(zmq.DEALER)
		self.socket.setsockopt(zmq.IDENTITY, self.identity.encode())
		self.socket.connect(conn_addr)
		self.add_handler(self.socket, self._process, ioloop.IOLoop.READ)

	def close(self, all_fds=False):
		super(Client, self).close(all_fds)
		if not all_fds:
			self.socket.close()

	def _process(self, fd, ev):
		self.logger.warn("Client._process must be override")

	def send_multipart(self, msg):
		self.socket.send_multipart(msg)

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
		

class FdLoop:
	def __init__(self, d_fd_n_cb):
		self.poll = zmq.Poller()
		self._e_stop = threading.Event()
		self._e_start = threading.Event()
		self._fd_handlers = d_fd_n_cb
		self.logger = logging.getLogger(__name__+'.'+self.__class__.__name__)
		self._exit = False
		t = threading.Thread(target=self.loop)
		t.setDaemon(True)
		t.start()

	@property
	def running(self):
		return self._e_start.is_set()
	
	def start(self):
		if not self.running:
			self._e_start.set()
			self._e_stop.clear()
			for fd in self._fd_handlers:
				self.poll.register(fd, zmq.POLLIN)

	def stop(self):
		if self.running:
			self._e_stop.set()
			self._e_start.clear()
			for fd,_cb in self.fd_n_cb:
				self.poll.unregister(fd)

	def exit(self):
		self.stop()
		self._exit = True
	
	def loop(self):
		while not self._exit:
			self._e_start.wait()
			while not self._e_stop.is_set():
				try:
					sockets = dict(self.poll.poll(500))
				except zmq.core.error.ZMQError as ex:
					if not self._e_stop.is_set():
						self.logger.error("Error on poll : %s", ex, exc_info=1)
				else:
					for fd in sockets:
						self._fd_handlers[fd](fd, sockets[fd])

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
		super(AsyncClassExposer,self).__init__(identity, ctx)
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
		return "ClassExposer(%s,%s,%s,..)" % (self.identity, self.conn_addr, self.exposed_obj)

class RemoteClient(Client):
	"""
	Permet de faire des appels à une classe distante
	"""
	def __init__(self, identity, conn_addr, remote_id, ctx=None):
		"""
		@param {str} identity
		@param {str} bind_addr adresse du frontend du serveur
		@param {str} remote_id identity du client distant
		@param {zmq.Context} zmq ctx
		"""
		super(RemoteClient, self).__init__(identity, conn_addr, ctx)
		self.remote_id = remote_id
		self._resp_events = {}

	def _uid(self):
		i = uuid.uuid1()
		return str(i)

	def _process(self, fd, _ev):
		msg = fd.recv_multipart()
		#print('RemoteClient %s received: %s' % (self.identity, msg))
		response = Response.unpack(msg[1])
		self._process_response(response)

	def _process_response(self, response):
		if response.uid in self._resp_events:
			self._resp_events[response.uid].set(response)
			self._resp_events.pop(response.uid)
	
	def _remote_call(self, fct, args=[], kwargs={}, cb_fct=None, uid=None, block=True, timeout=None):
		if uid is None: uid = self._uid()
		resp_ev = ResponseEvent()
		if cb_fct:
			resp_ev.cb_fct = cb_fct
		self._resp_events[uid] = resp_ev
		request = Request(uid, fct, args, kwargs)
		self.send_multipart([self.remote_id.encode(), request.pack()])
		if block:
			resp_ev.wait(timeout)
			if not resp_ev.is_set():
				raise ZeroBotTimeout("Timeout")
			if resp_ev.response.error:
				raise ZeroBotException(resp_ev.response.error)
			return resp_ev.response.data
		else:
			if timeout:
				self._set_async_timeout(uid, timeout)
			return resp_ev

	def _set_async_timeout(self, uuid, timeout):
		t = threading.Timer(timeout, self._async_timeout, args=(uuid, timeout))
		t.setDaemon(True)
		t.start()
	
	def _async_timeout(self, uuid, timeout):
		response = Response(uuid, {}, {'error': 'timeout', 'tb':''})
		self._process_response(response)
	
	def __getattr__(self, name):
		def auto_generated_remote_call(*args, block=True, timeout=None, cb_fct=None, uid=None, **kwargs):
			return self._remote_call(name, args, kwargs, cb_fct, uid, block, timeout)
		return auto_generated_remote_call


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
		self.logger.info("Server will start soon,")
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

if __name__ == "__main__":

	import sys

	log_lvl = int(sys.argv[1]) if len(sys.argv) >= 2 else 20

	logging.basicConfig(level=log_lvl)
	
	server = Server("tcp://*:8080","tcp://*:8081","tcp://*:8082")
	server.start(False)
	time.sleep(1)
	
	class Cool:
		def ping(self, num):
			return num+42

		def hello(self):
			return "world"

		def test(self, a=3, b=4, c=5):
			return a,b,c

		def echo(self, m):
			return m

	cool = AsyncClassExposer("cool", "tcp://localhost:8081", Cool())
	cool.start(False)
	
	remote_cool = RemoteClient("remote_cool", "tcp://localhost:8080", "cool")
	remote_cool.start(False)

	time.sleep(0.5)

	try:
		while 1:
			print(remote_cool.ping(56,block=True))
			time.sleep(1)
	except KeyboardInterrupt:
		remote_cool.stop()
		cool.stop()
		server.stop()
		time.sleep(0.2)
	"""
	print(remote_cool.ping(56,block=True))
	print(remote_cool.ping(56,block=True))
	print(remote_cool.help(block=True))
	print(remote_cool.help('hello',block=True))
	print(remote_cool.hello(block=True))
	print(remote_cool.test(c=10,block=True))
	try:
		print(remote_cool._cou())
	except ZeroBotException as ex:
		print(ex)
	"""
