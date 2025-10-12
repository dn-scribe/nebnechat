import os
import json
import logging
from flask import Flask, render_template, session, redirect, url_for, request, flash
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
# In modern browsers, there are increasing restrictions on cookies in iframes,
# especially with Storage Access API restrictions (Sec-Fetch-Storage-Access: none)
app.config['SESSION_COOKIE_NAME'] = 'session'   # Use Flask's default cookie name
app.config['SESSION_COOKIE_PATH'] = '/'         # Valid for all paths
app.config['SESSION_COOKIE_DOMAIN'] = None      # Don't restrict to specific domain
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'   # Using Lax as a more compatible default
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
            # First check our explicitly set user_token cookie - this is most reliable
            if 'user_token' in request.cookies:
                username = request.cookies.get('user_token')
                logging.info(f"Recovering session from user_token cookie: {username}")
                session['user_id'] = username
                session['is_admin'] = (username == 'danny')
                session.modified = True
                logging.debug(f"Recovered user_id '{username}' from user_token")
            else:
                # Fall back to standard session cookies
                for cookie_name in ['session', 'nebenchat_session']:
                    if cookie_name not in request.cookies:
                        continue
                    
                    cookie_value = request.cookies.get(cookie_name, '')
                    logging.debug(f"Examining {cookie_name} cookie: {cookie_value[:30]}...")
                    
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
    
    # Check each cookie type
    cookie_data = {}
    for cookie_name in ['session', 'nebenchat_session', 'user_token']:
        if cookie_name in request.cookies:
            cookie_value = request.cookies.get(cookie_name, '')
            cookie_data[cookie_name] = {
                'value_prefix': cookie_value[:30] + '...' if len(cookie_value) > 30 else cookie_value,
                'length': len(cookie_value)
            }
            
            # Check for usernames in cookie
            if 'neben' in cookie_value:
                user_from_cookie = 'neben'
                cookie_data[cookie_name]['contains_user'] = 'neben'
            elif 'danny' in cookie_value:
                user_from_cookie = 'danny'
                cookie_data[cookie_name]['contains_user'] = 'danny'
    
    # Check browser environment
    headers = dict(request.headers)
    is_iframe = headers.get('Sec-Fetch-Dest') == 'iframe'
    browser_info = {
        'is_iframe': is_iframe,
        'sec_fetch_dest': headers.get('Sec-Fetch-Dest'),
        'sec_fetch_site': headers.get('Sec-Fetch-Site'),
        'sec_fetch_mode': headers.get('Sec-Fetch-Mode'),
        'sec_fetch_user': headers.get('Sec-Fetch-User'),
        'user_agent': headers.get('User-Agent'),
    }
    
    output = {
        'session_keys': list(session.keys() if session else []),
        'session_data': dict(session) if session else {},
        'cookies': {k: v[:20] + '...' for k, v in request.cookies.items()},
        'detailed_cookie_info': cookie_data,
        'user_from_cookie': user_from_cookie,
        'browser_environment': browser_info,
        'headers': headers,
        'environ': {k: str(v) for k, v in request.environ.items() if k.startswith('HTTP_') or k.startswith('REMOTE_') or k.startswith('SERVER_')},
        'app_config': {k: str(v) for k, v in app.config.items() if 'SECRET' not in k.upper()}
    }
    
    # Add action buttons
    html_content = f"""
    <div class="mb-4">
        <h3>Session Debug</h3>
        <div class="d-flex gap-2 mb-3">
            <a href="/login" class="btn btn-primary">Go to Login</a>
            <a href="/cookie-guide" class="btn btn-info">Cookie Guide</a>
            <a href="/open-direct" class="btn btn-success">Open Directly</a>
            <a href="/debug-session" class="btn btn-secondary">Refresh Debug Info</a>
        </div>
    </div>
    <pre>{json.dumps(output, indent=2)}</pre>
    """
    
    return render_template('base.html', content=html_content)

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
    
    <h2>Direct Access Links</h2>
    <p>Try accessing the app directly via these links instead of through the iframe:</p>
    <ul>
        <li><a href="https://dn-9281411-nebenchat.hf.space/login" target="_blank">Login Page (Direct)</a></li>
        <li><a href="https://dn-9281411-nebenchat.hf.space/chat" target="_blank">Chat Page (Direct)</a></li>
    </ul>
    """
    
    # Check if we're likely in an iframe
    is_iframe = request.headers.get('Sec-Fetch-Dest') == 'iframe'
    if is_iframe:
        html_content += """
        <div class="alert alert-warning mt-3">
            <strong>You appear to be viewing this page in an iframe.</strong> 
            Try clicking one of the direct access links above to open the app in a new tab,
            which may resolve cookie-related login issues.
        </div>
        """
    
    return render_template('base.html', 
                          content=f'<div class="container mt-4">{html_content}</div>')

@app.route('/open-direct')
def open_direct():
    """Provide a simple page to open the app directly"""
    # Get the host from request headers
    host = request.headers.get('Host', 'dn-9281411-nebenchat.hf.space')
    direct_url = f"https://{host}/login"
    
    # Detect if we're in an iframe
    is_iframe = request.headers.get('Sec-Fetch-Dest') == 'iframe'
    storage_access_none = request.headers.get('Sec-Fetch-Storage-Access') == 'none'
    
    html_content = f"""
    <div class="text-center">
        <h1 class="mb-4">NebenChat - Open Directly</h1>
        <p class="mb-4">Click the button below to open NebenChat in a direct browser tab:</p>
        <a href="{direct_url}" target="_blank" class="btn btn-primary btn-lg">
            Open NebenChat
        </a>
    </div>
    """
    
    # If we're in an iframe with storage restrictions, add more information
    if is_iframe and storage_access_none:
        html_content += """
        <div class="mt-5 card">
            <div class="card-header">Why open in a new tab?</div>
            <div class="card-body">
                <p>Your browser is currently restricting cookie storage in this iframe.</p>
                <p>This means our chat application cannot maintain your login session properly.</p>
                <p>Opening the app directly in a new tab avoids these restrictions and allows the login to work correctly.</p>
            </div>
        </div>
        
        <div class="mt-3 alert alert-info">
            <strong>Technical Note:</strong> Modern browsers restrict third-party cookies in iframes for privacy reasons.
            The <code>Sec-Fetch-Storage-Access: none</code> header indicates that your browser is applying these restrictions.
        </div>
        """
    
    return render_template('base.html', content=html_content)

@app.route('/direct-login/<username>')
def direct_login(username):
    """Special login endpoint for direct access"""
    # Only allow specific usernames
    if username not in ['neben', 'danny']:
        flash('Invalid username specified', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if this is a direct access scenario
    referer = request.headers.get('Referer', '')
    if 'huggingface.co' not in referer and 'hf.space' not in referer:
        flash('This endpoint is only for direct access from Hugging Face Spaces', 'error')
        return redirect(url_for('auth.login'))
        
    # Set up session
    session['user_id'] = username
    session['is_admin'] = (username == 'danny')
    session.permanent = True
    session.modified = True
    
    # Set a direct cookie as well
    response = redirect(url_for('chat.chat_page'))
    response.set_cookie(
        'user_token', 
        value=username,
        max_age=86400,
        path='/',
        secure=True,
        httponly=True,
        samesite='Lax'  # Lax is more compatible
    )
    
    flash(f'Welcome back, {username}! You have been logged in directly.', 'success')
    return response
