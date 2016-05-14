import json
import os
import tarfile
import tempfile
import random

from flask import Blueprint, jsonify, request, current_app, send_file, url_for
from werkzeug.utils import secure_filename
#from itsdangerous import Signer, BadSignature

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
		download_in=current_app.config['DOWNLOAD_FREQUENCY'] + deviation + 60,
	)

@fuzzers.route('/fuzzers/download/<int:instance_id>', methods=['POST'])
def download(instance_id):
	instance = models.FuzzerInstance.get(id=instance_id)
	campaign = instance.campaign
	return jsonify(
		url=url_for('fuzzers.download_queue', campaign_id=campaign.id),
		download_in=current_app.config['DOWNLOAD_FREQUENCY'],
	)


@fuzzers.route('/fuzzers/upload/<int:instance_id>', methods=['POST'])
def upload(instance_id):
	instance = models.FuzzerInstance.get(id=instance_id)
	campaign = instance.campaign
	instance_queue_dir = os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(campaign.name), 'queue', secure_filename(instance.name))
	os.makedirs(instance_queue_dir, exist_ok=True)
	tar = tarfile.TarFile(fileobj=request.files['file'], mode='r:gz')
	tar.extractall(instance_queue_dir)
	return jsonify(
		upload_in=current_app.config['UPLOAD_FREQUENCY'],
	)


@fuzzers.route('/fuzzers/download_queue/<int:campaign_id>.tar.gz', methods=['GET'])
def download_queue(campaign_id):
	campaign = models.Campaign.get(id=campaign_id)
	if not campaign.queue_archive:
		fd, queue_archive = tempfile.mkstemp(prefix='mothership_')
		tar = tarfile.open(fileobj=os.fdopen(fd, 'wb'), mode='w:gz')
		queue_dir = os.path.join(secure_filename(campaign.name), 'queue')
		store_dir = os.path.join(current_app.config['DATA_DIRECTORY'], queue_dir)
		os.makedirs(store_dir, exist_ok=True)
		tar.add(store_dir, arcname=queue_dir)
		tar.close()
		campaign.queue_archive = queue_archive
		campaign.commit()
	return send_file(campaign.queue_archive)


@fuzzers.route('/fuzzers/submit_crash/<int:instance_id>', methods=['POST'])
def submit_crash(instance_id):
	instance = models.FuzzerInstance.get(id=instance_id)
	campaign = instance.campaign
	for filename, file in request.files.items():
		crash = models.Crash.create(
			instance_id=instance.id,
			campaign_id=instance.campaign_id,
			created=request.args['time'],
			name=file.filename,
			analyzed=False
		)
		crash_dir = os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(campaign.name), 'crashes')
		os.makedirs(crash_dir, exist_ok=True)
		upload_path = os.path.join(crash_dir, '%d_%s' % (crash.id, secure_filename(file.filename)))
		file.save(upload_path)
		crash.path = os.path.abspath(upload_path)
		crash.commit()
	return ''


@fuzzers.route('/fuzzers/analysis_queue')
def analysis_queue():
	return jsonify(queue=[{
		'campaign_id': crash.campaign_id,
		'crash_id': crash.id,
		'download': request.host_url[:-1] + url_for('fuzzers.download_crash', crash_id=crash.id)
	} for crash in models.Crash.all(analyzed=False)])


@fuzzers.route('/fuzzers/download_crash/<int:crash_id>')
def download_crash(crash_id):
	crash = models.Crash.get(id=crash_id)
	if not crash:
		return 'Crash not found', 404
	return send_file(crash.path)


@fuzzers.route('/fuzzers/submit_analysis/<int:crash_id>', methods=['POST'])
def submit_analysis(crash_id):
	crash = models.Crash.get(id=crash_id)
	if not crash:
		return 'Crash not found', 404
	crash.crash_in_debugger = request.json['crash']
	crash.analyzed = True
	if crash.crash_in_debugger:
		crash.address = request.json['pc']
		crash.backtrace = ', '.join(str(frame['address']) for frame in request.json['frames'])
		crash.faulting_instruction = request.json['faulting instruction']
		crash.exploitable = request.json['exploitable']['Exploitability Classification']
		crash.exploitable_hash = request.json['exploitable']['Hash']
		crash.exploitable_data = request.json['exploitable']
		crash.frames = request.json['frames']

	crash.commit()
	return ''
