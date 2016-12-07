import time

from mothership import models


def test_create_campaign():
	campaign = models.Campaign('test')
	campaign.put()
	assert campaign.id > 0
	assert campaign.get(id=campaign.id)
	assert len(list(campaign.all(id=campaign.id))) == 1
