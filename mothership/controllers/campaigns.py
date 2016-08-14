import shutil
import statistics
import subprocess
import time
import os

import sqlalchemy
from flask import Blueprint, render_template, render_template_string, flash, redirect, request, url_for, jsonify, current_app
from datetime import datetime
from sqlalchemy import case
from werkzeug.utils import secure_filename

from mothership import forms, models
from mothership.utils import format_timedelta_secs, pretty_size_dec, format_ago


campaigns = Blueprint('campaigns', __name__)


@campaigns.route('/')
def list_campaigns():
	if not os.path.exists(os.path.join(current_app.config['DATA_DIRECTORY'], 'libdislocator.so')):
		flash('Missing libdislocator.so', 'danger')
	if not os.path.exists(os.path.join(current_app.config['DATA_DIRECTORY'], 'afl-fuzz')):
		flash('Missing afl-fuzz', 'danger')
	return render_template('campaigns.html', campaigns=models.Campaign.query.all())

@campaigns.route('/campaigns/new', methods=['GET', 'POST'])
def new_campaign():
	form = forms.CampaignForm()
	form.copy_of.choices = [(-1, 'None')] + [(c.id, c.name) for c in models.Campaign.all()]
	if form.validate_on_submit():
		model = models.Campaign(form.name)
		form.populate_obj(model)
		model.active = True
		model.put()

		copyof = models.Campaign.get(id=form.copy_of.data)
		other = None
		if copyof:
			other = os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(copyof.name))
		dir = os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(model.name))
		os.makedirs(dir)
		if form.executable.has_file():
			form.executable.data.save(os.path.join(dir, 'executable'))
		elif other:
			shutil.copy(os.path.join(other, 'executable'), os.path.join(dir, 'executable'))

		for config_files in ['libraries', 'testcases', 'ld_preload']:
			dest = os.path.join(dir, config_files)
			if getattr(form, config_files).has_file():
				os.makedirs(dest)
				for lib in request.files.getlist(config_files):
					lib.save(os.path.join(dest, os.path.basename(lib.filename)))
			elif other:
				shutil.copytree(os.path.join(other, config_files), dest)
			else:
				os.makedirs(dest)

		if form.use_libdislocator.data:
			shutil.copy(os.path.join(current_app.config['DATA_DIRECTORY'], 'libdislocator.so'), os.path.join(dir, 'ld_preload'))

		dictionary = os.path.join(dir, 'dictionary')
		if form.dictionary.has_file():
			form.dictionary.data.save(dictionary)
			model.has_dictionary = True
			model.commit()
		elif other and os.path.exists(os.path.join(other, 'dictionary')):
			shutil.copy(os.path.join(other, 'dictionary'), os.path.join(dir, 'dictionary'))
			model.has_dictionary = True
			model.commit()

		flash('Campaign created', 'success')
		return redirect(request.args.get('next') or url_for('campaigns.campaign', campaign_id=model.id))
	return render_template('new-campaign.html', form=form)

@campaigns.route('/campaigns/<int:campaign_id>', methods=['GET', 'POST'])
def campaign(campaign_id):
	campaign_model = models.Campaign.get(id=campaign_id)
	if not campaign_model:
		return 'Campaign not found', 404
	if request.method == 'POST':
		dir = os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(campaign_model.name))
		if 'delete' in request.form:
			return redirect(url_for('campaigns.delete', campaign_id=campaign_id))
		if 'enable' in request.form:
			campaign_model.active = request.form['enable'].lower() == 'true'
			campaign_model.put()
			if campaign_model.active:
				flash('Campaign enabled', 'success')
			else:
				flash('Campaign disabled', 'success')
		if 'reset' in request.form:
			for fuzzer in campaign_model.fuzzers:
				fuzzer.snapshots.delete()
				fuzzer.crashes.delete()
			campaign_model.fuzzers.delete()
			campaign_model.put()
			try:
				shutil.rmtree(os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(campaign_model.name), 'sync_dir'))
			except FileNotFoundError:
				pass
			try:
				shutil.rmtree(os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(campaign_model.name), 'crashes'))
			except FileNotFoundError:
				pass
			flash('Campaign reset', 'success')
		uploaded = 0
		for lib in request.files.getlist('libraries'):
			if lib.filename:
				lib.save(os.path.join(dir, 'libraries', os.path.basename(lib.filename)))
				uploaded += 1
		for test in request.files.getlist('testcases'):
			if test.filename:
				test.save(os.path.join(dir, 'testcases', os.path.basename(test.filename)))
				uploaded += 1
		if uploaded:
			flash('Uploaded %d files' % uploaded, 'success')
		return redirect(url_for('campaigns.campaign', campaign_id=campaign_id))

	# TODO show campaign options, allow editing and show ldd output

	crashes = campaign_model.crashes.filter_by(analyzed=True, crash_in_debugger=True).group_by(models.Crash.backtrace).order_by(case({
		'EXPLOITABLE': 0,
		'PROBABLY_EXPLOITABLE': 1,
		'UNKNOWN': 2,
		'PROBABLY_NOT_EXPLOITABLE': 3},
		value=models.Crash.exploitable,
		else_=4
	))
	heisenbugs = campaign_model.crashes.filter_by(analyzed=True, crash_in_debugger=False)
	ldd = get_ldd(campaign_model)
	testcases = os.listdir(os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(campaign_model.name), 'testcases'))
	ld_preload = os.listdir(os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(campaign_model.name), 'ld_preload'))
	return render_template('campaign.html', campaign=campaign_model, crashes=crashes, heisenbugs=heisenbugs, testcases=testcases, ldd=ldd, ld_preload=ld_preload)


