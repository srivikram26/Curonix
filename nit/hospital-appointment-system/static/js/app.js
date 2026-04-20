/**
 * ============================================================
 * AI Hospital Appointment Scheduler - Core JavaScript
 * Shared utility functions for all panels
 * ============================================================
 */

// ============================================================
// API Helper - Centralized fetch wrapper
// ============================================================
const API = {
    /**
     * Make an API request with JSON body
     * @param {string} url - API endpoint
     * @param {string} method - HTTP method
     * @param {object} data - Request body (optional)
     * @returns {Promise<object>} Response data
     */
    async request(url, method = 'GET', data = null) {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin'
        };
        
        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }
        
        try {
            const response = await fetch(url, options);
            const result = await response.json();
            
            if (!response.ok && !result.success) {
                const error = new Error(result.error || 'HTTP ' + response.status);
                // Attach additional properties from result for role mismatch handling
                if (result.correct_role) {
                    error.correct_role = result.correct_role;
                }
                throw error;
            }
            
            return result;
        } catch (error) {
            console.error('API Error [' + method + ' ' + url + ']:', error);
            throw error;
        }
    },
    
    get(url) { return this.request(url, 'GET'); },
    post(url, data) { return this.request(url, 'POST', data); },
    put(url, data) { return this.request(url, 'PUT', data); },
    delete(url) { return this.request(url, 'DELETE'); }
};


// ============================================================
// Toast Notification System
// ============================================================
const Toast = {
    container: null,
    
    init() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }
    },
    
    /**
     * Show a toast notification
     * @param {string} message - Message to display
     * @param {string} type - 'success', 'error', or 'info'
     * @param {number} duration - Auto-dismiss time in ms
     */
    show(message, type = 'info', duration = 4000) {
        this.init();
        
        const icons = {
            success: '✓',
            error: '✕',
            info: 'ℹ'
        };
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span style="font-size:1.1rem;font-weight:bold;">${icons[type] || 'ℹ'}</span>
            <span>${message}</span>
        `;
        
        this.container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },
    
    success(msg) { this.show(msg, 'success'); },
    error(msg) { this.show(msg, 'error'); },
    info(msg) { this.show(msg, 'info'); },
    action(message, actionLabel, action, type = 'info', duration = 5000) {
        this.init();
        const toast = document.createElement('div');
        toast.className = `toast ${type} toast-action`;
        toast.innerHTML = `
            <span>${message}</span>
        `;
        const button = document.createElement('button');
        button.className = 'toast-action-btn';
        button.textContent = actionLabel;
        button.addEventListener('click', async () => {
            button.disabled = true;
            try {
                await action();
            } catch (err) {
                console.error(err);
            }
            toast.remove();
        });
        toast.appendChild(button);
        this.container.appendChild(toast);
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
};


// ============================================================
// Modal Manager
// ============================================================
const Modal = {
    normalize(selector) {
        if (!selector) return null;
        const trimmed = selector.trim();
        return trimmed.startsWith('#') || trimmed.startsWith('.') ? trimmed : `#${trimmed}`;
    },

    /**
     * Show a modal by selector
     */
    show(selector) {
        const modal = document.querySelector(this.normalize(selector));
        if (modal) modal.classList.add('active');
    },
    
    /**
     * Hide a modal by selector
     */
    hide(selector) {
        const modal = document.querySelector(this.normalize(selector));
        if (modal) modal.classList.remove('active');
    },

    open(selector) {
        this.show(selector);
    },
    
    close(selector) {
        this.hide(selector);
    },
    
    /**
     * Initialize close buttons for all modals
     */
    initCloseButtons() {
        document.querySelectorAll('.modal-close, [data-close-modal]').forEach(btn => {
            btn.addEventListener('click', () => {
                const overlay = btn.closest('.modal-overlay');
                if (overlay) overlay.classList.remove('active');
            });
        });
        
        // Close on overlay click
        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) overlay.classList.remove('active');
            });
        });
    }
};


// ============================================================
// Utility Functions
// ============================================================
const Utils = {
    /**
     * Format a date string to readable format
     * @param {string} dateStr - ISO date string
     * @returns {string} Formatted date
     */
    formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        const options = { year: 'numeric', month: 'long', day: 'numeric' };
        return new Date(dateStr).toLocaleDateString('en-US', options);
    },
    
    /**
     * Format time string (HH:MM) to 12-hour format
     * @param {string} timeStr - Time in HH:MM format
     * @returns {string} Formatted time (e.g., "2:30 PM")
     */
    formatTime(timeStr) {
        if (!timeStr) return 'N/A';
        const [hours, minutes] = timeStr.split(':');
        const h = parseInt(hours);
        const ampm = h >= 12 ? 'PM' : 'AM';
        const hour12 = h % 12 || 12;
        return `${hour12}:${minutes} ${ampm}`;
    },
    
    /**
     * Get appropriate CSS class for appointment status badge
     * @param {string} status - Appointment status
     * @returns {string} Badge CSS class
     */
    statusBadge(status) {
        return `badge badge-${status}`;
    },
    
    /**
     * Get appropriate CSS class for priority badge
     * @param {string} priority - Priority level
     * @returns {string} Badge CSS class
     */
    priorityBadge(priority) {
        return `badge badge-${priority}`;
    },
    
    /**
     * Show/hide loading spinner inside a container
     * @param {string} selector - Container CSS selector
     * @param {boolean} show - Show or hide
     */
    setLoading(selector, show = true) {
        const container = document.querySelector(selector);
        if (!container) return;
        
        if (show) {
            container.innerHTML = `
                <div class="loading-overlay">
                    <div class="spinner"></div>
                    <span>Loading...</span>
                </div>
            `;
        }
    },
    
    /**
     * Create an HTML element from a template string
     * @param {string} html - HTML string
     * @returns {HTMLElement}
     */
    createElement(html) {
        const template = document.createElement('template');
        template.innerHTML = html.trim();
        return template.content.firstChild;
    },
    
    /**
     * Debounce function
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    },
    
    /**
     * Get today's date in YYYY-MM-DD format
     */
    today() {
        return new Date().toISOString().split('T')[0];
    },
    
    /**
     * Format a number with commas
     */
    formatNumber(num) {
        return num ? num.toLocaleString() : '0';
    }
};


// ============================================================
// Logout Handler
// ============================================================
async function handleLogout() {
    try {
        const result = await API.post('/auth/api/logout');
        window.location.href = result.redirect || '/auth/select-role';
    } catch (error) {
        // Force redirect even if API fails
        window.location.href = '/auth/select-role';
    }
}


// ============================================================
// Initialize common components on DOM load
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    Modal.initCloseButtons();
    
    // Set minimum/maximum constraints based on data attributes
    document.querySelectorAll('input[type="date"][data-min-today]').forEach(input => {
        input.min = Utils.today();
    });
    document.querySelectorAll('input[type="date"][data-max-today]').forEach(input => {
        input.max = Utils.today();
    });
});

/**
 * Toggle password visibility when a button with `data-toggle-password` is clicked.
 * Keeps the same button markup working across all forms without inline JS.
 */
document.addEventListener('click', (event) => {
    const toggle = event.target.closest('[data-toggle-password]');
    if (!toggle) return;
    const targetId = toggle.dataset.target;
    if (!targetId) return;
    const input = document.getElementById(targetId);
    if (!input) return;
    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    toggle.textContent = isPassword ? '🙈' : '👁️';
});
