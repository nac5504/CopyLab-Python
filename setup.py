from setuptools import setup, find_packages

setup(
    name="copylab",
    version="0.1.0",
    description="Python SDK for CopyLab",
    author="Nicholas Candello",
    packages=find_packages(),
    py_modules=["copylab"],
    install_requires=[
        "firebase-admin",
        "requests"
    ],
)
