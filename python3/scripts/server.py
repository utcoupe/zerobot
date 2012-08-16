#!/usr/bin/env python3

import sys
import optparse
try:
	import zerobot
except:
	sys.path.append('..')
	import zerobot
import logging


usage = "usage: %prog [options]"
parser = optparse.OptionParser(usage,version="%prog 0.0.1")
parser.add_option("-f", "--frontend",
	action="store", dest="frontend", default=None,
	help="frontend bind addr. ex : tcp://*:8000")
parser.add_option("-b", "--backend",
	action="store", dest="backend", default=None,
	help="backend bind addr. ex : tcp://*:8001")
parser.add_option("-p", "--publish",
	action="store", dest="publish", default=None,
	help="publish bind addr. ex : tcp://*:8002")
parser.add_option("-l", "--log_lvl",
	action="store", dest="log_lvl", default=20,
	help="log level")


(options, _args) = parser.parse_args()


logging.basicConfig(level=options.log_lvl)

d = {}
if options.frontend: d["ft_bind_addr"] = options.frontend
if options.backend: d["bc_bind_addr"] = options.backend
if options.publish: d["pb_bind_addr"] = options.publish

server = zerobot.Server(**d)
server.start()
