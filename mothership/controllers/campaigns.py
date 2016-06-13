import shutil
import subprocess
import time
import os
from flask import Blueprint, render_template, render_template_string, flash, redirect, request, url_for, jsonify, current_app
from datetime import datetime
from sqlalchemy import case
from werkzeug.utils import secure_filename

from mothership import forms, models
from mothership.utils import format_timedelta_secs, pretty_size_dec, format_ago


campaigns = Blueprint('campaigns', __name__)


@campaigns.route('/campaigns')
def list_campaigns():
	return render_template('campaigns.html', campaigns=models.Campaign.query.all())

@campaigns.route('/campaigns/new', methods=['GET', 'POST'])
def new_campaign():
	form = forms.CampaignForm()
	form.copy_of.choices = [(-1, 'None')] + [(c.id, c.name) for c in models.Campaign.all()]
	if form.validate_on_submit():
		model = models.Campaign(form.name)
		form.populate_obj(model)
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

		libs = os.path.join(dir, 'libraries')
		if form.libraries.has_file():
			os.makedirs(libs)
			for lib in request.files.getlist('libraries'):
				lib.save(os.path.join(libs, os.path.basename(lib.filename)))
		elif other:
			shutil.copytree(os.path.join(other, 'libraries'), libs)
		else:
			os.makedirs(libs)

		tests = os.path.join(dir, 'testcases')
		if form.testcases.has_file():
			os.makedirs(tests)
			for test in request.files.getlist('testcases'):
				test.save(os.path.join(tests, os.path.basename(test.filename)))
		elif other:
			shutil.copytree(os.path.join(other, 'testcases'), tests)
		else:
			os.makedirs(tests)

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
			models.Campaign.update_all(active=False)
			campaign_model.active = request.form['enable'].lower() == 'true'
			campaign_model.put()
			flash('Campaign enabled', 'success')
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
		'PROBABLY_NOT_EXPLOITABLE': 2,
		'UNKNOWN': 3},
		value=models.Crash.exploitable,
		else_=4
	))
	heisenbugs = campaign_model.crashes.filter_by(analyzed=True, crash_in_debugger=False)
	ldd = get_ldd(campaign_model)
	testcases = os.listdir(os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(campaign_model.name), 'testcases'))
	return render_template('campaign.html', campaign=campaign_model, crashes=crashes, heisenbugs=heisenbugs, testcases=testcases, ldd=ldd)


def get_ldd(campaign_model):
	env = dict(os.environ)
	if 'LD_LIBRARY_PATH' in env:
		env['LD_LIBRARY_PATH'] += ':'
	else:
		env['LD_LIBRARY_PATH'] = ''
	env['LD_LIBRARY_PATH'] += os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(campaign_model.name), 'libraries')
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
					ldd_row = (parts[0], 'info', path.split(os.path.sep, 1)[1])
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


@campaigns.route('/campaigns/update/<int:campaign_id>', methods=['GET', 'POST'])
def update(campaign_id):
	campaign_model = models.Campaign.get(id=campaign_id)
	if 'enable' in request.args:
		# TODO: allow multiple active campaigns

		return redirect(url_for('campaigns.campaign', campaign_id=campaign_id))

	return '', 400


def count_crashes(crashes, **kwargs):
	return sum(1 if all(hasattr(crash, k) and getattr(crash, k) == v for k, v in kwargs.items()) else 0 for crash in crashes)

@campaigns.route('/campaigns/stats/<int:campaign_id>')
def stats(campaign_id):
	campaign_model = models.Campaign.get(id=campaign_id)
	current_time = int(time.time())
	total_executions, combined_run, last_path, last_crash, last_update = 0, 0, 0, 0, 0
	for instance in campaign_model.fuzzers:
		if instance.start_time is not None:
			total_executions += instance.execs_done
			combined_run += instance.last_update - instance.start_time
			last_path = max(last_path, instance.last_path)
			last_crash = max(last_crash, instance.last_crash)
			last_update = max(last_update, instance.last_update)
	crashes = list(models.Crash.query.filter_by(campaign_id=campaign_id, analyzed=True, crash_in_debugger=True).group_by(models.Crash.backtrace))
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


