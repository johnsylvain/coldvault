// Metrics component using Alpine.js
import { getMetricsSummary, getMetricsHistory, getMetricsProjection } from '../api.js';
import { formatStorage, formatCost } from '../utils/formatters.js';
import { waitForChart } from '../utils/helpers.js';
import { setChart, setActiveMetricsTab } from '../state.js';
import { showError } from './notifications.js';

export function metricsComponent() {
    return {
        activeTab: 'overview',
        summary: null,
        loading: false,
        storageDays: 30,
        costDays: 30,
        historyDays: 30,
        
        async init() {
            // Load when metrics tab becomes active
        },
        
        switchTab(tab) {
            this.activeTab = tab;
            setActiveMetricsTab(tab);
            
            if (tab === 'overview') {
                this.loadSummary();
                this.loadCharts();
            } else if (tab === 'history') {
                this.loadHistoryChart();
            } else if (tab === 'projection') {
                this.loadProjections();
            }
        },
        
        async loadSummary() {
            try {
                this.loading = true;
                const summary = await getMetricsSummary(30);
                this.summary = summary;
                this.loading = false;
            } catch (error) {
                this.loading = false;
                showError(`Failed to load metrics summary: ${error.message}`);
            }
        },
        
        async loadCharts() {
            waitForChart(() => {
                this.createStorageChart();
                this.createCostChart();
            });
        },
        
        async createStorageChart() {
            try {
                const history = await getMetricsHistory(this.storageDays);
                const canvas = document.getElementById('storage-chart');
                if (!canvas || !history.records || history.records.length === 0) {
                    return;
                }
                
                const ctx = canvas.getContext('2d');
                const labels = history.records.map(r => new Date(r.date).toLocaleDateString());
                const storageData = history.records.map(r => r.total_size_gb);
                
                setChart('storage', new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Storage (GB)',
                            data: storageData,
                            borderColor: '#6366f1',
                            backgroundColor: 'rgba(99, 102, 241, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                labels: { color: '#cbd5e1' }
                            }
                        },
                        scales: {
                            x: {
                                ticks: { color: '#94a3b8' },
                                grid: { color: 'rgba(148, 163, 184, 0.1)' }
                            },
                            y: {
                                ticks: { color: '#94a3b8', callback: (v) => v.toFixed(1) + ' GB' },
                                grid: { color: 'rgba(148, 163, 184, 0.1)' }
                            }
                        }
                    }
                }));
            } catch (error) {
                console.error('Failed to load storage chart:', error);
            }
        },
        
        async createCostChart() {
            try {
                const history = await getMetricsHistory(this.costDays);
                const canvas = document.getElementById('cost-chart');
                if (!canvas || !history.records || history.records.length === 0) {
                    return;
                }
                
                const ctx = canvas.getContext('2d');
                const labels = history.records.map(r => new Date(r.date).toLocaleDateString());
                const costData = history.records.map(r => r.monthly_cost);
                
                setChart('cost', new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Monthly Cost ($)',
                            data: costData,
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                labels: { color: '#cbd5e1' }
                            }
                        },
                        scales: {
                            x: {
                                ticks: { color: '#94a3b8' },
                                grid: { color: 'rgba(148, 163, 184, 0.1)' }
                            },
                            y: {
                                ticks: { color: '#94a3b8', callback: (v) => '$' + v.toFixed(2) },
                                grid: { color: 'rgba(148, 163, 184, 0.1)' }
                            }
                        }
                    }
                }));
            } catch (error) {
                console.error('Failed to load cost chart:', error);
            }
        },
        
        async loadHistoryChart() {
            waitForChart(() => {
                this.createHistoryChart();
            });
        },
        
        async createHistoryChart() {
            try {
                const history = await getMetricsHistory(this.historyDays);
                const canvas = document.getElementById('history-chart');
                if (!canvas || !history.records || history.records.length === 0) {
                    return;
                }
                
                const latest = history.records[history.records.length - 1];
                const labels = Object.keys(latest.size_by_class);
                const data = Object.values(latest.size_by_class);
                const colors = ['#6366f1', '#8b5cf6', '#ec4899', '#10b981'];
                
                const ctx = canvas.getContext('2d');
                setChart('history', new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Storage (GB)',
                            data: data,
                            backgroundColor: colors,
                            borderColor: colors.map(c => c + 'dd'),
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            x: {
                                ticks: { color: '#94a3b8' },
                                grid: { color: 'rgba(148, 163, 184, 0.1)' }
                            },
                            y: {
                                ticks: { color: '#94a3b8', callback: (v) => v.toFixed(1) + ' GB' },
                                grid: { color: 'rgba(148, 163, 184, 0.1)' }
                            }
                        }
                    }
                }));
            } catch (error) {
                console.error('Failed to load history chart:', error);
            }
        },
        
        async loadProjections() {
            try {
                this.loading = true;
                const projection = await getMetricsProjection(30);
                this.projection = projection;
                this.loading = false;
            } catch (error) {
                this.loading = false;
                showError(`Failed to load projections: ${error.message}`);
            }
        },
        
        formatStorage,
        formatCost
    };
}

// Global functions for backward compatibility
export function switchMetricsTabGlobal(tab, event) {
    const event_custom = new CustomEvent('switch-metrics-tab', { detail: { tab } });
    document.dispatchEvent(event_custom);
}

export function loadMetricsChartsGlobal() {
    const event = new CustomEvent('load-metrics-charts');
    document.dispatchEvent(event);
}

export function loadHistoryChartGlobal() {
    const event = new CustomEvent('load-history-chart');
    document.dispatchEvent(event);
}
