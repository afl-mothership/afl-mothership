import os

from flask import current_app
from flask_wtf import Form
from werkzeug.utils import secure_filename
from wtforms import StringField, SelectField, IntegerField
from flask_wtf.file import FileField
from wtforms import validators

from mothership.models import Campaign

class CampaignForm(Form):
	name = StringField('Name', validators=[validators.required()])
	executable_name = StringField('Executable Name', validators=[validators.required()], default='executable')
	executable_args = StringField('Executable Args', validators=[validators.required()], default='@@')
	afl_args = StringField('AFL Args', validators=[validators.required()], default='-m 100 -t 50+')
	copy_of = SelectField('Copy of', coerce=int, choices=[(-1, 'None')])
	desired_fuzzers = IntegerField('Desired Fuzzers')
	executable = FileField()
	libraries = FileField(
		render_kw={'multiple': True},
	)
	testcases = FileField(
		render_kw={'multiple': True},
	)
	dictionary = FileField()

	def validate(self):
		check_validate = super().validate()
		if not check_validate:
			return False

		campaign = Campaign.get(name=self.name.data)
		if campaign or os.path.exists(os.path.join(current_app.config['DATA_DIRECTORY'], secure_filename(self.name.data))):
			self.name.errors.append('Campaign with that name already exists')
			return False

		if self.copy_of.data == -1:
			if not self.executable.has_file():
				self.executable.errors.append('Must provide an executable or campaign to copy')
				return False
			if not self.testcases.has_file():
				self.testcases.errors.append('Must provide testcases or campaign to copy')
				return False
		else:
			copy_of = Campaign.get(id=self.copy_of.data)
			if not copy_of:
				self.copy_of.errors.append('Campaign to copy does not exist')
				return False

		return True

# class UploadImages(Form):
#
#
# 	upload = SubmitField('Upload')
# from mothership.models import User
#
#
# class LoginForm(Form):
# 	username = StringField(u'Username', validators=[validators.required()])
# 	password = PasswordField(u'Password', validators=[validators.optional()])
#
# 	def validate(self):
# 		check_validate = super(LoginForm, self).validate()
#
# 		# if our validators do not pass
# 		if not check_validate:
# 			return False
#
# 		# Does our the exist
# 		user = User.query.filter_by(username=self.username.data).first()
# 		if not user:
# 			self.username.errors.append('Invalid username or password')
# 			return False
#
# 		# Do the passwords match
# 		if not user.check_password(self.password.data):
# 			self.username.errors.append('Invalid username or password')
# 			return False
#
# 		return True
