import datetime
from collections import defaultdict
from itertools import tee
from math import ceil
from operator import itemgetter
from statistics import mean

from flask import Blueprint, jsonify, request, render_template
from sqlalchemy import desc
from sqlalchemy.orm.attributes import InstrumentedAttribute

from mothership import models
from sqlalchemy import func



graphs = Blueprint('graphs', __name__)

def get_starts(fuzzers):
	"""
	Compute the list of start times for a list of fuzzers so that the series of

	fuzzers[n].snapshots[0...m].unix_time - get_starts(fuzzers)[n]

	does not include gaps when no fuzzers where running

	:param fuzzers: the list of fuzzers to compute the start times for
	:return: the list of start values
	"""
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

def get_activity_periods(instances):
	r = []
	start = 0
	running = 0
	duration = 0
	startstop_events = sorted(
		[(i, i.snapshots.order_by(models.FuzzerSnapshot.unix_time).first().unix_time, True) for i in instances] +
		[(i, i.snapshots.order_by(desc(models.FuzzerSnapshot.unix_time)).first().unix_time, False) for i in instances],
		key=itemgetter(1))
	for instance, t, event in startstop_events:
		if event:
			if not running:
				instances = []
				start = t
			instances.append(instance)
			running += 1
		else:
			running -= 1
			if not running:
				r.append((start, t, instances))
				duration += t - start
	return r, duration

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


@graphs.route('/graphs/campaign/<int:campaign_id>/<property_name>')
def snapshot_property(campaign_id, property_name):
	if not hasattr(models.FuzzerSnapshot, property_name) or not type(getattr(models.FuzzerSnapshot, property_name)) is InstrumentedAttribute:
		return 'Snapshot does not have property "%s"' % property_name, 400

	campaign = models.Campaign.get(id=campaign_id)
	if not campaign.started or not campaign.fuzzers or not any(fuzzer.snapshots.first() for fuzzer in campaign.fuzzers):
		return jsonify()

	fuzzers = campaign.fuzzers.filter(models.FuzzerInstance.execs_done > 0)
	master = campaign.master_fuzzer

	data = []
	master_data = []
	activity_periods, _ = get_activity_periods(fuzzers.filter_by(master=False))
	running_time = 0
	for start, stop, instances in activity_periods:
		for fuzzer in instances:
			data.append((
				fuzzer.name, [(
					((snapshot.unix_time - start) + running_time) * 1000,
					getattr(snapshot, property_name)
				) for snapshot in fuzzer.snapshots.with_entities(models.FuzzerSnapshot.unix_time, getattr(models.FuzzerSnapshot, property_name))]
			))
		if master:
			master_snapshots = master.snapshots.filter(start < models.FuzzerSnapshot.unix_time, models.FuzzerSnapshot.unix_time < stop)
			for snapshot in master_snapshots.with_entities(models.FuzzerSnapshot.unix_time, getattr(models.FuzzerSnapshot, property_name)):
				master_data.append((((snapshot.unix_time - start) + running_time) * 1000, getattr(snapshot, property_name)))
		running_time += stop - start
	if master:
		data.append((
			'Master Instance',
			master_data
		))
	return graph(property_name.replace('_', ' ').title(), data, legend=False)


@graphs.route('/graph')
def render_graph():
	url = request.args.get('url')
	if not url:
		return 'Specify a graph URL in the request', 400
	return render_template('graph.html', url=request.host_url[:-1] + url)

