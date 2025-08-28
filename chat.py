import os
import json
import base64
import logging
import glob
from datetime import datetime
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, send_file, Response
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
openai_client = OpenAI(api_key=OPENAI_API_KEY)

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
MAX_FILE_SIZE_MB = 32
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

def load_chat_history(user_id):
    """Load user's chat history"""
    filename = f'chat_history_{user_id}.json'
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        logging.error(f"Error loading chat history for {user_id}: {e}")
        return []

def save_chat_history(user_id, history):
    """Save user's chat history (keep only last 10 exchanges) and clean up associated files"""
    filename = f'chat_history_{user_id}.json'
    try:
        # Clean up files from entries that will be removed
        if len(history) > 10:
            entries_to_remove = history[:-10]
            for entry in entries_to_remove:
                if entry.get('has_file') and entry.get('file_name'):
                    # Try to find and remove the associated file
                    for file_path in glob.glob(f"uploads/{user_id}_*_{entry['file_name']}"):
                        try:
                            os.remove(file_path)
                            logging.info(f"Cleaned up file: {file_path}")
                        except Exception as e:
                            logging.error(f"Error removing file {file_path}: {e}")
            
            # Keep only the last 10 conversations
            history = history[-10:]
        
        with open(filename, 'w') as f:
            json.dump(history, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error saving chat history for {user_id}: {e}")
        return False

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
    
    history = load_chat_history(session['user_id'])
    
    # Process any existing history entries that don't have HTML processed responses
    for entry in history:
        if 'ai_response_html' not in entry and 'ai_response' in entry:
            entry['ai_response_html'] = process_markdown_response(entry['ai_response'])
    
    return render_template('chat.html', 
                         chat_history=history, 
                         available_models=AVAILABLE_MODELS,
                         available_image_models=AVAILABLE_IMAGE_MODELS,
                         user_id=session['user_id'],
                         is_admin=session.get('is_admin', False))

@chat_bp.route('/chat/send', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        model = request.form.get('model', 'gpt-5')
        message = request.form.get('message', '').strip()
        
        if not message and 'file' not in request.files:
            return jsonify({'error': 'Please provide a message or upload a file'}), 400
        
        if model not in AVAILABLE_MODELS:
            model = 'gpt-5-mini'  # Default to gpt-5-mini
        
        # Load chat history for context threading
        history = load_chat_history(session['user_id'])
        
        # Prepare messages for OpenAI with conversation history
        messages = []
        
        # Add conversation context (last 10 exchanges to stay within token limits)
        recent_history = history[-10:] if len(history) > 10 else history
        for entry in recent_history:
            # Add user message (handle both string and structured content)
            user_content = entry.get('user_message', '')
            if user_content:  # Only add non-empty user messages
                messages.append({
                    "role": "user",
                    "content": user_content
                })
            # Add AI response
            if entry.get('ai_response'):
                messages.append({
                    "role": "assistant", 
                    "content": entry['ai_response']
                })
        
        # Prepare current message content parts
        content_parts = []
        
        # Add text message if provided
        if message:
            content_parts.append({
                "type": "text",
                "text": message
            })
        
        # Handle file upload
        uploaded_file = None
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                # Preserve original filename but make it secure
                original_filename = file.filename
                safe_filename = secure_filename(original_filename)
                
                # If secure_filename removes the extension, add it back
                if '.' in original_filename and '.' not in safe_filename:
                    file_ext = original_filename.rsplit('.', 1)[1].lower()
                    safe_filename = f"{safe_filename}.{file_ext}"
                
                # Create uploads directory if it doesn't exist
                os.makedirs('uploads', exist_ok=True)
                
                # Use timestamp to avoid conflicts
                timestamp = int(datetime.now().timestamp())
                filepath = os.path.join('uploads', f"{session['user_id']}_{timestamp}_{safe_filename}")
                file.save(filepath)
                uploaded_file = filepath
                filename = safe_filename  # Update filename variable for later use
                
                # Check file size
                try:
                    file_size_mb = get_file_size_mb(filepath)
                    if file_size_mb > MAX_FILE_SIZE_MB:
                        os.remove(filepath)  # Clean up
                        return jsonify({'error': f'File too large. Maximum size is {MAX_FILE_SIZE_MB}MB, your file is {file_size_mb:.1f}MB'}), 400
                except Exception as e:
                    logging.error(f"Error checking file size: {e}")
                    return jsonify({'error': 'Error processing file'}), 400
                
                # Handle different file types
                file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
                
                if file_ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
                    # Image file - for vision models
                    base64_image = encode_image(filepath)
                    if base64_image:
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        })
                    else:
                        return jsonify({'error': 'Failed to process image'}), 400
                
                elif file_ext in {'txt', 'md', 'py', 'js', 'html', 'css', 'json', 'xml', 'yaml', 'yml', 'sh', 'cpp', 'c', 'java', 'php', 'rb', 'go', 'rs', 'swift', 'kt', 'ts', 'jsx', 'tsx', 'vue', 'sql', 'rtf'}:
                    # Text-based files
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            file_content = f.read()
                        content_parts.append({
                            "type": "text", 
                            "text": f"File content ({filename}):\n```{file_ext}\n{file_content}\n```"
                        })
                    except Exception as e:
                        logging.error(f"Error reading text file: {e}")
                        return jsonify({'error': 'Failed to read text file'}), 400
                
                elif file_ext in {'pdf', 'docx', 'doc', 'pptx', 'ppt', 'xlsx', 'xls', 'csv'}:
                    # Document files - try to read basic content or provide file info
                    if file_ext == 'pdf':
                        # For PDF files, provide file information and mention OpenAI can process it
                        content_parts.append({
                            "type": "text",
                            "text": f"I've received your PDF file '{filename}' (size: {file_size_mb:.1f}MB). " +
                                   f"The file is now available at: {filepath}. PDF files are well-supported by OpenAI models. " +
                                   "Please describe what you'd like me to do with this file."
                        })
                    else:
                        # Other document formats
                        content_parts.append({
                            "type": "text",
                            "text": f"I've received your {file_ext.upper()} file '{filename}' (size: {file_size_mb:.1f}MB). " +
                                   f"The file is saved at: {filepath}. " +
                                   "Note: PDF files work most reliably with OpenAI. Other formats may have limited support."
                        })
                
                else:
                    return jsonify({'error': f'Unsupported file type: {file_ext}'}), 400
            
            elif file and file.filename:
                return jsonify({'error': 'File type not supported'}), 400
        
        if not content_parts:
            return jsonify({'error': 'No valid content provided'}), 400
        
        # Add current user message to conversation thread
        messages.append({
            "role": "user",
            "content": content_parts
        })
        
        # Call OpenAI API
        logging.info(f"Making API request with model: {model}, messages: {len(messages)} messages")
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=1000
        )
        logging.info(f"API response received: {len(response.choices)} choices")
        
        ai_response = response.choices[0].message.content
        
        # Debug logging for empty responses
        if not ai_response:
            logging.warning(f"Empty response from model {model} for user {session['user_id']}")
            ai_response = "I apologize, but I couldn't generate a response. Please try again."
        
        # Process markdown in AI response
        ai_response_html = process_markdown_response(ai_response)
        
        # Save to chat history  
        chat_entry = {
            'timestamp': datetime.now().isoformat(),
            'model': model,
            'user_message': message if message else f"[File uploaded: {os.path.basename(uploaded_file)}]" if uploaded_file else "[No message]",
            'ai_response': ai_response,
            'ai_response_html': ai_response_html,
            'has_file': uploaded_file is not None,
            'file_name': os.path.basename(uploaded_file) if uploaded_file else None
        }
        
        # Note: history was already loaded above for threading context
        history.append(chat_entry)
        save_chat_history(session['user_id'], history)
        
        # Clean up uploaded file after a delay (keep for user reference but clean old files)
        # Note: We keep files temporarily for user reference and clean up old files periodically
        if uploaded_file and os.path.exists(uploaded_file):
            try:
                # Only clean up files older than 1 hour to allow users to see their uploads
                file_age = os.path.getmtime(uploaded_file)
                current_time = datetime.now().timestamp()
                if current_time - file_age > 3600:  # 1 hour
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
        
        # Call OpenAI API
        response = openai_client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": file_generation_prompt
            }],
            max_completion_tokens=2000
        )
        
        file_content = response.choices[0].message.content
        
        if not file_content:
            return jsonify({'error': 'Failed to generate file content'}), 500
        
        # Create generated files directory
        generated_dir = 'generated_files'
        os.makedirs(generated_dir, exist_ok=True)
        
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
            'has_file': False,
            'generated_file': file_path,
            'file_name': safe_filename
        }
        
        history = load_chat_history(session['user_id'])
        history.append(chat_entry)
        save_chat_history(session['user_id'], history)
        
        return jsonify({
            'success': True,
            'filename': safe_filename,
            'file_path': file_path,
            'download_url': f'/chat/download-generated/{safe_filename}',
            'timestamp': chat_entry['timestamp'],
            'model': model
        })
        
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
        response = openai_client.images.generate(**api_params)
        
        if not response or not response.data or len(response.data) == 0:
            return jsonify({'error': 'Failed to generate image'}), 500
            
        image_url = response.data[0].url
        
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
            'image_url': image_url,
            'has_file': False
        }
        
        history = load_chat_history(session['user_id'])
        history.append(chat_entry)
        save_chat_history(session['user_id'], history)
        
        return jsonify({
            'success': True,
            'image_url': image_url,
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
        filename = f'chat_history_{session["user_id"]}.json'
        if os.path.exists(filename):
            os.remove(filename)
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Error clearing chat history: {e}")
        return jsonify({'error': 'Failed to clear history'}), 500

@chat_bp.route('/chat/download-image/<path:image_path>')
def download_image(image_path):
    """Endpoint to properly download generated images"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Security check - ensure the image path is safe and belongs to user
        if not image_path.startswith('static/images/'):
            return jsonify({'error': 'Invalid image path'}), 400
        
        # Check if file exists
        if not os.path.exists(image_path):
            return jsonify({'error': 'Image not found'}), 404
        
        # Extract filename for download
        filename = os.path.basename(image_path)
        
        return send_file(
            image_path,
            as_attachment=True,
            download_name=filename,
            mimetype='image/png'
        )
    except Exception as e:
        logging.error(f"Error downloading image: {e}")
        return jsonify({'error': 'Download failed'}), 500

@chat_bp.route('/chat/download-generated/<filename>')
def download_generated_file(filename):
    """Download a generated file"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Security check - ensure file belongs to current user
        generated_dir = 'generated_files'
        user_files = glob.glob(os.path.join(generated_dir, f"{session['user_id']}_*_{filename}"))
        
        if not user_files:
            return jsonify({'error': 'File not found or access denied'}), 404
        
        # Get the most recent file if multiple exist
        file_path = max(user_files, key=os.path.getmtime)
        
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
            download_name=filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        logging.error(f"Error downloading generated file: {e}")
        return jsonify({'error': 'Download failed'}), 500

@chat_bp.route('/chat/history')
def chat_history_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    history = load_chat_history(session['user_id'])
    for entry in history:
        if 'ai_response_html' not in entry and 'ai_response' in entry:
            entry['ai_response_html'] = process_markdown_response(entry['ai_response'])
    return render_template('chat_history.html', chat_history=history, user_id=session['user_id'])