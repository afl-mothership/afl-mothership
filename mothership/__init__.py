#! ../env/bin/python
# -*- coding: utf-8 -*-

__author__ = 'Simon Pinfold'
__email__ = 'simon@uint8.me'
__version__ = '1.0'

from flask import Flask
from webassets.loaders import PythonLoader as PythonAssetsLoader

from mothership.controllers.main import main
from mothership.controllers.campaigns import campaigns
from mothership.controllers.graphs import graphs
from mothership import assets
from mothership.models import db

from mothership.extensions import (
	cache,
	assets_env,
	debug_toolbar,
	login_manager
)


def create_app(object_name):
	"""
	An flask application factory, as explained here:
	http://flask.pocoo.org/docs/patterns/appfactories/

	Arguments:
		object_name: the python path of the config object,
					 e.g. mothership.settings.ProdConfig

		env: The name of the current environment, e.g. prod or dev
	"""

	app = Flask(__name__)

	app.config.from_object(object_name)

	# initialize the cache
	cache.init_app(app)

	# initialize the debug tool bar
	debug_toolbar.init_app(app)

	# initialize SQLAlchemy
	db.init_app(app)

	login_manager.init_app(app)

	# Import and register the different asset bundles
	assets_env.init_app(app)
	assets_loader = PythonAssetsLoader(assets)
	for name, bundle in assets_loader.load_bundles().items():
		assets_env.register(name, bundle)

	# register our blueprints
	app.register_blueprint(main)
	app.register_blueprint(campaigns)
	app.register_blueprint(graphs)

	return app
