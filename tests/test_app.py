from flask import url_for


def test_app(db, client):
	assert client.get(url_for('campaigns.list_campaigns')).status_code == 200


def test_list_campaigns(db, client):
	assert client.get(url_for('campaigns.list_campaigns')).status_code == 200