#!/usr/bin/env python3

import sys
import optparse
try:
	import zerobot
except:
	sys.path.append('..')
	import zerobot
import logging
import time

usage = "usage: %prog [options]"
parser = optparse.OptionParser(usage,version="%prog 0.0.1")
parser.add_option("-c", "--connect",
	action="store", dest="connect", default=None,
	help="connect. ex : tcp:localhost//*:8000")
parser.add_option("-r", "--remote-id",
	action="store", dest="remote_id", default=None,
	help="remote identity")
parser.add_option("-i", "--identity",
	action="store", dest="identity", default="Pinger",
	help="self identity")
parser.add_option("-f", "--fct",
	action="store", dest="fct", default="ping",
	help="custom commande. ex : custom_ping")
parser.add_option("-s", "--sleep",
	action="store", dest="sleep", type="float", default=1.0,
	help="sleep time in seconds between each sleep")
parser.add_option("-n", "--n-reqs",
	action="store", dest="n_reqs", type="int", default=-1,
	help="n of requests, -1 for infinity.")
parser.add_option("-a", "--args",
	action="store", dest="args", default="42",
	help="arguments to pass to the commande, python formatting.")
parser.add_option("-l", "--log_lvl",
	action="store", dest="log_lvl", default=20,
	help="log level")


(options, _args) = parser.parse_args()


logging.basicConfig(level=options.log_lvl)



remote_cool = zerobot.Client(options.identity, options.connect, options.remote_id)
remote_cool.start(False)
time.sleep(0.5)

args = eval(options.args)
if not isinstance(args, list):
	args = [args,]

tot_time = 0
n = 0
t_min = 10E10
t_max = -1
def loop():
	global tot_time,n,t_min,t_max
	start = time.time()
	r = remote_cool._remote_call(options.fct,args,block=True)
	ellapsed = time.time() - start
	tot_time += ellapsed
	n += 1
	t_min = min(t_min, ellapsed)
	t_max = max(t_max, ellapsed)
	print(r,"time=%0.3fms"%(ellapsed*1000))
	if options.sleep:
		time.sleep(options.sleep)

try:
	if options.n_reqs < 0:
		while 1:
			loop()
	else:
		for i in range(options.n_reqs):
			loop()
except KeyboardInterrupt:
	pass

print("%s packets transmitted, time=%0.3fms" % (n,tot_time*1000))
print("min/avg/max = %0.3f/%0.3f/%0.3f ms" % (t_min*1000, tot_time/n*1000, t_max*1000))
	
