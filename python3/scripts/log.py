#!/usr/bin/env python3

import sys
import optparse
try:
	import zerobot
except:
	sys.path.append('..')
	import zerobot
import logging
import zmq


usage = "usage: %prog [options]"
parser = optparse.OptionParser(usage,version="%prog 0.0.1")
parser.add_option("-c", "--connect",
	action="store", dest="host", default="tcp://localhost:5002",
	help="server publish addr. ex : tcp://localhost:5002")
parser.add_option("-s", "--subscribe",
	action="store", dest="subscribe", default="",
	help="subscribe channels separated by coma, default all. ex: id_client1,id_client5")

(options, _args) = parser.parse_args()

options.subscribe = list(filter(lambda x: bool(x), options.subscribe.split(',')))

print('Attempt to connect on ', options.host, '...')
ctx = zmq.Context()
socket = ctx.socket(zmq.SUB)
if options.subscribe:
	for sub in options.subscribe:
		socket.setsockopt(zmq.SUBSCRIBE, sub.encode())
		print('subscribe to', sub)
else:
	socket.setsockopt(zmq.SUBSCRIBE, b"")
	print('subscribe to all')
socket.connect(options.host)
print('Connected !')

try:
	while 1:
		c_from, c_to, msg = socket.recv_multipart()
		print('{:<25}{:<25}{}'.format('From : '+c_from.decode(), 'To : '+c_to.decode(), 'Msg : '+msg.decode()))
except:
	pass

socket.close()
ctx.term()

