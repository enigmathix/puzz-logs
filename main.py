from flask import Flask, render_template, request, make_response, redirect, flash
from google.appengine.api import wrap_wsgi_app
from google.cloud.logging import Client, DESCENDING
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import json
import pytz
import re
import os
import logging
import traceback

app = Flask(__name__)
app.wsgi_app = wrap_wsgi_app(app.wsgi_app)
app.secret_key = os.getenv('SECRET_KEY')

# permissions are created with IAM & Admin... Service Accounts... Pick main one
# ... Keys... download json
client = Client.from_service_account_json('service_account.json')

levels = {
	'DEFAULT': (logging.INFO, 1),
	'DEBUG': (logging.DEBUG, 6),
	'INFO': (logging.INFO, 6),
	'WARNING': (logging.WARNING, 6),
	'ERROR': (logging.ERROR, 12),
	'CRITICAL': (logging.CRITICAL, 24),
	'ENGINE': (logging.INFO, 1),
}

localdev = os.getenv('GAE_ENV') == 'localdev'
cdn = '/static' if localdev else os.getenv('CDN')
project = os.getenv('PROJECT')
domain = os.getenv('DOMAIN')
dateFmt = '%Y-%m-%dT%H:%M'
maxRows = 100
maxLogs = 200

def browser(userAgent):
	if "Chrome" in userAgent and "Edg" not in userAgent:
		browser = "Chrome"
	elif "Edg" in userAgent:
		browser = "Edge"
	elif "Firefox" in userAgent:
		browser = "Firefox"
	elif "Safari" in userAgent and "Chrome" not in userAgent:
		browser = "Safari"
	elif "MSIE" in userAgent or "Trident" in userAgent:
		browser = "Internet Explorer"
	else:
		browser = userAgent.split()[0] if userAgent else 'Unknown'

	if "Windows NT" in userAgent:
		os = "Windows"
	elif re.search(r"iPhone|iPad", userAgent):
		os = "iOS"
	elif "Mac OS X" in userAgent:
		os = "MacOS"
	elif "Android" in userAgent:
		os = "Android"
	elif "Linux" in userAgent:
		os = "Linux"
	else:
		parts = userAgent.split()
		os = parts[1].strip('(;') if len(parts) > 1 else 'Unknown'

	return {"browser": browser, "os": os}

#
# Log entries
#
class LogEntry():
	def __init__(self, timestamp):
		self.time = timestamp
		self.severity = ''
		self.status = ''
		self.hunt = ''
		self.user = ''
		self.ip = ''
		self.url = ''
		self.latency = ''
		self.wait = ''
		self.len = ''
		self.agent = ''
		self.client = ''
		self.messages = []

def addEntry(logEntries, timestamp, message, requestId=None, severity='DEFAULT', payload=None):
	if requestId in logEntries:
		logEntry = logEntries[requestId]
	else:
		logEntry = LogEntry(timestamp)

		if requestId:
			logEntries[requestId] = logEntry
		else:
			timekey = round(timestamp.timestamp())
			if timekey in logEntries:
				logEntry = logEntries[timekey]
			else:
				logEntries[timekey] = logEntry

	logEntry.severity = severity

	if message:
		if message.startswith('X_APPENGINE'):
			pairs = [pair.split(":") for pair in message.split(", ")]
			task = {var: val for var, val in pairs}
			logEntry.user = task['X_APPENGINE_TASKNAME']
			logEntry.url = task['X_APPENGINE_QUEUENAME']
			logEntry.ip = task['X_APPENGINE_USER_IP']
		else:
			logEntry.messages.insert(0, (severity, message))

	if payload:
		logEntry.status = str(int(payload.get('status', 200)))
		logEntry.hunt = payload.get('hunt', '')

		if not logEntry.user:
			logEntry.user = payload.get('user', '')

		logEntry.ip = payload.get('ip', '')
		logEntry.url = payload.get('resource', '')

		logEntry.latency = round(float(payload.get('latency', '0s')[:-1])*1000)
		logEntry.wait = round(float(payload.get('pendingTime', '0s')[:-1])*1000)
		logEntry.len = int(payload.get('responseSize', 0))

		logEntry.agent = payload.get('userAgent', '')
		logEntry.client = browser(logEntry.agent)

		for [sev, msg] in payload.get('msgs', []):
			logEntry.messages.append((sev, msg.replace('\n', '<br>')))

