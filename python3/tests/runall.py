#!/usr/bin/env python
import sys
import os
path = os.path.abspath(os.path.dirname(__file__))
import subprocess
p = subprocess.Popen('python -m unittest discover -p "test_*.py" -s %s -v' % path, shell=True)
p.wait()
sys.exit(p.returncode)
