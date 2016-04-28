from flask import Blueprint, render_template, flash, redirect, request, url_for
# from mothership.models import Campaign
# from mothership.forms import Campaign as CampaignForm
from mothership import forms, models

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
		return redirect(request.args.get("next") or url_for("campaigns.campaign", id=model.id))
	return render_template('new-campaign.html', form=form)

@campaigns.route('/campaign/<id>')
def campaign(id):
	return render_template('campaign.html', campaign=models.Campaign.get(id=id))