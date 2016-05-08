import time
import os
from flask import Blueprint, render_template, flash, redirect, request, url_for, jsonify
from datetime import datetime
# from mothership.models import Campaign
# from mothership.forms import Campaign as CampaignForm
from mothership import forms, models
from mothership.utils import format_timedelta_secs, pretty_size_dec, format_ago


campaigns = Blueprint('campaigns', __name__)


@campaigns.route('/campaigns')
def list_campaigns():
	return render_template('campaigns.html', campaigns=models.Campaign.query.all())

@campaigns.route('/campaigns/new', methods=["GET", "POST"])
def new_campaign():
	form = forms.CampaignForm()
	if form.validate_on_submit():
		model = models.Campaign(form.name)
		form.populate_obj(model)
		model.put()
		flash("Campaign created", "success")
		return redirect(request.args.get("next") or url_for("campaigns.campaign", campaign_id=model.id))
	return render_template('new-campaign.html', form=form)

@campaigns.route('/campaigns/<int:campaign_id>')
def campaign(campaign_id):
	campaign_model = models.Campaign.get(id=campaign_id)
	if not campaign_model:
		return 'Campaign not found', 404
	return render_template('campaign.html', campaign=campaign_model)


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


@campaigns.route('/campaigns/update/<int:campaign_id>', methods=["GET", "POST"])
def update(campaign_id):
	campaign_model = models.Campaign.get(id=campaign_id)
	if 'enable' in request.args:
		# TODO: allow multiple active campaigns
		models.Campaign.update_all(active=False)
		campaign_model.active = request.args['enable'].lower() == 'true'
		campaign_model.put()
		return redirect(url_for('campaigns.campaign', campaign_id=campaign_id))

	return '', 500


@campaigns.route('/campaigns/stats/<int:campaign_id>')
def stats(campaign_id):
	# campaign_model = models.Campaign.get(id=campaign_id)
	current_time = int(time.time())
	total_executions, combined_run, last_path, last_crash, last_update = 0, 0, 0, 0, 0
	for instance in models.FuzzerInstance.all(campaign_id=campaign_id):
		if instance.start_time:
			total_executions += instance.execs_done
			combined_run += instance.last_update - instance.start_time
			last_path = max(last_path, instance.last_path)
			last_crash = max(last_crash, instance.last_crash)
			last_update = max(last_update, instance.last_update)
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
		last_crash_str=format_ago(current_time, last_crash)
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