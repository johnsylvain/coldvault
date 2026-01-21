/**
 * Format bytes to human-readable storage size
 */
export function formatStorage(bytes) {
    if (bytes === 0) return '0 B';
    const kb = bytes / 1024;
    const mb = kb / 1024;
    const gb = mb / 1024;
    const tb = gb / 1024;
    
    if (tb >= 1) {
        return `${tb.toFixed(2)} TB`;
    } else if (gb >= 1) {
        return `${gb.toFixed(2)} GB`;
    } else if (mb >= 1) {
        return `${mb.toFixed(2)} MB`;
    } else if (kb >= 1) {
        return `${kb.toFixed(2)} KB`;
    } else {
        return `${bytes} B`;
    }
}

/**
 * Format cost to currency string
 */
export function formatCost(cost) {
    if (cost === 0) return '$0.00';
    if (cost < 0.01) {
        return `$${cost.toFixed(4)}`;
    } else if (cost < 1) {
        return `$${cost.toFixed(2)}`;
    } else {
        return `$${cost.toFixed(2)}`;
    }
}
