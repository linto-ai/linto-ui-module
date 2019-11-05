#!/usr/bin/env python3
from setuptools import setup, find_packages
import json

with open("manifest.json", 'r') as f:
    _version = json.load(f)["version"]

setup(
    name="linto_ui",
    version=_version,
    include_package_data=True,
    packages=find_packages(),
    entry_points = {
        'console_scripts': ['linto_ui=ui.linto_ui:main'],
    },
    install_requires=[
        'pygame',
        'tenacity',
        'paho-mqtt'
    ],
    package_data={},
    author="Rudy Baraglia",
    author_email="baraglia.rudy@gmail.com",
    description="linto_ui is the GUI for the LinTo device",
    license="AGPL V3",
    keywords="GUI linto pygame",
    url="",
    project_urls={
        "github" : ""
    },
    long_description="Refer to README"

)