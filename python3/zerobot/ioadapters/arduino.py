from collections import OrderedDict
import traceback

from ..ioadapter import *
from ..core import *


import logging
logger = logging.getLogger(__name__)

class ArduinoFunction:
	SEPARATOR = '+'
	
	def __init__(self, name, arduino_id, doc, args):
		"""
		@param {str} name
		@param {int} arduino_id id de la fonction cote arduino
		@param {str} doc
		@param {OrderedDict} args
		"""
		self.name = name
		self.arduino_id = arduino_id
		self.__doc__ = doc
		self.args = args

	def compute_params(self, *args, **kwargs):
		if len(args) > len(self.args):
			raise TypeError("%s takes exactly %d positional argument (%d given)" % (self.name, len(self.args), len(args)))

		args = list(args)
		
		params = OrderedDict(self.args)
		args.extend([None]*(len(self.args)-len(args)))
		for kparam,arg in zip(params,args):
			if arg is not None:
				params[kparam] = arg
		
		for k,v in kwargs.items():
			if k not in params:
				raise TypeError("%s got an unexpected keyword argument '%s'" % (self.name, k))
			params[k] = v

		for k,v in params.items():
			if v is None:
				raise TypeError("%s needs argument'%s'" % (self.name, k))
		
		return tuple(map(lambda x: int(x), params.values()))

	def encode_call(self, uid, params):
		"""
			    name   | size(bits) |  start   |  end  
			===========|============|==========|=======
			 uid       |     16     |     0    |   16
			 id_cmd    |      8     |    16    |   24
			 nb_args   |      8     |    24    |   32
			 arg0      |     16     |    32    |   48
			 arg1      |     16     |    48    |   64
			 ..        |     ..     |    ..    |   ..
			 argN      |     16     | 32+16*N  | 32+16*(N+1)
		"""
		b = b''
		b += uid.to_bytes(2, 'little')
		b += self.arduino_id.to_bytes(1, 'little')
		b += len(params).to_bytes(1, 'little')
		for p in params:
			b += p.to_bytes(2, 'little', signed=True)
		return b
	
	def __call__(self, uid, *args, **kwargs):
		params = self.compute_params(*args, **kwargs)
		encoded_call = self.encode_call(uid, params)
		return encoded_call
	
	def __repr__(self):
		params = ','.join([
			'{k}={v}'.format(k=k, v=v) if v is not None else k
			for k,v in self.args.items()
		])
		return "{name}({params})".format(name=self.name, params=params)

class ArduinoAdapter(IOAdapter):
	def __init__(self, identity, conn_addr, serial, functions={}, event_keys={}, *, max_id=10000, **kwargs):
		super(ArduinoAdapter, self).__init__(identity, conn_addr, **kwargs)
		self.serial = serial
		self.free_ids = list(range(max_id))
		self.requests = {}
		self.functions = functions
		self.event_keys = event_keys

	def read(self):
		"""
			    name   | size(bits) 
			===========|============
			 uid       |     16
			 type      |      8
			 nb_args   |      8
			 arg0      |     16
			 arg1      |     16     
			 ..        |     ..
			 argN      |     16
		"""
		while not self.serial:
			time.sleep(1)
		try:
			# uid
			b = self.serial.read(2)
			uid = int.from_bytes(b, 'little')
			logger.debug("uid %s %s", b, uid)
			# type
			b = self.serial.read(1)
			t = int.from_bytes(b, 'little')
			logger.debug("type %s %s", b, t)
			# nb args
			b = self.serial.read(1)
			nb_args = int.from_bytes(b, 'little')
			logger.debug("nb_args %s %s", b, nb_args)
			args = []
			for i in range(nb_args):
				b = self.serial.read(2)
				a = int.from_bytes(b, 'little', signed=True)
				logger.debug("barg%s %s %s", i, b, a)
				args.append(a)
			logger.info("read : uid=%s, t=%s, nb_args=%s, args=%s", uid, t, nb_args, args)
			return uid, t, args
		except Exception as ex:
			self.logger.exception(ex)

	def write(self, msg):
		msg = self.serial.write(msg)

	def process_io_to_sock(self, msg):
		uid, t, args = msg
		if t == 0:
			# alors c'est un event
			# l'uid est l'id de l'event
			ev_key = self.event_keys.get(uid, None)
			if ev_key is None:
				logger.warning('unknown event %s' % uid)
			else:
				logger.info("send event %s %s", ev_key, args)
				self.send_event(ev_key, args)
			return None
		else:
			# c'est une reponse
			req = self.requests.get(uid, None)
			if req is None:
				logger.warning('unknown reponse id %s' % uid)
			else:
				id_to, uuid = req
				rep = Response(uuid, args)
				del self.requests[uid]
				self.free_ids.append(uid)
				logger.info("reponse to %s : %s", id_to, rep)
				return [id_to, rep.pack()]
	
	def process_sock_to_io(self, msg):
		remote_id, packed_request = msg
		request = Request.unpack(packed_request)
		
		try:
			# si c'est une demande d'affichage de l'aide
			if request.fct == 'help':
				help_msg = self.help(request)
				response = Response(request.uid, help_msg, None)
				self.send_multipart([remote_id, response.pack()])
			# sinon c'est un appel a une fonction
			else:
				uid = request.uid
				i = self.free_ids.pop()
				self.requests[i] = (remote_id, uid)
				args = request.args
				kwargs = request.kwargs
				msg = self.functions[request.fct](i, *args, **kwargs)
				logger.info("send to serial : %s" % msg)
				return msg
		except Exception as ex:
			err = {}
			err['tb'] = traceback.format_exc()
			err['error'] = str(ex)
			response = Response(request.uid, None, err)
			self.send_multipart([remote_id, response.pack()])

	def help(self, request):
		if not request.args:
			return '\n'.join(( str(v) for v in self.functions.values()))
		else:
			return self.functions[request.args[0]].__doc__
