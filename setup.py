#!/usr/bin/env python
import versioneer
from setuptools import setup, find_packages

PROJECT = 'Joule'

# Change docs/sphinx/conf.py too!

try:
    long_description = open('README.rst', 'rt').read()
except IOError:
    long_description = ''

setup(
    name=PROJECT,
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description='Process manager for embedded systems',
    long_description=long_description,

    author='John Donnal',
    author_email='donnal@usna.edu',

    url='https://git.wattsworth.net/wattsworth/joule.git',
    download_url='[none]',

    classifiers=['Programming Language :: Python',
                 'Environment :: Console',
                 ],
    platforms=['Any'],
    scripts=[],
    provides=[],
    install_requires=['cliff',
                      'numpy',
                      'psutil',
                      'python-datetime-tz',
                      'requests',
                      'aiohttp'],
    namespace_packages=[],
    packages=find_packages(),
    include_package_data=True,

    entry_points={
        'console_scripts': [
            'joule = joule.main:main',
            'jouled = joule.daemon.daemon:main'
        ],
        'joule.commands': [
            'modules = joule.cmds.modules:ModulesCmd',
            'logs = joule.cmds.logs:LogsCmd',
            'reader = joule.client.cmd:ReaderCmd',
        ],
    },
    options={
        'build_scripts': {
            'executable': '/usr/local/bin/python3.5'
        }
    },
    zip_safe=False,
)
