#!/usr/bin/env python3
from __future__ import print_function

import os
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import logging
import traceback

import requests
try:
	from urllib import request as urllib_request
except ImportError:
	import urllib as urllib_request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SHARE_WHEN_POSSIBLE = False
DEBUG = False
SUBMIT_FREQUENCY = 60
SNAPSHOT_FREQUENCY = 60


class tempdir:
	def __init__(self, prefix='tmp'):
		self.prefix = prefix

	def __enter__(self):
		self.dir = tempfile.mkdtemp(prefix=self.prefix)
		return self.dir

	def __exit__(self, exc_type, exc_val, exc_tb):
		shutil.rmtree(self.dir)


def optimistic_parse(value):
	for t in [int, float]:
		try:
			return t(value)
		except ValueError:
			pass
	if '%' in value:
		return optimistic_parse(value.replace('%', ''))
	return value


class AflInstance(threading.Thread):

	def __init__(self, directory, testcases, sync_dir, name, args, program, program_args):
		super(AflInstance, self).__init__()

		self.directory = directory
		self.testcases = testcases
		self.sync_dir = sync_dir
		self.name = name
		self.extra_args = args
		self.program = program
		self.program_args = program_args

		self.process = None

	def run(self):
		args = [os.path.join(self.directory, './afl-fuzz'),
		        '-i', self.testcases, '-o',
		        self.sync_dir, '-S', self.name] + \
		        self.extra_args + \
				['--', self.program] + self.program_args

		logger.info('Starting afl with %r' % ' '.join(args))
		env = dict(os.environ)
		if 'LD_LIBRARY_PATH' in env:
			env['LD_LIBRARY_PATH'] += ':'
		else:
			env['LD_LIBRARY_PATH'] = ''
		env['LD_LIBRARY_PATH'] += os.path.join(os.path.dirname(self.program), 'libraries')
		env['AFL_IMPORT_FIRST'] = 'True'
		env['AFL_PRELOAD'] = os.path.join(self.directory, './libdislocator.so')
		# env['AFL_NO_VAR_CHECK'] = 'True'
		if DEBUG:
			self.process = subprocess.Popen(args, env=env)
		else:
			self.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
			for line in iter(self.process.stdout.readline, ""):
				if not line:
					break
				sys.stdout.write(str(self.process.pid) + ' - ' + line.decode('ascii'))

		print('waiting on', self.process)
		self.process.wait()
		print('done waiting on', self.process)
		if self.process.returncode != 0:
			raise Exception("Process exited with %d" % self.process.returncode)

	def terminate(self):
		self.process.terminate()


