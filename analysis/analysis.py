#!/usr/bin/env python3
# import q

import json
import os
import shutil
import subprocess
import tempfile
from queue import Full

import requests
from textwrap import wrap
from urllib import request as urllib_request
from itertools import zip_longest
from multiprocessing import Process, Queue

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
		subprocess.run(['gdb', '-n', '-batch', '--command', config, '--command', gdbscript, '--args'] + args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
	mothership = sys.argv[1]  # 'http://ragnarok:5000'
	count = int(sys.argv[2])

	queue = Queue(10 * count)

	with tempdir(prefix='mothership_gdb_') as temp_dir:
		print(temp_dir)

		def download_file(url):
			crash_id = url.split('/')[-1]
			local_filename = os.path.join(temp_dir, crash_id)
			r = requests.get(url, stream=True)
			with open(local_filename, 'wb') as f:
				for chunk in r.iter_content(chunk_size=1024):
					if chunk:
						f.write(chunk)
			return local_filename

		def analyse(queue):
			while True:
				crash_id, path = queue.get()
				analysis = Analysis(['identify', path])
				if analysis.crash:
					print(crash_id, 'crashed at:', analysis.pc)
					result = {
						'crash': True,
						'pc': analysis.pc,
						'faulting instruction': analysis.faulting_instruction,
						'exploitable': analysis.exploitable,
						'frames': analysis.frames
					}
				else:
					print(crash_id, 'did not crash')
					result = {
						'crash': False
					}
				requests.post('%s/fuzzers/submit_analysis/%d' % (mothership, crash_id), json=result)

		for _ in range(count):
			p = Process(target=analyse, args=(queue,))
			p.start()

		while True:
			analysis_queue = requests.get(mothership + '/fuzzers/analysis_queue').json()['queue']
			if not analysis_queue:
				break
			for crash in analysis_queue[:10]:
				path = download_file(crash['download'])
				crash_id = crash['crash_id']
				print('downloaded', crash_id)
				queue.put((crash_id, path))
		print('Queue empty - we\'re done here!')
		exit(0)



