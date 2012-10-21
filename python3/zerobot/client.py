
from .core import *


class Client(BaseClient):
	def __init__(self, identity, conn_addr, remote_id, ctx=None):
		super(Client, self).__init__(identity, conn_addr, ctx)
		self.remote_id = remote_id

	def start(self, block=False):
		super(Client, self).start(block)

	def close(self):
		self.stop()
		self.socket.close()
		if self._ctx_is_mine:
			self.ctx.term()

	def _uid(self):
		i = uuid.uuid1()
		return str(i)
	
	def _remote_call(self, fct, args=[], kwargs={}, cb_fct=None, uid=None, block=True, timeout=None):
		if uid is None: uid = self._uid()
		request = Request(uid, fct, args, kwargs)
		self.send_multipart([self.remote_id.encode(), request.pack()])
		msg = self.socket.recv_multipart()
		response = Response.unpack(msg[1])
		if response.error:
			raise ZeroBotException(response.error)
		return response.data
	
	def __getattr__(self, name):
		def auto_generated_remote_call(*args, block=True, timeout=None, cb_fct=None, uid=None, **kwargs):
			return self._remote_call(name, args, kwargs, cb_fct, uid, block, timeout)
		return auto_generated_remote_call
	
class AsyncClient(BaseClient):
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
		super(AsyncClient, self).__init__(identity, conn_addr, ctx)
		
		self.remote_id = remote_id
		self._resp_events = {}
		self._cb_push = self.ctx.socket(zmq.PUSH)
		self._cb_push.bind("ipc://%s-worker"%self.identity)
		self._cb_pull = self.ctx.socket(zmq.PULL)
		self._cb_pull.connect("ipc://%s-worker"%self.identity)
		self.add_handler(self._cb_pull, self._process_cb, ioloop.IOLoop.READ)
		self._to_close.append(self._cb_pull)
		self._to_close.append(self._cb_push)

	def _process_cb(self, fd, _ev):
		packed_response = fd.recv()
		response = Response.unpack(packed_response)
		self._process_response(response)
	
	def _uid(self):
		i = uuid.uuid1()
		return str(i)

	def _process(self, fd, _ev):
		msg = fd.recv_multipart()
		#print('AsyncClient %s received: %s' % (self.identity, msg))
		self._cb_push.send(msg[1])

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
				#print(resp_ev.response.error['tb'])
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

