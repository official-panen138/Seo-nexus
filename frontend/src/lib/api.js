import axios from 'axios';

const API_BASE = process.env.REACT_APP_BACKEND_URL + '/api';

// Create axios instance
const api = axios.create({
    baseURL: API_BASE,
    headers: {
        'Content-Type': 'application/json'
    }
});

// Add auth interceptor
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('seo_nexus_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Add response interceptor for auth errors
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('seo_nexus_token');
            localStorage.removeItem('seo_nexus_user');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

// Auth API
export const authAPI = {
    login: (email, password) => api.post('/auth/login', { email, password }),
    register: (data) => api.post('/auth/register', data),
    getMe: () => api.get('/auth/me')
};

// Users API
export const usersAPI = {
    getAll: () => api.get('/users'),
    update: (userId, role) => api.put(`/users/${userId}`, null, { params: { role } }),
    delete: (userId) => api.delete(`/users/${userId}`)
};

// Categories API
export const categoriesAPI = {
    getAll: () => api.get('/categories'),
    create: (data) => api.post('/categories', data),
    update: (categoryId, data) => api.put(`/categories/${categoryId}`, data),
    delete: (categoryId) => api.delete(`/categories/${categoryId}`)
};

// Brands API
export const brandsAPI = {
    getAll: () => api.get('/brands'),
    create: (data) => api.post('/brands', data),
    update: (brandId, data) => api.put(`/brands/${brandId}`, data),
    delete: (brandId) => api.delete(`/brands/${brandId}`)
};

// Domains API
export const domainsAPI = {
    getAll: (params) => api.get('/domains', { params }),
    getOne: (domainId) => api.get(`/domains/${domainId}`),
    create: (data) => api.post('/domains', data),
    update: (domainId, data) => api.put(`/domains/${domainId}`, data),
    delete: (domainId) => api.delete(`/domains/${domainId}`),
    checkNow: (domainId) => api.post(`/domains/${domainId}/check`),
    mute: (domainId, duration) => api.post(`/domains/${domainId}/mute`, null, { params: { duration } }),
    unmute: (domainId) => api.delete(`/domains/${domainId}/mute`)
};

// Groups API
export const groupsAPI = {
    getAll: () => api.get('/groups'),
    getOne: (groupId) => api.get(`/groups/${groupId}`),
    create: (data) => api.post('/groups', data),
    update: (groupId, data) => api.put(`/groups/${groupId}`, data),
    delete: (groupId) => api.delete(`/groups/${groupId}`)
};

// Monitoring API
export const monitoringAPI = {
    getStats: () => api.get('/monitoring/stats')
};

// Alerts API
export const alertsAPI = {
    getAll: (params) => api.get('/alerts', { params }),
    acknowledge: (alertId) => api.post(`/alerts/${alertId}/acknowledge`)
};

// SEO Conflicts API
export const conflictsAPI = {
    detect: () => api.get('/seo/conflicts')
};

// Reports API
export const reportsAPI = {
    getDashboardStats: () => api.get('/reports/dashboard-stats'),
    getTierDistribution: (brandId) => api.get('/reports/tier-distribution', { params: { brand_id: brandId } }),
    getIndexStatus: (brandId) => api.get('/reports/index-status', { params: { brand_id: brandId } }),
    getBrandHealth: () => api.get('/reports/brand-health'),
    getOrphanDomains: () => api.get('/reports/orphan-domains'),
    exportDomains: (format, brandId, groupId) => api.get('/reports/export', { 
        params: { format, brand_id: brandId, group_id: groupId } 
    })
};

// Settings API
export const settingsAPI = {
    getTelegram: () => api.get('/settings/telegram'),
    updateTelegram: (data) => api.put('/settings/telegram', data),
    testTelegram: () => api.post('/settings/telegram/test')
};

// Audit logs API
export const auditAPI = {
    getLogs: (limit, entityType) => api.get('/audit-logs', { params: { limit, entity_type: entityType } })
};

// Seed data API
export const seedAPI = {
    seedData: () => api.post('/seed-data')
};

export default api;
