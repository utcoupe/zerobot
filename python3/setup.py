
import os
from setuptools import setup

exec(open(os.path.join(os.path.dirname(__file__),"zerobot","version.py")).read())


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "zerobot",
    version = __version__,
    author = __author__,
    author_email = "thomas.recouvreux@gmail.com",
    description = ("An architecture that allow fast communication between clients."),
    install_requires=['pyzmq'],
    tests_require=[],
    keywords = "zmq rpc robot",
    url = "http://github.com/utcoupe/zerobot",
    packages=['zerobot', 'tests'],
    long_description=read('README'),
    license = "BSD",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
    ],
)
