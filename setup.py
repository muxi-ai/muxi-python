from setuptools import setup, find_packages

setup(
    name="muxi",  # package name on PyPI
    version="0.20260106.1",
    description="MUXI Python SDK",
    author="Ran Aroussi",
    author_email="ran@aroussi.com",
    packages=find_packages(exclude=["tests", "examples"]),
    install_requires=[],
    python_requires=">=3.10",
    license="Apache-2.0",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
)
