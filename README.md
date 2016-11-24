#AFL Mothership

Manage and run multiple synchronising AFL fuzzers.
The accomponying project report can be found [here](http://uint8.me/~simon/SimonPinfold_COMP489_Final.pdf).

## Setup

Clone (or download) the repo
```
git clone https://github.com/afl-mothership/afl-mothership.git
cd afl-mothership
```

Create a python3 virtualenv and install the requirements
```
virtualenv -p $(which python3) venv
source venv/bin/activate
pip install -r requirements.txt
```

Create the database
```
python manage.py createdb
```

Run the (development) server
```
python manage.py runserver
```

Check the server is running
[http://localhost:5000/](http://localhost:5000/)

The page should have two error alerts: "Missing libdislocator.so" and "Missing afl-fuzz"
To fix you must provide the afl-fuzz binary and (if desired) the libdislocator shared object.

Download and build afl-fuzz:

```
pushd /tmp/
wget http://lcamtuf.coredump.cx/afl/releases/afl-latest.tgz
tar xfz afl-latest.tgz
cd afl-2.35b/ # change version number to what was extracted
make
```

Optionally build libdislocator
```
cd libdislocator/
make
```

Copy the files into AFL mothership's data directory
```
popd
cp -t data/ /tmp/afl-2.35b/afl-fuzz /tmp/afl-2.35b/libdislocator/libdislocator.so
```

Reload the webpage and the errors should be gone! You can now create campaigns.

Note that manage.py runserver should only be used for development and real use should have uwsgi or similar serving the app.

e.g.
```
pip install uwsgi
./venv/bin/uwsgi --home venv --wsgi-file manage.py --callable app --master
```

## Creating Campaigns

Use the "new campaign" button to create a campaign. Choose a name and appropriate parameters. 

The executable should be built with afl-gcc/g++ or afl-clang then uploaded.

Multiple testcases can be uploaded along with an optional dictionary and libraries required by the executable.

Libraries and testcases also be added to a campaign after creation and a campaign will show libraries that are required by the executable.

## Launching Fuzzers

Fuzzers are launched using `slave/slave.py`.

Ensure that the desired campaigns are activated in the web interface and launch slaves on the desired host(s) with
```
python slave.py <web address of mothership> <number of fuzzers to run> [temp directory to operate out of]
```

An example of how launching of slaves can be automated on AWS EC2 using cloud init is provided in [`cloud-init.sh`](https://github.com/afl-mothership/afl-mothership/blob/master/slave/cloud-init.sh). Note that this must be modified to use the correct address of the mothership. This script is designed for running the mothership and slaves inside the same VPC, communicating over the internal network.


## Launching fuzzers on AWS example
```
ec2-request-spot-instances ami-f5f41398 --price 0.15 -t c3.large \
--valid-until 2016-07-04T23:23:18.000Z -z us-west-1c -k mothership -g mothership \
--user-data-file ./cloud-init.sh \
-n 4 --availability-zone-group "ImageMagick-6.7.0-identify-bmp-8-fuzzers"
```

```
ec2-request-spot-instances ami-6e84fa0e --price 0.15 -t c3.large \
--valid-until 2016-07-10T23:23:18.000Z -z us-west-1c -k "mothership keypair (us-west)" \
-g mothership --user-data-file ./cloud-init.sh -n 4 \
-availability-zone-group "libarchive 2.2.1 bstdar | 8 fuzzers"
```
