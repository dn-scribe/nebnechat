import os
import json
import base64
import logging
import glob
from datetime import datetime
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, send_file, Response, g
from werkzeug.utils import secure_filename
import requests
from openai import OpenAI
import markdown
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound
import re

chat_bp = Blueprint('chat', __name__)

# OpenAI setup
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your-api-key-here")
# Remove global client; use per-request client via Flask's g
def get_openai_client():
    if 'openai_client' not in g:
        g.openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return g.openai_client

# Available models - updated with all supported OpenAI models
AVAILABLE_MODELS = [
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano", 
    "gpt-5-chat-latest",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4",
    "gpt-4-turbo",
    "gpt-3.5-turbo"
]

# Available image generation models
AVAILABLE_IMAGE_MODELS = {
    "dall-e-3": {
        "name": "DALL-E 3",
        "sizes": ["1024x1024", "1024x1792", "1792x1024"],
        "quality": ["standard", "hd"]
    },
    "dall-e-2": {
        "name": "DALL-E 2", 
        "sizes": ["256x256", "512x512", "1024x1024"],
        "quality": ["standard"]
    }
}

# OpenAI supported file formats based on latest API documentation
ALLOWED_EXTENSIONS = {
    # Images (for vision models)
    'png', 'jpg', 'jpeg', 'gif', 'webp',
    # Text files
    'txt', 'md', 'py', 'js', 'html', 'css', 'json', 'xml', 'yaml', 'yml', 'sh',
    # Documents (most reliable)  
    'pdf',
    # Spreadsheets and structured data
    'csv', 'xlsx', 'xls',
    # Presentations
    'pptx', 'ppt',
    # Other document formats
    'docx', 'doc', 'rtf',
    # Code files
    'cpp', 'c', 'java', 'php', 'rb', 'go', 'rs', 'swift', 'kt', 'ts', 'jsx', 'tsx', 'vue', 'sql'
}

# File size limits (in MB)
MAX_FILE_SIZE_MB = 150
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_size_mb(file_path):
    """Get file size in MB"""
    return os.path.getsize(file_path) / (1024 * 1024)

def process_markdown_response(text):
    """Process AI response to render markdown and syntax highlight code blocks"""
    if not text:
        return text
    
    # Custom renderer for code blocks with syntax highlighting
    class CodeHtmlFormatter(HtmlFormatter):
        def __init__(self, **options):
            super().__init__(**options)
            self.style = 'github-dark'
    
    def highlight_code(match):
        language = match.group(1) or ''
        code = match.group(2)
        
        try:
            if language:
                lexer = get_lexer_by_name(language, stripall=True)
            else:
                lexer = guess_lexer(code)
            
            formatter = CodeHtmlFormatter(
                style='github-dark',
                cssclass='highlight',
                linenos=False,
                wrapcode=True
            )
            
            highlighted = highlight(code, lexer, formatter)
            return f'<div class="code-block"><div class="code-header"><span class="language-label">{lexer.name}</span><button class="copy-code-btn btn btn-sm btn-outline-light" data-code="{code.replace(chr(34), "&quot;").replace(chr(39), "&#39;")}"><i class="fas fa-copy"></i></button></div>{highlighted}</div>'
        except ClassNotFound:
            # If language not found, return plain code block
            return f'<div class="code-block"><div class="code-header"><span class="language-label">Code</span><button class="copy-code-btn btn btn-sm btn-outline-light" data-code="{code.replace(chr(34), "&quot;").replace(chr(39), "&#39;")}"><i class="fas fa-copy"></i></button></div><pre><code>{code}</code></pre></div>'
    
    # Process code blocks with language specification
    text = re.sub(r'```(\w+)?\n(.*?)```', highlight_code, text, flags=re.DOTALL)
    
    # Process inline code
    text = re.sub(r'`([^`]+)`', r'<code class="inline-code">\1</code>', text)
    
    # Convert markdown to HTML
    md = markdown.Markdown(extensions=['fenced_code', 'codehilite', 'tables'])
    html_content = md.convert(text)
    
    return html_content

import uuid

