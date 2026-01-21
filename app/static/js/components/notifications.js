// Notification component using Alpine.js
export function notificationsComponent() {
    return {
        message: '',
        type: 'info',
        show: false,
        
        showNotification(message, type = 'info') {
            this.message = message;
            this.type = type;
            this.show = true;
            
            setTimeout(() => {
                this.show = false;
            }, 4000);
        },
        
        showError(message) {
            this.showNotification(message, 'error');
        },
        
        showSuccess(message) {
            this.showNotification(message, 'info');
        }
    };
}

// Global notification helper (for use outside Alpine components)
let globalNotificationComponent = null;

export function setGlobalNotificationComponent(component) {
    globalNotificationComponent = component;
}

export function showNotification(message, type = 'info') {
    if (globalNotificationComponent) {
        globalNotificationComponent.showNotification(message, type);
    } else {
        // Fallback to direct DOM manipulation
        const notification = document.getElementById('notification');
        if (notification) {
            notification.textContent = message;
            notification.className = `notification ${type} show`;
            setTimeout(() => {
                notification.classList.remove('show');
            }, 4000);
        } else {
            console.warn('Notification element not found');
        }
    }
}

export function showError(message) {
    showNotification(message, 'error');
}

export function showSuccess(message) {
    showNotification(message, 'info');
}
