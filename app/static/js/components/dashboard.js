// Dashboard component using Alpine.js
import { getDashboardOverview } from '../api.js';
import { formatStorage, formatCost } from '../utils/formatters.js';
import { updateDashboard } from '../state.js';
import { showError } from './notifications.js';

export function dashboardComponent() {
    return {
        stats: {
            jobs: { total: 0 },
            backups: { successful: 0, failed: 0 },
            storage: { total_bytes: 0 },
            costs: { monthly_estimate: 0 }
        },
        loading: true,
        
        async init() {
            await this.load();
            // Auto-refresh every 10 seconds
            setInterval(() => this.load(), 10000);
        },
        
        async load() {
            try {
                this.loading = true;
                const overview = await getDashboardOverview();
                this.stats = overview;
                updateDashboard(overview);
                this.loading = false;
            } catch (error) {
                this.loading = false;
                showError(`Failed to load dashboard: ${error.message}`);
            }
        },
        
        formatStorage,
        formatCost
    };
}
