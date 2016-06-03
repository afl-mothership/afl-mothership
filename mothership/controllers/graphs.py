from collections import defaultdict

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
	run_times = [(f.start_time, f.snapshots.order_by(desc(models.FuzzerSnapshot.unix_time)).first().unix_time) for f in fuzzers]
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




@graphs.route('/graphs/campaign/<int:campaign_id>/aggregated')
def aggregated(campaign_id):
	campaign = models.Campaign.get(id=campaign_id)
	if not campaign.started or not models.Crash.get(campaign_id=campaign_id):
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

	fuzzers = [f for f in campaign.fuzzers.order_by(models.FuzzerInstance.start_time) if f.started]
	return graph(property_name.replace('_', ' ').title(), [(
		fuzzer.name,
		[[
			(snapshot.unix_time - start) * 1000,
			getattr(snapshot, property_name)
		] for snapshot in fuzzer.snapshots]
	) for start, fuzzer in zip(get_starts(fuzzers), fuzzers)], legend=False)


@graphs.route('/graph')
def render_graph():
	url = request.args.get('url')
	if not url:
		return 'Specify a graph URL in the request', 400
	return render_template('graph.html', url=url)
