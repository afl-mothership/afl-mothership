#!/usr/bin/env python3
import asyncio
import json
import os
import random
import shutil
import tempfile

import functools
import requests
import subprocess
import sys
from textwrap import wrap
from itertools import zip_longest

import time

exploitable_path = '/usr/lib/python3.5/site-packages/exploitable-1.32-py3.5.egg/exploitable/exploitable.py'


class tempdir:
	def __init__(self, prefix='tmp'):
		self.prefix = prefix

	def __enter__(self):
		self.dir = tempfile.mkdtemp(prefix=self.prefix)
		return self.dir

	def __exit__(self, exc_type, exc_val, exc_tb):
		shutil.rmtree(self.dir)


async def analyse(temp_dir, args):
	gdbscript = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gdbscript.py')
	config = os.path.join(temp_dir, 'config.py')
	output = os.path.join(temp_dir, 'output.json')
	with open(config, 'w') as f:
		f.write('output = "%s"\n' % output)
		f.write('exploitable_path = "%s"\n' % exploitable_path)
	# TODO: set shell to /bin/sh
	proc = await asyncio.create_subprocess_exec(*(['gdb', '-n', '-batch', '--command', config, '--command', gdbscript, '--args'] + args), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	await proc.wait()
	with open(output, 'r') as f:
		result = json.loads(f.read())
	return Analysis(result)

class Analysis:
	def __init__(self, result):
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


def download_file(url, save_path):
	r = requests.get(url, stream=True)
	with open(save_path, 'wb') as f:
		for chunk in r.iter_content(chunk_size=1024):
			if chunk:
				f.write(chunk)

if __name__ == '__main__':
	mothership = sys.argv[1]
	count = int(sys.argv[2])

	queue = asyncio.Queue(3 * count)
	loop = asyncio.get_event_loop()

	# perf_counts = [0] * 2
	# perf_bucket = 0
	# perf_last = time.time()

	with tempdir(prefix='mothership_gdb_') as temp_dir:
		print(temp_dir)

		async def download_crashes():
			while True:
				analysis_queue = await loop.run_in_executor(None, requests.get, mothership + '/fuzzers/analysis_queue')
				for crash in random.sample(analysis_queue.json()['queue'], 10):
					crash_name = str(crash['crash_id'])
					print('downloading', crash_name)
					local_filename = os.path.join(temp_dir, crash_name)
					await loop.run_in_executor(None, download_file, crash['download'], local_filename)
					await queue.put((crash['crash_id'], local_filename))

		async def analyse_crashes(temp_dir):
			while True:
				crash_id, path = await queue.get()
				analysis = await analyse(temp_dir, ['./identify', path])  # TODO: fetch binary and args
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

				# global perf_bucket
				# global perf_last
				# perf_counts[perf_bucket] += 1
				# if time.time() - perf_last  > 10:
				# 	for _ in range(100):
				# 		print(perf_counts[perf_bucket] / 10, 'execs /s')
				# 	perf_counts[perf_bucket] = 0
				# 	perf_bucket = perf_bucket
				# 	perf_last = time.time()


		loop.create_task(download_crashes())
		names = ['worker_%d' % n for n in range(count)]
		for name in names:
			dir = os.path.join(temp_dir, name)
			os.makedirs(dir, exist_ok=True)
			loop.create_task(analyse_crashes(dir))
		loop.run_forever()




