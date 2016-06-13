import tempfile
db_file = tempfile.NamedTemporaryFile()


class Config(object):
	SECRET_KEY = 'secret key'
	FUZZER_KEY = 'secret key'
	DATA_DIRECTORY = 'data'
	UPLOAD_FREQUENCY = 60 * 15    # 15 minutes
	DOWNLOAD_FREQUENCY = 60 * 30  # 30 minutes

class ProdConfig(Config):
	ENV = 'prod'
	SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://<username>:<password>@<identifier>.amazonaws.com/mothership'
	CACHE_TYPE = 'simple'
	ASSETS_DEBUG = True


class DevConfig(Config):
	ENV = 'dev'
	DEBUG = True
	SQLALCHEMY_TRACK_MODIFICATIONS = False
	DEBUG_TB_INTERCEPT_REDIRECTS = False

	SQLALCHEMY_DATABASE_URI = 'sqlite:///../database.db'

	CACHE_TYPE = 'null'
	ASSETS_DEBUG = True


class TestConfig(Config):
	ENV = 'test'
	DEBUG = True
	DEBUG_TB_INTERCEPT_REDIRECTS = False

	SQLALCHEMY_DATABASE_URI = 'sqlite:///' + db_file.name
	SQLALCHEMY_ECHO = True

	CACHE_TYPE = 'null'
	WTF_CSRF_ENABLED = False
