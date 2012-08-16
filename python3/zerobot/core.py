import zmq
import json
import uuid
import threading
import time
import logging
from zmq.eventloop import ioloop

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
		return "%s(%s,%s,%s,%s)" % (self.__class__.__name__, self.uid, self.fct, self.args, self.kwargs)

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
		return "%s(%s,%s,%s)" % (self.__class__.__name__, self.uid, self.data, self.error)

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
	def __init__(self, ctx=None):
		ioloop.IOLoop.__init__(self)
		self.ctx = ctx or zmq.Context()
		self._ctx_is_mine = ctx is None
		self.logger = logging.getLogger(__name__+'.'+self.__class__.__name__)
		self._to_close = []

	def start(self, block=True):
		self.logger.info("%s started", self)
		if block:
			super(Base,self).start()
		else:
			t = threading.Thread(target=super(Base,self).start, name="Thread-%s"%self)
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
		time.sleep(0.05)
		if not all_fds:
			for sock in self._to_close:
				sock.close()
		if self._ctx_is_mine:
			self.ctx.term()
		self.logger.info("closed")

	def __repr__(self):
		return "%s(..)" % (self.__class__.__name__, )

class BaseClient(Base):
	def __init__(self, identity, conn_addr, ctx=None):
		"""
		@param {str} identity identité du client
		@param {str} conn_addr adresse sur laquelle se connecter
		@param {zmq.Context} zmq context
		"""
		super(BaseClient, self).__init__(ctx)
		self.identity = identity
		self.conn_addr = conn_addr
		self.socket = self.ctx.socket(zmq.DEALER)
		self.socket.setsockopt(zmq.IDENTITY, self.identity.encode())
		self.socket.connect(conn_addr)
		self.add_handler(self.socket, self._process, ioloop.IOLoop.READ)
		self._to_close.append(self.socket)

	def _process(self, fd, ev):
		raise Exception("BaseClient._process must be override")

	def send_multipart(self, msg):
		self.socket.send_multipart(msg)

	def send(self, msg):
		self.socket.send(msg)

	def __repr__(self):
		return "%s(%s,%s,..)" % (self.__class__.__name__, self.identity, self.conn_addr)


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
