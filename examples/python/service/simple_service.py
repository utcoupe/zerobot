#!/usr/bin/env python3


import sys
sys.path.append('../../../python3')
import zerobot
import time




class MyService:
	def ping(self, num):
		""" Pong ? """
		return int(num)+42

	def time(self):
		"""
		Il est quelle heure ?
		"""
		return time.time()

	def cool(self, a=3,b=2,c=4):
		return (a,b,c)

	def big_cool(self, *args, **kwargs):
		"""
		Une fonction avec un nombre variable de parametres positionnels
		et nommés
		"""
		return kwargs


service = zerobot.Service("myservice", "tcp://localhost:5001", MyService())
service.start()



