"""
Setup script for MUXI Python SDK.

All package metadata and dependencies are defined in pyproject.toml; this setup.py
reads from that single source of truth.
"""

import os
import sys
import tomli
from setuptools import setup, find_packages

try:
    from muxi.version import __version__
except Exception:
    __version__ = "0.0.0"

# Read configuration from pyproject.toml
if not os.path.exists("pyproject.toml"):
    print("ERROR: pyproject.toml not found")
    sys.exit(1)

try:
    with open("pyproject.toml", "rb") as f:
        project = tomli.load(f).get("project", {})
except Exception as e:
    print(f"ERROR: Failed to parse pyproject.toml: {e}")
    sys.exit(1)

name = project.get("name", "muxi")
description = project.get("description", "")
authors = project.get("authors", [])
author = authors[0].get("name", "MUXI Team") if authors else "MUXI Team"
author_email = authors[0].get("email", "dev@muxi.org") if authors else "dev@muxi.org"
install_requires = project.get("dependencies", [])
extras_require = project.get("optional-dependencies", {}) if "optional-dependencies" in project else {}
python_requires = project.get("requires-python", ">=3.10")
classifiers = project.get("classifiers", [])
urls = project.get("urls", {})
license_text = project.get("license", {}).get("text", "Apache-2.0")

# Long description
try:
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
except FileNotFoundError:
    long_description = description

setup(
    name=name,
    version=__version__,
    author=author,
    author_email=author_email,
    description=description,
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=urls.get("Homepage", "https://github.com/muxi-ai/muxi-python"),
    project_urls=urls,
    packages=find_packages(exclude=["tests", "examples"]),
    include_package_data=True,
    license=license_text,
    classifiers=classifiers,
    python_requires=python_requires,
    install_requires=install_requires,
    extras_require=extras_require,
    zip_safe=False,
)

