import os
import yaml
# import bcrypt
import logging
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__)

USERS_FILE = 'users.yml'
SECRET_KEY = os.environ.get('SECRET', 'default-secret-key')

def load_users():
    """Load users from YAML file"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return yaml.safe_load(f) or {}
        return {}
    except Exception as e:
        logging.error(f"Error loading users: {e}")
        return {}

def save_users(users):
    """Save users to YAML file"""
    try:
        with open(USERS_FILE, 'w') as f:
            yaml.dump(users, f, default_flow_style=False)
        return True
    except Exception as e:
        logging.error(f"Error saving users: {e}")
        return False

def hash_password(password):
    """Hash password with bcrypt"""
    return generate_password_hash(f"{password}{SECRET_KEY}")

def verify_password(password, hashed):
    """Verify password against hash"""
    return check_password_hash(hashed, f"{password}{SECRET_KEY}")

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        logging.debug(f"Login attempt: username='{username}'")
        if not username or not password:
            logging.debug("Missing username or password.")
            flash('Please enter both username and password', 'error')
            return render_template('login.html')
        users = load_users()
        logging.debug(f"Loaded users: {list(users.keys())}")
        if username in users:
            logging.debug(f"User '{username}' found. Verifying password...")
            if verify_password(password, users[username]['password']):
                # Set session data with explicit cookie settings
                session.clear()  # Clear any existing session data
                session['user_id'] = username
                session['is_admin'] = users[username].get('is_admin', False)
                session.permanent = True  # Make sure the session is permanent
                session.modified = True  # Explicitly mark session as modified
                
                # Debug logging
                logging.debug(f"Login successful for user '{username}'")
                logging.debug(f"Session set with keys: {list(session.keys())}")
                logging.debug(f"Session data: {dict(session)}")
                logging.debug(f"Request headers: {dict(request.headers)}")
                
                flash(f'Welcome back, {username}!', 'success')
                
                # Create response with redirect and set cookies explicitly
                response = redirect(url_for('chat.chat_page'))
                
                # Check if this is likely an iframe context based on headers
                is_iframe = request.headers.get('Sec-Fetch-Dest') == 'iframe'
                
                # Set SameSite based on context
                samesite = 'None' if is_iframe else 'Lax'
                
                # Set cookies explicitly with the appropriate settings
                response.set_cookie(
                    'user_token', 
                    value=username,  # Simple non-secure user identifier for recovery
                    max_age=86400,   # 24 hours
                    path='/',
                    secure=True,    # Always secure for HTTPS
                    httponly=True,  # Protect against XSS
                    samesite=samesite  # Adaptive based on context
                )
                
                logging.debug(f"Set explicit cookie with SameSite={samesite}")
                
                return response
            else:
                logging.debug(f"Password verification failed for user '{username}'.")
        else:
            logging.debug(f"User '{username}' not found.")
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not username or not password or not confirm_password:
            flash('All fields are required', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('register.html')
        
        users = load_users()
        
        # Check user limit (max 10 users)
        if len(users) >= 10:
            flash('Registration is currently closed. Maximum of 10 users allowed.', 'error')
            return render_template('register.html')
        
        if username in users:
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        # Create new user
        users[username] = {
            'password': hash_password(password),
            'is_admin': len(users) == 0,  # First user is admin
            'created_at': str(os.path.getmtime(__file__))  # Simple timestamp
        }
        
        if save_users(users):
            session['user_id'] = username
            session['is_admin'] = users[username]['is_admin']
            flash(f'Account created successfully! Welcome, {username}!', 'success')
            return redirect(url_for('chat.chat_page'))
        else:
            flash('Error creating account. Please try again.', 'error')
    
    return render_template('register.html')

@auth_bp.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session or not session.get('is_admin', False):
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('auth.login'))
    
    users = load_users()
    
    if request.method == 'POST':
        action = request.form.get('action')
        target_user = request.form.get('username', '').strip()
        
        if action == 'delete' and target_user:
            if target_user == session['user_id']:
                flash('Cannot delete your own account', 'error')
            elif target_user in users:
                del users[target_user]
                if save_users(users):
                    flash(f'User {target_user} deleted successfully', 'success')
                    # Clean up user's chat history
                    try:
                        chat_file = f'chat_history_{target_user}.json'
                        if os.path.exists(chat_file):
                            os.remove(chat_file)
                    except Exception as e:
                        logging.error(f"Error cleaning up chat history: {e}")
                else:
                    flash('Error deleting user', 'error')
            else:
                flash('User not found', 'error')
        
        elif action == 'add':
            new_username = request.form.get('new_username', '').strip()
            new_password = request.form.get('new_password', '')
            
            if not new_username or not new_password:
                flash('Username and password are required', 'error')
            elif new_username in users:
                flash('Username already exists', 'error')
            elif len(users) >= 10:
                flash('Cannot add user. Maximum of 10 users allowed.', 'error')
            elif len(new_password) < 6:
                flash('Password must be at least 6 characters long', 'error')
            else:
                users[new_username] = {
                    'password': hash_password(new_password),
                    'is_admin': False,
                    'created_at': str(os.path.getmtime(__file__))
                }
                if save_users(users):
                    flash(f'User {new_username} added successfully', 'success')
                else:
                    flash('Error adding user', 'error')
    
    return render_template('admin.html', users=users, current_user=session['user_id'])

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))
