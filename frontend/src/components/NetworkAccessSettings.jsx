import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../lib/auth';
import { networksAPI } from '../lib/api';
import api from '../lib/api';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Badge } from './ui/badge';
import { Skeleton } from './ui/skeleton';
import { ScrollArea } from './ui/scroll-area';
import { toast } from 'sonner';
import { 
    Shield,
    Users,
    Globe,
    Lock,
    Loader2,
    X,
    UserPlus,
    AlertTriangle,
    CheckCircle,
    Info,
    Search,
    Plus,
    Clock,
    History
} from 'lucide-react';
import axios from 'axios';

// Create a v3 API instance for access control
const apiV3 = axios.create({
    baseURL: process.env.REACT_APP_BACKEND_URL + '/api/v3',
    headers: { 'Content-Type': 'application/json' }
});

// Add auth interceptor
apiV3.interceptors.request.use((config) => {
    const token = localStorage.getItem('seo_nexus_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

const VISIBILITY_OPTIONS = [
    {
        value: 'brand_based',
        label: 'Brand Based',
        description: 'All users with access to this brand can view',
        icon: Users,
        color: 'text-blue-400'
    },
    {
        value: 'restricted',
        label: 'Restricted',
        description: 'Only selected users can view',
        icon: Lock,
        color: 'text-amber-400'
    },
    {
        value: 'public',
        label: 'Public (Super Admin)',
        description: 'Visible to all platform users',
        icon: Globe,
        color: 'text-emerald-400',
        superAdminOnly: true
    }
];

const ROLE_COLORS = {
    super_admin: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    admin: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    viewer: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30'
};

export function NetworkAccessSettings({ networkId, brandId }) {
    const { user } = useAuth();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [selectedUserIds, setSelectedUserIds] = useState([]);
    const [selectedUsers, setSelectedUsers] = useState([]);
    const [visibilityMode, setVisibilityMode] = useState('brand_based');
    
    // Search state
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    const [showDropdown, setShowDropdown] = useState(false);
    const searchTimeoutRef = useRef(null);
    const dropdownRef = useRef(null);

    const isSuperAdmin = user?.role === 'super_admin';
    const isAdmin = user?.role === 'admin' || isSuperAdmin;

    // Load access control settings
    useEffect(() => {
        if (networkId) {
            loadAccessSettings();
        }
    }, [networkId]);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setShowDropdown(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const loadAccessSettings = async () => {
        setLoading(true);
        try {
            const res = await apiV3.get(`/networks/${networkId}/access-control`);
            setVisibilityMode(res.data.visibility_mode || 'brand_based');
            setSelectedUserIds(res.data.allowed_user_ids || []);
            setSelectedUsers(res.data.allowed_users || []);
        } catch (err) {
            console.error('Failed to load access settings:', err);
            toast.error('Failed to load access settings');
        } finally {
            setLoading(false);
        }
    };

    // Debounced user search
    const searchUsers = useCallback(async (query) => {
        if (query.length < 2) {
            setSearchResults([]);
            return;
        }

        setIsSearching(true);
        try {
            const res = await apiV3.get(`/users/search`, {
                params: { q: query, network_id: networkId }
            });
            // Filter out already selected users
            const filtered = (res.data.results || []).filter(
                u => !selectedUserIds.includes(u.id)
            );
            setSearchResults(filtered);
        } catch (err) {
            console.error('User search failed:', err);
            setSearchResults([]);
        } finally {
            setIsSearching(false);
        }
    }, [networkId, selectedUserIds]);

    // Handle search input change with debounce
    const handleSearchChange = (e) => {
        const value = e.target.value;
        setSearchQuery(value);
        setShowDropdown(true);

        // Clear previous timeout
        if (searchTimeoutRef.current) {
            clearTimeout(searchTimeoutRef.current);
        }

        // Debounce search (300ms)
        searchTimeoutRef.current = setTimeout(() => {
            searchUsers(value);
        }, 300);
    };

    const addUser = (user) => {
        if (!selectedUserIds.includes(user.id)) {
            setSelectedUserIds(prev => [...prev, user.id]);
            setSelectedUsers(prev => [...prev, user]);
        }
        setSearchQuery('');
        setSearchResults([]);
        setShowDropdown(false);
    };

    const removeUser = (userId) => {
        setSelectedUserIds(prev => prev.filter(id => id !== userId));
        setSelectedUsers(prev => prev.filter(u => u.id !== userId));
    };

    const handleSave = async () => {
        // Warn if restricted mode with no users
        if (visibilityMode === 'restricted' && selectedUserIds.length === 0) {
            const confirmed = window.confirm(
                'No users selected. Only Super Admins will be able to access this network.\n\nAre you sure you want to continue?'
            );
            if (!confirmed) return;
        }

        setSaving(true);
        try {
            await apiV3.put(`/networks/${networkId}/access-control`, {
                visibility_mode: visibilityMode,
                allowed_user_ids: visibilityMode === 'restricted' ? selectedUserIds : []
            });
            toast.success('Access settings updated');
            loadAccessSettings();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to update access settings');
        } finally {
            setSaving(false);
        }
    };

    if (!isAdmin) {
        return null;
    }

    if (loading) {
        return (
            <Card className="bg-card border-border">
                <CardHeader>
                    <Skeleton className="h-6 w-48" />
                    <Skeleton className="h-4 w-72 mt-2" />
                </CardHeader>
                <CardContent>
                    <Skeleton className="h-32 w-full" />
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="bg-card border-border" data-testid="network-access-settings">
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Shield className="h-5 w-5 text-emerald-500" />
                    Access Control
                </CardTitle>
                <CardDescription>
                    Control who can view and access this network
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                {/* Visibility Mode Selection */}
                <div>
                    <Label className="text-sm font-medium mb-3 block">Visibility Mode</Label>
                    <div className="grid gap-3">
                        {VISIBILITY_OPTIONS.map((option) => {
                            if (option.superAdminOnly && !isSuperAdmin) return null;
                            
                            const Icon = option.icon;
                            const isSelected = visibilityMode === option.value;
                            
                            return (
                                <div
                                    key={option.value}
                                    onClick={() => setVisibilityMode(option.value)}
                                    className={`p-4 rounded-lg border cursor-pointer transition-all ${
                                        isSelected 
                                            ? 'border-emerald-500/50 bg-emerald-950/20' 
                                            : 'border-border hover:border-zinc-600 bg-zinc-900/30'
                                    }`}
                                    data-testid={`visibility-${option.value}`}
                                >
                                    <div className="flex items-start gap-3">
                                        <div className={`p-2 rounded-lg ${isSelected ? 'bg-emerald-500/20' : 'bg-zinc-800'}`}>
                                            <Icon className={`h-5 w-5 ${isSelected ? 'text-emerald-400' : option.color}`} />
                                        </div>
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2">
                                                <span className="font-medium text-white">{option.label}</span>
                                                {isSelected && <CheckCircle className="h-4 w-4 text-emerald-400" />}
                                            </div>
                                            <p className="text-sm text-zinc-400 mt-1">{option.description}</p>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* User Selection (for Restricted mode) */}
                {visibilityMode === 'restricted' && (
                    <div className="border-t border-border pt-6">
                        <div className="flex items-center justify-between mb-4">
                            <Label className="text-sm font-medium flex items-center gap-2">
                                <UserPlus className="h-4 w-4 text-zinc-500" />
                                Allowed Users ({selectedUserIds.length})
                            </Label>
                        </div>

                        {/* Warning if no users selected */}
                        {selectedUserIds.length === 0 && (
                            <div className="mb-4 p-4 rounded-lg bg-amber-950/30 border border-amber-900/50 flex items-start gap-3">
                                <AlertTriangle className="h-5 w-5 text-amber-400 mt-0.5 flex-shrink-0" />
                                <div>
                                    <p className="text-sm text-amber-300 font-medium">No users selected</p>
                                    <p className="text-xs text-amber-300/70 mt-1">
                                        Only Super Admins will be able to access this network. Add users below to grant access.
                                    </p>
                                </div>
                            </div>
                        )}

                        {/* User Search Input */}
                        <div className="mb-4 relative" ref={dropdownRef}>
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                                <Input
                                    value={searchQuery}
                                    onChange={handleSearchChange}
                                    onFocus={() => setShowDropdown(true)}
                                    placeholder="Search users by name or email (min 2 chars)..."
                                    className="pl-10 bg-black border-border"
                                    data-testid="user-search-input"
                                />
                                {isSearching && (
                                    <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500 animate-spin" />
                                )}
                            </div>

                            {/* Search Results Dropdown */}
                            {showDropdown && searchQuery.length >= 2 && (
                                <div className="absolute z-50 mt-2 w-full border border-border rounded-lg bg-zinc-900 max-h-[250px] overflow-hidden shadow-lg">
                                    <ScrollArea className="h-full max-h-[250px]">
                                        {isSearching ? (
                                            <div className="p-4 text-center text-zinc-500 text-sm flex items-center justify-center gap-2">
                                                <Loader2 className="h-4 w-4 animate-spin" />
                                                Searching...
                                            </div>
                                        ) : searchResults.length > 0 ? (
                                            <div className="p-1">
                                                {searchResults.map(u => (
                                                    <div
                                                        key={u.id}
                                                        onClick={() => addUser(u)}
                                                        className="flex items-center justify-between p-3 rounded hover:bg-zinc-800 cursor-pointer"
                                                        data-testid={`search-result-${u.id}`}
                                                    >
                                                        <div className="flex items-center gap-3">
                                                            <div className={`h-8 w-8 rounded-full flex items-center justify-center text-white text-sm font-medium ${
                                                                u.role === 'super_admin' ? 'bg-amber-600' : 
                                                                u.role === 'admin' ? 'bg-blue-600' : 'bg-zinc-600'
                                                            }`}>
                                                                {u.name?.charAt(0)?.toUpperCase() || u.email?.charAt(0)?.toUpperCase()}
                                                            </div>
                                                            <div>
                                                                <p className="text-sm text-white font-medium">{u.name}</p>
                                                                <p className="text-xs text-zinc-500">{u.email}</p>
                                                            </div>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <Badge variant="outline" className={ROLE_COLORS[u.role] || ''}>
                                                                {u.role?.replace('_', ' ')}
                                                            </Badge>
                                                            <Plus className="h-4 w-4 text-emerald-400" />
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            <div className="p-4 text-center text-zinc-500 text-sm">
                                                No users found matching "{searchQuery}"
                                            </div>
                                        )}
                                    </ScrollArea>
                                </div>
                            )}

                            {/* Hint when query is too short */}
                            {showDropdown && searchQuery.length > 0 && searchQuery.length < 2 && (
                                <div className="absolute z-50 mt-2 w-full border border-border rounded-lg bg-zinc-900 p-3 shadow-lg">
                                    <p className="text-sm text-zinc-500 text-center">Type at least 2 characters to search</p>
                                </div>
                            )}
                        </div>

                        {/* Selected Users List */}
                        {selectedUsers.length > 0 && (
                            <div className="space-y-2">
                                <Label className="text-xs text-zinc-500 uppercase">Assigned Users</Label>
                                <div className="space-y-2 max-h-[250px] overflow-y-auto pr-2">
                                    {selectedUsers.map(u => (
                                        <div
                                            key={u.id}
                                            className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/50 border border-border"
                                            data-testid={`selected-user-${u.id}`}
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className={`h-10 w-10 rounded-full flex items-center justify-center text-white font-medium ${
                                                    u.role === 'super_admin' ? 'bg-amber-600' : 
                                                    u.role === 'admin' ? 'bg-blue-600' : 'bg-zinc-600'
                                                }`}>
                                                    {u.name?.charAt(0)?.toUpperCase() || u.email?.charAt(0)?.toUpperCase()}
                                                </div>
                                                <div>
                                                    <p className="text-white font-medium">{u.name || u.email?.split('@')[0]}</p>
                                                    <p className="text-xs text-zinc-500">{u.email}</p>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                <Badge variant="outline" className={ROLE_COLORS[u.role] || ''}>
                                                    {u.role?.replace('_', ' ')}
                                                </Badge>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => removeUser(u.id)}
                                                    className="h-8 w-8 hover:bg-red-500/10 hover:text-red-400"
                                                    data-testid={`remove-user-${u.id}`}
                                                >
                                                    <X className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* Info Box */}
                <div className="p-4 rounded-lg bg-blue-950/20 border border-blue-900/30 flex items-start gap-3">
                    <Info className="h-5 w-5 text-blue-400 mt-0.5 flex-shrink-0" />
                    <div className="text-sm text-blue-300/80">
                        <p className="font-medium text-blue-300 mb-1">About Access Control</p>
                        <ul className="list-disc list-inside space-y-1">
                            <li><strong>Brand Based:</strong> Default mode. Users with brand access can view.</li>
                            <li><strong>Restricted:</strong> Only selected users can view this network.</li>
                            {isSuperAdmin && <li><strong>Public:</strong> All platform users can view.</li>}
                        </ul>
                    </div>
                </div>

                {/* Save Button */}
                <div className="flex justify-end pt-4 border-t border-border">
                    <Button 
                        onClick={handleSave} 
                        disabled={saving}
                        className="gap-2"
                        data-testid="save-access-btn"
                    >
                        {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                        <Shield className="h-4 w-4" />
                        Save Access Settings
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
