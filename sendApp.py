import csv
import smtplib
import os
import threading
from email.message import EmailMessage
from flask import Flask, request, render_template, redirect, url_for, flash
from functools import wraps
import logging

# New: database imports
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

try:
	import psycopg2
	from psycopg2.extras import RealDictCursor
except Exception:  # psycopg2 may not be available locally
	psycopg2 = None
	RealDictCursor = None

# New: requests for email HTTP APIs
try:
	import requests
except Exception:
	requests = None

# Application setup
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
# Allow overriding CSV storage path via environment variable (useful for cloud volumes)
CSV_FILE = os.environ.get('CSV_FILE', 'user_data.csv')
# Ensure the directory for the CSV file exists (handles cloud volume mounts like /data)
_csv_dir = os.path.dirname(CSV_FILE) or '.'
os.makedirs(_csv_dir, exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Email configuration (replace with your details)
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'orbrom97@gmail.com')  # CHANGE THIS
SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD', 'rloj qlxt xapn wnub')  # CHANGE THIS
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL', 'harshamot.brom@gmail.com')  # CHANGE THIS

# SendGrid configuration (optional fallback)
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')

# Resend configuration (optional fallback)
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
RESEND_FROM = os.environ.get('RESEND_FROM', SENDER_EMAIL)

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
_DB_AVAILABLE = psycopg2 is not None and bool(DATABASE_URL)

# Debug viewer token (set value in Railway Variables, e.g., a random string)
DEBUG_TOKEN = os.environ.get('DEBUG_TOKEN')

# Thread lock for CSV operations
csv_lock = threading.Lock()

# ---------- Database helpers ----------

def _ensure_sslmode_in_url(db_url: str) -> str:
	"""Ensure sslmode=require is present in the connection string for managed Postgres."""
	try:
		parsed = urlparse(db_url)
		query = parse_qs(parsed.query)
		if 'sslmode' not in query:
			query['sslmode'] = ['require']
			new_query = urlencode({k: v[0] for k, v in query.items()})
			parsed = parsed._replace(query=new_query)
			return urlunparse(parsed)
		return db_url
	except Exception:
		return db_url


def get_db_connection():
	if not _DB_AVAILABLE:
		return None
	try:
		conn = psycopg2.connect(_ensure_sslmode_in_url(DATABASE_URL))
		return conn
	except Exception as e:
		logger.error(f"Failed to connect to Postgres: {e}")
		return None


def init_db():
	"""Create submissions table if it does not exist."""
	conn = get_db_connection()
	if conn is None:
		logger.info("Postgres not available; using CSV storage.")
		return
	try:
		with conn:
			with conn.cursor() as cur:
				cur.execute(
					"""
					CREATE TABLE IF NOT EXISTS submissions (
						id SERIAL PRIMARY KEY,
						name TEXT NOT NULL,
						email_from TEXT NOT NULL,
						message TEXT NOT NULL,
						created_at TIMESTAMP NOT NULL DEFAULT NOW()
					);
					"""
				)
		logger.info("Postgres table ensured: submissions")
	except Exception as e:
		logger.error(f"Failed to init Postgres: {e}")
	finally:
		try:
			conn.close()
		except Exception:
			pass


# This is the main page that serves the form
@app.route('/')
def home():
	return render_template('index.html')


def validate_form_data(data):
	"""Validate form data for security and completeness"""
	required_fields = ['name', 'email_from', 'message']
	
	for field in required_fields:
		if not data.get(field) or not data[field].strip():
			return False, f"Field '{field}' is required"
	
	# Basic email validation
	email = data['email_from'].strip()
	if '@' not in email or '.' not in email.split('@')[-1]:
		return False, "Invalid email format"
	
	# Basic length validation
	if len(data['message']) > 10000:
		return False, "Message too long (max 10,000 characters)"
	
	return True, None


# ---------- Storage backends ----------