def load_chat_sessions(user_id):
    """Load user's chat sessions (list of sessions, each a dict with metadata and exchanges)"""
    filename = f'/tmp/chat_history_{user_id}.json'
    try:
        # Ensure parent directory exists
        os.makedirs('/tmp', exist_ok=True)
        
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
                # Migrate old flat history to a single session
                if isinstance(data, list) and data and isinstance(data[0], dict) and "exchanges" in data[0]:
                    # Add summary field if missing
                    for s in data:
                        if "summary" not in s:
                            if s.get("exchanges") and s["exchanges"]:
                                first_msg = s["exchanges"][0].get("user_message", "")
                                s["summary"] = " ".join(first_msg.split()[:10]) + ("..." if len(first_msg.split()) > 10 else "")
                            else:
                                s["summary"] = ""
                    return data
                elif isinstance(data, list):
                    session = {
                        "session_id": str(uuid.uuid4()),
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                        "exchanges": data,
                        "summary": " ".join(data[0].get("user_message", "").split()[:10]) + ("..." if len(data[0].get("user_message", "").split()) > 10 else "") if data else ""
                    }
                    return [session]
        return []
    except Exception as e:
        logging.error(f"Error loading chat sessions for {user_id}: {e}")
        return []

def save_chat_sessions(user_id, sessions):
    """Save user's chat sessions (keep only last 10 sessions) and delete OpenAI vector store if session is deleted"""
    filename = f'/tmp/chat_history_{user_id}.json'
    try:
        # Ensure parent directory exists
        os.makedirs('/tmp', exist_ok=True)
        
        # Clean up files from entries that will be removed (from dropped sessions)
        if len(sessions) > 10:
            sessions_to_remove = sessions[:-10]
            for session in sessions_to_remove:
                # Delete OpenAI vector store if present
                vector_store_id = session.get("vector_store_id")
                if vector_store_id:
                    try:
                        client = get_openai_client()
                        client.vector_stores.delete(vector_store_id=vector_store_id)
                        logging.info(f"Deleted OpenAI vector store {vector_store_id}")
                    except Exception as e:
                        logging.error(f"Error deleting OpenAI vector store {vector_store_id}: {e}")
                for entry in session.get("exchanges", []):
                    if entry.get('has_file') and entry.get('file_name'):
                        for file_path in glob.glob(f"/tmp/uploads/{user_id}_*_{entry['file_name']}"):
                            try:
                                os.remove(file_path)
                                logging.info(f"Cleaned up file: {file_path}")
                            except Exception as e:
                                logging.error(f"Error removing file {file_path}: {e}")
            sessions = sessions[-10:]
        with open(filename, 'w') as f:
            json.dump(sessions, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error saving chat sessions for {user_id}: {e}")
        return False

def get_current_session(user_id):
    """Get the current session (last in list) or None if none exists."""
    sessions = load_chat_sessions(user_id)
    if not sessions:
        return None, []
    return sessions[-1], sessions

def set_current_session(user_id, session):
    """Set the given session as the current session (move to end of list)"""
    sessions = load_chat_sessions(user_id)
    # Remove if already present
    sessions = [s for s in sessions if s["session_id"] != session["session_id"]]
    session["updated_at"] = datetime.now().isoformat()
    sessions.append(session)
    save_chat_sessions(user_id, sessions)
    return True

def encode_image(image_path):
    """Encode image to base64"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logging.error(f"Error encoding image: {e}")
        return None

@chat_bp.route('/chat')
def chat_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # Log basic session data for debugging
    logging.debug(f"Chat page access - user_id: {session['user_id']}")
    
    current_session, sessions = get_current_session(session['user_id'])
    if current_session is None:
        # No valid session, create a new one directly
        new_session = {
            "session_id": str(uuid.uuid4()),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "exchanges": [],
            "summary": ""
        }
        sessions.append(new_session)
        save_chat_sessions(session['user_id'], sessions)
        current_session = new_session
    history = current_session["exchanges"]
    
    # Process any existing history entries that don't have HTML processed responses
    for entry in history:
        if 'ai_response_html' not in entry and 'ai_response' in entry:
            entry['ai_response_html'] = process_markdown_response(entry['ai_response'])
    
    return render_template('chat.html',
                         chat_history=history,
                         chat_sessions=sessions,
                         available_models=AVAILABLE_MODELS,
                         available_image_models=AVAILABLE_IMAGE_MODELS,
                         user_id=session['user_id'],
                         is_admin=session.get('is_admin', False))

@chat_bp.route('/chat/send', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        model = request.form.get('model', 'gpt-4.1-mini')
        message = request.form.get('message', '').strip()
        user_id = session['user_id']

        if not message and 'file' not in request.files:
            return jsonify({'error': 'Please provide a message or upload a file'}), 400

        if model not in AVAILABLE_MODELS:
            model = 'gpt-5-mini'  # Default to gpt-5-mini

        # Load current session and all sessions
        current_session, sessions = get_current_session(user_id)

        # If no session exists or last session has exchanges, create a new session
        if not current_session or (current_session and current_session.get("exchanges")):
            # Create a new OpenAI vector store for this session
            client = get_openai_client()
            vs_name = f"session_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            vs = client.vector_stores.create(name=vs_name)
            vector_store_id = vs.id
            current_session = {
                "session_id": str(uuid.uuid4()),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "exchanges": [],
                "summary": "",
                "vector_store_id": vector_store_id
            }
            sessions.append(current_session)
        else:
            vector_store_id = current_session.get("vector_store_id")
            if not vector_store_id:
                # If missing, create one for this session
                client = get_openai_client()
                vs_name = f"session_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                vs = client.vector_stores.create(name=vs_name)
                vector_store_id = vs.id
                current_session["vector_store_id"] = vector_store_id

        # Check for long inactivity (more than 10 minutes since last message)
        exchanges = current_session["exchanges"]
        if exchanges:
            try:
                last_entry = exchanges[-1]
                last_time = last_entry.get('timestamp')
                if last_time:
                    last_dt = datetime.fromisoformat(last_time)
                    now_dt = datetime.now()
                    diff = (now_dt - last_dt).total_seconds()
                    if diff > 600:  # 600 seconds = 10 minutes
                        # Archive current session and start new one
                        client = get_openai_client()
                        vs_name = f"session_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        vs = client.vector_stores.create(name=vs_name)
                        vector_store_id = vs.id
                        current_session = {
                            "session_id": str(uuid.uuid4()),
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat(),
                            "exchanges": [],
                            "summary": "",
                            "vector_store_id": vector_store_id
                        }
                        sessions.append(current_session)
                        save_chat_sessions(user_id, sessions)
                        exchanges = current_session["exchanges"]
            except Exception as e:
                logging.error(f"Error checking chat inactivity: {e}")

        # Prepare messages for OpenAI with conversation history
        messages = []

        # Add conversation context (last 10 exchanges to stay within token limits)
        recent_history = exchanges[-10:] if len(exchanges) > 10 else exchanges
        for entry in recent_history:
            user_content = entry.get('user_message', '')
            if user_content:
                messages.append({
                    "role": "user",
                    "content": user_content
                })
            if entry.get('ai_response'):
                messages.append({
                    "role": "assistant",
                    "content": entry['ai_response']
                })


        # Prepare current message content parts
        content_parts = []

        uploaded_file = None
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                original_filename = file.filename
                safe_filename = secure_filename(original_filename)
                if '.' in original_filename and '.' not in safe_filename:
                    file_ext = original_filename.rsplit('.', 1)[1].lower()
                    safe_filename = f"{safe_filename}.{file_ext}"
                # Ensure directory exists with proper permissions
                os.makedirs('/tmp/uploads', exist_ok=True)
                try:
                    # Try to ensure directory is writable
                    if not os.access('/tmp/uploads', os.W_OK):
                        os.chmod('/tmp/uploads', 0o777)
                except Exception as e:
                    logging.error(f"Error setting permissions on /tmp/uploads: {e}")
                timestamp = int(datetime.now().timestamp())
                filepath = os.path.join('/tmp/uploads', f"{user_id}_{timestamp}_{safe_filename}")
                file.save(filepath)
                uploaded_file = filepath
                filename = safe_filename
                try:
                    file_size_mb = get_file_size_mb(filepath)
                    file_size_bytes = os.path.getsize(filepath)
                    if file_size_mb > MAX_FILE_SIZE_MB:
                        os.remove(filepath)
                        return jsonify({'error': f'File too large. Maximum size is {MAX_FILE_SIZE_MB}MB, your file is {file_size_mb:.1f}MB'}), 400
                except Exception as e:
                    logging.error(f"Error checking file size: {e}")
                    return jsonify({'error': 'Error processing file'}), 400
                file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
                if file_ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
                    base64_image = encode_image(filepath)
                    if base64_image:
                        content_parts.append({
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{base64_image}"
                        })
                    else:
                        return jsonify({'error': 'Failed to process image'}), 400
                elif file_ext in {'txt', 'md', 'py', 'js', 'html', 'css', 'json', 'xml', 'yaml', 'yml', 'sh', 'cpp', 'c', 'java', 'php', 'rb', 'go', 'rs', 'swift', 'kt', 'ts', 'jsx', 'tsx', 'vue', 'sql', 'rtf', 'pdf', 'docx', 'doc', 'pptx', 'ppt', 'xlsx', 'xls', 'csv'}:
                    # If file is >4KB, upload to OpenAI and attach to vector store
                    if file_size_bytes > 4096:
                        try:
                            client = get_openai_client()
                            with open(filepath, "rb") as f:
                                file_resp = client.files.create(file=f, purpose="assistants")
                            file_id = file_resp.id
                            # Attach file to vector store
                            vs_id = current_session["vector_store_id"]
                            client.vector_stores.files.create(vector_store_id=vs_id, file_id=file_id)
                            content_parts.append({
                                "type": "input_text",
                                "text": f"File '{filename}' ({file_size_mb:.1f}MB) uploaded to OpenAI vector store. You can now search its content."
                            })
                        except Exception as e:
                            logging.error(f"OpenAI vector store file upload error: {e}")
                            return jsonify({'error': 'Failed to upload file to OpenAI vector store'}), 500
                    else:
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                file_content = f.read()
                            content_parts.append({
                                "type": "input_text",
                                "text": f"File content ({filename}):\n```{file_ext}\n{file_content}\n```"
                            })
                            
                        except Exception as e:
                            logging.error(f"Error reading text file: {e}")
                            return jsonify({'error': 'Failed to read text file'}), 400
                else:
                    return jsonify({'error': f'Unsupported file type: {file_ext}'}), 400

        if content_parts:
            messages.extend(content_parts)

        messages.append({
          "role": "user",
            "content": message if message else ""
        })
        # Use file_search tool with vector store if present
        tools = []
        websearch_warning = None
        vs_id = current_session.get("vector_store_id")
        if vs_id:
            tools.append({
                "type": "file_search",
                "vector_store_ids": [vs_id],
                "max_num_results": 5
            })

        logging.info(f"Making API request with model: {model}, input: {messages}, tools: {tools}")
        response = get_openai_client().responses.create(
            model=model,
            input=messages,
            tools=tools if tools else None
        )
        ai_response = getattr(response, "output_text", None)

        if not ai_response:
            logging.warning(f"Empty response from model {model} for user {user_id}")
            ai_response = "I apologize, but I couldn't generate a response. Please try again."

        ai_response_html = process_markdown_response(ai_response)

        chat_entry = {
            'timestamp': datetime.now().isoformat(),
            'model': model,
            'user_message': message if message else f"[File uploaded: {os.path.basename(uploaded_file)}]" if uploaded_file else "[No message]",
            'ai_response': ai_response,
            'ai_response_html': ai_response_html,
            'has_file': uploaded_file is not None,
            'file_name': os.path.basename(uploaded_file) if uploaded_file else None
        }

        # Append to current session, limit to 10 exchanges
        current_session["exchanges"].append(chat_entry)
        current_session["exchanges"] = current_session["exchanges"][-10:]
        current_session["updated_at"] = datetime.now().isoformat()
        # Set summary if this is the first message in the session
        if len(current_session["exchanges"]) == 1:
            first_msg = chat_entry['user_message']
            current_session["summary"] = " ".join(first_msg.split()[:10]) + ("..." if len(first_msg.split()) > 10 else "")
        # Save sessions (move current to end)
        set_current_session(user_id, current_session)

        if uploaded_file and os.path.exists(uploaded_file):
            try:
                file_age = os.path.getmtime(uploaded_file)
                current_time = datetime.now().timestamp()
                if current_time - file_age > 3600:
                    os.remove(uploaded_file)
                    logging.info(f"Cleaned up old file: {uploaded_file}")
            except Exception as e:
                logging.error(f"Error during file cleanup check: {e}")

        return jsonify({
            'success': True,
            'response': ai_response_html,
            'timestamp': chat_entry['timestamp'],
            'model': model
        })

    except Exception as e:
        logging.error(f"Error in chat: {e}")
        return jsonify({'error': f'Error processing request: {str(e)}'}), 500

@chat_bp.route('/chat/generate-file', methods=['POST'])
def generate_file():
    """Generate a file based on AI response and make it downloadable"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        prompt = request.form.get('prompt', '').strip()
        file_type = request.form.get('file_type', 'txt').lower()
        filename = request.form.get('filename', '').strip()
        model = request.form.get('model', 'gpt-5')
        
        if not prompt:
            return jsonify({'error': 'Please provide a prompt for file generation'}), 400
        
        if not filename:
            return jsonify({'error': 'Please provide a filename'}), 400
        
        # Validate file type
        allowed_generated_types = ['txt', 'md', 'py', 'js', 'html', 'css', 'json', 'yaml', 'csv', 'sql', 'xml']
        if file_type not in allowed_generated_types:
            return jsonify({'error': f'Unsupported file type for generation: {file_type}'}), 400
        
        # Ensure filename has the correct extension
        if not filename.endswith(f'.{file_type}'):
            filename = f"{filename}.{file_type}"
        
        # Create a specific prompt for file generation
        file_generation_prompt = f"""
Generate a {file_type.upper()} file based on this request: {prompt}

Please provide ONLY the file content without any explanations, markdown formatting, or additional text.
The content should be ready to save directly as a .{file_type} file.
"""
        
        # Prepare OpenAI responses.create input
        input_payload = [{
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": file_generation_prompt
                }
            ]
        }]

        # Websearch tool support (optional, via form field)
        websearch = request.form.get('websearch', 'off') == 'on'
        websearch_supported_models = [
            "gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o4-mini", "o3", "gpt-5"
        ]
        tools = []
        websearch_warning = None
        if websearch:
            if any(model.startswith(m) for m in websearch_supported_models):
                tools = [{
                    "type": "web_search_preview",
                    "search_context_size": "low"
                }]
            else:
                websearch_warning = (
                    "Web search is not supported for the selected model. "
                    "Supported models: gpt-4o-mini, gpt-4o, gpt-4.1-mini, gpt-4.1, o4-mini, o3, gpt-5."
                )

        # Call OpenAI API
        response = get_openai_client().responses.create(
            model=model,
            input=input_payload,
            tools=tools if tools else None
        )
        file_content = getattr(response, "output_text", None)

        if not file_content:
            return jsonify({'error': 'Failed to generate file content'}), 500
        
        # Create generated files directory (now /tmp/downloaded)
        generated_dir = '/tmp/downloaded'
        os.makedirs(generated_dir, exist_ok=True)
        try:
            # Try to ensure directory is writable
            if not os.access(generated_dir, os.W_OK):
                os.chmod(generated_dir, 0o777)
        except Exception as e:
            logging.error(f"Error setting permissions on {generated_dir}: {e}")

        # Save file with timestamp to avoid conflicts
        timestamp = int(datetime.now().timestamp())
        safe_filename = secure_filename(filename)
        file_path = os.path.join(generated_dir, f"{session['user_id']}_{timestamp}_{safe_filename}")

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)

        # Save to chat history
        chat_entry = {
            'timestamp': datetime.now().isoformat(),
            'model': model,
            'user_message': f"Generate {file_type} file: {prompt}",
            'ai_response': f"Generated file: {safe_filename}",
            'ai_response_html': f"Generated file: <strong>{safe_filename}</strong>",
            'has_file': True,
            'generated_file': file_path,
            'file_name': f"{session['user_id']}_{timestamp}_{safe_filename}"
        }

        current_session, _ = get_current_session(session['user_id'])
        history = current_session["exchanges"]
        history.append(chat_entry)
        set_current_session(session['user_id'], current_session)

        response_payload = {
            'success': True,
            'filename': f"{session['user_id']}_{timestamp}_{safe_filename}",
            'file_path': file_path,
            'download_url': f"/chat/download-generated/{session['user_id']}_{timestamp}_{safe_filename}",
            'timestamp': chat_entry['timestamp'],
            'model': model
        }
        if websearch_warning:
            response_payload['warning'] = websearch_warning

        return jsonify(response_payload)
        
    except Exception as e:
        logging.error(f"Error generating file: {e}")
        return jsonify({'error': f'Error generating file: {str(e)}'}), 500

