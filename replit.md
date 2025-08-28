# Overview

This is a Flask-based AI chatbot web application that provides users with an interface to interact with OpenAI's GPT models. The application features user authentication, chat history management, comprehensive file upload capabilities, and administrative controls with user limits. Users can engage in conversations with AI models, upload various file types for analysis, generate AI images, and switch between different GPT models. The system maintains individual chat histories for each user and provides admin functionality for user management with a maximum of 10 users.

Recent enhancements include:
- Comprehensive file attachment support for all OpenAI-compatible formats (PDF, documents, spreadsheets, code files, images)
- File size validation (32MB maximum)  
- User management system with 10-user limit enforced at registration and admin levels
- **Conversation threading**: Maintains context across messages using OpenAI's chat completions API with last 10 exchanges
- **Clear history functionality**: Resets conversation thread when clearing chat history
- Markdown rendering with syntax-highlighted code blocks
- Copy functionality for both user and AI messages
- Fixed image download functionality
- Enhanced admin panel with user statistics and system information
- Improved error handling for JSON responses and file uploads

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
The application uses a traditional server-side rendered architecture with Flask templates and Bootstrap for styling. The frontend consists of HTML templates that extend a base template, providing a consistent dark-themed interface. JavaScript handles dynamic interactions like chat functionality, model switching, and file uploads. The UI is responsive and includes features like copy-to-clipboard functionality and real-time chat updates.

## Backend Architecture
The application follows a modular Flask blueprint architecture with three main components:
- **Main App** (`app.py`): Handles application initialization, configuration, and routing coordination
- **Authentication Module** (`auth.py`): Manages user registration, login, logout, and admin functionality
- **Chat Module** (`chat.py`): Handles AI interactions, chat history, and file processing

The application uses session-based authentication stored in Flask sessions, with user data persisted to YAML files for simplicity.

## Data Storage
The system uses file-based storage rather than a traditional database:
- **User Data**: Stored in `users.yml` using YAML format with bcrypt-hashed passwords
- **Chat History**: Individual JSON files per user (`chat_history_{user_id}.json`) storing conversation data
- **File Uploads**: Stored in an `uploads` directory with secure filename handling

This approach was chosen for simplicity and quick deployment, avoiding database setup requirements.

## Authentication & Authorization
The authentication system uses:
- **Password Security**: Bcrypt hashing with a secret key salt for enhanced security
- **Session Management**: Flask sessions for maintaining user login state
- **Role-Based Access**: Admin flag in user data for administrative privileges with enhanced admin panel
- **Input Validation**: Server-side validation for registration and login forms
- **User Limits**: Maximum 10 users enforced system-wide with clear messaging when limit is reached
- **Admin Interface**: Full user management including add/delete users, view statistics, and system monitoring

## AI Integration
The chat system integrates with OpenAI's API:
- **Model Selection**: Supports multiple GPT models (gpt-5, gpt-5-mini, gpt-5-nano, gpt-4, gpt-4-turbo, gpt-3.5-turbo)
- **Comprehensive File Support**: Handles multiple file types including:
  - Images (PNG, JPG, GIF, WebP) for vision models
  - Documents (PDF, Word, PowerPoint, RTF) 
  - Spreadsheets (CSV, Excel)
  - Code files (Python, JavaScript, HTML, CSS, JSON, SQL, etc.)
  - Text files (TXT, Markdown, YAML)
- **File Processing**: Smart file type detection with appropriate handling for each format
- **Size Validation**: 32MB maximum file size with user-friendly error messages
- **Image Generation**: DALL-E integration for AI image creation
- **Context Management**: Maintains conversation context within chat sessions
- **Markdown Processing**: AI responses are processed to render markdown with syntax-highlighted code blocks
- **Copy Functionality**: Users can copy both their own messages and code snippets from AI responses
- **Enhanced Downloads**: Images can be properly downloaded through dedicated endpoints

# External Dependencies

## Third-Party Services
- **OpenAI API**: Primary AI service for chat completions and image generation
- **CDN Resources**: Bootstrap CSS framework and Font Awesome icons served from CDNs

## Python Packages
- **Flask**: Web framework for application structure and routing
- **OpenAI**: Official Python client for OpenAI API interactions
- **PyYAML**: YAML file parsing for user data storage
- **bcrypt**: Password hashing (via Werkzeug security utilities)
- **Werkzeug**: WSGI utilities including proxy handling and security functions
- **Requests**: HTTP client library for external API calls
- **Markdown**: Processing markdown text to HTML with extensions support
- **Pygments**: Syntax highlighting for code blocks in multiple programming languages

## Frontend Libraries
- **Bootstrap 5**: CSS framework for responsive design and dark theme
- **Font Awesome**: Icon library for UI elements
- **Vanilla JavaScript**: Client-side functionality without additional frameworks

## File System Dependencies
- **Upload Directory**: Local file storage for user-uploaded images
- **YAML Storage**: File-based user data persistence
- **JSON Storage**: Individual chat history files per user