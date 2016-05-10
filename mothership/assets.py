from flask_assets import Bundle

common_css = Bundle(
	'css/vendor/bootstrap.min.css',
	'css/vendor/helper.css',
	'css/main.css',
	filters='cssmin',
	output='public/css/common.css'
)

common_js = Bundle(
	'js/vendor/jquery.min.js',
	'js/vendor/bootstrap.min.js',

	'js/vendor/highcharts.src.js',
	'js/vendor/heatmap.src.js',
	'js/vendor/exporting.js',
	'js/vendor/offline-exporting.js',


	Bundle(
		'js/main.js',
		filters='jsmin'
	),
	output='public/js/common.js'
)
