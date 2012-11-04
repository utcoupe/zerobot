#!/usr/bin/env python

import zerobot
import zmq

import sys
import threading
import time
import logging
n_clients = int(sys.argv[1])
n_reqs = int(sys.argv[2])
block = sys.argv[3] == "block"
log_lvl = int(sys.argv[4]) if len(sys.argv) > 4 else 20
logging.basicConfig(level=log_lvl)
	
server = zerobot.Server("tcp://*:8000","tcp://*:8001","tcp://*:8002")
server.start(False)
time.sleep(0.1)

class Cool:
	def ping(self, num):
		return num+42

	def hello(self):
		return "world"

	def test(self, a=3, b=4, c=5):
		return a,b,c

	def echo(self, m):
		return m

	def sleep(self, n):
		time.sleep(1)
		return "ok"

#cool = zerobot.AsyncService("cool", "tcp://localhost:8001", Cool(), init_workers=5, dynamic_workers=True)
cool = zerobot.Service("cool", "tcp://localhost:8001", Cool())
cool.start(False)
"""
ctx = zmq.Context()
cool = ctx.socket(zmq.DEALER)
cool.identity = b"cool"
cool.connect("tcp://localhost:8001")
import re
r = re.compile(".*?\"uid\": \"(.*?)\".*?")
def loop():
	while True:
		msg = cool.recv_multipart()
		t = r.match(msg[1].decode())
		uid = t.group(1)
		cool.send_multipart([msg[0], ('{"data":96, "error":null, "uid":"%s"}'%uid).encode()])
	cool.close()
t = threading.Thread(target=loop)
t.setDaemon(True)
t.start()
"""

class ClientBenchmark(threading.Thread):
	def __init__(self, identity, n_reqs, block):
		threading.Thread.__init__(self)
		self.client = zerobot.AsyncClient(identity, "tcp://localhost:8000", "cool")
		self.client.start(False)
		"""
		ctx = zmq.Context()
		self.client = ctx.socket(zmq.DEALER)
		self.client.identity = identity.encode()
		self.client.connect("tcp://localhost:8000")
		self.msg = '{"uid": "%s", "fct": "ping", "args":[42], "kwargs":{}}'
		"""
		self.n_reqs = n_reqs
		self.block = block
		self.n = 0
		self.event = threading.Event()
		self.setDaemon(True)
	
	def run(self):

		kwargs = {'c':'0'*100,'b':'2'*100,'a':'3'*100}
		cb = None if self.block else self.cb
		
		for i in range(self.n_reqs):
			"""if i%2:
				self.client.test(block=self.block, cb_fct=cb, **kwargs)
			else:
				self.client.sleep(1, block=self.block, cb_fct=cb)
			"""
			"""
			self.client.send_multipart([b"cool", (self.msg % i).encode()])
			if self.block:
				self.client.recv_multipart()
			"""
			#self.client.test(block=self.block, cb_fct=cb, **kwargs)
			self.client.ping(42, block=self.block, cb_fct=cb)

		if not self.block:
			#for i in range(self.n_reqs): self.client.recv_multipart()
			while not self.event.is_set(): self.event.wait(1)

	def close(self):
		self.client.close()
		self.event.set()

	def cb(self, response):
		self.n += 1
		if self.n == self.n_reqs: self.event.set()

def benchmark(nb_clients, nb_reqs, msg, block):

	clients = []
	for i in range(nb_clients):
		client = ClientBenchmark("remote-%s"%i, nb_reqs, block)
		clients.append(client)
	
	start = time.time()
	for i in range(nb_clients):
		clients[i].start()
	
	for i in range(nb_clients):
		clients[i].join()
	ellapsed = time.time()-start
	
	tot_reqs = nb_clients*nb_reqs
	average = ellapsed/tot_reqs
	reqs_sec = round(tot_reqs/ellapsed)
	print('%s clients, %s reqs %s (tot:%sreqs) : %0.2fs, average : %0.2fms, reqs/s : %s'
		% (nb_clients, nb_reqs, 'block' if block else 'async', tot_reqs, ellapsed, average*1000, reqs_sec))

	for i in range(nb_clients):
		clients[i].close()

benchmark(n_clients, n_reqs, "coucou", block)
