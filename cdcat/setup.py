#!/usr/bin/env python
# encoding: utf-8

from setuptools import setup

setup(
    name         = "cdcat",
    version      = "0.1",
    description  = "Use the database from cdcat to copy wanted files.",
    author       = "Robin `ypid` Schneider",
    author_email = "ypid23@aol.de",
    url          = "https://github.com/ypid/scripts/tree/master/cdcat",
    packages     = ["cdcat"],
    license      = "GPLv3",
    test_suite   = "tests",
)
