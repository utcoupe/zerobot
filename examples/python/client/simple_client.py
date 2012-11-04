#!/usr/bin/env python

import sys
sys.path.append('../../../python3')
import zerobot

client = zerobot.Client("myclient", "tcp://localhost:5000", "myservice")

# lancement du thread du client, a voir si ca ne doit pas etre fait automatiquement
# dans le __init__
client.start(False)

print('ping', client.ping(42))
print('time', client.time())

try:
	print(client.nexistepas())
except Exception as ex:
	print(ex)

print('doc global', client.help())
print('doc time :', client.help('time'))
print('doc cool :', client.help('cool'))
print('doc nexistepas :', client.help('nexistepas'))
