import os
import sys
from pprint import pprint
import requests
import threading


def optimistic_parse(value):
	for t in [int, float]:
		try:
			return t(value)
		except ValueError:
			pass
	if '%' in value:
		return optimistic_parse(value.replace('%', ''))
	return value

def main():
	mothership = 'http://localhost:5000'
	if len(sys.argv) > 2:
		mothership = sys.argv[2]
	status_file = os.path.join(sys.argv[1], 'fuzzer_stats')
	plot_file = os.path.join(sys.argv[1], 'plot_data')

	status = {}
	with open(status_file, 'r') as f:
		for line in f.readlines():
			key, value = line.replace('\n', '').split(':')
			status[key.strip()] = optimistic_parse(value[1:])

	snapshots = []
	with open(plot_file, 'r') as f:
		keys = f.readline()[2:-1].split(', ')
		for line in f.readlines():
			values = line[:-1].split(', ')
			values[6] = values[6][:-1]
			snapshot = dict(zip(keys, values))
			snapshots.append(snapshot)

	r = requests.get(mothership + '/fuzzers/register?hostname=imported')
	pprint(r.json())
	instance = r.json()['id']
	requests.post('%s/fuzzers/submit/%d' % (mothership, instance), json={
		'snapshots': snapshots,
		'status': status
	})

	sem = threading.Semaphore(25)

	def submit_crash(crash_path):
		with sem:
			print(os.path.basename(crash_path))
			with open(crash_path, 'rb') as crash_file:
				requests.post('%s/fuzzers/submit_crash/%d?time=%d' % (mothership, instance, os.path.getmtime(crash_path)), files={'file': crash_file})

	crash_dir = os.path.join(sys.argv[1], 'crashes')
	crashes = os.listdir(crash_dir)
	for crash_name in crashes:
		if crash_name == 'README.txt':
			continue
		crash_path = os.path.join(crash_dir, crash_name)
		threading.Thread(target=submit_crash, args=(crash_path,)).start()


if __name__ == '__main__':
	main()