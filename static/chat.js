// Chat functionality for AI Chatbot
class ChatApp {
    constructor() {
        this.currentModel = 'gpt-5-mini'; // Default to gpt-5-mini
        this.imageOptionsVisible = false;
        this.fileOptionsVisible = false;
        this.initializeEventListeners();
        this.scrollToBottom();
    }

    initializeEventListeners() {
        // Chat form submission
        const chatForm = document.getElementById('chatForm');
        if (chatForm) {
            chatForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.sendMessage();
            });
        }

        // Model selection
        document.querySelectorAll('.model-option').forEach(option => {
            option.addEventListener('click', (e) => {
                e.preventDefault();
                this.changeModel(e.target.dataset.model);
            });
        });

        // Copy buttons
        document.addEventListener('click', (e) => {
            if (e.target.closest('.copy-btn')) {
                const btn = e.target.closest('.copy-btn');
                this.copyToClipboard(btn.dataset.text, btn);
            } else if (e.target.closest('.copy-code-btn')) {
                const btn = e.target.closest('.copy-code-btn');
                this.copyToClipboard(btn.dataset.code, btn);
            }
        });

        // Clear history button
        const clearBtn = document.getElementById('clearHistoryBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                this.clearHistory();
            });
        }

        // Generate image button
        const generateImageBtn = document.getElementById('generateImageBtn');
        if (generateImageBtn) {
            generateImageBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleImageButtonClick();
            });
        }

        // Generate file button
        const generateFileBtn = document.getElementById('generateFileBtn');
        if (generateFileBtn) {
            generateFileBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleFileButtonClick();
            });
        }

        // Image model selection
        const imageModelSelect = document.getElementById('imageModel');
        if (imageModelSelect) {
            imageModelSelect.addEventListener('change', () => {
                this.updateImageOptions();
            });
        }

        // Enter key handling for message textarea
        const messageTextarea = document.getElementById('message');
        if (messageTextarea) {
            messageTextarea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
    }

    changeModel(model) {
        this.currentModel = model;
        document.getElementById('currentModel').textContent = model;
    }

    showLoading() {
        const modal = new bootstrap.Modal(document.getElementById('loadingModal'));
        modal.show();
        return modal;
    }

    hideLoading(modal) {
        modal.hide();
    }

    async sendMessage() {
        const messageInput = document.getElementById('message');
        const fileInput = document.getElementById('file');
        const message = messageInput.value.trim();
        const file = fileInput.files[0];

        if (!message && !file) {
            this.showError('Please enter a message or select a file to upload.');
            return;
        }

        const loadingModal = this.showLoading();

        try {
            const formData = new FormData();
            formData.append('message', message);
            formData.append('model', this.currentModel);
            
            if (file) {
                formData.append('file', file);
            }

            const response = await fetch('/chat/send', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                throw new Error(`Expected JSON response, got: ${text.substring(0, 100)}`);
            }

            const data = await response.json();

            if (data.success) {
                this.addMessageToChat({
                    user_message: message,
                    ai_response: data.response,
                    timestamp: data.timestamp,
                    model: data.model,
                    has_file: !!file,
                    file_name: file ? file.name : null
                });

                // Clear form
                messageInput.value = '';
                fileInput.value = '';
            } else {
                this.showError(data.error || 'Error sending message');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showError('Network error. Please try again.');
        } finally {
            this.hideLoading(loadingModal);
        }
    }

    handleImageButtonClick() {
        if (!this.imageOptionsVisible) {
            this.showImageOptions();
        } else {
            this.generateImage();
        }
    }

    showImageOptions() {
        const imageOptions = document.getElementById('imageOptions');
        const generateBtn = document.getElementById('generateImageBtn');
        
        imageOptions.style.display = 'block';
        generateBtn.innerHTML = '<i class="fas fa-magic"></i> Generate Now';
        generateBtn.className = 'btn btn-success';
        this.imageOptionsVisible = true;
        this.updateImageOptions();
    }

    hideImageOptions() {
        const imageOptions = document.getElementById('imageOptions');
        const generateBtn = document.getElementById('generateImageBtn');
        
        imageOptions.style.display = 'none';
        generateBtn.innerHTML = '<i class="fas fa-image"></i> Generate Image';
        generateBtn.className = 'btn btn-secondary';
        this.imageOptionsVisible = false;
    }

    updateImageOptions() {
        const imageModelSelect = document.getElementById('imageModel');
        const imageSizeSelect = document.getElementById('imageSize');
        const imageQualitySelect = document.getElementById('imageQuality');
        
        if (!imageModelSelect || !window.imageModelConfig) return;
        
        const selectedModel = imageModelSelect.value;
        const modelConfig = window.imageModelConfig[selectedModel];
        
        if (modelConfig) {
            // Update sizes
            imageSizeSelect.innerHTML = '';
            modelConfig.sizes.forEach(size => {
                const option = document.createElement('option');
                option.value = size;
                option.textContent = size;
                imageSizeSelect.appendChild(option);
            });
            
            // Update quality options
            imageQualitySelect.innerHTML = '';
            modelConfig.quality.forEach(quality => {
                const option = document.createElement('option');
                option.value = quality;
                option.textContent = quality === 'hd' ? 'HD' : 'Standard';
                imageQualitySelect.appendChild(option);
            });
        }
    }

    async generateImage() {
        const messageInput = document.getElementById('message');
        const prompt = messageInput.value.trim();
        const imageModel = document.getElementById('imageModel').value;
        const imageSize = document.getElementById('imageSize').value;
        const imageQuality = document.getElementById('imageQuality').value;

        if (!prompt) {
            this.showError('Please enter a prompt for image generation.');
            return;
        }

        const loadingModal = this.showLoading();

        try {
            const formData = new FormData();
            formData.append('prompt', prompt);
            formData.append('image_model', imageModel);
            formData.append('image_size', imageSize);
            formData.append('image_quality', imageQuality);

            const response = await fetch('/chat/generate-image', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                this.addImageToChat({
                    user_message: `Generate image: ${prompt}`,
                    image_url: data.image_url,
                    timestamp: data.timestamp,
                    model: data.model
                });

                // Clear form and hide options
                messageInput.value = '';
                this.hideImageOptions();
            } else {
                this.showError(data.error || 'Error generating image');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showError('Network error. Please try again.');
        } finally {
            this.hideLoading(loadingModal);
        }
    }

    addMessageToChat(entry) {
        const chatHistory = document.getElementById('chatHistory');
        
        // Create user message
        const userMessageDiv = document.createElement('div');
        userMessageDiv.className = 'chat-message user-message';
        userMessageDiv.innerHTML = `
            <div class="message-header">
                <strong><i class="fas fa-user"></i> You</strong>
                <div class="d-flex gap-2 align-items-center">
                    <button class="btn btn-sm btn-outline-secondary copy-btn" data-text="${entry.user_message.replace(/"/g, '&quot;')}">
                        <i class="fas fa-copy"></i>
                    </button>
                    <small class="text-muted">${new Date(entry.timestamp).toLocaleString()}</small>
                </div>
            </div>
            <div class="message-content">
                ${entry.user_message}
                ${entry.has_file ? `<small class="text-info d-block"><i class="fas fa-file"></i> Uploaded: ${entry.file_name}</small>` : ''}
            </div>
        `;

        // Create AI message
        const aiMessageDiv = document.createElement('div');
        aiMessageDiv.className = 'chat-message ai-message';
        aiMessageDiv.innerHTML = `
            <div class="message-header">
                <strong><i class="fas fa-robot"></i> AI (${entry.model})</strong>
                <button class="btn btn-sm btn-outline-secondary copy-btn" data-text="${entry.ai_response.replace(/"/g, '&quot;')}">
                    <i class="fas fa-copy"></i>
                </button>
            </div>
            <div class="message-content">
                <div class="ai-response">${entry.ai_response}</div>
            </div>
        `;

        chatHistory.appendChild(userMessageDiv);
        chatHistory.appendChild(aiMessageDiv);
        
        this.scrollToBottom();
    }

    addImageToChat(entry) {
        const chatHistory = document.getElementById('chatHistory');
        
        // Create user message
        const userMessageDiv = document.createElement('div');
        userMessageDiv.className = 'chat-message user-message';
        userMessageDiv.innerHTML = `
            <div class="message-header">
                <strong><i class="fas fa-user"></i> You</strong>
                <small class="text-muted">${new Date(entry.timestamp).toLocaleString()}</small>
            </div>
            <div class="message-content">${entry.user_message}</div>
        `;

        // Create AI message with image
        const aiMessageDiv = document.createElement('div');
        aiMessageDiv.className = 'chat-message ai-message';
        aiMessageDiv.innerHTML = `
            <div class="message-header">
                <strong><i class="fas fa-robot"></i> AI (${entry.model})</strong>
                <button class="btn btn-sm btn-outline-secondary copy-btn" data-text="${entry.image_url}">
                    <i class="fas fa-copy"></i>
                </button>
            </div>
            <div class="message-content">
                <img src="${entry.image_url}" class="img-fluid generated-image" alt="Generated image">
                <a href="${entry.image_url}" download class="btn btn-sm btn-outline-success mt-2">
                    <i class="fas fa-download"></i> Download Image
                </a>
            </div>
        `;

        chatHistory.appendChild(userMessageDiv);
        chatHistory.appendChild(aiMessageDiv);
        
        this.scrollToBottom();
    }

    handleFileButtonClick() {
        if (!this.fileOptionsVisible) {
            this.showFileOptions();
        } else {
            this.generateFile();
        }
    }

    showFileOptions() {
        const fileOptions = document.getElementById('fileOptions');
        const generateBtn = document.getElementById('generateFileBtn');
        
        fileOptions.style.display = 'block';
        generateBtn.innerHTML = '<i class="fas fa-magic"></i> Generate Now';
        generateBtn.className = 'btn btn-warning';
        this.fileOptionsVisible = true;
    }

    hideFileOptions() {
        const fileOptions = document.getElementById('fileOptions');
        const generateBtn = document.getElementById('generateFileBtn');
        
        fileOptions.style.display = 'none';
        generateBtn.innerHTML = '<i class="fas fa-file-code"></i> Generate File';
        generateBtn.className = 'btn btn-info';
        this.fileOptionsVisible = false;
    }

    async generateFile() {
        const messageInput = document.getElementById('message');
        const fileTypeSelect = document.getElementById('fileType');
        const filenameInput = document.getElementById('generateFilename');
        
        const prompt = messageInput.value.trim();
        const fileType = fileTypeSelect.value;
        const filename = filenameInput.value.trim();

        if (!prompt) {
            this.showError('Please enter a description of what file you want to generate.');
            return;
        }

        if (!filename) {
            this.showError('Please enter a filename for the generated file.');
            return;
        }

        const loadingModal = this.showLoading();

        try {
            const formData = new FormData();
            formData.append('prompt', prompt);
            formData.append('file_type', fileType);
            formData.append('filename', filename);
            formData.append('model', this.currentModel);

            const response = await fetch('/chat/generate-file', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                throw new Error(`Expected JSON response, got: ${text.substring(0, 100)}`);
            }

            const data = await response.json();

            if (data.success) {
                this.addFileGenerationToChat({
                    user_message: `Generate ${fileType} file: ${prompt}`,
                    ai_response: `Generated file: ${data.filename}`,
                    timestamp: data.timestamp,
                    model: data.model,
                    filename: data.filename,
                    download_url: data.download_url
                });

                // Clear form
                messageInput.value = '';
                filenameInput.value = '';
                this.hideFileOptions();
                this.showSuccess(`File ${data.filename} generated successfully!`);
            } else {
                this.showError(data.error || 'Error generating file');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showError('Network error. Please try again.');
        } finally {
            this.hideLoading(loadingModal);
        }
    }

    addFileGenerationToChat(entry) {
        const chatHistory = document.getElementById('chatHistory');
        
        // User message
        const userMessageDiv = document.createElement('div');
        userMessageDiv.className = 'chat-message user-message';
        userMessageDiv.innerHTML = `
            <div class="message-header">
                <strong><i class="fas fa-user"></i> You</strong>
                <div class="d-flex gap-2 align-items-center">
                    <button class="btn btn-sm btn-outline-secondary copy-btn" data-text="${entry.user_message}">
                        <i class="fas fa-copy"></i>
                    </button>
                    <small class="text-muted">${entry.timestamp}</small>
                </div>
            </div>
            <div class="message-content">
                ${entry.user_message}
            </div>
        `;

        // AI response with download link
        const aiMessageDiv = document.createElement('div');
        aiMessageDiv.className = 'chat-message ai-message';
        aiMessageDiv.innerHTML = `
            <div class="message-header">
                <strong><i class="fas fa-robot"></i> AI (${entry.model})</strong>
                <button class="btn btn-sm btn-outline-secondary copy-btn" data-text="${entry.ai_response}">
                    <i class="fas fa-copy"></i>
                </button>
            </div>
            <div class="message-content">
                <p>${entry.ai_response}</p>
                <div class="mt-2">
                    <a href="${entry.download_url}" class="btn btn-sm btn-outline-success" download="${entry.filename}">
                        <i class="fas fa-download"></i> Download ${entry.filename}
                    </a>
                </div>
            </div>
        `;

        chatHistory.appendChild(userMessageDiv);
        chatHistory.appendChild(aiMessageDiv);
        
        this.scrollToBottom();
    }

    async clearHistory() {
        if (!confirm('Are you sure you want to clear your chat history? This cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch('/chat/clear', {
                method: 'POST'
            });

            const data = await response.json();

            if (data.success) {
                document.getElementById('chatHistory').innerHTML = '';
                this.showSuccess('Chat history cleared successfully.');
            } else {
                this.showError('Failed to clear chat history.');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showError('Network error. Please try again.');
        }
    }

    async copyToClipboard(text, button) {
        try {
            await navigator.clipboard.writeText(text);
            
            // Visual feedback
            const originalIcon = button.innerHTML;
            button.innerHTML = '<i class="fas fa-check"></i>';
            button.classList.add('text-success');
            
            setTimeout(() => {
                button.innerHTML = originalIcon;
                button.classList.remove('text-success');
            }, 1500);
            
        } catch (error) {
            console.error('Copy failed:', error);
            
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            
            try {
                document.execCommand('copy');
                this.showSuccess('Copied to clipboard!');
            } catch (fallbackError) {
                this.showError('Copy failed. Please copy manually.');
            }
            
            document.body.removeChild(textArea);
        }
    }

    scrollToBottom() {
        const chatHistory = document.getElementById('chatHistory');
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    showError(message) {
        this.showAlert(message, 'danger');
    }

    showSuccess(message) {
        this.showAlert(message, 'success');
    }

    showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Insert at the top of the main container
        const container = document.querySelector('main.container');
        container.insertBefore(alertDiv, container.firstChild);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
}

// Initialize chat app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ChatApp();
});
