#!/usr/bin/env python3

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

#cool = zerobot.AsyncClassExposer("cool", "tcp://localhost:8001", Cool(), init_workers=5, dynamic_workers=False)
cool = zerobot.ClassExposer("cool", "tcp://localhost:8001", Cool())
cool.start(False)

class ClientBenchmark(threading.Thread):
	def __init__(self, identity, n_reqs, block):
		threading.Thread.__init__(self)
		self.client = zerobot.RemoteClient(identity, "tcp://localhost:8000", "cool")
		self.n_reqs = n_reqs
		self.block = block
		self.n = 0
		self.event = threading.Event()
		self.setDaemon(True)
		self.client.start(False)
	
	def run(self):

		kwargs = {'c':'0'*100,'b':'2'*100,'a':'3'*100}
		cb = None if self.block else self.cb
		
		for i in range(self.n_reqs):
			"""if i%2:
				self.client.test(block=self.block, cb_fct=cb, **kwargs)
			else:
				self.client.sleep(1, block=self.block, cb_fct=cb)
			"""
			self.client.test(block=self.block, cb_fct=cb, **kwargs)

		if not self.block:
			while not self.event.is_set():
				self.event.wait(1)

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
	print('%s clients, %s reqs %s (tot:%sreqs) : %0.2fs, average : %0.2fms'
		% (nb_clients, nb_reqs, 'block' if block else 'async', tot_reqs, ellapsed, average*1000))

	for i in range(nb_clients):
		clients[i].close()

benchmark(n_clients, n_reqs, "coucou", block)
