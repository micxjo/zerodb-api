from setuptools import setup, find_packages

INSTALL_REQUIRES = [
    'zerodb',
    'flask',
    'jsonpickle',
    'six'
]

TESTS_REQUIRE = [
    'pytest',
    'requests'
]

setup(
    name='zerodb-api',
    version="0.1.0",
    description="ZeroDB API server",
    license="AGPLv3",
    packages=find_packages(),
    namespace_packages=['zerodbext'],
    setup_requires=['pytest_runner'],
    install_requires=INSTALL_REQUIRES,
    tests_require=TESTS_REQUIRE
)