def save_to_db(data) -> bool:
	"""Save to Postgres. Returns True on success, False otherwise."""
	conn = get_db_connection()
	if conn is None:
		return False
	try:
		with conn:
			with conn.cursor() as cur:
				cur.execute(
					"""
					INSERT INTO submissions (name, email_from, message)
					VALUES (%s, %s, %s)
					""",
					(data['name'], data['email_from'], data['message'])
				)
		return True
	except Exception as e:
		logger.error(f"Error saving to Postgres: {e}")
		return False
	finally:
		try:
			conn.close()
		except Exception:
			pass


def save_to_csv(data):
	"""Thread-safe CSV saving with improved error handling"""
	with csv_lock:
		try:
			# Determine if a new header is needed (first-time file creation)
			file_exists = os.path.exists(CSV_FILE)
			
			with open(CSV_FILE, 'a', newline='', encoding='utf-8') as csvfile:
				fieldnames = ['name', 'email_from', 'message']
				writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
				
				# Write the header row if the file is new
				if not file_exists:
					writer.writeheader()
				
				# Append the new data row
				writer.writerow(data)
			
			logger.info("Data saved to CSV successfully")
			
		except Exception as e:
			logger.error(f"Error saving to CSV: {e}")
			raise


# This route handles the form submission
@app.route('/submit', methods=['POST'])
def submit():
	if request.method == 'POST':
		try:
			user_data = {
				'name': request.form.get('name', '').strip(),
				'email_from': request.form.get('email_from', '').strip(),
				'message': request.form.get('message', '').strip()
			}
			
			# Validate form data
			is_valid, error_msg = validate_form_data(user_data)
			if not is_valid:
				flash(error_msg, 'error')
				return redirect(url_for('home'))
			
			# Primary: save to Postgres if available; fallback to CSV
			stored = save_to_db(user_data)
			if not stored:
				save_to_csv(user_data)
			
			# Send email asynchronously
			email_thread = threading.Thread(target=send_notification_email, args=(user_data,))
			email_thread.daemon = True
			email_thread.start()

			# Redirect the user to a success page
			return redirect(url_for('success'))
			
		except Exception as e:
			logger.error(f"Error processing form submission: {e}")
			flash("An error occurred processing your submission. Please try again.", 'error')
			return redirect(url_for('home'))
	
	return "Method Not Allowed", 405


@app.route('/success')
def success():
	return "Thank you for your submission! We have received your data and a notification email has been sent."


def _send_email_via_smtp(subject: str, body: str) -> bool:
	try:
		with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
			server.starttls()
			server.login(SENDER_EMAIL, SENDER_PASSWORD)
			msg = EmailMessage()
			msg['Subject'] = subject
			msg['From'] = SENDER_EMAIL
			msg['To'] = RECIPIENT_EMAIL
			msg.set_content(body)
			server.send_message(msg)
		return True
	except Exception as e:
		logger.error(f"SMTP send failed: {e}")
		return False


def _send_email_via_sendgrid(subject: str, body: str) -> bool:
	if not SENDGRID_API_KEY or requests is None:
		return False
	try:
		resp = requests.post(
			'https://api.sendgrid.com/v3/mail/send',
			headers={
				'Authorization': f'Bearer {SENDGRID_API_KEY}',
				'Content-Type': 'application/json'
			},
			json={
				'personalizations': [{
					'to': [{'email': RECIPIENT_EMAIL}],
					'subject': subject
				}],
				'from': {'email': SENDER_EMAIL},
				'content': [{'type': 'text/plain', 'value': body}]
			}
		)
		if 200 <= resp.status_code < 300:
			return True
		logger.error(f"SendGrid send failed: {resp.status_code} {resp.text}")
		return False
	except Exception as e:
		logger.error(f"SendGrid exception: {e}")
		return False


def _send_email_via_resend(subject: str, body: str) -> bool:
	if not RESEND_API_KEY or requests is None:
		return False
	try:
		resp = requests.post(
			'https://api.resend.com/emails',
			headers={
				'Authorization': f'Bearer {RESEND_API_KEY}',
				'Content-Type': 'application/json'
			},
			json={
				'from': RESEND_FROM,
				'to': [RECIPIENT_EMAIL],
				'subject': subject,
				'text': body
			}
		)
		if 200 <= resp.status_code < 300:
			return True
		logger.error(f"Resend send failed: {resp.status_code} {resp.text}")
		return False
	except Exception as e:
		logger.error(f"Resend exception: {e}")
		return False


