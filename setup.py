#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" Install utility for package CodifiedNorms """

from setuptools import setup

package_name = 'codifiednorms'
package_version = '0.1'

setup(
    author='Vikas Munshi',
    author_email='vikas.munshi@gmail.com',
    classifiers=[
        'Programming Language :: Python :: 3.9',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
    ],
    description='Python3 library for "Codified Norms"',
    download_url='https://github.com/vikasmunshi/ConfigAsCode/CodifiedNorms/',
    install_requires=[],
    license='GNU GPL3',
    long_description=open('README.md').read(),
    name='{}-{}'.format(package_name, package_version),
    package_dir={package_name: 'CodifiedNorms'},
    packages=[package_name],
    platforms=['Linux', 'MacOS'],
    python_requires='>=3.9',
    url='https://github.com/vikasmunshi/ConfigAsCode/CodifiedNorms/',
    version=package_version,
)
