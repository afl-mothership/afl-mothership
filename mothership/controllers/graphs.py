from flask import Blueprint, jsonify
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

def get_distinct(campaign, start=0):
	r = []
	# start = 0
	crash_alias = aliased(models.Crash)
	sub = models.db_session.query(func.min(crash_alias.created)).filter(models.Crash.address == crash_alias.address)
	for crash in models.Crash.query.filter(models.Crash.created == sub).filter_by(campaign_id=campaign.id, crash_in_debugger=True).order_by(models.Crash.created):
		c = len(r) // 2
		created = (crash.created - start) * 1000
		r.append([created - 1, c])
		r.append([created, c + 1])
	#print(campaign.fuzzers.order_by(models.FuzzerInstance.last_update))
	r.append([(campaign.fuzzers.order_by(desc(models.FuzzerInstance.last_update)).first().last_update - start) * 1000, len(r) // 2])
	return r

@graphs.route('/graphs/campaign/<int:campaign_id>/distinct_addresses')
def graph_campaign_addresses(campaign_id):
	campaign = models.Campaign.get(id=campaign_id)
	if not campaign.started:
		return jsonify()
	start = min(fuzzer.start_time for fuzzer in campaign.fuzzers if fuzzer.start_time)
	return jsonify(
		title={
			'text': 'Distinct Addresses'
		},
		series=[{
			'name': 'All Fuzzers',
			'data': get_distinct(campaign, start=start)
		}],
		xAxis={
			'type': 'datetime',
			'title': {
				'text': 'Duration'
			}
		},
		yAxis={
			'title': {
				'text': 'Distinct Addresses'
			}
		}
	)


@graphs.route('/graphs/campaign/<int:campaign_id>/<property_name>')
def graph_campaign(campaign_id, property_name):
	if not hasattr(models.FuzzerSnapshot, property_name) or not type(getattr(models.FuzzerSnapshot, property_name)) is InstrumentedAttribute:
		return 'Snapshot does not have property "%s"' % property_name, 400

	campaign = models.Campaign.get(id=campaign_id)
	if not campaign.started:
		return jsonify()
	start = min(fuzzer.start_time for fuzzer in campaign.fuzzers if fuzzer.start_time)
	series = []
	fuzzers = campaign.fuzzers.order_by(models.FuzzerInstance.start_time)
	return jsonify(
		title={
			'text': property_name.replace('_', ' ').title()
		},
		series=[{
			'name': fuzzer.name,
			'data': [[
				(snapshot.unix_time - start) * 1000,
				getattr(snapshot, property_name)
			] for snapshot in fuzzer.snapshots]
		} for fuzzer in campaign.fuzzers if fuzzer.started],
		xAxis={
			'type': 'datetime',
			'title': {
				'text': 'Duration'
			}
		},
		yAxis={
			'title': {
				'text': property_name.replace('_', ' ').title()
			}
		}
	)