@chat_bp.route('/chat/generate-image', methods=['POST'])
def generate_image():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        prompt = request.form.get('prompt', '').strip()
        image_model = request.form.get('image_model', 'dall-e-3')
        image_size = request.form.get('image_size', '1024x1024')
        image_quality = request.form.get('image_quality', 'standard')
        
        if not prompt:
            return jsonify({'error': 'Please provide a prompt for image generation'}), 400
        
        # Validate model
        if image_model not in AVAILABLE_IMAGE_MODELS:
            image_model = 'dall-e-3'  # Default to DALL-E 3
        
        model_config = AVAILABLE_IMAGE_MODELS[image_model]
        
        # Validate size for the selected model
        if image_size not in model_config['sizes']:
            image_size = model_config['sizes'][0]  # Default to first available size
        
        # Validate quality for the selected model
        if image_quality not in model_config['quality']:
            image_quality = model_config['quality'][0]  # Default to first available quality
        
        # Prepare API parameters
        api_params = {
            'model': image_model,
            'prompt': prompt,
            'n': 1,
            'size': image_size
        }
        
        # Add quality parameter only for DALL-E 3
        if image_model == 'dall-e-3':
            api_params['quality'] = image_quality
        
        # Generate image using selected model
        response = get_openai_client().images.generate(**api_params)
        if not response or not response.data or len(response.data) == 0:
            return jsonify({'error': 'Failed to generate image'}), 500
        image_url = response.data[0].url

        # Download the image and save locally
        import requests
        from urllib.parse import urlparse
        local_dir = '/tmp/downloaded'
        os.makedirs(local_dir, exist_ok=True)
        # Use timestamp and user_id for unique filename
        timestamp = int(datetime.now().timestamp())
        ext = image_url.split('.')[-1].split('?')[0]
        if ext.lower() not in ['png', 'jpg', 'jpeg', 'webp', 'gif']:
            ext = 'png'
        local_filename = f"{session['user_id']}_{timestamp}.{ext}"
        local_path = os.path.join(local_dir, local_filename)
        try:
            img_resp = requests.get(image_url)
            img_resp.raise_for_status()
            with open(local_path, 'wb') as f:
                f.write(img_resp.content)
        except Exception as e:
            logging.error(f"Error downloading generated image: {e}")
            return jsonify({'error': 'Failed to download generated image'}), 500

        # Create model display name with settings
        model_display = f"{model_config['name']} ({image_size}"
        if image_model == 'dall-e-3' and image_quality == 'hd':
            model_display += f", {image_quality.upper()}"
        model_display += ")"

        # Save to chat history
        chat_entry = {
            'timestamp': datetime.now().isoformat(),
            'model': model_display,
            'user_message': f"Generate image: {prompt}",
            'ai_response': f"Generated image using {model_display}",
            'image_url': f"/chat/download-image/{local_filename}",
            'has_file': True,
            'file_name': local_filename
        }

        current_session, _ = get_current_session(session['user_id'])
        history = current_session["exchanges"]
        history.append(chat_entry)
        set_current_session(session['user_id'], current_session)

        return jsonify({
            'success': True,
            'image_url': f"/chat/download-image/{local_filename}",
            'timestamp': chat_entry['timestamp'],
            'model': model_display
        })
        
    except Exception as e:
        logging.error(f"Error generating image: {e}")
        return jsonify({'error': f'Error generating image: {str(e)}'}), 500

