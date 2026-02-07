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

// Role display helpers
export const ROLE_LABELS = {
    'super_admin': 'Super Admin',
    'admin': 'Admin',
    'viewer': 'Viewer'
};

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
