
from .core import *

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

