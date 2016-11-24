#!/usr/bin/env python
from __future__ import print_function

import os
try:
	import queue
except ImportError:
	import Queue as queue
import shutil
import subprocess
import sys
import signal
import tarfile
import tempfile
import threading
import requests
import logging
import json
import atexit
import time

try:
	from urllib import request as urllib_request
except ImportError:
	import urllib as urllib_request

logging.basicConfig(level=logging.DEBUG, format="[%(levelname)10s: %(filename)25s - %(funcName)25s() ] %(message)s")
exploitable_path = '/usr/lib/python3.5/site-packages/exploitable-1.32-py3.5.egg/exploitable/exploitable.py'


class tempdir:
	def __init__(self, prefix='tmp'):
		self.prefix = prefix

	def __enter__(self):
		self.dir = tempfile.mkdtemp(prefix=self.prefix)
		return self.dir

	def __exit__(self, exc_type, exc_val, exc_tb):
		shutil.rmtree(self.dir)


def feed_queue(dest_dir, queue, queue_url, campaign_id):
	s = requests.Session()
	while True:
		logger.debug('fetching %s', queue_url)
		analysis_queue = s.get(queue_url).json()['crashes']
		for crash in analysis_queue:
			crash_name = str(crash['crash_id'])
			logger.info('downloading %s', crash_name)
			local_filename = os.path.join(dest_dir, crash_name)
			urllib_request.urlretrieve(crash['download'], filename=local_filename)
			logger.debug('%d crashes waiting', queue.qsize())
			queue.put((crash['crash_id'], local_filename))

def submit_results(queue, submit_url):
	s = requests.Session()
	while True:
		crash_id, result = queue.get()
		logger.debug('%d results waiting', queue.qsize())
		logger.debug('submitting %d', crash_id)
		logger.info(result)
		_ = s.post(submit_url % crash_id, data=json.dumps(result), headers={'content-type': 'application/json'}).content

def gdb_main():
	global logger
	logger = logging.getLogger('gdb')
	logger.info('gdb started')

	sys.path.append(os.path.dirname(exploitable_path))
	gdb.execute('source %s' % exploitable_path)

	gdb.execute('handle SIGALRM stop', to_string=True)
	class ALRMBreakpoint(gdb.Breakpoint):
		def stop(self):
			logger.info('reached _init')
			gdb.execute('call alarm(5)')
			return False
	ALRMBreakpoint('_init')

	analysis_queue = requests.get(queue_url).json()['crashes']

	for crash in analysis_queue:
		crash_name = str(crash['crash_id'])
		logger.info('downloading %s', crash_name)
		logger.info('downloading %s', crash_name)
		crash_path = os.path.join(dir, crash_name)
		urllib_request.urlretrieve(crash['download'], filename=crash_path)

		crash_id = crash['crash_id']

		logger.info('analysing crash %d', crash_id)

		# TODO: complex running syntax
		gdb.execute('set args 4 1 0 < "%s"' % crash_path)
		#gdb.execute('set args -r "%s"' % crash_path)

		logger.debug('starting executable')

		logger.info(gdb.execute('run', to_string=True))
		logger.debug('executable stopped')

		frames = []
		try:
			frame = gdb.newest_frame()
		except gdb.error:
			result = {
				'crash': False
				# TODO: store exit code from run
			}
			logger.info('submitting crash: %d result: no crash', crash_id)
		else:
			while frame:
				frames.append(frame)
				frame = frame.older()

			bt = gdb.execute('bt 50', to_string=True).split('\n')[:-1]

			# gobble some excess output
			gdb.execute('exploitable', to_string=True)

			exploitable = {}
			for line in gdb.execute('exploitable', to_string=True).split('\n'):
				if not line:
					continue
				logger.info(line)
				field, value = line.split(': ', 1)
				exploitable[field] = value

			result = {
				'crash': True,
				'pc': int(gdb.parse_and_eval('$pc')),
				'faulting instruction': gdb.execute('x/i $pc', to_string=True)[3:],
				'exploitable': exploitable,
				'frames': [{
					'address': frame.pc(),
					'function': frame.name(),
					'filename': frame.function().symtab.fullname() if frame.function() else None,
					'description': backtrace
				} for frame, backtrace in zip(frames, bt)]
			}
			logger.info('submitting crash: %d result: crash @ %s', crash_id, hex(result['pc']))

		#logger.info(result)
		_ = requests.post(submit_url % crash_id, data=json.dumps(result), headers={'content-type': 'application/json'}).content
		os.remove(crash_path)


def main():
	global logger
	logger = logging.getLogger('main')

	mothership = sys.argv[1]
	if not mothership.startswith('http'):
		mothership = 'http://' + mothership
	campaign = int(sys.argv[2])
	if len(sys.argv) > 3:
		global exploitable_path
		exploitable_path = sys.argv[3]
	logger.debug('using exploitable_path = %s', exploitable_path)

	with tempdir('mothership_gdb_') as dir:
		logger.info('operating out of %s', dir)

		# TODO: support complex running syntax and custom program names

		executable_url = '%s/fuzzers/download/%d/executable' % (mothership, campaign)
		logger.debug('fetching %s', executable_url)
		executable = os.path.join(dir, 'executable')
		urllib_request.urlretrieve(executable_url, filename=executable)
		os.chmod(executable, 0o755)

		libraries_url = '%s/fuzzers/download/%d/libraries.tar' % (mothership, campaign)
		logger.debug('fetching %s', libraries_url)
		libraries = os.path.join(dir, 'libraries')
		os.mkdir(libraries)
		libraries_tar = os.path.join(dir, 'libraries.tar.gz')
		urllib_request.urlretrieve(libraries_url, filename=libraries_tar)
		with tarfile.open(libraries_tar, 'r:') as tar:
			for file in tar.getmembers():
				if not file.isdir():
					with open(os.path.join(libraries, os.path.basename(file.name)), 'wb') as f:
						f.write(tar.extractfile(file).read())

		env = dict(os.environ)
		env['LD_LIBRARY_PATH'] = libraries
		env['SHELL'] = '/bin/sh'

		# FIXME: on AWS
		# debuginfo-install glibc
		# env['LD_PRELOAD'] = '/lib64/libpthread.so.0'

		config = os.path.join(dir, 'config.py')
		with open(config, 'w') as f:
			f.write('submit_url = "%s/fuzzers/submit_analysis/%%d"\n' % mothership)
			f.write('queue_url = "%s/fuzzers/analysis_queue/%d"\n' % (mothership, campaign))
			f.write('campaign_id = %d\n' % campaign)
			f.write('dir = "%s"\n' % dir)
			f.write('exploitable_path = "%s"\n' % exploitable_path)

		logger.debug('written %s', config)

		logger.info('starting gdb')
		args = ['gdb', '-n', '-batch', '--command', config, '--command', os.path.abspath(__file__), executable]
		logger.info(' '.join(args))
		if False:
			# FIXME: use dry run args
			exit(0)
		p = subprocess.Popen(args, env=env, stdout=subprocess.PIPE)  # , stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)
		atexit.register(p.terminate)
		try:
			p.wait()
		except KeyboardInterrupt:
			pass
		finally:
			logger.warn('TERMINATING')
			p.terminate()
			time.sleep(1)
			p.kill()


if 'gdb' in locals():
	gdb_main()
elif __name__ == '__main__':
	main()
