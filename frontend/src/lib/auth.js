import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authAPI } from './api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const loadUser = useCallback(async () => {
        const token = localStorage.getItem('seo_nexus_token');
        const savedUser = localStorage.getItem('seo_nexus_user');
        
        if (token && savedUser) {
            try {
                setUser(JSON.parse(savedUser));
                // Verify token is still valid
                const response = await authAPI.getMe();
                setUser(response.data);
                localStorage.setItem('seo_nexus_user', JSON.stringify(response.data));
            } catch (err) {
                console.error('Token validation failed:', err);
                localStorage.removeItem('seo_nexus_token');
                localStorage.removeItem('seo_nexus_user');
                setUser(null);
            }
        }
        setLoading(false);
    }, []);

    useEffect(() => {
        loadUser();
    }, [loadUser]);

    const login = async (email, password) => {
        setError(null);
        try {
            const response = await authAPI.login(email, password);
            const { access_token, user: userData } = response.data;
            localStorage.setItem('seo_nexus_token', access_token);
            localStorage.setItem('seo_nexus_user', JSON.stringify(userData));
            setUser(userData);
            return userData;
        } catch (err) {
            const message = err.response?.data?.detail || 'Login failed';
            setError(message);
            throw new Error(message);
        }
    };

    const register = async (data) => {
        setError(null);
        try {
            const response = await authAPI.register(data);
            // Check if registration returned pending status (no token)
            if (response.data.status === 'pending') {
                return { pending: true, message: response.data.message };
            }
            // Normal flow - user is activated immediately (first user)
            const { access_token, user: userData } = response.data;
            localStorage.setItem('seo_nexus_token', access_token);
            localStorage.setItem('seo_nexus_user', JSON.stringify(userData));
            setUser(userData);
            return userData;
        } catch (err) {
            const message = err.response?.data?.detail || 'Registration failed';
            setError(message);
            throw new Error(message);
        }
    };

    const logout = () => {
        localStorage.removeItem('seo_nexus_token');
        localStorage.removeItem('seo_nexus_user');
        setUser(null);
    };

    const hasRole = (roles) => {
        if (!user) return false;
        if (typeof roles === 'string') return user.role === roles;
        return roles.includes(user.role);
    };

    const isSuperAdmin = () => hasRole('super_admin');
    const isAdmin = () => hasRole(['super_admin', 'admin']);
    const canEdit = () => hasRole(['super_admin', 'admin']);

    return (
        <AuthContext.Provider value={{
            user,
            loading,
            error,
            login,
            register,
            logout,
            hasRole,
            isSuperAdmin,
            isAdmin,
            canEdit,
            isAuthenticated: !!user
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

export default AuthContext;