class MothershipSlave:

	def __init__(self, mothership_url, directory):
		self.mothership_url = mothership_url
		self.directory = directory
		self.submitted_crashes = {'README.txt'}
		self.snapshot_times = set()
		self.snapshot_tell = 0
		self.last_snapshot = 0

		self.id = None
		self.instance = None
		self.upload_timer = None
		self.submit_timer = None

		try:
			logger.info('Registering slave')
			request = requests.get(mothership_url + '/fuzzers/register?hostname=%s' % socket.gethostname())
			if request.status_code == 404:
				logger.error('No more campaigns requiring fuzzers')
				self.valid = False
				return
			self.valid = True
			register = request.json()
		except requests.ConnectionError as e:
			raise Exception('Could not connect to %s' % mothership_url, e)

		self.id = register['id']
		logger.info('Slave registered with id=%d' % self.id)

		self.name = register['name']
		self.campaign_name = register['campaign_name']
		self.campaign_id = register['campaign_id']
		self.download_url = register['download']
		self.upload_url = register['upload']
		self.submit_url = register['submit']
		self.submit_crash = register['submit_crash']

		self.program = register['program']
		self.program_args = register['program_args']
		self.args = register['args']
		self.upload_in = register['upload_in']

		self.campaign_directory = os.path.join(directory, register['campaign_name'])
		if not SHARE_WHEN_POSSIBLE:
			self.campaign_directory += '_' + str(self.id)
		self.testcases = os.path.join(self.campaign_directory, 'testcases')
		self.sync_dir = os.path.join(self.campaign_directory, 'sync_dir')
		self.own_dir = os.path.join(self.sync_dir, self.name)

	def start(self):
		if self.id is None:
			# register attempt failed
			return

		logger.info('Starting fuzzer in %s' % self.own_dir)
		self.instance = AflInstance(
			self.directory,
			self.testcases,
			self.sync_dir,
			self.name,
			self.args,
			os.path.join(self.campaign_directory, self.program),
			self.program_args,
		)
		self.instance.daemon = True

		logger.info('Upload in %d', self.upload_in )
		self.upload_timer = threading.Timer(self.upload_in, self.upload_queue)

		self.submit_timer = threading.Timer(SUBMIT_FREQUENCY, self.submit)

		self.instance.start()
		self.upload_timer.start()
		self.submit_timer.start()

	def upload_queue(self):
		logger.info('Uploading queue')

		try:
			def state_filter(tarinfo):
				if '.state' in tarinfo.name:
					return None
				else:
					return tarinfo

			queue_tar = os.path.join(self.own_dir, 'queue.tar.gz')
			with tarfile.open(queue_tar, 'w:') as tar:
				tar.add(os.path.join(self.own_dir, 'queue'), arcname='queue', filter=state_filter)
			with open(queue_tar, 'rb') as f:
				response = requests.post(self.upload_url, files={'file': f})

			upload_in = response.json()['upload_in']
			logger.info('Scheduling re-upload in %d', upload_in)
			self.upload_timer = threading.Timer(upload_in, self.upload_queue)
			self.upload_timer.start()
		except Exception as e:
			logger.warn(e)
			logger.warn('Retrying in 1 minute')
			traceback.print_exc()
			self.upload_timer = threading.Timer(60, self.upload_queue)
			self.upload_timer.daemon = True
			self.upload_timer.start()

	def submit(self):
		logger.info('Submitting status')

		status_file = os.path.join(self.own_dir, 'fuzzer_stats')
		plot_file = os.path.join(self.own_dir, 'plot_data')
		crash_dir = os.path.join(self.own_dir, 'crashes')

		try:
			status = {}
			with open(status_file, 'r') as f:
				for line in f.readlines():
					key, value = line.replace('\n', '').split(':', 1)
					status[key.strip()] = optimistic_parse(value[1:])
			logger.info('%d - %r' % (self.instance.process.pid, status))

			snapshots = []
			with open(plot_file, 'r') as f:
				keys = f.readline()[2:-1].split(', ')
				if self.snapshot_tell:
					f.seek(self.snapshot_tell)
				for line in f.readlines():
					values = line[:-1].split(', ')
					if values[0] not in self.snapshot_times:
						self.snapshot_times.add(values[0])
						values[6] = values[6][:-1]
						values = [optimistic_parse(v) for v in values]
						if values[0] - self.last_snapshot > SNAPSHOT_FREQUENCY:
							self.last_snapshot = values[0]
							snapshots.append(dict(zip(keys, values)))
				self.snapshot_tell = f.tell()

			response = requests.post(self.submit_url, json={
				'snapshots': snapshots,
				'status': status
			})

			for crash_name in os.listdir(crash_dir):
				if crash_name in self.submitted_crashes:
					continue
				self.submitted_crashes.add(crash_name)
				crash_path = os.path.join(crash_dir, crash_name)
				logger.info('Submitting crash %s' % crash_name)
				with open(crash_path, 'rb') as crash_file:
					requests.post(self.submit_crash + '?time=%d' % os.path.getmtime(crash_path), files={'file': crash_file})

			if response.json()['terminate']:
				logger.warn('Terminating instance %d' % self.id)
				requests.post('%s/fuzzers/terminate/%d' % (mothership_url, self.id))
				self.instance.terminate()
				self.upload_timer.cancel()
				return

		except Exception as e:
			# File not created yet
			logger.warn(e)
			traceback.print_exc()

		self.submit_timer = threading.Timer(SUBMIT_FREQUENCY, self.submit)
		self.submit_timer.daemon = True
		self.submit_timer.start()

	def join(self):
		if self.instance:
			self.instance.join()

