#!/usr/bin/env python
import versioneer 

PROJECT = 'Joule'

# Change docs/sphinx/conf.py too!


from setuptools import setup, find_packages

try:
        long_description = open('README.rst', 'rt').read()
except IOError:
        long_description = ''

setup(
        name = PROJECT,
        version = versioneer.get_version(),
        cmdclass = versioneer.get_cmdclass(),
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
        install_requires = ['cliff',
                            'numpy',
                            'psutil'],
        namespace_packages = [],
        packages=find_packages(exclude="test"),
        include_package_data=True,

        entry_points={
                'console_scripts': [
                        'joule = joule.main:main',
                        'jouled = joule.daemon.daemon:main'
                        ],
                'joule.commands' : [
                        'modules = joule.cmds.modules:ModulesCmd',
                        'logs = joule.cmds.logs:LogsCmd'
                        ],
                },
        zip_safe = False,
)
