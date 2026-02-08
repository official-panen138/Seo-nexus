import { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from './AuthContext';

const BrandContext = createContext(null);

const BRAND_STORAGE_KEY = 'seo_nexus_selected_brand';

export function BrandProvider({ children }) {
    const { user } = useAuth();
    const [selectedBrandId, setSelectedBrandId] = useState(null);
    const [brands, setBrands] = useState([]);
    const [loading, setLoading] = useState(true);

    // Load brands on mount
    useEffect(() => {
        loadBrands();
    }, [user]);

    // Load selected brand from localStorage (Super Admin only)
    useEffect(() => {
        if (user?.role === 'super_admin') {
            const stored = localStorage.getItem(BRAND_STORAGE_KEY);
            if (stored && stored !== 'all') {
                setSelectedBrandId(stored);
            } else {
                setSelectedBrandId(null); // "All Brands" for Super Admin
            }
        } else if (user?.brand_scope_ids?.length > 0) {
            // Non-super admin: default to first brand in scope
            setSelectedBrandId(user.brand_scope_ids[0]);
        }
    }, [user]);

    const loadBrands = async () => {
        try {
            const token = localStorage.getItem('seo_nexus_token');
            if (!token) return;

            const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/brands`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (response.ok) {
                const data = await response.json();
                setBrands(data);
            }
        } catch (error) {
            console.error('Failed to load brands:', error);
        } finally {
            setLoading(false);
        }
    };

    const selectBrand = (brandId) => {
        if (user?.role === 'super_admin') {
            // Super Admin can select any brand or "all"
            if (brandId === 'all' || brandId === null) {
                localStorage.setItem(BRAND_STORAGE_KEY, 'all');
                setSelectedBrandId(null);
            } else {
                localStorage.setItem(BRAND_STORAGE_KEY, brandId);
                setSelectedBrandId(brandId);
            }
        } else {
            // Non-super admin can only select from their scope
            if (user?.brand_scope_ids?.includes(brandId)) {
                setSelectedBrandId(brandId);
            }
        }
    };

    // Get brands available to the current user
    const availableBrands = user?.role === 'super_admin' 
        ? brands 
        : brands.filter(b => user?.brand_scope_ids?.includes(b.id));

    // Check if user has access to a specific brand
    const hasAccessToBrand = (brandId) => {
        if (user?.role === 'super_admin') return true;
        return user?.brand_scope_ids?.includes(brandId) || false;
    };

    // Get current brand filter for API calls
    const getBrandFilter = () => {
        if (user?.role === 'super_admin' && selectedBrandId === null) {
            return null; // No filter - all brands
        }
        return selectedBrandId;
    };

    const value = {
        selectedBrandId,
        selectBrand,
        brands,
        availableBrands,
        hasAccessToBrand,
        getBrandFilter,
        loading,
        isSuperAdmin: user?.role === 'super_admin',
        canSelectAllBrands: user?.role === 'super_admin'
    };

    return (
        <BrandContext.Provider value={value}>
            {children}
        </BrandContext.Provider>
    );
}

export function useBrand() {
    const context = useContext(BrandContext);
    if (!context) {
        throw new Error('useBrand must be used within a BrandProvider');
    }
    return context;
}

export default BrandContext;
