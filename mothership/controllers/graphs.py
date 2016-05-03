from flask import Blueprint, jsonify
from sqlalchemy.orm.attributes import InstrumentedAttribute

from mothership import models

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

@graphs.route('/graphs/campaign/<int:campaign_id>/<property_name>')
def graph_campaign(campaign_id, property_name):
	if not hasattr(models.FuzzerSnapshot, property_name) or not type(getattr(models.FuzzerSnapshot, property_name)) is InstrumentedAttribute:
		return 'Snapshot does not have property "%s"' % property_name, 400

	campaign = models.Campaign.get(id=campaign_id)
	if not campaign.started:
		return jsonify()
	start = min(fuzzer.start_time for fuzzer in campaign.fuzzers if fuzzer.start_time)
	return jsonify(
		title={
			'text': property_name.replace('_', ' ').title()
		},
		series=[{
			'name': fuzzer.name,
			'data': [[
				(snapshot.unix_time-start)*1000,
				getattr(snapshot, property_name)
			] for snapshot in fuzzer.snapshots]
		} for fuzzer in campaign.fuzzers if fuzzer.started],  # TODO fuzzer valid/has snapshots property
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
		},
		exporting={

		}
	)
