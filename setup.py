#!/usr/bin/env python

from setuptools import setup, find_packages

PROJECT = 'Joule'

# Change docs/sphinx/conf.py too!

try:
    long_description = open('README.rst', 'rt').read()
except IOError:
    long_description = ''

setup(
    name=PROJECT,
    version='0.2.2',  # versioneer.get_version(),
    #cmdclass=versioneer.get_cmdclass(),
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
                      'scipy',
                      'psutil',
                      'requests',
                      'aiohttp',
                      'markdown',
                      'BeautifulSoup4',
                      'dateparser'],
    namespace_packages=[],
    packages=find_packages(),
    include_package_data=True,

    entry_points={
        'console_scripts': [
            'joule = joule.main:main',
            'jouled = joule.daemon.daemon:main',
            'joule-random-reader = joule.client.builtins.random_reader:main',
            'joule-file-reader = joule.client.builtins.file_reader:main',
            'joule-mean-filter = joule.client.builtins.mean_filter:main',
            'joule-median-filter = joule.client.builtins.median_filter:main'
        ],
        'joule.commands': [
            'modules = joule.cmds.modules:ModulesCmd',
            'logs = joule.cmds.logs:LogsCmd',
            'initialize = joule.cmds.initialize:InitializeCmd',
            'docs = joule.cmds.docs:DocsCmd'
        ],
    },
    #options={
    #    'build_scripts': {
    #        'executable': '/usr/local/bin/python3.5'
    #    }
    #},
    zip_safe=False,
)
