import { createContext, useContext, useState, useEffect } from 'react';

const BrandingContext = createContext(null);

const DEFAULT_BRANDING = {
    site_title: 'SEO//NOC',
    site_description: 'Domain Network Management System',
    logo_url: '',
    tagline: 'Domain Network Management System'
};

export function BrandingProvider({ children }) {
    const [branding, setBranding] = useState(DEFAULT_BRANDING);
    const [loading, setLoading] = useState(true);

    const loadBranding = async () => {
        try {
            const token = localStorage.getItem('seo_nexus_token');
            if (!token) {
                setLoading(false);
                return;
            }
            
            const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/settings/branding`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (response.ok) {
                const data = await response.json();
                setBranding({
                    site_title: data.site_title || DEFAULT_BRANDING.site_title,
                    site_description: data.site_description || DEFAULT_BRANDING.site_description,
                    logo_url: data.logo_url || DEFAULT_BRANDING.logo_url,
                    tagline: data.tagline || data.site_description || DEFAULT_BRANDING.tagline
                });
            }
        } catch (err) {
            console.log('Using default branding');
        } finally {
            setLoading(false);
        }
    };
            setBranding({
                site_title: data.site_title || DEFAULT_BRANDING.site_title,
                site_description: data.site_description || DEFAULT_BRANDING.site_description,
                logo_url: data.logo_url || DEFAULT_BRANDING.logo_url,
                tagline: data.tagline || data.site_description || DEFAULT_BRANDING.tagline
            });
        } catch (err) {
            console.log('Using default branding');
            setBranding(DEFAULT_BRANDING);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadBranding();
    }, []);

    // Apply branding to document when it changes
    useEffect(() => {
        if (!loading) {
            // Update document title
            document.title = `${branding.site_title} | ${branding.tagline}`;
            
            // Update meta description
            const metaDesc = document.querySelector('meta[name="description"]');
            if (metaDesc) {
                metaDesc.setAttribute('content', branding.site_description);
            }
        }
    }, [branding, loading]);

    const updateBranding = (newBranding) => {
        setBranding(prev => ({ ...prev, ...newBranding }));
    };

    const refreshBranding = () => {
        loadBranding();
    };

    return (
        <BrandingContext.Provider value={{ branding, loading, updateBranding, refreshBranding }}>
            {children}
        </BrandingContext.Provider>
    );
}

export function useBranding() {
    const context = useContext(BrandingContext);
    if (!context) {
        return { 
            branding: DEFAULT_BRANDING, 
            loading: false, 
            updateBranding: () => {}, 
            refreshBranding: () => {} 
        };
    }
    return context;
}
