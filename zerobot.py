import zmq
import zhelpers
import threading
import time
import random
import json
import inspect
import traceback
import uuid
import logging




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
		

class AsyncClient(threading.Thread):
	def __init__(self, identity, bind_addr, ctx=None):
		"""
		@param {str} identity identité du client
		@param {str} bind_addr adresse sur laquelle se connecter
		@param {zmq.Context} zmq context
		"""
		threading.Thread.__init__ (self)
		self.identity = identity
		self.ctx = ctx or zmq.Context()
		self._ctx_is_mine = ctx is None
		self.socket = self.ctx.socket(zmq.DEALER)
		self.socket.setsockopt(zmq.IDENTITY, self.identity.encode())
		self.socket.connect(bind_addr)
		#print('Client %s started' % (self.identity))
		self.setDaemon(True)
		self._e_stop = threading.Event()
		self.logger = logging.getLogger(__name__+'.'+self.__class__.__name__)

	def run(self):
		socket = self.socket
		poll = zmq.Poller()
		poll.register(socket, zmq.POLLIN)
		
		self.logger.info('%s started', self.identity)
		
		while not self._e_stop.is_set():
			try:
				sockets = dict(poll.poll(500))
			except zmq.core.error.ZMQError as ex:
				if not self._e_stop.is_set():
					self.logger.error("Client %s get an error on poll : %s", self.identity, ex)
			else:
				if socket in sockets:
					if sockets[socket] == zmq.POLLIN:
						msg = socket.recv_multipart()
						self._process(msg)
						del msg

		self.socket.close()
		if self._ctx_is_mine and not self.ctx.closed:
			self.ctx.term()

		self.logger.info("Client %s stopped", self.identity)

	def _process(self, msg):
		"""
		méthode appellée à chaque reception d'un message
		"""
		self.logger.warn("method AsyncClient._process must be override")
		
	def stop(self):
		self._e_stop.set()
	
class ClassExposer(AsyncClient):
	"""
	Permet d'exposer les méthodes d'une classe à distance.
	"""
	def __init__(self, identity, bind_addr, exposed_obj, ctx=None):
		"""
		@param {str} identity nom unique du client
		@param {str} bind_addr l'adresse du backend du serveur
		@param {Object} une instance de l'objet à exposer
		@param {zmq.Context} zmq context
		"""
		super(ClassExposer, self).__init__(identity, bind_addr, ctx)
		self.exposed_obj = exposed_obj

	def _process(self, msg):
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
		#print('ClassExposer %s received: %s' % (self.identity, msg))
		remote_id = msg[0]
		request = Request.unpack(msg[1])
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
		self.socket.send_multipart([remote_id, response.pack()])

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

class RemoteClient(AsyncClient):
	"""
	Permet de faire des appels à une classe distante
	"""
	def __init__(self, identity, bind_addr, remote_id, ctx=None):
		"""
		@param {str} identity
		@param {str} bind_addr adresse du frontend du serveur
		@param {str} remote_id identity du client distant
		@param {zmq.Context} zmq ctx
		"""
		super(RemoteClient, self).__init__(identity, bind_addr, ctx)
		self.remote_id = remote_id
		self._resp_events = {}

	def _uid(self):
		i = uuid.uuid1()
		return str(i)

	def _process(self, msg):
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
		self.socket.send_multipart([self.remote_id.encode(), request.pack()])
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


class Server(threading.Thread):
	def __init__(self, ft_bind_addr="tcp://*:5000", bc_bind_addr="tcp://*:5001", pb_bind_addr="tcp://*:5002", ctx=None):
		threading.Thread.__init__ (self)
		self.ctx = ctx or zmq.Context()
		self._ctx_is_mine = ctx is None
		self.frontend = self.ctx.socket(zmq.ROUTER)
		self.frontend.bind(ft_bind_addr)
		self.backend = self.ctx.socket(zmq.ROUTER)
		self.backend.bind(bc_bind_addr)
		self.publisher = self.ctx.socket(zmq.PUB)
		self.publisher.bind(pb_bind_addr)
		self.setDaemon(True)
		self._e_stop = threading.Event()
		self._ft_addr = ft_bind_addr
		self._bc_addr = bc_bind_addr
		self._pb_addr = pb_bind_addr
		self.logger = logging.getLogger(__name__+'.'+self.__class__.__name__)
	
	def run(self):
		
		frontend,backend,publisher = self.frontend,self.backend,self.publisher
		poll = zmq.Poller()
		poll.register(self.frontend, zmq.POLLIN)
		poll.register(self.backend, zmq.POLLIN)

		self.logger.info("Server ready")
		self.logger.info("Listening\t%s", self._ft_addr)
		self.logger.info("Backend\t%s", self._bc_addr)
		self.logger.info("Publishing\t%s", self._pb_addr)
		
		while not self._e_stop.is_set():
			try:
				sockets = dict(poll.poll(500))
			except zmq.core.error.ZMQError as ex:
				if not self._e_stop.is_set():
					self.logger.error("Server get an error on poll : %s", ex)
			else:
				if frontend in sockets:
					if sockets[frontend] == zmq.POLLIN:
						#print("frontend")
						#id_from, id_to, msg = zhelpers.dump(frontend)
						id_from, id_to, msg = frontend.recv_multipart()
						#print('Frontend received %s' % ((id_from, id_to, msg),))
						backend.send_multipart([id_to,id_from,msg])
						publisher.send_multipart([id_from,id_to,msg])
				if backend in sockets:
					if sockets[backend] == zmq.POLLIN:
						#print("backend")
						#id_from,id_to,msg = zhelpers.dump(backend)
						id_from,id_to,msg = backend.recv_multipart()
						#print('Backend received %s' % (msg,))
						frontend.send_multipart([id_to,id_from,msg])
						publisher.send_multipart([id_from,id_to,msg])
		
		frontend.close()
		backend.close()
		publisher.close()
		if self._ctx_is_mine and not self.ctx.closed:
			self.ctx.term()
		self.logger.info("Server stopped.")

	def stop(self):
		self._e_stop.set()


if __name__ == "__main__":

	logging.basicConfig(level=-1000)
	
	server = Server("tcp://*:8080","tcp://*:8081","tcp://*:8082")
	server.start()
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

	cool = ClassExposer("cool", "tcp://localhost:8081", Cool())
	cool.start()
	
	remote_cool = RemoteClient("remote_cool", "tcp://localhost:8080", "cool")
	remote_cool.start()

	time.sleep(0.5)

	while 1:
		print(remote_cool.ping(56,block=True))
		time.sleep(1)
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
