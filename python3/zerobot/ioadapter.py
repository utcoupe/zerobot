
from .core import *
import subprocess

class IOAdapter(BaseClient):
	"""
	Permet de faire le pont entre quelque chose derrière une interface io classique
	par exemple subprocess.stdin et subprocess.stdout, et le monde zmq.
	
	"""
	def __init__(self, identity, conn_addr, ctx=None):
		super(IOAdapter,self).__init__(identity, conn_addr, ctx)
		self._e_stop = threading.Event()
		self.t_read_loop = threading.Thread(target=self.read_loop, name="%s.read_loop"%self)
		self.t_read_loop.setDaemon(True)

	def start(self, block=True):
		self.t_read_loop.start()
		super(IOAdapter,self).start(block)

	def stop(self):
		self._e_stop.set()
		super(IOAdapter,self).stop()
	
	def read(self):
		""" Lecture de l'io """
		raise Exception("IOAdapter.read must be override")

	def process_sock_to_io(self, msg):
		""" Traitement du message venant de l'io vers le socket """
		return msg

	def write(self):
		""" Écriture de l'io """
		raise Exception("IOAdapter.write must be override")

	def process_io_to_sock(self, msg):
		""" Traitement du message venant du socket vers l'io """
		return msg
	
	def read_loop(self):
		while not self._e_stop.is_set():
			msg = self.read()
			msg = self.process_sock_to_io(msg)
			if isinstance(msg,list):
				self.send_multipart(msg)
			else:
				self.send(msg)

	def _process(self, fd, _ev):
		msg = fd.recv_multipart()
		msg = self.process_io_to_sock(msg)
		self.write(msg)

class SubProcessAdapter(IOAdapter):
	def __init__(self, identity, conn_addr, popen_args, ctx=None):
		super(SubProcessAdapter,self).__init__(identity, conn_addr, ctx)
		self.p = subprocess.Popen(popen_args, stdout=subprocess.PIPE, stdin=subprocess.PIPE)

	def read(self):
		msg = self.p.stdout.readline()
		return msg

	def write(self):
		self.p.stdin.write()

