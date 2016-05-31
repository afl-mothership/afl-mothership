#!/usr/bin/env python3
# import q

import json
import os
import shutil
import subprocess
import tempfile
import requests
from textwrap import wrap
from urllib import request as urllib_request
from itertools import zip_longest

import sys

exploitable_path = '/usr/lib/python3.5/site-packages/exploitable-1.32-py3.5.egg/exploitable/exploitable.py'


class tempdir:
	def __init__(self, prefix='tmp'):
		self.prefix = prefix

	def __enter__(self):
		self.dir = tempfile.mkdtemp(prefix=self.prefix)
		return self.dir

	def __exit__(self, exc_type, exc_val, exc_tb):
		shutil.rmtree(self.dir)


class Analysis:
	def __init__(self, args, temp_dir=None):
		path = os.path.dirname(os.path.abspath(__file__))
		gdbscript = os.path.join(path, 'gdbscript.py')

		if temp_dir:
			result = self.get_result(args, gdbscript, temp_dir)
		else:
			with tempdir(prefix='mothership_gdb_') as my_temp_dir:
				result = self.get_result(args, gdbscript, my_temp_dir)

		self.exploitable = {}
		if result['crash']:
			self.crash = True
			for line in result['exploitable']:
				if not line:
					continue
				field, value = line.split(': ')
				self.exploitable[field] = value
			self.frames = [
				{
					**frame,
					'description': elem
				} for frame, elem in zip_longest(result['frames'], result['bt'])
			]
			self.faulting_instruction = result['faulting instruction']
			self.pc = result['pc']
		else:
			self.crash = False

	def get_result(self, args, gdbscript, temp_dir):
		config = os.path.join(temp_dir, 'config.py')
		output = os.path.join(temp_dir, 'output.json')
		with open(config, 'w') as f:
			f.write('output = "%s"\n' % output)
			f.write('exploitable_path = "%s"\n' % exploitable_path)
		subprocess.run(['gdb', '-n', '-batch', '--command', config, '--command', gdbscript, '--args'] + args)
		with open(output, 'r') as f:
			result = json.loads(f.read())
		return result

	def print(self):
		print()

		def str_dict(d):
			s = ''
			for k, v in sorted(d.items()):
				if type(v) is str:
					space = '\n\t  ' + ' ' * len(k)
					v = space.join(wrap(v, width=120))
				s += '\t%s: %s\n' % (k, v)
			return s

		if self.crash:
			print('PC: ', hex(self.pc))
			print('\t' + self.faulting_instruction)
			print('Exploitable: ')
			print(str_dict(self.exploitable))
			print('Frames:')
			print('\n'.join(str_dict(frame) for frame in self.frames))
		else:
			print('No crash')

if __name__ == '__main__':
	mothership = 'http://ragnarok:5000'

	while True:
		queue = requests.get(mothership + '/fuzzers/analysis_queue').json()['queue']
		if not queue:
			print('Queue empty - we\'re done here!')
			break
		crash_id = queue[0]['crash_id']
		download = queue[0]['download']

		with tempdir(prefix='mothership_gdb_') as temp_dir:
			sample = os.path.join(temp_dir, 'sample')
			urllib_request.urlretrieve(download, filename=sample)
			analysis = Analysis(['identify', sample])
			print('Crash:', crash_id)
			if analysis.crash:
				result = {
					'crash': True,
					'pc': analysis.pc,
					'faulting instruction': analysis.faulting_instruction,
					'exploitable': analysis.exploitable,
					'frames': analysis.frames
				}
			else:
				result = {
					'crash': False
				}
			requests.post('%s/fuzzers/submit_analysis/%d' % (mothership, crash_id), json=result)

