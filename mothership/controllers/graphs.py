import random

from flask import Blueprint, jsonify
from mothership import models

graphs = Blueprint('graphs', __name__)


@graphs.route('/graphs/campaign/<id>')
def campaign(id):
	#  campaign = models.Campaign.get(id=id)
	return jsonify(
		data={
			"x": list(range(0, 1000)),
			"y": [random.randint(x-100, x+100) for x in range(1000)],
		},
		layout={

		}
	)
