#!/usr/bin/env python3
"""
Setup configuration for WoL-Caster
"""

from setuptools import setup, find_packages
import os
import sys

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Read requirements
with open(os.path.join(this_directory, 'requirements.txt'), encoding='utf-8') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="wol-caster",
    version="1.0.0",
    author="Cardigans of the Galaxy",
    author_email="",
    description="A powerful cross-platform Wake-on-LAN network broadcaster with GUI and CLI modes",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/CardigansoftheGalaxy/wol-caster",
    project_urls={
        "Bug Tracker": "https://github.com/CardigansoftheGalaxy/wol-caster/issues",
        "Documentation": "https://github.com/CardigansoftheGalaxy/wol-caster/blob/main/README.md",
        "Source Code": "https://github.com/CardigansoftheGalaxy/wol-caster",
    },
    packages=find_packages(),
    py_modules=["wol_caster"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: System Administrators",
        "Intended Audience :: End Users/Desktop",
        "Topic :: System :: Networking",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Environment :: Console",
        "Environment :: X11 Applications :: GTK",
        "Environment :: Win32 (MS Windows)",
        "Environment :: MacOS X",
    ],
    python_requires=">=3.6",
    install_requires=requirements,
    extras_require={
        "gui": ["tkinter"],  # Usually built-in, but listed for completeness
        "dev": ["pyinstaller>=5.0", "pytest", "black", "flake8"],
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
    keywords="wake-on-lan wol network broadcast magic-packet networking administration",
    zip_safe=False,
    include_package_data=True,
    package_data={
        "": ["README.md", "LICENSE", "requirements.txt"],
    },
)