def send_notification_email(data):
	"""Send notification email using SMTP; fallback to SendGrid or Resend HTTP APIs if SMTP blocked."""
	# Escape user input to prevent header injection
	safe_name = data['name'].replace('\n', '').replace('\r', '')
	safe_email = data['email_from'].replace('\n', '').replace('\r', '')
	safe_message = data['message'].replace('\n', ' ').replace('\r', ' ')
	
	subject = 'New Form Submission'
	body = (
		"Hello,\n\nA new submission has been received.\n\n"
		f"Name: {safe_name}\n"
		f"Email: {safe_email}\n"
		f"Message:\n{safe_message}\n\n"
		"Best regards,\nForm Bot"
	)
	
	if _send_email_via_smtp(subject, body):
		logger.info("Email sent successfully via SMTP!")
		return
	if _send_email_via_sendgrid(subject, body):
		logger.info("Email sent successfully via SendGrid API!")
		return
	if _send_email_via_resend(subject, body):
		logger.info("Email sent successfully via Resend API!")
		return
	logger.error("All email methods failed.")

# Error handlers for better debugging
@app.errorhandler(500)
def internal_error(error):
	logger.error(f"Internal server error: {error}")
	return "Internal server error. Check the logs for details.", 500

@app.errorhandler(404)
def not_found(error):
	return "Page not found.", 404


# Debug endpoint to view recent submissions (token protected)
@app.route('/debug/submissions')
def debug_submissions():
	token = request.args.get('token')
	if not DEBUG_TOKEN or token != DEBUG_TOKEN:
		return "Unauthorized", 401
	# Try Postgres first
	conn = get_db_connection()
	if conn is not None:
		try:
			with conn:
				with conn.cursor(cursor_factory=RealDictCursor) as cur:
					cur.execute(
						"""
						SELECT id, name, email_from, LEFT(message, 200) AS message_preview, created_at
						FROM submissions
						ORDER BY created_at DESC
						LIMIT 20
						"""
					)
					rows = cur.fetchall()
					return {"backend": "postgres", "rows": rows}
		except Exception as e:
			logger.error(f"Debug fetch Postgres failed: {e}")
		finally:
			try:
				conn.close()
			except Exception:
				pass
	# Fallback: read CSV last 20 lines
	try:
		if not os.path.exists(CSV_FILE):
			return {"backend": "csv", "rows": []}
		rows = []
		with open(CSV_FILE, 'r', encoding='utf-8') as f:
			reader = csv.DictReader(f)
			for row in reader:
				rows.append({
					"name": row.get('name'),
					"email_from": row.get('email_from'),
					"message_preview": (row.get('message') or '')[:200]
				})
		return {"backend": "csv", "rows": rows[-20:]}
	except Exception as e:
		logger.error(f"Debug fetch CSV failed: {e}")
		return {"backend": "csv", "rows": []}


# Debug endpoint to trigger a test email (token protected)
@app.route('/debug/test-email')
def debug_test_email():
	token = request.args.get('token')
	if not DEBUG_TOKEN or token != DEBUG_TOKEN:
		return "Unauthorized", 401
	data = {
		'name': 'Test User',
		'email_from': 'test@example.com',
		'message': 'This is a test email triggered from /debug/test-email.'
	}
	try:
		send_notification_email(data)
		return {"status": "ok"}
	except Exception as e:
		logger.error(f"Test email failed: {e}")
		return {"status": "error", "error": str(e)}, 500


# Initialize database table at startup (best-effort)
init_db()

if __name__ == '__main__':
	# Production-ready configuration
	debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
	port = int(os.environ.get('PORT', 5000))
	
	logger.info(f"Starting Flask app in {'debug' if debug_mode else 'production'} mode on port {port}")
	
	# Use production WSGI server in cloud environments
	if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER'):
		# Production deployment
		app.run(host='0.0.0.0', port=port, debug=False)
	else:
		# Local development
		app.run(debug=debug_mode, host='0.0.0.0', port=port)