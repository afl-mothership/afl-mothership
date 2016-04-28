from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import UserMixin, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Model:
	id = db.Column(db.Integer(), primary_key=True)

	@classmethod
	def get(cls, **kwargs):
		return cls.query.filter_by(**kwargs).first()

	@classmethod
	def create(cls, **kwargs):
		model = cls(**kwargs)
		db.session.add(model)
		db.session.commit()
		return model

	def put(self):
		db.session.add(self)
		db.session.commit()
		print("PUT")

	def delete(self):
		db.session.delete(self)
		db.session.commit()

	def commit(self):
		db.session.commit()


class Campaign(Model, db.Model):
	__tablename__ = 'campaign'

	name = db.Column(db.String())
	fuzzers = db.relationship('FuzzerInstance', backref='fuzzer', lazy='dynamic')

	def __init__(self, name):
		self.name = name


class FuzzerInstance(Model, db.Model):
	__tablename__ = 'instance'

	campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))
	snapshots = db.relationship('FuzzerSnapshot', backref='fuzzer', lazy='dynamic')


class FuzzerSnapshot(Model, db.Model):
	__tablename__ = 'snapshot'

	instance_id = db.Column(db.Integer, db.ForeignKey('instance.id'))
	unix_time = db.Column(db.Integer())
	cycles_done = db.Column(db.Integer())
	cur_path = db.Column(db.Integer())
	paths_total = db.Column(db.Integer())
	pending_total = db.Column(db.Integer())
	pending_favs = db.Column(db.Integer())
	map_size = db.Column(db.Float())
	unique_crashes = db.Column(db.Integer())
	unique_hangs = db.Column(db.Integer())
	max_depth = db.Column(db.Integer())
	execs_per_sec = db.Column(db.Float())

# class User(db.Model, UserMixin):
# 	id = db.Column(db.Integer(), primary_key=True)
# 	username = db.Column(db.String())
# 	password = db.Column(db.String())
#
# 	def __init__(self, username, password):
# 		self.username = username
# 		self.set_password(password)
#
# 	def set_password(self, password):
# 		self.password = generate_password_hash(password)
#
# 	def check_password(self, value):
# 		return check_password_hash(self.password, value)
#
# 	def is_authenticated(self):
# 		if isinstance(self, AnonymousUserMixin):
# 			return False
# 		else:
# 			return True
#
# 	def is_active(self):
# 		return True
#
# 	def is_anonymous(self):
# 		if isinstance(self, AnonymousUserMixin):
# 			return True
# 		else:
# 			return False
#
# 	def get_id(self):
# 		return self.id
#
# 	def __repr__(self):
# 		return '<User %r>' % self.username
