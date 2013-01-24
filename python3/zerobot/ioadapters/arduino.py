
from ..ioadapter import *
from ..core import *

from collections import OrderedDict

import traceback

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

		params = OrderedDict(self.args)
		args.extends([None]*len(self.args)-len(args))
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
		
		return tuple(params.values())

	def encode_call(self, params):
		return self.SEPARATOR.join([self.arduino_id]+params)
	
	def __call__(self, *args, **kwargs):
		params = self.compute_params(*args, **kwargs)
		encoded_call = self.encode_call(params)
		return encoded_call
	
	def __repr__(self):
		params = ','.join([
			'{k}={v}'.format(k=k, v=v) if v is not None else k
			for k,v in self.args.items()
		])
		return "{name}({params})".format(name=self.name, params=params)

class ArduinoAdapter(IOAdapter):
	def __init__(self, identity, conn_addr, port, functions={}, *, ctx=None):
		super(ArduinoAdapter, self).__init__(identity, conn_addr, ctx=ctx)
		self.serial = None # TODO
		self.hash_uid = {} # contient la relation hash=>uuid
		self.functions = functions

	def read(self):
		while not self.serial:
			time.sleep(1)
		try:
			msg = self.serial.readline()
			return msg
		except Exception as ex:
			self.logger.error(ex)

	def write(self, msg):
		msg = self.serial.write(msg.strip()+'\n')

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
				hash_uid = hash(uid)
				self.hash_uid[hash_uid] = uid
				args = [hash_uid]+request.args
				kwargs = request.kwargs
				
				self.functions[request.fct](*args, **kwargs)
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
