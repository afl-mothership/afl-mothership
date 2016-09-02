#!/usr/bin/env python3
from __future__ import print_function

import logging
import os
import signal
import sys

from slave import *
# FIXME: just for pycharm
try:
	from slave.slave import *
except:
	pass
# FIXME: end

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler('slave.log')
logger.addHandler(file_handler)
# console_handler = logging.StreamHandler()
# logger.addHandler(console_handler)


active = True

class AflMasterInstance(AflInstance):

	def get_args(self, sync_dir, testcases):
		return [os.path.join(self.afl_directory, './afl-fuzz'), '-i', testcases, '-o', sync_dir, '-M', self.name] + self.afl_args

class MothershipMaster(MothershipSlave):

	def __init__(self, mothership_url, directory, master_of):
		self.master_of = master_of
		super(MothershipMaster, self).__init__(mothership_url, directory)

	def register(self, mothership_url):
		try:
			logger.info('Registering slave')
			request = requests.get(mothership_url + '/fuzzers/register?hostname=%s&master=%d' % (socket.gethostname(), self.master_of))
			if request.status_code == 404:
				raise Exception('No more campaigns requiring fuzzers')
			elif request.status_code == 400:
				raise Exception('Could not become master: %s' % request.text)
			return request.json()
		except requests.ConnectionError as e:
			raise Exception('Could not connect to %s' % mothership_url, e)

	def start(self):
		logger.info('Starting master fuzzer in %s' % self.own_dir)
		self.instance = AflMasterInstance(
			self.directory,
			self.campaign_directory,
			self.name,
			self.args,

			self.program,
			self.program_args,
		)
		self.instance.daemon = True

		logger.info('Upload in %d', self.upload_in)
		self.upload_timer = threading.Timer(self.upload_in, self.upload_queue)
		self.upload_timer.daemon = True

		self.submit_timer = threading.Timer(SUBMIT_FREQUENCY, self.submit)
		self.submit_timer.daemon = True

		self.instance.start()
		self.upload_timer.start()
		self.submit_timer.start()

	def upload_queue(self):
		global active
		if active:
			super(MothershipMaster, self).upload_queue()
		else:
			self.upload_timer = threading.Timer(60, self.upload_queue)
			self.upload_timer.daemon = True
			self.upload_timer.start()

	def submit(self):
		global active
		if active:
			super(MothershipMaster, self).submit()
		else:
			self.upload_timer = threading.Timer(60, self.submit)
			self.upload_timer.daemon = True
			self.upload_timer.start()

def run_master(mothership_url, workingdir, master_of):
	with tempdir(workingdir, 'mothership_afl_master_') as directory:
		logger.info('Starting master in %s' % (directory,))
		master = MothershipMaster(mothership_url, directory, master_of)

		os.makedirs(master.campaign_directory)
		download_afl(mothership_url, directory)
		download_queue(master.download_url, master.campaign_directory, [], executable_name=master.program)

		master.start()
		while not master.instance.process:
			time.sleep(1)

		global active
		while not master.instance.process.poll():
			#time.sleep(5 * 60)
			time.sleep(10)
			try:
				campaign_active = requests.get(mothership_url + '/fuzzers/is_active/%d' % master_of).json()['active']
			except Exception:
				continue
			if active != campaign_active:
				if campaign_active:
					logger.warn('Resuming master')
					os.kill(master.instance.process.pid, signal.SIGCONT)
				else:
					logger.warn('Pausing master')
					os.kill(master.instance.process.pid, signal.SIGSTOP)
				active = campaign_active

		master.join()


def main():
	mothership_url = sys.argv[1]
	if not mothership_url.startswith('http'):
		mothership_url = 'http://' + mothership_url

	master_of = int(sys.argv[2])

	try:
		workingdir = sys.argv[3]
	except IndexError:
		workingdir = '/tmp/'

	try:
		os.mkdir('logs')
	except:
		pass
	run_master(mothership_url, workingdir, master_of)
	logger.info('exiting')
	sys.exit()

if __name__ == '__main__':
	main()