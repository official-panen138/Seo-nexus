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

// ==================== V3 API ====================
// New architecture with separated concerns

const V3_BASE = process.env.REACT_APP_BACKEND_URL + '/api/v3';

const apiV3 = axios.create({
    baseURL: V3_BASE,
    headers: {
        'Content-Type': 'application/json'
    }
});

// Add auth interceptor for V3
apiV3.interceptors.request.use((config) => {
    const token = localStorage.getItem('seo_nexus_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

apiV3.interceptors.response.use(
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

// V3 Registrars API (Master Data)
export const registrarsAPI = {
    getAll: (params) => apiV3.get('/registrars', { params }),
    getOne: (registrarId) => apiV3.get(`/registrars/${registrarId}`),
    create: (data) => apiV3.post('/registrars', data),
    update: (registrarId, data) => apiV3.put(`/registrars/${registrarId}`, data),
    delete: (registrarId) => apiV3.delete(`/registrars/${registrarId}`)
};

// V3 Asset Domains API
export const assetDomainsAPI = {
    getAll: (params) => apiV3.get('/asset-domains', { params }),
    getOne: (assetId) => apiV3.get(`/asset-domains/${assetId}`),
    create: (data) => apiV3.post('/asset-domains', data),
    update: (assetId, data) => apiV3.put(`/asset-domains/${assetId}`, data),
    delete: (assetId) => apiV3.delete(`/asset-domains/${assetId}`)
};

// V3 SEO Networks API
export const networksAPI = {
    getAll: (params) => apiV3.get('/networks', { params }),
    getOne: (networkId) => apiV3.get(`/networks/${networkId}`),
    getTiers: (networkId) => apiV3.get(`/networks/${networkId}/tiers`),
    create: (data) => apiV3.post('/networks', data),
    update: (networkId, data) => apiV3.put(`/networks/${networkId}`, data),
    delete: (networkId) => apiV3.delete(`/networks/${networkId}`)
};

// V3 Structure Entries API
export const structureAPI = {
    getAll: (params) => apiV3.get('/structure', { params }),
    getOne: (entryId) => apiV3.get(`/structure/${entryId}`),
    create: (data) => apiV3.post('/structure', data),
    update: (entryId, data) => apiV3.put(`/structure/${entryId}`, data),
    delete: (entryId) => apiV3.delete(`/structure/${entryId}`)
};

// V3 Activity Logs API
export const activityLogsAPI = {
    getAll: (params) => apiV3.get('/activity-logs', { params }),
    getStats: () => apiV3.get('/activity-logs/stats')
};

// V3 Reports API
export const v3ReportsAPI = {
    getDashboard: () => apiV3.get('/reports/dashboard'),
    getConflicts: () => apiV3.get('/reports/conflicts')
};

export default api;
