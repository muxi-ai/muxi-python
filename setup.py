import tomli
from setuptools import setup, find_packages

try:
    from muxi.version import __version__
except Exception:
    __version__ = "0.0.0"

with open("pyproject.toml", "rb") as f:
    project = tomli.loads(f.read()).get("project", {})


setup(
    name=project.get("name", "muxi"),
    version=__version__,
    description=project.get("description", ""),
    author=project.get("authors", [{"name": "MUXI Team"}])[0].get("name", "MUXI Team"),
    author_email=project.get("authors", [{"email": "dev@muxi.org"}])[0].get("email", "dev@muxi.org"),
    packages=find_packages(exclude=["tests", "examples"]),
    install_requires=project.get("dependencies", []),
    python_requires=project.get("requires-python", ">=3.10"),
    license=project.get("license", {}).get("text", "Apache-2.0"),
    classifiers=project.get("classifiers", []),
    url=project.get("urls", {}).get("Homepage", "https://github.com/muxi-ai/muxi-python"),
    project_urls=project.get("urls", {}),
)
