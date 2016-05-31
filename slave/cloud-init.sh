#!/bin/bash

# URL of the mothership server
MOTHERSHIP=http://home.uint8.me:5000
# Number of afl-instances to run on the slave(s)
CORES=2

# Github repo to download the slave script from
GITHUB=https://raw.githubusercontent.com/synap5e/afl-mothership


set -xe
su ec2-user <<EOSU
cd /home/ec2-user
mkdir afl-slave
cd afl-slave
virtualenv venv
source venv/bin/activate
wget $GITHUB/master/slave/requirements.txt
pip install -r requirements.txt
wget $GITHUB/master/slave/slave.py
chmod +x slave.py
python slave.py $MOTHERSHIP $CORES
EOSU
