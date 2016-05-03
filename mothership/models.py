from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.orm.attributes import InstrumentedAttribute

db = SQLAlchemy()

def init_db():
	Campaign.update_all(queue_archive=None)

class Model:
	id = db.Column(db.Integer(), primary_key=True)

	@classmethod
	def get(cls, **kwargs):
		return cls.query.filter_by(**kwargs).first()

	@classmethod
	def all(cls, **kwargs):
		return cls.query.filter_by(**kwargs)

	@classmethod
	def create(cls, **kwargs):
		model = cls(**kwargs)
		db.session.add(model)
		db.session.commit()
		return model

	def put(self):
		db.session.add(self)
		db.session.commit()

	def delete(self):
		db.session.delete(self)
		db.session.commit()

	@staticmethod
	def commit():
		db.session.commit()

	def update(self, **kwargs):
		for k in kwargs:
			if hasattr(type(self), k) and type(getattr(type(self), k)) is InstrumentedAttribute:
				setattr(self, k, kwargs[k])
			else:
				raise KeyError('%r does not have property %r' % (type(self), k))

	@classmethod
	def update_all(cls, **kwargs):
		updates = {}
		for k in kwargs:
			if hasattr(cls, k) and type(getattr(cls, k)) is InstrumentedAttribute:
				updates[getattr(cls, k)] = kwargs[k]
			else:
				raise KeyError('%r does not have property %r' % (cls, k))
		cls.query.update(updates)

	def to_dict(self):
		r = {}
		for k in dir(type(self)):
			if type(getattr(type(self), k)) is InstrumentedAttribute and type(getattr(self, k)) in [str, int, float]:
				r[k] = getattr(self, k)
		return r


class Campaign(Model, db.Model):
	__tablename__ = 'campaign'

	name = db.Column(db.String())
	fuzzers = db.relationship('FuzzerInstance', backref='fuzzer', lazy='dynamic')

	active = db.Column(db.Boolean(), default=False)
	queue_archive = db.Column(db.String())

	def __init__(self, name):
		self.name = name

	@property
	def started(self):
		return bool(self.fuzzers.filter(FuzzerInstance.last_update != None).first())


class FuzzerInstance(Model, db.Model):
	__tablename__ = 'instance'

	campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))
	snapshots = db.relationship('FuzzerSnapshot', backref='fuzzer', lazy='dynamic')
	hostname = db.Column(db.String())

	start_time = db.Column(db.Integer())
	last_update = db.Column(db.Integer())
	fuzzer_pid = db.Column(db.Integer())
	cycles_done = db.Column(db.Integer())
	execs_done = db.Column(db.Integer())
	execs_per_sec = db.Column(db.Float())
	paths_total = db.Column(db.Integer())
	paths_favored = db.Column(db.Integer())
	paths_found = db.Column(db.Integer())
	paths_imported = db.Column(db.Integer())
	max_depth = db.Column(db.Integer())
	cur_path = db.Column(db.Integer())
	pending_favs = db.Column(db.Integer())
	pending_total = db.Column(db.Integer())
	variable_paths = db.Column(db.Integer())
	bitmap_cvg = db.Column(db.Float())
	unique_crashes = db.Column(db.Integer())
	unique_hangs = db.Column(db.Integer())
	last_path = db.Column(db.Integer())
	last_crash = db.Column(db.Integer())
	last_hang = db.Column(db.Integer())
	exec_timeout = db.Column(db.Integer())
	afl_banner = db.Column(db.String())
	afl_version = db.Column(db.String())
	command_line = db.Column(db.String())

	@property
	def name(self):
		if self.hostname:
			return 'fuzzer %d (%s)' % (self.id, self.hostname)
		return 'fuzzer %d' % self.id

	@property
	def campaign(self):
		return Campaign.get(id=self.id)

	@property
	def started(self):
	    return bool(self.last_update)

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
