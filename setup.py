#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup


setup(
    name='justbry',
    version='0.1',
    description='Fully Pythonized Framework for Creating React Applications and Services',
    
    author='Steep Pepper',
    author_email='steephairy@gmail.com',
    url='https://github.com/longnetwork/justbry',

    python_requires=">=3.11",

    package_dir={
        'justbry': '.',
    },

    include_package_data = True,


    package_data={
        'justbry.static': ["*.*"],
    },
    

    install_requires=[
        'uvicorn[standart]>=0.37',
        'starlette>=0.48',
        'python-multipart>=0.0.20',
        'websockets>=14.1',
        'requests>=2.32',
        'itsdangerous>=2.2.0',
    ],

)
