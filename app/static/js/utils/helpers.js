/**
 * Wait for Chart.js to load
 */
export function waitForChart(callback, maxAttempts = 50) {
    if (typeof Chart !== 'undefined') {
        callback();
    } else if (maxAttempts > 0) {
        setTimeout(() => waitForChart(callback, maxAttempts - 1), 100);
    } else {
        console.error('Chart.js failed to load after 5 seconds');
    }
}

/**
 * Escape HTML to prevent XSS
 */
export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format date to relative time (e.g., "2 hours ago", "3 days ago")
 */
export function formatRelativeTime(dateString) {
    if (!dateString) return 'Unknown time';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);
    const diffWeeks = Math.floor(diffDays / 7);
    const diffMonths = Math.floor(diffDays / 30);
    const diffYears = Math.floor(diffDays / 365);
    
    if (diffSeconds < 60) {
        return diffSeconds <= 0 ? 'just now' : `${diffSeconds} second${diffSeconds !== 1 ? 's' : ''} ago`;
    } else if (diffMinutes < 60) {
        return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
    } else if (diffHours < 24) {
        return `about ${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    } else if (diffDays < 7) {
        return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    } else if (diffWeeks < 4) {
        return `${diffWeeks} week${diffWeeks !== 1 ? 's' : ''} ago`;
    } else if (diffMonths < 12) {
        return `${diffMonths} month${diffMonths !== 1 ? 's' : ''} ago`;
    } else {
        return `${diffYears} year${diffYears !== 1 ? 's' : ''} ago`;
    }
}

/**
 * Format date to absolute date string (e.g., "1/22/2026, 4:13:35 PM")
 */
export function formatAbsoluteDate(dateString) {
    if (!dateString) return 'Unknown time';
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        month: 'numeric',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
    });
}

/**
 * Format date to locale string (for backward compatibility)
 * Now defaults to relative time
 */
export function formatDate(dateString) {
    return formatRelativeTime(dateString);
}

/**
 * Create HTML for a clickable date that toggles between relative and absolute
 */
export function createClickableDate(dateString, options = {}) {
    if (!dateString) return options.fallback || 'Unknown time';
    
    const { 
        fallback = 'Unknown time',
        className = 'clickable-date'
    } = options;
    
    const relativeTime = formatRelativeTime(dateString);
    const absoluteDate = formatAbsoluteDate(dateString);
    
    // Return HTML with data attributes - will be initialized by initializeClickableDates()
    return `<span class="${className}" data-date-relative="${escapeHtml(relativeTime)}" data-date-absolute="${escapeHtml(absoluteDate)}" data-date-showing="relative" title="Click to show absolute date">${escapeHtml(relativeTime)}</span>`;
}

/**
 * Initialize click handlers for all clickable dates in the document or a specific container
 */
export function initializeClickableDates(container = document) {
    const clickableDates = container.querySelectorAll('.clickable-date');
    clickableDates.forEach(el => {
        // Remove existing listeners by cloning
        if (el.dataset.dateInitialized) return;
        el.dataset.dateInitialized = 'true';
        
        el.addEventListener('click', function() {
            const showing = this.dataset.dateShowing;
            if (showing === 'relative') {
                this.textContent = this.dataset.dateAbsolute;
                this.dataset.dateShowing = 'absolute';
                this.title = 'Click to show relative time';
            } else {
                this.textContent = this.dataset.dateRelative;
                this.dataset.dateShowing = 'relative';
                this.title = 'Click to show absolute date';
            }
        });
    });
}
