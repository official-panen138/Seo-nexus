import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../lib/auth';
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
    Trash2
} from 'lucide-react';

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
    const [accessControl, setAccessControl] = useState(null);
    const [allUsers, setAllUsers] = useState([]);
    const [selectedUserIds, setSelectedUserIds] = useState([]);
    const [visibilityMode, setVisibilityMode] = useState('brand_based');
    const [searchQuery, setSearchQuery] = useState('');
    const [showUserSelector, setShowUserSelector] = useState(false);

    const isSuperAdmin = user?.role === 'super_admin';
    const isAdmin = user?.role === 'admin' || isSuperAdmin;

    useEffect(() => {
        if (networkId) {
            loadData();
        }
    }, [networkId, brandId]);

    const loadData = async () => {
        setLoading(true);
        try {
            // Load access control settings
            const accessRes = await api.get(`/api/v3/networks/${networkId}/access-control`);
            setAccessControl(accessRes.data);
            setVisibilityMode(accessRes.data.visibility_mode || 'brand_based');
            setSelectedUserIds(accessRes.data.allowed_user_ids || []);
            
            // Load all users
            const usersRes = await api.get('/api/users');
            setAllUsers(usersRes.data || []);
        } catch (err) {
            console.error('Failed to load access settings:', err);
            toast.error('Failed to load access settings');
        } finally {
            setLoading(false);
        }
    };

    // Filter users based on eligibility rules
    const eligibleUsers = useMemo(() => {
        if (!allUsers.length) return [];
        
        return allUsers.filter(u => {
            // Super Admin can assign anyone
            if (isSuperAdmin) return true;
            
            // Admin can only assign users with same brand access
            if (user?.role === 'admin') {
                // Must share brand access
                const hasSharedBrand = u.brand_ids?.includes(brandId) || u.role === 'super_admin';
                // Can only assign Viewer or Admin (not Super Admin)
                const isAssignable = u.role !== 'super_admin';
                return hasSharedBrand && isAssignable;
            }
            
            return false;
        });
    }, [allUsers, isSuperAdmin, user, brandId]);

    // Filter users for search
    const filteredUsers = useMemo(() => {
        if (!searchQuery.trim()) return eligibleUsers;
        
        const query = searchQuery.toLowerCase();
        return eligibleUsers.filter(u => 
            (u.name?.toLowerCase().includes(query)) ||
            (u.email?.toLowerCase().includes(query))
        );
    }, [eligibleUsers, searchQuery]);

    // Get selected user objects
    const selectedUsers = useMemo(() => {
        return allUsers.filter(u => selectedUserIds.includes(u.id));
    }, [allUsers, selectedUserIds]);

    // Users available to add (not already selected)
    const availableUsers = useMemo(() => {
        return filteredUsers.filter(u => !selectedUserIds.includes(u.id));
    }, [filteredUsers, selectedUserIds]);

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
            await api.put(`/api/v3/networks/${networkId}/access-control`, {
                visibility_mode: visibilityMode,
                allowed_user_ids: visibilityMode === 'restricted' ? selectedUserIds : []
            });
            toast.success('Access settings updated');
            loadData();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to update access settings');
        } finally {
            setSaving(false);
        }
    };

    const addUser = (userId) => {
        if (!selectedUserIds.includes(userId)) {
            setSelectedUserIds(prev => [...prev, userId]);
        }
        setSearchQuery('');
    };

    const removeUser = (userId) => {
        setSelectedUserIds(prev => prev.filter(id => id !== userId));
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

                        {/* User Search & Add */}
                        <div className="mb-4">
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                                <Input
                                    value={searchQuery}
                                    onChange={(e) => {
                                        setSearchQuery(e.target.value);
                                        setShowUserSelector(true);
                                    }}
                                    onFocus={() => setShowUserSelector(true)}
                                    placeholder="Search users by name or email..."
                                    className="pl-10 bg-black border-border"
                                    data-testid="user-search-input"
                                />
                            </div>

                            {/* User Dropdown */}
                            {showUserSelector && (searchQuery || availableUsers.length > 0) && (
                                <div className="mt-2 border border-border rounded-lg bg-zinc-900 max-h-[200px] overflow-hidden">
                                    <ScrollArea className="h-full max-h-[200px]">
                                        {availableUsers.length > 0 ? (
                                            <div className="p-1">
                                                {availableUsers.slice(0, 10).map(u => (
                                                    <div
                                                        key={u.id}
                                                        onClick={() => addUser(u.id)}
                                                        className="flex items-center justify-between p-2 rounded hover:bg-zinc-800 cursor-pointer"
                                                        data-testid={`add-user-${u.id}`}
                                                    >
                                                        <div className="flex items-center gap-3">
                                                            <div className={`h-8 w-8 rounded-full flex items-center justify-center text-white text-sm font-medium ${
                                                                u.role === 'super_admin' ? 'bg-amber-600' : 
                                                                u.role === 'admin' ? 'bg-blue-600' : 'bg-zinc-600'
                                                            }`}>
                                                                {u.name?.charAt(0)?.toUpperCase() || u.email?.charAt(0)?.toUpperCase()}
                                                            </div>
                                                            <div>
                                                                <p className="text-sm text-white font-medium">{u.name || u.email.split('@')[0]}</p>
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
                                                {searchQuery ? 'No users found matching your search' : 'All eligible users have been added'}
                                            </div>
                                        )}
                                    </ScrollArea>
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
                                                    <p className="text-white font-medium">{u.name || u.email.split('@')[0]}</p>
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