@chat_bp.route('/chat/clear', methods=['POST'])
def clear_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        # Archive current session and start a new one
        sessions = load_chat_sessions(session['user_id'])
        new_session = {
            "session_id": str(uuid.uuid4()),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "exchanges": []
        }
        sessions.append(new_session)
        save_chat_sessions(session['user_id'], sessions)
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Error clearing chat history: {e}")
        return jsonify({'error': 'Failed to clear history'}), 500

# --- New endpoints for session management ---

@chat_bp.route('/chat/sessions', methods=['GET'])
def list_sessions():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    sessions = load_chat_sessions(session['user_id'])
    # Only return sessions with at least one exchange
    filtered_sessions = [s for s in sessions if s.get("exchanges")]
    # Return metadata only, including summary
    session_list = [
        {
            "session_id": s["session_id"],
            "created_at": s["created_at"],
            "updated_at": s.get("updated_at", s["created_at"]),
            "num_exchanges": len(s.get("exchanges", [])),
            "summary": s.get("summary", "")
        }
        for s in filtered_sessions
    ]
    return jsonify(session_list)

@chat_bp.route('/chat/sessions/revert', methods=['POST'])
def revert_session():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    session_id = request.json.get("session_id")
    sessions = load_chat_sessions(session['user_id'])
    found = None
    for s in sessions:
        if s["session_id"] == session_id:
            found = s
            break
    if not found:
        return jsonify({'error': 'Session not found'}), 404
    # Move found session to end (current)
    set_current_session(session['user_id'], found)
    return jsonify({'success': True})

