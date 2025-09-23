# Contact Form - Rematch

A beautiful, modern contact form built with Flask that saves submissions to CSV and sends email notifications.

## Features

- 🎨 **Beautiful Modern UI** - Glassmorphism design with animations
- 📧 **Email Notifications** - Automatic email alerts for new submissions
- 📊 **CSV Data Storage** - All submissions saved to user_data.csv
- 🔒 **Secure** - Input validation and sanitization
- 📱 **Responsive** - Works perfectly on all devices
- ⚡ **Fast** - Optimized for performance

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export SENDER_EMAIL="your_email@gmail.com"
export SENDER_PASSWORD="your_app_password"
export RECIPIENT_EMAIL="notifications@yourdomain.com"
```

3. Run the application:
```bash
python sendApp.py
```

4. Visit `http://localhost:5000`

## Deployment

This app is ready for deployment on:
- Railway
- Render
- Heroku
- AWS
- Google Cloud
- Azure

## Configuration

The app uses environment variables for configuration:
- `SENDER_EMAIL` - Gmail address for sending emails
- `SENDER_PASSWORD` - Gmail App Password
- `RECIPIENT_EMAIL` - Where to send notifications
- `PORT` - Port to run on (default: 5000)
- `FLASK_DEBUG` - Debug mode (True/False)

## File Structure

```
Rematch form/
├── sendApp.py          # Main Flask application
├── requirements.txt    # Python dependencies
├── Procfile           # Deployment configuration
├── README.md          # This file
└── templates/
    └── index.html     # Beautiful contact form template
```
