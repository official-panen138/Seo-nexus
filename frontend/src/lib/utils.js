import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
    return twMerge(clsx(inputs));
}

// Tier display helpers
export const TIER_LABELS = {
    'tier_5': 'Tier 5',
    'tier_4': 'Tier 4',
    'tier_3': 'Tier 3',
    'tier_2': 'Tier 2',
    'tier_1': 'Tier 1',
    'lp_money_site': 'LP / Money Site'
};

export const TIER_ORDER = ['lp_money_site', 'tier_1', 'tier_2', 'tier_3', 'tier_4', 'tier_5'];

export const TIER_COLORS = {
    'tier_5': '#A855F7',
    'tier_4': '#818CF8',
    'tier_3': '#3B82F6',
    'tier_2': '#14B8A6',
    'tier_1': '#22C55E',
    'lp_money_site': '#F59E0B'
};

export const getTierBadgeClass = (tier) => {
    const classes = {
        'tier_5': 'badge-tier-5',
        'tier_4': 'badge-tier-4',
        'tier_3': 'badge-tier-3',
        'tier_2': 'badge-tier-2',
        'tier_1': 'badge-tier-1',
        'lp_money_site': 'badge-tier-lp'
    };
    return classes[tier] || 'badge-tier-5';
};

// Status display helpers
export const STATUS_LABELS = {
    'canonical': 'Canonical',
    '301_redirect': '301 Redirect',
    '302_redirect': '302 Redirect',
    'restore': 'Restore'
};

export const INDEX_STATUS_LABELS = {
    'index': 'Index',
    'noindex': 'Noindex'
};

// Monitoring interval labels
export const MONITORING_INTERVAL_LABELS = {
    '5min': '5 Minutes',
    '15min': '15 Minutes',
    '1hour': '1 Hour',
    'daily': 'Daily'
};

// Ping status labels
export const PING_STATUS_LABELS = {
    'up': 'Up',
    'down': 'Down',
    'unknown': 'Unknown'
};

// HTTP status labels
export const HTTP_STATUS_LABELS = {
    '200': '200 OK',
    '3xx': '3xx Redirect',
    '4xx': '4xx Client Error',
    '5xx': '5xx Server Error',
    'timeout': 'Timeout',
    'error': 'Error'
};

// Alert severity labels and colors
export const SEVERITY_LABELS = {
    'critical': 'Critical',
    'high': 'High',
    'medium': 'Medium',
    'low': 'Low'
};

export const SEVERITY_COLORS = {
    'critical': '#EF4444',
    'high': '#F59E0B',
    'medium': '#3B82F6',
    'low': '#6B7280'
};

export const getSeverityBadgeClass = (severity) => {
    const classes = {
        'critical': 'bg-red-500/20 text-red-400 border-red-500/30',
        'high': 'bg-amber-500/20 text-amber-400 border-amber-500/30',
        'medium': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        'low': 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30'
    };
    return classes[severity] || classes.low;
};

// Alert type labels
export const ALERT_TYPE_LABELS = {
    'monitoring': 'Monitoring',
    'expiration': 'Expiration',
    'seo_conflict': 'SEO Conflict'
};

// Role display helpers
export const ROLE_LABELS = {
    'super_admin': 'Super Admin',
    'admin': 'Admin',
    'viewer': 'Viewer'
};

// Common registrars
export const REGISTRARS = [
    'Namecheap',
    'GoDaddy',
    'Dynadot',
    'Cloudflare',
    'Google Domains',
    'Name.com',
    'Porkbun',
    'Hover',
    'Gandi',
    'Other'
];

// Format date
export const formatDate = (dateString) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
};

export const formatDateTime = (dateString) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
};

// Calculate days until expiration
export const getDaysUntilExpiration = (expirationDate) => {
    if (!expirationDate) return null;
    const expDate = new Date(expirationDate);
    const now = new Date();
    const diffTime = expDate - now;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
};

export const getExpirationBadgeClass = (days) => {
    if (days === null) return '';
    if (days <= 0) return 'bg-red-500/20 text-red-400 border-red-500/30';
    if (days <= 7) return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    if (days <= 30) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
};

// Download helper
export const downloadFile = (content, filename, type = 'text/plain') => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
};

// Debounce helper
export const debounce = (func, wait) => {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
};
