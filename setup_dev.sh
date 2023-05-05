#!/usr/bin/env bash

echo "***************************"
echo "   dev setup start   "
echo "***************************"

# create python virtual environment
python3 -m venv --clear venv

# activate virtual environment
source ./venv/bin/activate

# upgrage pip
pip install pip -U -i https://mirrors.aliyun.com/pypi/simple/

# install from freeze requirements
pip install -r requirements.txt -U -i https://mirrors.aliyun.com/pypi/simple/

echo "***************************"
echo "   dev setup finish   "
echo "***************************"
