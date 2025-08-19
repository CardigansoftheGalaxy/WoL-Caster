#!/usr/bin/env python3
"""
Setup script for WoL-Caster
"""

from setuptools import setup, find_packages
import os

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read the version from the main module
def get_version():
    with open("wol_caster.py", "r") as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split('"')[1]
    return "1.0.0"

setup(
    name="wol-caster",
    version=get_version(),
    author="Cardigans of the Galaxy",
    author_email="",
    description="A powerful, intelligent cross-platform utility that automatically detects all your network interfaces and broadcasts Wake-on-LAN magic packets",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/CardigansoftheGalaxy/wol-caster",
    project_urls={
        "Bug Tracker": "https://github.com/CardigansoftheGalaxy/wol-caster/issues",
        "Documentation": "https://github.com/CardigansoftheGalaxy/wol-caster",
        "Source Code": "https://github.com/CardigansoftheGalaxy/wol-caster",
    },
    py_modules=["wol_caster"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Information Technology",
        "Topic :: System :: Networking",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Environment :: Console",
        "Environment :: X11 Applications :: Qt",
    ],
    python_requires=">=3.6",
    install_requires=[
        "netifaces>=0.11.0",
        'ipaddress>=1.0.23; python_version < "3.3"',
        'pyobjc-framework-Cocoa>=9.0; sys_platform == "darwin"',
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov",
            "black",
            "flake8",
            "pyinstaller",
        ],
    },
    entry_points={
        "console_scripts": [
            "wol=wol_caster:main",
            "wol-cast=wol_caster:main",
            "wol-caster=wol_caster:main",
            "wolcast=wol_caster:main",
            "wolcaster=wol_caster:main",
        ],
    },
    keywords="wake-on-lan, wol, network, broadcasting, magic-packet, network-administration",
    zip_safe=False,
    include_package_data=True,
)
