import os
import logging
from flask import Flask, render_template, session, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_session import Session

# Configure logging
logging.basicConfig(level=logging.DEBUG)


app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# More reliable session configuration for container environments
# Use a fixed session cookie name to avoid default changing
app.config['SESSION_COOKIE_NAME'] = 'nebenchat_session'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'  # Store session files here
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours in seconds
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_SAMESITE'] = None  # Allow cross-site cookies in container setup
app.config['SESSION_COOKIE_SECURE'] = False   # Don't require HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Protect against XSS
app.config['SESSION_COOKIE_PATH'] = '/'       # Valid for all paths

# Initialize Flask-Session
Session(app)

# Configure upload settings
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Import and register blueprints
from auth import auth_bp
from chat import chat_bp

app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('chat.chat_page'))
    return redirect(url_for('auth.login'))

@app.errorhandler(404)
def not_found(error):
    return render_template('base.html', content='<div class="alert alert-danger">Page not found</div>'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('base.html', content='<div class="alert alert-danger">Internal server error</div>'), 500
