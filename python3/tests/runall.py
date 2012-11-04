#!/usr/bin/env python

import os
path = os.path.abspath(os.path.dirname(__file__))
import subprocess
p = subprocess.Popen('python3 -m unittest discover -p "test_*.py" -s %s -v' % path, shell=True)
p.wait()
