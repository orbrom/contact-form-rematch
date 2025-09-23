import csv
import smtplib
import os
import threading
from email.message import EmailMessage
from flask import Flask, request, render_template, redirect, url_for, flash
from functools import wraps
import logging

# Application setup
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
CSV_FILE = 'user_data.csv'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Email configuration (replace with your details)
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'orbrom97@gmail.com')  # CHANGE THIS
SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD', 'rloj qlxt xapn wnub')  # CHANGE THIS
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL', 'harshamot.brom@gmail.com')  # CHANGE THIS

# Thread lock for CSV operations
csv_lock = threading.Lock()

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
            
            # Funnel 1: Save to CSV (thread-safe)
            save_to_csv(user_data)
            
            # Funnel 2: Send email asynchronously
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

def send_notification_email(data):
    """Send notification email with improved error handling and security"""
    try:
        msg = EmailMessage()
        msg['Subject'] = 'New Form Submission'
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        
        # Escape user input to prevent email header injection
        safe_name = data['name'].replace('\n', '').replace('\r', '')
        safe_email = data['email_from'].replace('\n', '').replace('\r', '')
        safe_message = data['message'].replace('\n', ' ').replace('\r', ' ')
        
        # Customize the email body with your desired syntax
        email_body = f"Hello,\n\nA new submission has been received.\n\n" \
                     f"Name: {safe_name}\n" \
                     f"Email: {safe_email}\n" \
                     f"Message:\n{safe_message}\n\n" \
                     f"Best regards,\nForm Bot"
        
        msg.set_content(email_body)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        logger.info("Email sent successfully!")
        
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed. Check email credentials.")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error occurred: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")

# Error handlers for better debugging
@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return "Internal server error. Check the logs for details.", 500

@app.errorhandler(404)
def not_found(error):
    return "Page not found.", 404

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