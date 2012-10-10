
import sys
import optparse
try:
	import zerobot
except:
	sys.path.append('..')
	import zerobot
import logging
import time
import re
import traceback

usage = "usage: %prog [options]"
parser = optparse.OptionParser(usage,version="%prog 0.0.1")
parser.add_option("-c", "--connect",
	action="store", dest="connect", default="tcp://localhost:5000",
	help="connect. ex : tcp:localhost:5000")
parser.add_option("-r", "--remote-id",
	action="store", dest="remote_id", default="time_service",
	help="remote identity")
parser.add_option("-i", "--identity",
	action="store", dest="identity", default="Console",
	help="self identity")
parser.add_option("-l", "--log_lvl",
	action="store", dest="log_lvl", default=20,
	help="log level")

(options, _args) = parser.parse_args()

logging.basicConfig(level=options.log_lvl)

print('Console id           ',options.identity)
print('Host                 ',options.connect)
print('Remote service id    ',options.remote_id)
client = zerobot.Client(options.identity, options.connect, options.remote_id)
client.start(False)
time.sleep(0.5)

