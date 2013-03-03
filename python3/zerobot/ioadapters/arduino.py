from collections import OrderedDict
from ..ioadapter import *
from ..core import *

import traceback
import struct
import os
import re
import serial

import logging
logger = logging.getLogger(__name__)
			

class BinaryProtocol:
	
	def pack(self, uid, id_cmd, args):
		"""
			    name   | size(bits) |  start   |  end  
			===========|============|==========|=======
			 uid	   |	 16	|     0	   |   16
			 id_cmd	   |	  8	|    16	   |   24
			 nb_args   |	  8	|    24	   |   32
			 arg0	   |	 16	|    32	   |   48
			 arg1	   |	 16	|    48	   |   64
			 ..	   |	 ..	|    ..	   |   ..
			 argN	   |	 16	| 32+16*N  | 32+16*(N+1)
		"""
		uid = int(uid)
		id_cmd = int(id_cmd)
		args = list([ int(x) for x in args ])
		n_args = len(args)
		b = struct.pack('hbb'+('h'*n_args), uid, id_cmd, n_args, *args)
		return b

	def read(self, fd):
		"""
			    name   | size(bits) 
			===========|============
			 uid	   |	 16
			 type	   |	  8
			 nb_args   |	  8
			 arg0	   |	 16
			 arg1	   |	 16	
			 ..	   |	 ..
			 argN	   |	 16
		"""
		buff_header = fd.read(struct.calcsize('hbb'))
		logger.debug("buff_header : %s", buff_header)
		header = self.unpack_header(buff_header)
		uid,flags,n_args = header
		buff_contents = fd.read(struct.calcsize('h'*n_args))
		args = self.unpack_contents(header, buff_contents)
		logger.debug("buff_contents : %s", buff_contents)
		return uid,flags,args
	
	def unpack_header(self, buff):
		uid,flags,n_args = struct.unpack('hbb', buff)
		return uid,flags,n_args

	def unpack_contents(self, header, buff):
		uid,flags,n_args = header
		args = struct.unpack('h'*n_args, buff)
		return args


class TextProtocol:
	SEP = '+'
	
	def pack(self, uid, id_cmd, args):
		m = self.SEP.join([str(uid), str(id_cmd)] + [ str(x) for x in args ])
		m += '\n'
		m = m.encode('utf-8')
		return m

	def read(self, fd):
		buff = fd.readline()[:-1]
		logger.debug("recv : %s", buff)
		msg = buff.decode('utf-8')
		if msg.endswith(self.SEP):
			msg = msg[:-1]
		msg = msg.split(self.SEP)
		uid = int(msg[0])
		flags = int(msg[1])
		args = msg[2:]
		return uid,flags,args

class ArduinoFunction:
	
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
	
	def __repr__(self):
		params = ','.join([
			'{k}={v}'.format(k=k, v=v) if v is not None else k
			for k,v in self.args.items()
		])
		return "{name}({params})".format(name=self.name, params=params)

