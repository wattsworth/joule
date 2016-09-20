#!/usr/bin/env python

PROJECT = 'Joule'

# Change docs/sphinx/conf.py too!
VERSION = '0.1'

from setuptools import setup, find_packages

try:
        long_description = open('README.rst', 'rt').read()
except IOError:
        long_description = ''

setup(
        name = PROJECT,
        version = VERSION,

        description = 'Process manager for embedded systems',
        long_description = long_description,

        author = 'John Donnal',
        author_email = 'donnal@usna.edu',

        url = 'https://git.wattsworth.net/wattsworth/joule.git',
        download_url = '[none]',

        classifiers=['Programming Language :: Python',
                     'Environment :: Console',
                     ],
        platforms=['Any'],
        scripts = [],
        provides = [],
        install_requires = ['cliff'],
       namespace_packages = [],
        packages=find_packages(),
        include_package_data=True,

        entry_points={
                'console_scripts': [
                        'joule = joule.main:main',
                        'jouled = joule.daemon.daemon:main'
                        ],
                'joule.commands' : [
#                        'daemon = joule.daemon.cmd:DaemonCmd',
                        'status = joule.cmds.status:StatusCmd'
                        ],
                },
        zip_safe = False,
)
