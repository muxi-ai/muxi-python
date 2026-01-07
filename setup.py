from setuptools import setup, find_packages

try:
    from muxi.version import __version__
except Exception:
    __version__ = "0.0.0"


setup(
    name="muxi",
    version=__version__,
    description="MUXI Python SDK",
    author="Ran Aroussi",
    author_email="ran@aroussi.com",
    packages=find_packages(exclude=["tests", "examples"]),
    install_requires=[],
    python_requires=">=3.10",
    license="Apache-2.0",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    url="https://github.com/muxi-ai/muxi-python",
    project_urls={
        "Homepage": "https://muxi.org",
        "Source": "https://github.com/muxi-ai/muxi-python",
        "Issues": "https://github.com/muxi-ai/muxi-python/issues",
    },
)
