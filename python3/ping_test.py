
from zerobot import *




if __name__ == "__main__":

	import sys

	log_lvl = int(sys.argv[1]) if len(sys.argv) >= 2 else 20

	logging.basicConfig(level=log_lvl)
	
	server = Server("tcp://*:8080","tcp://*:8081","tcp://*:8082")
	server.start(False)
	time.sleep(1)
	
	class Cool:
		def ping(self, num):
			return num+42

		def hello(self):
			return "world"

		def test(self, a=3, b=4, c=5):
			return a,b,c

		def echo(self, m):
			return m

	cool = Service("cool", "tcp://localhost:8081", Cool())
	cool.start(False)
	time.sleep(100000)
	
	"""remote_cool = Client("remote_cool", "tcp://localhost:8080", "cool")
	remote_cool.start(False)

	time.sleep(0.5)

	try:
		while 1:
			print(remote_cool.ping(56,block=True))
			time.sleep(1)
	except KeyboardInterrupt:
		remote_cool.stop()
		cool.stop()
		server.stop()
		time.sleep(0.2)"""
	"""
	print(remote_cool.ping(56,block=True))
	print(remote_cool.ping(56,block=True))
	print(remote_cool.help(block=True))
	print(remote_cool.help('hello',block=True))
	print(remote_cool.hello(block=True))
	print(remote_cool.test(c=10,block=True))
	try:
		print(remote_cool._cou())
	except ZeroBotException as ex:
		print(ex)
	"""