@chat_bp.route('/chat/sessions/new', methods=['POST'])
def new_session():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    sessions = load_chat_sessions(session['user_id'])
    new_session = {
        "session_id": str(uuid.uuid4()),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "exchanges": []
    }
    sessions.append(new_session)
    save_chat_sessions(session['user_id'], sessions)
    return jsonify({'success': True, 'session_id': new_session["session_id"]})

@chat_bp.route('/chat/download-image/<filename>')
def download_image(filename):
    """Endpoint to properly download generated images from /tmp/downloaded"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        # Only allow files from /tmp/downloaded and matching user_id
        local_dir = '/tmp/downloaded'
        if not filename or '..' in filename or '/' in filename:
            return jsonify({'error': 'Invalid filename'}), 400
        # Optionally, check user_id in filename
        if not filename.startswith(f"{session['user_id']}_"):
            return jsonify({'error': 'Access denied'}), 403
        file_path = os.path.join(local_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'Image not found'}), 404
        # Guess mimetype
        ext = filename.split('.')[-1].lower()
        mimetype = 'image/png'
        if ext in ['jpg', 'jpeg']:
            mimetype = 'image/jpeg'
        elif ext == 'gif':
            mimetype = 'image/gif'
        elif ext == 'webp':
            mimetype = 'image/webp'
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
    except Exception as e:
        logging.error(f"Error downloading image: {e}")
        return jsonify({'error': 'Download failed'}), 500

@chat_bp.route('/chat/download-generated/<filename>')
def download_generated_file(filename):
    """Download a generated file from /tmp/downloaded, only if it matches user_id"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        generated_dir = '/tmp/downloaded'
        if not filename or '..' in filename or '/' in filename:
            return jsonify({'error': 'Invalid filename'}), 400
        if not filename.startswith(f"{session['user_id']}_"):
            return jsonify({'error': 'Access denied'}), 403
        file_path = os.path.join(generated_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found or access denied'}), 404
        # Determine MIME type based on extension
        ext = filename.split('.')[-1].lower()
        mime_types = {
            'txt': 'text/plain',
            'md': 'text/markdown',
            'py': 'text/x-python',
            'js': 'application/javascript',
            'html': 'text/html',
            'css': 'text/css',
            'json': 'application/json',
            'yaml': 'application/x-yaml',
            'yml': 'application/x-yaml',
            'csv': 'text/csv',
            'sql': 'application/sql',
            'xml': 'application/xml'
        }
        mimetype = mime_types.get(ext, 'text/plain')
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename.split('_', 2)[-1],
            mimetype=mimetype
        )
    except Exception as e:
        logging.error(f"Error downloading generated file: {e}")
        return jsonify({'error': 'Download failed'}), 500

@chat_bp.route('/chat/history')
def chat_history_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    current_session, _ = get_current_session(session['user_id'])
    history = current_session["exchanges"]
    for entry in history:
        if 'ai_response_html' not in entry and 'ai_response' in entry:
            entry['ai_response_html'] = process_markdown_response(entry['ai_response'])
    return render_template('chat_history.html', chat_history=history, user_id=session['user_id'])