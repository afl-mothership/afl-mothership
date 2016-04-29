import os
import sys
from pprint import pprint
import requests


def slist(l):
	return ', '.join(l)


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
			snapshots.append(dict(zip(keys, values)))

	pprint(status)
	r = requests.get(mothership + '/fuzzers/register?hostname=imported')
	pprint(r.json())
	instance = r.json()['id']
	requests.post(mothership + '/fuzzers/submit/%d' % instance, json={
		'snapshots': snapshots,
		'status': status
	})

if __name__ == '__main__':
	main()