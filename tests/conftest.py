import os, sys
import pytest

""" So PYTHONPATH enviroment variable doesn't have to 
	be set for pytest to find mothership module. """
curdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(curdir,'..'))

from mothership import create_app, settings
from mothership import db as _db


@pytest.fixture(scope='session')
def app(request):
	app = create_app('mothership.settings.TestConfig')

	# Establish an application context before running the tests.
	ctx = app.app_context()
	ctx.push()

	def teardown():
		ctx.pop()

	request.addfinalizer(teardown)
	return app


@pytest.fixture(scope='session')
def db(app, request):
	"""Session-wide test database."""
	if os.path.exists(settings.db_file.name):
		os.unlink(settings.db_file.name)

	_db.app = app
	_db.create_all()

	request.addfinalizer(_db.drop_all)
	return _db


@pytest.fixture(scope='function')
def session(db, request):
	"""Creates a new database session for a test."""
	connection = db.engine.connect()
	transaction = connection.begin()

	options = dict(bind=connection, binds={})
	session = db.create_scoped_session(options=options)

	db.session = session

	def teardown():
		transaction.rollback()
		connection.close()
		session.remove()

	request.addfinalizer(teardown)
	return session