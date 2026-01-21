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
 * Format date to locale string
 */
export function formatDate(dateString) {
    return new Date(dateString).toLocaleString();
}
