import os
import json
import logging
from flask import Flask, render_template, session, redirect, url_for, request
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Detect Hugging Face Spaces environment
HF_SPACE = os.environ.get('SPACE_ID') is not None
logging.debug(f"Running in Hugging Face Space: {HF_SPACE}")

app = Flask(__name__)
# Use a very strong and static secret key
app.secret_key = "veryHardToGuessStaticSecretKeyForNebenChat_1234!@#$"

# Configure the app to work properly with Hugging Face Spaces reverse proxies
# x_for=1: trust X-Forwarded-For header
# x_proto=1: trust X-Forwarded-Proto header
# x_host=1: trust X-Forwarded-Host header
# x_prefix=1: trust X-Forwarded-Prefix header
# x_port=1: trust X-Forwarded-Port header
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1, x_port=1)

# Force HTTPS scheme for URL generation
app.config['PREFERRED_URL_SCHEME'] = 'https'  # HF Spaces uses HTTPS

# Session configuration for Hugging Face Spaces
# The key issue is that we must NOT set SESSION_COOKIE_DOMAIN and use default path
app.config['SESSION_COOKIE_SAMESITE'] = None    # Allow cookies in iframes (None, not 'None' string)
app.config['SESSION_COOKIE_SECURE'] = False     # Allow both HTTP and HTTPS 
app.config['SESSION_COOKIE_HTTPONLY'] = True    # Protect against XSS
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours in seconds
app.config['SESSION_COOKIE_PATH'] = '/'         # Valid for all paths
app.config['SESSION_COOKIE_DOMAIN'] = None      # Don't restrict to specific domain
app.config['SESSION_COOKIE_NAME'] = 'session'   # Use Flask's default cookie name

# Enable session permanence by default
@app.before_request
def make_session_permanent():
    session.permanent = True

# Configure upload settings
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Debug the session configuration
for key in sorted(app.config):
    if 'SESSION' in key or 'COOKIE' in key or 'SECRET' in key:
        logging.debug(f"Flask Config: {key} = {app.config[key]}")

# Import and register blueprints
from auth import auth_bp
from chat import chat_bp

app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)

@app.route('/')
def index():
    # Check for user in session
    if 'user_id' in session:
        return redirect(url_for('chat.chat_page'))
    return redirect(url_for('auth.login'))

@app.errorhandler(404)
def not_found(error):
    return render_template('base.html', content='<div class="alert alert-danger">Page not found</div>'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('base.html', content='<div class="alert alert-danger">Internal server error</div>'), 500

@app.route('/debug-session')
def debug_session():
    """Debug endpoint to check session data"""
    output = {
        'session_keys': list(session.keys() if session else []),
        'session_data': dict(session) if session else {},
        'cookies': dict(request.cookies),
        'headers': dict(request.headers),
        'environ': {k: str(v) for k, v in request.environ.items() if k.startswith('HTTP_') or k.startswith('REMOTE_') or k.startswith('SERVER_')},
        'app_config': {k: str(v) for k, v in app.config.items() if 'SECRET' not in k.upper()}
    }
    return render_template('base.html', content=f'<pre>{json.dumps(output, indent=2)}</pre>')
