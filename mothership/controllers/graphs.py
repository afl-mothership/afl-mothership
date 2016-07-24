import statistics
from collections import defaultdict

import time
from flask import Blueprint, jsonify, request, render_template
from sqlalchemy import desc
from sqlalchemy.orm import aliased
from sqlalchemy.orm.attributes import InstrumentedAttribute

from mothership import models
from sqlalchemy import func

graphs = Blueprint('graphs', __name__)


# def trace(snapshots, property_name, starttime=None):
# 	try:
# 		start = snapshots[0].unix_time
# 	except IndexError:
# 		return {}
# 	if starttime:
# 		start = starttime
# 	x = []
# 	y = []
# 	for snapshot in snapshots:
# 		x.append((snapshot.unix_time-start)*1000)
# 		y.append(getattr(snapshot, property_name))
# 	return {'x': x, 'y': y}
# def crashes_at(fuzzer, time):
# 	q = models.Crash.query.filter(models.Crash.created < time).filter()
# 	print(q)
# 	return q.count()

def get_starts(fuzzers):
	"""
	Compute the list of start times for a list of fuzzers so that the series of

	fuzzers[n].snapshots[0...m].unix_time - get_starts(fuzzers)[n]

	does not include gaps when no fuzzers where running

	:param fuzzers: the list of fuzzers to compute the start times for
	:return: the list of start values
	"""
	#run_times = [(f.start_time, f.snapshots.order_by(desc(models.FuzzerSnapshot.unix_time)).first().unix_time) for f in fuzzers]
	run_times = [(f.start_time, f.last_update) for f in fuzzers]
	start, stop = run_times[0]
	starts = []
	for run_time, fuzzer in zip(run_times, fuzzers):
		n_start, n_stop = run_time
		if n_start > stop:
			start += n_start - stop
		stop = n_stop
		starts.append(start)
	return starts

def unique_crashes(campaign_id, consider_unique, **crash_filter):
	r = []
	s = set()
	for crash in models.Crash.all(campaign_id=campaign_id, crash_in_debugger=True, **crash_filter).order_by(models.Crash.created):
		if getattr(crash, consider_unique) in s:
			continue
		s.add(getattr(crash, consider_unique))
		r.append(crash)
	return r

def get_distinct(campaign, consider_unique, **crash_filter):
	r = []
	fuzzers = [f for f in campaign.fuzzers.order_by(models.FuzzerInstance.start_time) if f.started]
	starts = dict(zip((f.id for f in fuzzers), get_starts(fuzzers)))
	last_created, last_crashes, this_crashes = 0, 0, 0
	for crash in unique_crashes(campaign.id, consider_unique, **crash_filter):
		created = (crash.created - starts[crash.instance_id]) * 1000
		if last_created == created:
			this_crashes += 1
		else:
			r.append([last_created, last_crashes])
			r.append([last_created + 1, this_crashes])
			last_created, last_crashes, this_crashes = created, this_crashes, this_crashes + 1
	r.append([(fuzzers[-1].last_update - starts[fuzzers[-1].id]) * 1000, last_crashes])
	return r


def graph(title, series, chart_type='line', legend=True):
	return jsonify(
		chart={
			'type': chart_type
		},
		title={
			'text': title
		},
		series=[{
			'name': data[0],
			'data': data[1],
			'type': data[2] if data[2:] else chart_type,
		} for data in series],
		xAxis={
			'type': 'datetime',
			'title': {
				'text': 'Duration'
			}
		},
		yAxis={
			'title': {
				'text': title
			}
		},
		legend={
			'enabled': legend
		}
	)


