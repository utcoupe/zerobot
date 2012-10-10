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
	action="store", dest="connect", default="tcp://localhost:5001",
	help="connect. ex : tcp:localhost:5001")
parser.add_option("-i", "--identity",
	action="store", dest="identity", default="time_service",
	help="service identity")
parser.add_option("-l", "--log_lvl",
	action="store", dest="log_lvl", default=20,
	help="log level")


(options, _args) = parser.parse_args()



logging.basicConfig(level=options.log_lvl)


class TimeService:
	def ping(self, num):
		return num+42

	def time(self):
		return time.time()


service = zerobot.Service(options.identity, options.connect, TimeService())
service.start()

#./ping.py
#./ping.py -f time -a []

