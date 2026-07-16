// static/js/chat.js

document.addEventListener('DOMContentLoaded', () => {
    // Only initialize socket if we are in an active chat
    if (typeof window.CHAT_CONFIG === 'undefined') return;
    
    const socket = io();
    const chatMessages = document.getElementById('chatMessages');
    const chatForm = document.getElementById('chatForm');
    const messageInput = document.getElementById('messageInput');
    const typingIndicator = document.getElementById('typingIndicator');
    
    const config = window.CHAT_CONFIG;
    
    // Auto-scroll to bottom on load
    scrollToBottom();
    
    // Join the conversation room
    socket.on('connect', () => {
        socket.emit('join', { conversation_id: config.conversationId });
    });
    
    // Handle form submission
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const content = messageInput.value.trim();
        if (!content) return;
        
        socket.emit('send_message', {
            conversation_id: config.conversationId,
            content: content
        });
        
        // Clear input and typing status
        messageInput.value = '';
        socket.emit('typing', { conversation_id: config.conversationId, is_typing: false });
    });
    
    // Enter key to submit, Shift+Enter for newline
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });
    
    // Handle incoming messages
    socket.on('receive_message', (msg) => {
        // Create message element
        const isOut = msg.sender_id === config.currentUserId;
        const wrapperDiv = document.createElement('div');
        wrapperDiv.className = `message-wrapper ${isOut ? 'message-out' : 'message-in'}`;
        
        // Remove "empty state" message if it exists
        const emptyState = chatMessages.querySelector('.text-center.text-muted.my-4');
        if (emptyState) {
            emptyState.remove();
        }
        
        wrapperDiv.innerHTML = `
            <div class="message-bubble shadow-sm fade-in">
                <div class="message-content">${escapeHTML(msg.content)}</div>
                <div class="message-meta">${formatTime(msg.created_at)}</div>
            </div>
        `;
        
        chatMessages.appendChild(wrapperDiv);
        scrollToBottom();
        
        // Update sidebar preview if visible
        const activeItem = document.querySelector('.conversation-item.active .conv-preview');
        if (activeItem) {
            const previewText = msg.content.length > 30 ? msg.content.substring(0, 30) + '...' : msg.content;
            activeItem.textContent = previewText;
        }
    });
    
    // Handle Typing Indicator
    let typingTimer;
    const TYPING_TIMER_LENGTH = 1500;
    
    messageInput.addEventListener('input', () => {
        socket.emit('typing', { conversation_id: config.conversationId, is_typing: true });
        
        clearTimeout(typingTimer);
        typingTimer = setTimeout(() => {
            socket.emit('typing', { conversation_id: config.conversationId, is_typing: false });
        }, TYPING_TIMER_LENGTH);
    });
    
    socket.on('typing_status', (data) => {
        if (data.is_typing) {
            typingIndicator.classList.remove('d-none');
            scrollToBottom();
        } else {
            typingIndicator.classList.add('d-none');
        }
    });
    
    // Helpers
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    function escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
    
    function formatTime(dateStr) {
        // Simplistic format, assumes YYYY-MM-DD HH:MM:SS
        const date = new Date(dateStr + 'Z'); // parse as UTC
        if (isNaN(date)) return dateStr;
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }
});