# @graphs.route('/graphs/campaign/<int:campaign_id>/heatmap')
# def heatmap(campaign_id):
# 	campaign = models.Campaign.get(id=campaign_id)
# 	if not campaign.started:
# 		return jsonify()
# 	# start = get_starts(campaign.fuzzers)[0]
# 	crashes = defaultdict(int)
# 	addresses = set()
# 	# maxcrash = 0
# 	for crash in campaign.crashes.filter(models.Crash.address != None):
# 		location = crash.backtrace
# 		# if crash.address > 100000000000000:
# 		# 	from pprint import pprint
# 		# 	print()
# 		# 	print(crash.address)
# 		# 	pprint(list(frame for frame in crash.get_frames()))
# 		# 	break
# 		# 	location = crash.get_frames()[0]['function']
# 		# 	continue
# 		# maxcrash = max(maxcrash, crash.address)
# 		# + ' (' + (crash.get_frames()[0]['function'] or '??') + ')'
#
# 		addresses.add(location)
# 		crashes[(location, ((crash.created - crash.fuzzer.start_time) // (12*60*60)) )] += 1
# 	# crashes2 = defaultdict(int)
# 	# for (address, time), count in crashes.items():
# 	# 	crashes2[(address//20000, time)] += count
# 	# crashes = crashes2
# 	# crashes = {(k[0], )}
# 	addresses = sorted(addresses)
# 	categories = [str(x) for x in addresses]
# 	return jsonify(
# 		chart= {
# 			'type': 'heatmap',
# 			# marginTop: 40,
# 			# marginBottom: 80,
# 			# plotBorderWidth: 1
# 		},
# 		colorAxis= {
# 			'min': 0,
# 			'max': 25,
# 			'minColor': '#0000FF',
# 			'maxColor': '#FF0000'
# 			# startOnTick: false,
# 			# endOnTick: false,
# 			# labels: {
# 			# 	 format: '{value}℃'
# 			# }
# 		},
# 		series= [{
# 			'colsize': 1,
# 			'data': [
# 				[addresses.index(k[0]), k[1], v] for k, v in sorted(crashes.items(), key=lambda x: x[0])
# 			]
# 		}],
# 		# yAxis= {
# 		# 	'type': 'datetime',
# 		# 	'min': 0,
# 		# 	'max': 24*60*60*1000,
# 		# },
# 		xAxis= {
# 			# 'tickLength': 500
# 			#'categories': categories,
#
# 			# 'min': 0,
# 			# 'max': 100
# 		}
# 	)


@graphs.route('/graphs/campaign/<int:campaign_id>/aggregated')
def aggregated(campaign_id):
	campaign = models.Campaign.get(id=campaign_id)
	if not campaign.started or not models.Crash.get(campaign_id=campaign_id, analyzed=True):
		return jsonify()
	return graph('Crashes', [
		#('Distinct Addresses', get_distinct(campaign, 'address')),
		('Distinct Backtraces', get_distinct(campaign, 'backtrace'))
	])


# @graphs.route('/graphs/campaign/<int:campaign_id>/breakdown')
# def breakdown(campaign_id):
# 	campaign = models.Campaign.get(id=campaign_id)
# 	if not campaign.started or not models.Crash.get(campaign_id=campaign_id):
# 		return jsonify()
# 	crashes = models.Crash.query \
# 		.filter_by(campaign_id=campaign.id, analyzed=True, crash_in_debugger=True) \
# 		.group_by(models.Crash.backtrace, models.Crash.instance_id) \
# 		.order_by(models.Crash.instance_id)
# 	counted = set()
# 	results = defaultdict(int)
# 	for crash in crashes:
# 		if crash.backtrace not in counted:
# 			results[crash.instance_id] += 1
# 			counted.add(crash.backtrace)
# 	return graph(
# 		'Return Per Fuzzer',
# 		#**{str(k): v for k, v in results.items()},
# 		chart_type='column'
# 	)

	# fuzzers = [f for f in campaign.fuzzers.order_by(models.FuzzerInstance.start_time) if f.started]
	# fuzzer_map = {f.id: f for f in fuzzers}
	# starts = dict(zip((f.id for f in fuzzers), get_starts(fuzzers)))
	# results = defaultdict(lambda: [0, 0, 0, []])  # last_created, last_crashes, this_crashes, series
	# for crash in unique_crashes(campaign.id, 'backtrace'):
	# 	created = (crash.created - starts[crash.instance_id]) * 1000
	# 	last_created, last_crashes, this_crashes, series = results[crash.instance_id]
	# 	if last_created == created:
	# 		this_crashes += 1
	# 	else:
	# 		series.append([last_created, last_crashes])
	# 		series.append([last_created + 1, this_crashes])
	# 		last_created, last_crashes, this_crashes = created, this_crashes, this_crashes + 1
	# 	results[crash.instance_id] = last_created, last_crashes, this_crashes, series
	# for instance_id in results:
	# 	last_created, last_crashes, this_crashes, series = results[instance_id]
	# 	results[instance_id][3].append([(fuzzer_map[instance_id].last_update - starts[instance_id]) * 1000, last_crashes])
	# return graph('Distinct Addresses', [
	# 	(str(instance_id), series) for instance_id, (last_created, last_crashes, this_crashes, series) in results.items()
	# ])