class ArduinoAdapter(IOAdapter):
	def __init__(self, identity, conn_addr, serial, functions={},
		     event_keys={}, errors={}, *, max_id=2000, protocol='txt',
		     protocol_file=None, prefix='Q_', prefix_erreur = 'E_',
       		     **kwargs):
		super(ArduinoAdapter, self).__init__(identity, conn_addr, **kwargs)
		if protocol not in ('txt', 'bin'):
			raise ValueError('protocol must be text or bin')
		self.serial = serial
		self.free_ids = list(range(max_id))
		self.requests = {}
		self.functions = functions
		self.event_keys = event_keys
		self.errors = errors
		if protocol == 'bin':
			self.protocol = BinaryProtocol()
		else:
			self.protocol = TextProtocol()

		if not(protocol_file is None):
			self.load_protocol_from_file(protocol_file, prefix, prefix_erreur)

		self.arduino_disconnected = False

	def read(self):
		while not self.serial:
			time.sleep(1)
		try:
			m = self.protocol.read(self.serial)
			if m:
				uid,flags,args = m
				logger.info("read : uid=%s, flags=%s, args=%s", uid, flags, args)
				return uid, flags, args
		except serial.SerialException as ex:
			if not(self.arduino_disconnected):
				self.send_event('disconnected', str(ex))
				self.arduino_disconnected = True
		except Exception as ex:
			self.logger.exception(ex)

	def write(self, msg):
		msg = self.serial.write(msg)

	def process_io_to_sock(self, msg):
		uid, t, args = msg
		if (t & 0x01) == 0:
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
				if (t & 0x02) == 0:
					rep = Response(uuid, args)
				else:  # Il y a une erreur
					err = {'tb':''}
					err_value = int(args[0])
					if (err_value in self.errors.keys()):
						err['error'] = self.errors[err_value]
					else:
						err['error'] = err_value
					rep = Response(uuid, None, err)
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
			elif request.fct == 'kill':
				resp = Response(request.uid, 'goobye', None)
				self.send_multipart([remote_id, response.pack()])
				quit()
			# sinon c'est un appel a une fonction
			else:
				uid = request.uid
				i = self.free_ids.pop()
				self.requests[i] = (remote_id, uid)
				args = request.args
				kwargs = request.kwargs
				f = self.functions[request.fct]
				args = f.compute_params(*args, **kwargs)
				msg = self.protocol.pack(i, f.arduino_id, args)
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
			return self.functions[request.args[0]].__doc__ + ['kill']

	def load_protocol_from_file(self, protocol_file, prefix, prefix_erreur):
		"""
		Récupérer le protocol dans le fichier .h précisé.
		Les commandes doivent être formater de la sorte :
		{@code
		/**
		Documentation
		\@param abc
		\@param t
		*/
		#define {prefixe}NOM_DE_LA_COMMANDE		4
		}

		@param str_protocol
		@param prefix le prefixes des defines
		@return une liste de dictionnaires {id: ?, name: ?, params: ?, doc: ?} + le caracère de séparation
		"""
		
		try:
			str_protocol =  open(protocol_file).read()
		except IOError as e:
			self.logger.error("Unable to load protocol file (%s) : %s" % (protocol_file, e.strerror))
			return

		sep = '+'

		# spec des regexp
		spec_sep = '#define\s+SEP\s+[\'"](?P<sep>.)[\'"]'
		spec_doc = '\/\*\*(?P<doc>(.(?!\*\/))*.)\*\/'
		spec_define = '#define\s+{prefix}(?P<name>\w+)\s+(?P<id>\d+)'.format(prefix=prefix)
		spec_cmd = spec_doc+"\s*"+spec_define
		spec_params = '@param\s+(?P<param>[a-zA-Z_]\w*)'
		spec_event = '@event'
		spec_erreur = '#define\s+%s(?P<name>\w+)\s+-?(?P<value>\d+)' % prefix_erreur

		# compilation de la regexp des params car elle es appellée plusieurs fois
		re_params = re.compile(spec_params)
		re_event = re.compile(spec_event)

		# recherche du caractère de séparation
		t = re.search(spec_sep, str_protocol)
		if t:
			self.separator = t.group("sep")
		else:
			raise ProtocolException("le protocol de contient pas de caractère de séparation")

		# recherche des commandes
		for t in re.finditer(spec_cmd,str_protocol,re.DOTALL):
			name = t.group('name').lower()
			if re_event.search(t.group('doc')):
				self.event_keys[int(t.group('id'))] = name
			else:
				params = OrderedDict()
				for p in re_params.finditer(t.group('doc')):
					params[p.group('param')] = None
				self.functions[name] = ArduinoFunction(name, int(t.group('id')), t.group('doc'), params)

		for t in re.finditer(spec_erreur, str_protocol, re.DOTALL):
			name = t.group('name').lower()
			val = int(t.group('value'))
			self.errors[val] = name
