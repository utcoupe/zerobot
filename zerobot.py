import zmq
import zhelpers
import threading
import time
import random
import json
import inspect
import traceback
import uuid

class ZeroBotException(Exception):
	def __init__(self, err):
		Exception.__init__(self, err['error'])
		self.tb = err['tb']

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

	@staticmethod
	def unpack(msg):
		#print('Response.unpack', msg)
		d = json.loads(msg.decode())
		return Response(**d)

class ResponseEvent:
	def __init__(self, cb_fct=None):
		self._ev = threading.Event()
		self.response = None
		self.cb_fct = cb_fct
		
	def set(self, response):
		self.response = response
		self._ev.set()
		if self.cb_fct:
			self.cb_fct(response)

	def wait(self, timeout=None):
		self._ev.wait(timeout)

	def is_set(self):
		return self._ev.is_set()
		

class AsyncClient(threading.Thread):
	def __init__(self, identity, bind_addr, ctx=None):
		threading.Thread.__init__ (self)
		self.identity = identity
		self.ctx = ctx or zmq.Context()
		self.socket = self.ctx.socket(zmq.DEALER)
		self.socket.setsockopt(zmq.IDENTITY, self.identity.encode())
		self.socket.connect(bind_addr)
		print('Client %s started' % (self.identity))
		self.setDaemon(True)
		self._e_stop = threading.Event()

	def run(self):
		while not self._e_stop.is_set():
			msg = self.socket.recv_multipart()
			self._process(msg)
			del msg
		self.socket.close()
		self.ctx.term()

	def _process(self, msg):
		print('Client %s received %s' % (self.identity, msg))
		
	def stop(self):
		self._e_stop.set()
	
class ClassExposer(AsyncClient):
	"""
	Permet d'exposer les méthodes d'une classe à distance.
	"""
	def __init__(self, identity, bind_addr, exposed_obj, ctx=None):
		super(ClassExposer, self).__init__(identity, bind_addr, ctx)
		self.exposed_obj = exposed_obj

	def _process(self, msg):
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
		super(RemoteClient, self).__init__(identity, bind_addr, ctx)
		self.remote_id = remote_id
		self._resp_events = {}

	def _uid(self):
		i = uuid.uuid1()
		return str(i)

	def _process(self, msg):
		#print('RemoteClient %s received: %s' % (self.identity, msg))
		response = Response.unpack(msg[1])
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
				raise Exception("Timeout")
			if resp_ev.response.error:
				raise ZeroBotException(resp_ev.response.error)
			return resp_ev.response.data

	def __getattr__(self, name):
		def auto_generated_remote_call(*args, block=True, timeout=None, cb_fct=None, uid=None, **kwargs):
			return self._remote_call(name, args, kwargs, cb_fct, uid, block, timeout)
		return auto_generated_remote_call


class Server(threading.Thread):
	def __init__(self, ft_bind_addr, bc_bind_addr, pb_bind_addr):
		threading.Thread.__init__ (self)
		self.ctx = zmq.Context()
		self.frontend = self.ctx.socket(zmq.ROUTER)
		self.frontend.bind(ft_bind_addr)
		self.backend = self.ctx.socket(zmq.ROUTER)
		self.backend.bind(bc_bind_addr)
		self.publisher = self.ctx.socket(zmq.PUB)
		self.publisher.bind(pb_bind_addr)
		self.setDaemon(True)
		self._e_stop = threading.Event()
	
	def run(self):
		
		frontend,backend,publisher = self.frontend,self.backend,self.publisher
		poll = zmq.Poller()
		poll.register(self.frontend, zmq.POLLIN)
		poll.register(self.backend, zmq.POLLIN)
		
		while not self._e_stop.is_set():
			sockets = dict(poll.poll())
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
		self.ctx.term()

	def stop(self):
		self._e_stop.set()


if __name__ == "__main__":
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
	"""print(remote_cool.ping(56,block=True))
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
	
	"""
	import sys
	N,N_REQ,LEN_MSG,ASYNC = sys.argv[1:]
	N = int(N)
	N_REQ = int(N_REQ)
	LEN_MSG = int(LEN_MSG)
	MSG="1"*LEN_MSG
	ctx = zmq.Context()

	remotes = []
	for i in range(N):
		c = RemoteClient("remote_cool-%s"%i, "tcp://localhost:8080", "cool", ctx=ctx)
		c.start()
		remotes.append(c)
	time.sleep(0.5)
	
	class Cb:
		def __init__(self):
			self.n = 0
			self.event = threading.Event()
		def cb(self, response):
			self.n += 1
			if self.n == N_REQ: self.event.set()
	
	def benchmark(i,c):

		cb = Cb()
		block = ASYNC != 'async'

		start=time.time()
		for _ in range(N_REQ):
			c.test(c=1,b=2,a=3, block=block, cb_fct=cb.cb)
		
		if not block:
			cb.event.wait(0.002*N*N_REQ)
			if not cb.event.is_set():
				print("#%s drops %s packets" % (i, N_REQ-cb.n))

	threads = []
	for i in range(N):
		t = threading.Thread(target=benchmark, args=(i,remotes[i],))
		threads.append(t)
	
	start = time.time()
	for i in range(N):
		threads[i].start()
	
	for i in range(N):
		threads[i].join()
	ellapsed = time.time()-start
	tot_reqs = N*N_REQ
	average = ellapsed/tot_reqs
	print('%s clients, %s reqs (tot:%sreqs) : %ss, average : %sms' % (N, N_REQ, tot_reqs, ellapsed, average*1000))
	
	#time.sleep(3)
	#remote_cool.stop()
	cool.stop()
	server.stop()
	"""
	server.join()