# @graphs.route('/graphs/campaign/<int:campaign_id>/fuzzer_overlap')
# def fuzzer_overlap(campaign_id):
# 	campaign = models.Campaign.get(id=campaign_id)
# 	if not campaign.started or not models.FuzzerSnapshot.get(campaign_id=campaign_id):
# 		return jsonify()
# 	return graph('', [])


@graphs.route('/graphs/campaign/<int:campaign_id>/<property_name>')
def snapshot_property(campaign_id, property_name):
	if not hasattr(models.FuzzerSnapshot, property_name) or not type(getattr(models.FuzzerSnapshot, property_name)) is InstrumentedAttribute:
		return 'Snapshot does not have property "%s"' % property_name, 400

	campaign = models.Campaign.get(id=campaign_id)
	if not campaign.started or not campaign.fuzzers or not any(fuzzer.snapshots.first() for fuzzer in campaign.fuzzers):
		return jsonify()

	mode = request.args.get('mode', 'multi')
	fuzzers = campaign.fuzzers.filter(models.FuzzerInstance.last_update)
	if mode == 'multi':
		data = [(
			fuzzer.name,
			[[
				(snapshot.unix_time - start) * 1000,
				getattr(snapshot, property_name)
			] for snapshot in fuzzer.snapshots.with_entities(models.FuzzerSnapshot.unix_time, getattr(models.FuzzerSnapshot, property_name))]
		) for start, fuzzer in zip(get_starts(fuzzers), fuzzers)]
	elif mode == 'avg':
		data = {}
		#sub = models.db_session.query(func.min(crash_alias.created)).filter(getattr(models.Crash, consider_unique) == getattr(crash_alias, consider_unique))
		sub = models.FuzzerInstance.all().filter_by(campaign_id=campaign_id).with_entities(models.FuzzerInstance.id)
		q = models.FuzzerSnapshot.all().filter(models.FuzzerSnapshot.instance_id.in_(sub), models.FuzzerSnapshot.id % 10 == 0)


		ts = {fuzzer.id: {} for fuzzer in fuzzers}
		for x in q:
			ts[x.instance_id].append([x.unix_time, getattr(x, property_name)])

		data = [
			[name, data] for name, data in ts.items()
		]

		#print(len(list(q)))
		# start = campaign.fuzzers.order_by(models.FuzzerInstance.start_time).first().start_time
		# end = campaign.fuzzers.order_by(desc(models.FuzzerInstance.last_update)).first().last_update
		#
		# print(start, end)
		# steps = 32
		# print(list(range(start, end, (end - start) // steps)))
		#
		# data = []
		# for step_time in range(start, end, (end - start) // steps):
		# 	ddata = []
		# 	print(step_time)
		# 	for fuzzer in campaign.fuzzers:
		# 		print(fuzzer.snapshots.with_entities(models.FuzzerSnapshot.unix_time, getattr(models.FuzzerSnapshot, property_name)))
		# 		snapshot = fuzzer.snapshots.filter(models.FuzzerSnapshot.unix_time < step_time).order_by(desc(models.FuzzerSnapshot.unix_time)).first()
		# 		ddata.append(getattr(snapshot, property_name) if snapshot else 0)
		# 	data.append([(step_time - start) * 1000, min(ddata) if ddata else 0, max(ddata) if ddata else 0])
		# print(data)
		# data = [['avg', data, 'arearange']]
		# for fuzzer in campaign.fuzzers:
		# 	for snapshot in fuzzer.snapshots.with_entities(models.FuzzerSnapshot.unix_time, getattr(models.FuzzerSnapshot, property_name)):
		# 		data[snapshot.unix_time]


	return graph(property_name.replace('_', ' ').title(), data, legend=False)



@graphs.route('/graph')
def render_graph():
	url = request.args.get('url')
	if not url:
		return 'Specify a graph URL in the request', 400
	return render_template('graph.html', url=request.host_url[:-1] + url)


@graphs.route('/graph/staticdata')
def staticdata():
	return open('C:\\tools\\foo.txt').read()