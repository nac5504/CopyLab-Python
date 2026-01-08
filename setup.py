from setuptools import setup, find_packages

setup(
    name="copylab",
    version="1.0.2",
    description="CopyLab Python SDK for secure notification management",
    author="CopyLab",
    package_dir={"": "Sources"},
    packages=find_packages(where="Sources"),
    install_requires=[
        "requests>=2.25.0",
    ],
    python_requires=">=3.8",
)
