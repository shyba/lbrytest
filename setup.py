#!/usr/bin/env python
from setuptools import setup

setup(
    name='orchstr8',
    version='0.0.1',
    url='https://github.com/lbryio/orchstr8',
    license='MIT',
    description='Services orchestration and testing library for lbry.',
    author='LBRY Inc.',
    author_email='hello@lbry.io',
    keywords='lbry,unittest',
    classifiers=[
        'Framework :: AsyncIO',
        'Framework :: Twisted',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
        'Topic :: Internet',
        'Topic :: Communications :: File Sharing',
        'Topic :: Software Development :: Testing',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Benchmark',
        'Topic :: System :: Distributed Computing',
        'Topic :: Utilities',
    ],
    packages=['orchstr8'],
    install_requires=[
        'requests',
        'twisted'
    ]
)
