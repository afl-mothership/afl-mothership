#!/bin/bash

# URL of the mothership server. WARNING: make sure this is accessible from the slave. You probably want to use the internal ip
MOTHERSHIP=http://172.31.30.196

# Number of afl-instances to run on each slave
# This can be specified explicitly or read the number of cores from cpuinfo
# CORES=2
CORES=`grep -c ^processor /proc/cpuinfo`

# Directory to operate out of - use ephemeral local storage
# It may be nessicary to specify to mount ephemeral drives when creating machines 
WORKINGDIR=/media/ephemeral0

# Github repo to download the slave script from
GITHUB=https://raw.githubusercontent.com/afl-mothership/afl-mothership

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
