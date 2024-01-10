from setuptools import setup

with open("version.txt") as f:
    version = f.read().strip()

with open("README.md", encoding="utf-8") as f:
    long_description = f.read().strip()

setup(
    name="connecpy",
    version=version,
    description="Server and client lib for Connect Protocol",
    long_description=long_description,
    long_description_content_type="text/markdown",
    licesnse="unlicense",
    packages=["connecpy"],
    install_requires=["protobuf", "httpx", "starlette"],
    test_requires=[],
    zip_safe=False,
)
