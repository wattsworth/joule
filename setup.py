#!/usr/bin/env python

from setuptools import setup, find_packages
import versioneer

PROJECT = 'Joule'

# Change docs/sphinx/conf.py too!

try:
    long_description = open('README.rst', 'rt').read()
except IOError:
    long_description = ''

setup(
    name=PROJECT,
    version = versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description='Decentralized data processing for IoT platforms',
    long_description=long_description,

    author='John Donnal',
    author_email='donnal@usna.edu',

    url='http://wattsworth.net/joule',
    download_url='https://github.com/wattsworth/joule',
    license='open source (see LICENSE)',
    classifiers=['Programming Language :: Python',
                 'Environment :: Console',
                 ],
    platforms=['Any'],
    scripts=[],
    provides=[],
    install_requires=['click',
                      'treelib',
                      'numpy',
                      'scipy',
                      'psutil',
                      'aiohttp',
                      'markdown',
                      'BeautifulSoup4',
                      'dateparser',
                      'tabulate',
                      'sqlalchemy',
                      'aiohttp-jinja2',
                      'jinja2',
                      'asyncpg',
                      'psycopg2-binary',
                      'uvloop',
                      'aiodns',
                      'cchardet',
                      'pyopenssl',
                      'dsnparse'],
    tests_require=['asynctest',
                   'nose2',
                   'testing.postgresql',
                   'requests'],
    test_suite='tests',
    namespace_packages=[],
    packages=find_packages(exclude=["tests.*"]),
    include_package_data=True,

    entry_points={
        'console_scripts': [
            'joule = joule.cli:main',
            'jouled = joule.daemon:main',
            'joule-random-reader = joule.client.builtins.random_reader:main',
            'joule-file-reader = joule.client.builtins.file_reader:main',
            'joule-mean-filter = joule.client.builtins.mean_filter:main',
            'joule-median-filter = joule.client.builtins.median_filter:main',
            'joule-visualizer-filter = joule.client.builtins.visualizer:main'
        ]
    },
    #options={
    #    'build_scripts': {
    #        'executable': '/usr/local/bin/python3.5'
    #    }
    #},
    zip_safe=False,
)
