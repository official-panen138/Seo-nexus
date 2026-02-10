import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { menuPermissionsAPI } from './api';
import { useAuth } from './auth';

const MenuPermissionsContext = createContext(null);

export const MenuPermissionsProvider = ({ children }) => {
    const { user, isAuthenticated } = useAuth();
    const [permissions, setPermissions] = useState({
        enabledMenus: [],
        isSuperAdmin: false,
        loading: true,
        error: null
    });

    // Check if user is super admin from auth context
    const userIsSuperAdmin = user?.role === 'super_admin';

    const loadPermissions = useCallback(async () => {
        if (!isAuthenticated || !user) {
            setPermissions(prev => ({ ...prev, loading: false }));
            return;
        }

        // If user is super_admin, grant all access immediately without API call
        if (user.role === 'super_admin') {
            setPermissions({
                enabledMenus: [], // Not needed for super admin
                isSuperAdmin: true,
                loading: false,
                error: null
            });
            return;
        }

        try {
            const response = await menuPermissionsAPI.getMyPermissions();
            setPermissions({
                enabledMenus: response.data.enabled_menus || [],
                isSuperAdmin: response.data.is_super_admin || false,
                loading: false,
                error: null
            });
        } catch (error) {
            console.error('Failed to load menu permissions:', error);
            // On error, use defaults based on role
            const defaultMenus = user.role === 'admin' 
                ? ['dashboard', 'asset_domains', 'seo_networks', 'alert_center', 'reports', 'team_evaluation', 'brands', 'categories', 'registrars', 'users', 'audit_logs', 'metrics', 'v3_activity', 'monitoring', 'activity_types', 'scheduler', 'settings']
                : [];
            setPermissions({
                enabledMenus: defaultMenus,
                isSuperAdmin: false,
                loading: false,
                error: 'Failed to load permissions'
            });
        }
    }, [isAuthenticated, user]);

    useEffect(() => {
        loadPermissions();
    }, [loadPermissions]);

    // Check if a menu key is accessible
    const canAccessMenu = useCallback((menuKey) => {
        // Super admin check from both sources
        if (permissions.isSuperAdmin || userIsSuperAdmin) return true;
        return permissions.enabledMenus.includes(menuKey);
    }, [permissions, userIsSuperAdmin]);

    // Check if a path is accessible
    const canAccessPath = useCallback((path) => {
        if (permissions.isSuperAdmin || userIsSuperAdmin) return true;
        
        // Map paths to menu keys
        const pathToKeyMap = {
            '/dashboard': 'dashboard',
            '/domains': 'asset_domains',
            '/groups': 'seo_networks',
            '/alerts': 'alert_center',
            '/reports': 'reports',
            '/reports/team-evaluation': 'team_evaluation',
            '/brands': 'brands',
            '/categories': 'categories',
            '/registrars': 'registrars',
            '/users': 'users',
            '/audit-logs': 'audit_logs',
            '/metrics': 'metrics',
            '/activity-logs': 'v3_activity',
            '/settings/activity-types': 'activity_types',
            '/settings/scheduler': 'scheduler',
            '/settings/monitoring': 'monitoring',
            '/settings': 'settings'
        };

        const menuKey = pathToKeyMap[path];
        if (!menuKey) return true; // Unknown paths are allowed by default
        
        return permissions.enabledMenus.includes(menuKey);
    }, [permissions, userIsSuperAdmin]);

    // Refresh permissions (call after role change or permission update)
    const refreshPermissions = useCallback(() => {
        loadPermissions();
    }, [loadPermissions]);

    return (
        <MenuPermissionsContext.Provider value={{
            ...permissions,
            isSuperAdmin: permissions.isSuperAdmin || userIsSuperAdmin,
            canAccessMenu,
            canAccessPath,
            refreshPermissions
        }}>
            {children}
        </MenuPermissionsContext.Provider>
    );
};

export const useMenuPermissions = () => {
    const context = useContext(MenuPermissionsContext);
    if (!context) {
        throw new Error('useMenuPermissions must be used within MenuPermissionsProvider');
    }
    return context;
};
