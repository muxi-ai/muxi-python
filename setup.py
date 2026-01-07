from setuptools import setup, find_packages

setup(
    name="muxi-client",
    version="0.20260106.1",
    description="MUXI Client (Python SDK)",
    author="Ran Aroussi",
    author_email="ran@aroussi.com",
    packages=find_packages(),
    install_requires=[
        # Add web-specific dependencies here
    ],
    python_requires=">=3.10",
)
