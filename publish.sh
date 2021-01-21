#!/bin/bash
#

set -e

rm -fr dist/
python3 setup.py sdist bdist_wheel
twine upload dist/* -u codeskyblue
