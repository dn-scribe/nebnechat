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

# Debug function to inspect cookies
def debug_cookies():
    if request.cookies:
        for name, value in request.cookies.items():
            logging.debug(f"Cookie: {name}={value[:10]}...")

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

# Critical session configuration changes for Hugging Face Spaces
# 1. Use Flask's default cookie name for compatibility
# 2. Don't restrict by domain and use root path
# 3. Set SameSite policy to None to ensure cookies work in iframes
# 4. Set Secure to True since HF Spaces uses HTTPS
app.config['SESSION_COOKIE_NAME'] = 'session'   # Use Flask's default cookie name to match existing cookies
app.config['SESSION_COOKIE_PATH'] = '/'         # Valid for all paths
app.config['SESSION_COOKIE_DOMAIN'] = None      # Don't restrict to specific domain
app.config['SESSION_COOKIE_SAMESITE'] = 'None'  # Required for cookies in iframes
app.config['SESSION_COOKIE_SECURE'] = True      # Use secure cookies for HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True    # Protect against XSS
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours in seconds

# Session handling and cookie debugging
@app.before_request
def handle_session():
    # Make session permanent
    session.permanent = True
    
    # Debug all cookies
    debug_cookies()
    
    # If user_id not in session, try to recover from any cookie
    if 'user_id' not in session:
        try:
            # First try the standard session cookie
            for cookie_name in ['session', 'nebenchat_session']:
                if cookie_name in request.cookies:
                    cookie_value = request.cookies.get(cookie_name, '')
                    
                    # Check if cookie contains known usernames
                    for username in ['neben', 'danny']:
                        if username in cookie_value:
                            logging.info(f"Recovering session for {username} from {cookie_name}")
                            session['user_id'] = username
                            session['is_admin'] = (username == 'danny')
                            session.modified = True
                            logging.debug(f"Recovered user_id '{username}' from {cookie_name}")
                            break
                    
                    if 'user_id' in session:
                        break
                        
        except Exception as e:
            logging.error(f"Error recovering user from cookie: {str(e)}")
            
    # Force session to be marked as modified to ensure it gets saved
    if 'user_id' in session:
        session.modified = True

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
    # Try to recover the user from cookies for debugging
    user_from_cookie = None
    for cookie_name in ['session', 'nebenchat_session']:
        cookie_value = request.cookies.get(cookie_name, '')
        if 'neben' in cookie_value:
            user_from_cookie = 'neben'
            break
        elif 'danny' in cookie_value:
            user_from_cookie = 'danny'
            break
    
    output = {
        'session_keys': list(session.keys() if session else []),
        'session_data': dict(session) if session else {},
        'user_from_cookie': user_from_cookie,
        'cookies': {k: v[:20] + '...' for k, v in request.cookies.items()},
        'headers': dict(request.headers),
        'environ': {k: str(v) for k, v in request.environ.items() if k.startswith('HTTP_') or k.startswith('REMOTE_') or k.startswith('SERVER_')},
        'app_config': {k: str(v) for k, v in app.config.items() if 'SECRET' not in k.upper()}
    }
    return render_template('base.html', content=f'<pre>{json.dumps(output, indent=2)}</pre>')

@app.route('/login-status')
def login_status():
    """Simple endpoint to check login status"""
    if 'user_id' in session:
        return f"Logged in as: {session['user_id']}"
    else:
        # Check cookies directly as a fallback
        for cookie_name in ['session', 'nebenchat_session']:
            cookie_value = request.cookies.get(cookie_name, '')
            if 'neben' in cookie_value:
                return "Cookie contains 'neben' but session is not set correctly"
            elif 'danny' in cookie_value:
                return "Cookie contains 'danny' but session is not set correctly"
        return "Not logged in"

@app.route('/cookie-guide')
def cookie_guide():
    """Help page for cookie issues"""
    html_content = """
    <h1>Cookie Issues in Hugging Face Spaces</h1>
    <p>If you're having trouble staying logged in on Hugging Face Spaces, particularly on mobile devices, try these solutions:</p>
    
    <h2>For iPhone/iPad Users</h2>
    <ol>
        <li>Go to Settings > Safari > Privacy & Security</li>
        <li>Make sure "Block All Cookies" is turned OFF</li>
        <li>Ensure "Prevent Cross-Site Tracking" is turned OFF (this can block cookies in iframes)</li>
        <li>Try opening the app in Safari directly, not within another app's browser view</li>
    </ol>
    
    <h2>For Android Users</h2>
    <ol>
        <li>Go to Settings > Privacy > Cookies</li>
        <li>Make sure cookies are allowed</li>
        <li>Consider disabling tracking prevention features</li>
    </ol>
    
    <h2>General Solutions</h2>
    <ol>
        <li>Try opening the app in a regular browser tab instead of an iframe</li>
        <li>Clear your browser cookies and cache</li>
        <li>Try a different browser</li>
        <li>If using the app in "Private" or "Incognito" mode, try regular browsing mode instead</li>
    </ol>
    
    <h2>Why This Happens</h2>
    <p>Hugging Face Spaces runs apps in iframes, which can trigger strict cookie policies in modern browsers, 
    especially on mobile devices. This is a security feature of browsers, but it can interfere with web 
    applications that need to maintain login sessions.</p>
    """
    
    return render_template('base.html', 
                          content=f'<div class="container mt-4">{html_content}</div>')
