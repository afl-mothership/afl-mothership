from flask_wtf import Form
from wtforms import StringField
from wtforms import validators

from mothership.models import Campaign

class CampaignForm(Form):
	name = StringField('Name', validators=[validators.required()])

	def validate(self):
		check_validate = super().validate()
		if not check_validate:
			return False

		campaign = Campaign.get(name=self.name.data)
		if campaign:
			self.name.errors.append('Campaign with that name already exists')
			return False

		return True

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
