from flask import Blueprint, render_template, jsonify, flash, request, redirect, url_for
# from flask_socketio import SocketIO
# from flask.ext.login import login_user, logout_user, login_required

from mothership.extensions import cache
# from mothership.forms import LoginForm

main = Blueprint('main', __name__)
#socketio = SocketIO()

@main.route('/')
@cache.cached(timeout=1000)
def home():
	return render_template('index.html')

@main.route('/stats')
def stats():
	return jsonify(data='1')





# @main.route("/login", methods=["GET", "POST"])
# def login():
# 	form = LoginForm()
#
# 	if form.validate_on_submit():
# 		user = User.query.filter_by(username=form.username.data).one()
# 		login_user(user)
#
# 		flash("Logged in successfully.", "success")
# 		return redirect(request.args.get("next") or url_for(".home"))
#
# 	return render_template("login.html", form=form)
#
#
# @main.route("/logout")
# def logout():
# 	logout_user()
# 	flash("You have been logged out.", "success")
#
# 	return redirect(url_for(".home"))
#
#
# @main.route("/restricted")
# @login_required
# def restricted():
# 	return "You can only see this if you are logged in!", 200
