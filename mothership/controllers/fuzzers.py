import os
import tarfile
import tempfile
import random

from flask import Blueprint, jsonify, request, current_app, send_file
from werkzeug.utils import secure_filename
from itsdangerous import Signer, BadSignature

from mothership import models

fuzzers = Blueprint('fuzzers', __name__)

def get_best_campaign():
	# TODO: for now we just get the active
	return models.Campaign.get(active=True)


# TODO: make instances each own a secret key used to sign submitted data
# use a wrapper on the endpoints we want the data verified for
# def get_signature(value):
# 	return Signer(current_app.config['FUZZER_KEY']).sign(str(value).encode('ascii')).decode('ascii').rsplit('.')
# def check_signature(value, signature):
# 	signed_value = str(value) + '.' + signature
# 	Signer(current_app.config['FUZZER_KEY']).unsign(signed_value)

@fuzzers.route('/fuzzers/submit/<int:instance_id>', methods=['POST'])
def submit(instance_id):
	instance = models.FuzzerInstance.get(id=instance_id)
	instance.update(**request.json['status'])
	for snapshot_data in request.json['snapshots']:
		snapshot = models.FuzzerSnapshot()
		snapshot.update(**snapshot_data)
		instance.snapshots.append(snapshot)
	instance.commit()
	return jsonify(
		upload_in=current_app.config['UPLOAD_FREQUENCY'],
		download_in=current_app.config['DOWNLOAD_FREQUENCY']
	)

@fuzzers.route('/fuzzers/register')
def register():
	hostname = request.args.get('hostname')
	campaign = get_best_campaign()
	if not campaign:
		return 'No active campaigns', 400
	instance = models.FuzzerInstance.create(hostname=hostname)
	campaign.fuzzers.append(instance)
	campaign.commit()

	# avoid all hosts starting at the same time from reporting at the same time
	deviation = random.randint(-15, 15)
	return jsonify(
		id=instance.id,
		name=instance.name,
		upload_in=current_app.config['UPLOAD_FREQUENCY'] + deviation,
		download_in=current_app.config['DOWNLOAD_FREQUENCY'] + deviation + 60,  # download after upload if times are the same
	)

@fuzzers.route('/fuzzers/download_queue/<int:instance_id>', methods=['POST'])
def download_queue(instance_id):
	instance = models.FuzzerInstance.get(id=instance_id)
	campaign = instance.campaign
	if not campaign.queue_archive:
		fd, queue_archive = tempfile.mkstemp('mothership')
		tar = tarfile.open(fileobj=os.fdopen(fd, 'wb'), mode='w:gz')
		tar.add(os.path.join(current_app.config['QUEUE_DIRECTORY'], secure_filename(campaign.name)))
		tar.close()
		campaign.queue_archive = queue_archive
		campaign.commit()
	return send_file(campaign.queue_archive)


@fuzzers.route('/fuzzers/upload_queue/<int:instance_id>', methods=['POST'])
def upload_queue(instance_id):
	instance = models.FuzzerInstance.get(id=instance_id)
	campaign = instance.campaign

	upload_dir = os.path.join(current_app.config['QUEUE_DIRECTORY'], secure_filename(campaign.name), secure_filename(instance.name))
	tar = tarfile.TarFile(fileobj=request.files['file'], mode='r:gz')
	tar.extractall(upload_dir)
	return ''

