import datetime
from math import floor, log


def format_timedelta(value, time_format='{days} days {hours} hours {minutes} minutes'):
	if hasattr(value, 'seconds'):
		seconds = value.seconds + value.days * 24 * 3600
	else:
		seconds = int(value)

	seconds_total = seconds

	minutes = int(floor(seconds / 60))
	minutes_total = minutes
	seconds -= minutes * 60

	hours = int(floor(minutes / 60))
	hours_total = hours
	minutes -= hours * 60

	days = int(floor(hours / 24))
	days_total = days
	hours -= days * 24

	years = int(floor(days / 365))
	years_total = years
	days -= years * 365

	return time_format.format(**{
		'seconds': seconds,
		'seconds2': str(seconds).zfill(2),
		'minutes': minutes,
		'minutes2': str(minutes).zfill(2),
		'hours': hours,
		'hours2': str(hours).zfill(2),
		'days': days,
		'years': years,
		'seconds_total': seconds_total,
		'minutes_total': minutes_total,
		'hours_total': hours_total,
		'days_total': days_total,
		'years_total': years_total,
	})

def format_timedelta_secs(secs, time_format='{days} days {hours} hours {minutes} minutes'):
	return format_timedelta(datetime.timedelta(seconds=secs), time_format=time_format)


def pretty_size(n, b=1024, u='B', pre=[''] + [p + 'i' for p in 'KMGTPEZY']):
	pow, n = min(int(log(max(n, 1), b)), len(pre) - 1), n
	return "%.2f %s%s" % (n / b ** float(pow), pre[pow], u)

def pretty_size_dec(value):
	return pretty_size(value, b=1000, u = '', pre = ['', 'Thousand', 'Million', 'Billion'])


def format_ago(current_time, ago):
	return (format_timedelta_secs(current_time - ago) + ' ago') if ago else 'none so far',