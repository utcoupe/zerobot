#!/usr/bin/env python3

import sys
sys.path.append('../../../python3')
import zerobot
import logging

logging.basicConfig(level=20)

server = zerobot.Server()
server.start()
