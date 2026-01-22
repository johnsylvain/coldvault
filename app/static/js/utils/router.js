// Simple hash-based client-side router
class Router {
    constructor() {
        this.routes = new Map();
        this.currentRoute = null;
    }

    init() {
        // Listen for hashchange (back/forward buttons and direct hash changes)
        window.addEventListener('hashchange', (e) => {
            this.handleRoute(this.getHash());
        });

        // Handle initial route
        const initialHash = this.getHash();
        if (!initialHash || initialHash === '/') {
            this.navigate('/dashboard', true);
        } else {
            this.handleRoute(initialHash);
        }
    }

    getHash() {
        // Get hash without the #, or return '/dashboard' as default
        const hash = window.location.hash.slice(1);
        return hash || '/dashboard';
    }

    register(path, handler) {
        this.routes.set(path, handler);
    }

    navigate(path, replace = false) {
        // Ensure path starts with /
        if (!path.startsWith('/')) {
            path = '/' + path;
        }

        // Update hash
        window.location.hash = path;
        
        // Handle route immediately (hashchange event may not fire for programmatic changes)
        this.handleRoute(path);
    }

    handleRoute(path) {
        // Normalize path
        if (path === '/' || path === '' || !path) {
            path = '/dashboard';
        }

        // Close mobile menu on navigation
        if (typeof window.closeMobileMenu === 'function' && window.innerWidth <= 768) {
            window.closeMobileMenu();
        }

        // Try exact match first
        if (this.routes.has(path)) {
            const handler = this.routes.get(path);
            handler();
            this.currentRoute = path;
            return;
        }

        // Try pattern matching for nested routes (e.g., /metrics/overview)
        for (const [route, handler] of this.routes.entries()) {
            if (route.includes('*')) {
                const pattern = route.replace('*', '.*');
                const regex = new RegExp(`^${pattern}$`);
                if (regex.test(path)) {
                    handler(path);
                    this.currentRoute = path;
                    return;
                }
            }
        }

        // Default to dashboard if no match
        if (path !== '/dashboard') {
            this.navigate('/dashboard', true);
        }
    }

    getCurrentRoute() {
        return this.currentRoute || this.getHash();
    }
}

// Export singleton instance
export const router = new Router();
