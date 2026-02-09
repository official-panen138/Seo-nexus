import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import api from '../lib/api';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Badge } from './ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Skeleton } from './ui/skeleton';
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
    Info
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

export function NetworkAccessSettings({ networkId, brandId }) {
    const { user } = useAuth();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [accessControl, setAccessControl] = useState(null);
    const [brandUsers, setBrandUsers] = useState([]);
    const [selectedUsers, setSelectedUsers] = useState([]);
    const [visibilityMode, setVisibilityMode] = useState('brand_based');

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
            setSelectedUsers(accessRes.data.allowed_user_ids || []);
            
            // Load users who have access to this brand
            const usersRes = await api.get('/api/users');
            const filteredUsers = usersRes.data.filter(u => 
                u.role === 'super_admin' || 
                (u.brand_ids && u.brand_ids.includes(brandId))
            );
            setBrandUsers(filteredUsers);
        } catch (err) {
            console.error('Failed to load access settings:', err);
            toast.error('Failed to load access settings');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            await api.put(`/api/v3/networks/${networkId}/access-control`, {
                visibility_mode: visibilityMode,
                allowed_user_ids: visibilityMode === 'restricted' ? selectedUsers : []
            });
            toast.success('Access settings updated');
            loadData();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to update access settings');
        } finally {
            setSaving(false);
        }
    };

    const toggleUser = (userId) => {
        setSelectedUsers(prev => 
            prev.includes(userId) 
                ? prev.filter(id => id !== userId)
                : [...prev, userId]
        );
    };

    if (!isAdmin) {
        return null; // Don't show to non-admins
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
                                Allowed Users ({selectedUsers.length})
                            </Label>
                        </div>
                        
                        {brandUsers.length > 0 ? (
                            <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2">
                                {brandUsers.map((u) => {
                                    const isSelected = selectedUsers.includes(u.id);
                                    return (
                                        <div
                                            key={u.id}
                                            onClick={() => toggleUser(u.id)}
                                            className={`p-3 rounded-lg border cursor-pointer transition-all flex items-center justify-between ${
                                                isSelected 
                                                    ? 'border-emerald-500/50 bg-emerald-950/20' 
                                                    : 'border-border hover:border-zinc-600 bg-zinc-900/30'
                                            }`}
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className={`h-8 w-8 rounded-full flex items-center justify-center text-white text-sm font-medium ${
                                                    u.role === 'super_admin' ? 'bg-amber-600' : 
                                                    u.role === 'admin' ? 'bg-blue-600' : 'bg-zinc-600'
                                                }`}>
                                                    {u.name?.charAt(0)?.toUpperCase() || u.email?.charAt(0)?.toUpperCase()}
                                                </div>
                                                <div>
                                                    <p className="text-white text-sm font-medium">{u.name || u.email.split('@')[0]}</p>
                                                    <p className="text-xs text-zinc-500">{u.email}</p>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Badge variant="outline" className="text-xs">
                                                    {u.role}
                                                </Badge>
                                                {isSelected && (
                                                    <CheckCircle className="h-4 w-4 text-emerald-400" />
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="text-center py-8 text-zinc-500">
                                <Users className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                <p className="text-sm">No users available</p>
                            </div>
                        )}
                        
                        {selectedUsers.length === 0 && (
                            <div className="mt-4 p-3 rounded-lg bg-amber-950/30 border border-amber-900/50 flex items-start gap-2">
                                <AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 flex-shrink-0" />
                                <p className="text-sm text-amber-300">
                                    No users selected. Only Super Admins will be able to access this network.
                                </p>
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
                            <li><strong>Public:</strong> All platform users can view (Super Admin only).</li>
                        </ul>
                    </div>
                </div>

                {/* Save Button */}
                <div className="flex justify-end pt-4 border-t border-border">
                    <Button 
                        onClick={handleSave} 
                        disabled={saving}
                        className="gap-2"
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
