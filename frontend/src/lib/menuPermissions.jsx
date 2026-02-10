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

    const loadPermissions = useCallback(async () => {
        if (!isAuthenticated || !user) {
            setPermissions(prev => ({ ...prev, loading: false }));
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
            setPermissions(prev => ({
                ...prev,
                loading: false,
                error: 'Failed to load permissions'
            }));
        }
    }, [isAuthenticated, user]);

    useEffect(() => {
        loadPermissions();
    }, [loadPermissions]);

    // Check if a menu key is accessible
    const canAccessMenu = useCallback((menuKey) => {
        if (permissions.isSuperAdmin) return true;
        return permissions.enabledMenus.includes(menuKey);
    }, [permissions]);

    // Check if a path is accessible
    const canAccessPath = useCallback((path) => {
        if (permissions.isSuperAdmin) return true;
        
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
    }, [permissions]);

    // Refresh permissions (call after role change or permission update)
    const refreshPermissions = useCallback(() => {
        loadPermissions();
    }, [loadPermissions]);

    return (
        <MenuPermissionsContext.Provider value={{
            ...permissions,
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