def download_queue(download_url, directory, skip_dirs, executable_name=None):
	logger.info('Downloading campaign data from %s to %s' % (download_url, directory))

	try:
		response = requests.get(download_url).json()

		if executable_name:
			# Only download executable, libraries and testcases if this is the first time we run
			executable_path = os.path.join(directory, executable_name)
			urllib_request.urlretrieve(response['executable'], filename=executable_path)
			os.chmod(executable_path, 0o755)

			libraries_tar = os.path.join(directory, 'libraries.tar.gz')
			urllib_request.urlretrieve(response['libraries'], filename=libraries_tar)
			with tarfile.open(libraries_tar, 'r:') as tar:
				tar.extractall(directory)

			testcases_tar = os.path.join(directory, 'testcases.tar.gz')
			urllib_request.urlretrieve(response['testcases'], filename=testcases_tar)
			with tarfile.open(testcases_tar, 'r:') as tar:
				tar.extractall(directory)

		for download_sync_dir in response['sync_dirs']:
			sync_dir_name, _ = os.path.basename(download_sync_dir).rsplit('.', 1)
			if sync_dir_name in skip_dirs:
				continue
			extract_path = os.path.join(directory, 'sync_dir', sync_dir_name)
			try:
				os.makedirs(extract_path)
			except os.error as e:
				pass
			tar_path = os.path.join(directory, 'sync_dir', sync_dir_name + '.tar')
			urllib_request.urlretrieve(download_sync_dir, filename=tar_path)
			with tarfile.open(tar_path, 'r:') as tar:
				new_files = [t for t in tar.getmembers() if not os.path.exists(os.path.join(extract_path, t.name))]
				tar.extractall(extract_path, new_files)

		logger.info('Scheduling re-download in %d', response['sync_in'])
		download = threading.Timer(response['sync_in'], download_queue, (download_url, directory, skip_dirs))
		download.daemon = True
		download.start()

	except Exception as e:
		logger.warn(e)
		logger.warn('Retrying in 1 minute')
		traceback.print_exc()
		download = threading.Timer(60, download_queue, (download_url, directory, skip_dirs))
		download.daemon = True
		download.start()


def download_afl(mothership_url, directory):
	logger.info('Downloading afl-fuzz and libdislocator.so to %s', mothership_url)
	afl = os.path.join(directory, 'afl-fuzz')
	urllib_request.urlretrieve('%s/fuzzers/download/afl-fuzz' % mothership_url, filename=afl)
	os.chmod(afl, 0o755)

	libdislocator = os.path.join(directory, 'libdislocator.so')
	urllib_request.urlretrieve('%s/fuzzers/download/libdislocator.so' % mothership_url, filename=libdislocator)


def main(mothership_url, count):
	with tempdir('mothership_afl_') as directory:
		logger.info('Starting %d slave(s) in %s' % (count, directory))
		slaves = [MothershipSlave(mothership_url, directory) for _ in range(count)]
		campaigns = {slave.campaign_directory: slave for slave in slaves if slave.valid}

		if not campaigns:
			logger.warn('No valid campaigns')
			return

		download_afl(mothership_url, directory)
		for slave in campaigns.values():
			os.makedirs(slave.campaign_directory)
			if SHARE_WHEN_POSSIBLE:
				skip_dirs = [s.name for s in slaves if s.valid and s.campaign_id == slave.campaign_id]
			else:
				skip_dirs = [slave.name]
			download_queue(slave.download_url, slave.campaign_directory, skip_dirs, executable_name=slave.program)

		for slave in slaves:
			if slave.valid:
				slave.start()

		for slave in slaves:
			print('waiting on', slave)
			slave.join()
			print('finished waiting on', slave)


if __name__ == '__main__':
	try:
		mothership_url = sys.argv[1]
	except IndexError:
		mothership_url = 'http://localhost:5000'
	if not mothership_url.startswith('http'):
		mothership_url = 'http://' + mothership_url

	try:
		count = int(sys.argv[2])
	except IndexError:
		count = 1

	main(mothership_url, count)
	sys.exit()
