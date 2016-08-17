#!/bin/bash

# URL of the mothership server. WARNING: make sure this is accessible from the slave. You probably want to use the internal ip
MOTHERSHIP=http://172.31.30.196
#http://172.31.16.9
# Number of afl-instances to run on each slave
CORES=2
#CORES=`grep -c ^processor /proc/cpuinfo`
WORKINGDIR=/media/ephemeral0

# Github repo to download the slave script from
GITHUB=https://raw.githubusercontent.com/synap5e/afl-mothership


set -xe
chmod o+w $WORKINGDIR
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
python slave.py $MOTHERSHIP $CORES $WORKINGDIR
EOSU