#
# Log handler
#
@app.route('/', methods=['GET', 'POST'])
def logHandler():
	# get input parameters
	tz = request.values.get('timezone', 'UTC')
	tz = pytz.timezone(tz)
	seconds = request.values.get('seconds')
	if not seconds:
		seconds = '59'

	level = request.values.get('level', 'DEFAULT')
	search = request.values.get('search', '')

	endDatetime = request.args.get('t')

	if endDatetime:
		endDatetime = datetime.fromtimestamp(float(endDatetime), tz=timezone.utc)
	else:
		userDate = request.values.get('endtime')

		if userDate:
			endDatetime = tz.localize(datetime.strptime(userDate, dateFmt)).astimezone(pytz.utc) + timedelta(seconds=int(seconds))
		else:
			endDatetime = datetime.utcnow()

	endDatetime = endDatetime.replace(tzinfo=None)
	startDatetime = endDatetime - timedelta(hours=levels[level][1])
	queryStart = startDatetime.isoformat(sep='T', timespec='seconds')
	queryEnd = endDatetime.isoformat(sep='T', timespec='seconds')
	startTime = startDatetime.isoformat(sep='T', timespec='minutes')
	endTime = endDatetime.isoformat(sep='T', timespec='minutes')
	logEntries = {}
	lastTime = None

	try:
		# non default levels can take forever to get 100 results
		if level == 'DEFAULT':
			query = f'projects/{project}/logs/stderr AND timestamp <= "{queryEnd}"'
		elif level == 'ENGINE':
			query = f'projects/{project}/logs/appengine.googleapis.com%2Frequest_log AND timestamp <= "{queryEnd}"'
		else:
			query = f'projects/{project}/logs/stderr AND {level} AND timestamp >= "{queryStart}" AND timestamp <= "{queryEnd}"'

		if search:
			query += f' AND "{search}"'

		entries = client.list_entries(max_results=maxLogs, order_by=DESCENDING, filter_=query)

		for entry in entries:
			log = entry.payload
			lastTime = entry.timestamp

			if type(log) == dict:	# app custom logs
				addEntry(logEntries, entry.timestamp, log['message'], log['payload'].get('requestId', ''), 'INFO', log['payload'])
			elif type(log) == str:	# system logs
				# format is [time] [pid] [INFO] message
				addEntry(logEntries, entry.timestamp, re.sub('[\[].*?[\]]', '', log).strip())
			else:	# request logs
				addEntry(logEntries, entry.timestamp, None, log['requestId'], None, log)

				for appLog in log.get('line', []):
					addEntry(logEntries, entry.timestamp, appLog['logMessage'], log['requestId'], appLog['severity'], log)
	except Exception as e:
		logging.error(str(e) + traceback.format_exc())
		flash(f'Query failed, consider changing your criteria: {str(e)}', 'error')

	if lastTime:
		startTime = lastTime.replace(tzinfo=None).isoformat(sep='T', timespec='minutes')

	# built template dictionary
	templateValues = {
		'cdn': cdn,
		'domain': domain,
		'logs': logEntries.values(),
		'levels': levels.items(),
		'selectedLevel': level,
		'search': search,
		'prev': lastTime.timestamp()+1 if lastTime else '',
		'starttime': startTime,
		'endtime': endTime,
	}

	# render
	response = make_response(render_template('logs.html', **templateValues))
	return response

#
# Warmup
#
@app.route('/_ah/warmup')
def warmup():
	return '', 200

#
# Handle all errors
#
@app.errorhandler(Exception)
def internalError(error):
	flash(str(error), 'error')
	return redirect(f'/', 302)