def get_ldd(campaign_model):
	env = dict(os.environ)
	if 'LD_LIBRARY_PATH' in env:
		env['LD_LIBRARY_PATH'] = ':' + env['LD_LIBRARY_PATH']
	else:
		env['LD_LIBRARY_PATH'] = ''
	env['LD_LIBRARY_PATH'] = os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(campaign_model.name), 'libraries') + env['LD_LIBRARY_PATH']
	try:
		p = subprocess.Popen(['ldd', os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(campaign_model.name), 'executable')], env=env, stdout=subprocess.PIPE)
		process_output = p.communicate()
	except FileNotFoundError:
		ldd = None
	else:
		ldd = []
		for line in process_output[0].decode('ascii').split('\n'):
			if not line or line[0] != '\t':
				continue
			parts = line.split()
			if len(parts) < 3:
				continue
			found = 'not found' not in line
			if found:
				path = parts[2]
				if path.startswith(current_app.config['DATA_DIRECTORY']):
					ldd_row = (parts[0], 'info', path.rsplit(os.path.sep, 1)[-1])
				else:
					ldd_row = (parts[0], '', path)
			else:
				ldd_row = (parts[0], 'danger', 'Not Found')
			if ldd_row not in ldd:
				ldd.append(ldd_row)
	return ldd


@campaigns.route('/campaigns/delete/<int:campaign_id>', methods=['GET', 'POST'])
def delete(campaign_id):
	# TODO
	if request.method == 'POST':
		campaign_model = models.Campaign.get(id=campaign_id)
		if not campaign_model:
			return 'Campaign not found', 404
		for fuzzer in campaign_model.fuzzers:
			fuzzer.snapshots.delete()
			fuzzer.crashes.delete()
		campaign_model.fuzzers.delete()
		campaign_model.delete()
		dir = os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(campaign_model.name))
		try:
			shutil.rmtree(dir)
		except FileNotFoundError:
			pass
		flash('Campaign deleted', 'success')
		return redirect(url_for('campaigns.list_campaigns'))
	else:
		html = '<form method="post">' \
			'<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>' \
			'<button type="submit" class="btn btn-danger" name="delete">Confirm</button>' \
			'</form>'
		return render_template_string(html)

@campaigns.route('/campaigns/<int:campaign_id>/crashes')
def analysis_queue_campaign(campaign_id):
	campaign_model = models.Campaign.get(id=campaign_id)
	if not campaign_model:
		return 'Campaign not found', 404
	return render_template('directory.html', title=campaign_model.name, children=[
		{
			'name': os.path.split(crash.path)[1],
			'href': url_for('fuzzers.download_crash', crash_id=crash.id),
			'date': ' ' * (70 - len(os.path.split(crash.path)[1])) + datetime.fromtimestamp(crash.created).strftime('%x %X'),
			'size': str(os.stat(crash.path).st_size).rjust(20)
		} for crash in models.Crash.all(campaign_id=campaign_id)
	])

def count_crashes(crashes, **kwargs):
	return sum(1 if all(hasattr(crash, k) and getattr(crash, k) == v for k, v in kwargs.items()) else 0 for crash in crashes)

@campaigns.route('/campaigns/stats/<int:campaign_id>')
def stats(campaign_id):
	campaign_model = models.Campaign.get(id=campaign_id)
	current_time = int(time.time())
	total_executions, combined_run, last_path, last_crash, last_update = 0, 0, 0, 0, 0
	for instance in campaign_model.fuzzers:
		if instance.started:
			total_executions += instance.execs_done
			combined_run += instance.last_update - instance.start_time
			last_path = max(last_path, instance.last_path)
			last_crash = max(last_crash, instance.last_crash)
			last_update = max(last_update, instance.last_update)
	crashes = list(models.Crash.query.filter_by(campaign_id=campaign_id, analyzed=True, crash_in_debugger=True).group_by(models.Crash.backtrace))
	cvg = campaign_model.bitmap_cvg

	return jsonify(
		now=current_time,

		total_executions=total_executions,
		total_executions_str=pretty_size_dec(total_executions),

		combined_run=total_executions,
		combined_run_str=format_timedelta_secs(combined_run),

		last_instance=last_update,
		last_instance_str=format_ago(current_time, last_update),

		last_path=last_path,
		last_path_str=format_ago(current_time, last_path),

		last_crash=last_path,
		last_crash_str=format_ago(current_time, last_crash),

		awaiting_analysis=models.Crash.query.filter_by(campaign_id=campaign_id, analyzed=False).count(),
		analyzed_crashes=models.Crash.query.filter_by(campaign_id=campaign_id, analyzed=True).count(),
		distinct_crashes=len(crashes),

		bitmap_coverage_mean=cvg[0],
		bitmap_coverage_stdev=cvg[1],
		bitmap_coverage_str='%0.1f%% SD=%0.1f' % cvg,

		exploitable=count_crashes(crashes, exploitable='EXPLOITABLE'),
		probably_exploitable=count_crashes(crashes, exploitable='PROBABLY_EXPLOITABLE'),
		probably_not_exploitable=count_crashes(crashes, exploitable='PROBABLY_NOT_EXPLOITABLE'),
		unknown=count_crashes(crashes, exploitable='UNKNOWN'),
		heisenbugs=models.Crash.query.filter_by(campaign_id=campaign_id, crash_in_debugger=False).count(),

	)


@campaigns.route('/campaigns/data/<int:campaign_id>')
def data(campaign_id):
	campaign_data = models.Campaign.get(id=campaign_id).to_dict()
	instances = []
	for instance in models.FuzzerInstance.all(campaign_id=campaign_id):
		instances.append(instance.to_dict())
	campaign_data['instances'] = instances
	return jsonify(
		campaign=campaign_data
	)


