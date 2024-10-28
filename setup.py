import setuptools

with open("README.md", "r") as f:
    long_description = f.read()


setuptools.setup(
    name="dataconfigs",
    author="Mantas Birškus",
    author_email="mantix7@gmail.com",
    license="Apache",
    description="Turn your dataclasses into configs seamlessly.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    version="0.1.0",
    url="https://github.com/mantasu/dataconfigs",
    project_urls={
        "Documentation": "https://mantasu.github.io/dataconfigs",
        "Bug Tracker": "https://github.com/mantasu/dataconfigs/issues",
    },
    keywords=[
        "python",
        "config",
        "configuration",
        "configurable",
    ],
    install_requires=[
        "docstring-parser",
    ],
    classifiers=[
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Natural Language :: English",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Environment :: MacOS X",
        "Environment :: Win32 (MS Windows)",
        "Environment :: Other Environment",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.12",
)
