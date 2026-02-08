import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Trash2, Loader2, Users, Shield, Building2, Edit } from 'lucide-react';
import { formatDate } from '../lib/utils';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ROLE_LABELS = {
    'super_admin': 'Super Admin',
    'admin': 'Admin',
    'viewer': 'Viewer'
};

export default function UsersPage() {
    const { user: currentUser, hasRole } = useAuth();
    const [users, setUsers] = useState([]);
    const [brands, setBrands] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [selectedUser, setSelectedUser] = useState(null);
    const [editForm, setEditForm] = useState({
        role: '',
        brand_scope_ids: []
    });

    const isSuperAdmin = hasRole('super_admin');

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const headers = { 'Authorization': `Bearer ${token}` };

            const [usersRes, brandsRes] = await Promise.all([
                fetch(`${API_URL}/api/users`, { headers }),
                fetch(`${API_URL}/api/brands?include_archived=false`, { headers })
            ]);

            if (usersRes.ok) {
                const data = await usersRes.json();
                setUsers(data);
            }

            if (brandsRes.ok) {
                const data = await brandsRes.json();
                setBrands(data);
            }
        } catch (err) {
            toast.error('Failed to load data');
        } finally {
            setLoading(false);
        }
    };

    const openEditDialog = (user) => {
        setSelectedUser(user);
        setEditForm({
            role: user.role,
            brand_scope_ids: user.brand_scope_ids || []
        });
        setEditDialogOpen(true);
    };

    const handleUpdateUser = async () => {
        if (!selectedUser) return;

        // Validation
        if (editForm.role !== 'super_admin' && editForm.brand_scope_ids.length === 0) {
            toast.error('Admin and Viewer users must have at least one brand assigned');
            return;
        }

        setSaving(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const response = await fetch(`${API_URL}/api/users/${selectedUser.id}`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    role: editForm.role,
                    brand_scope_ids: editForm.role === 'super_admin' ? null : editForm.brand_scope_ids
                })
            });

            if (response.ok) {
                toast.success('User updated');
                setEditDialogOpen(false);
                loadData();
            } else {
                const error = await response.json();
                toast.error(error.detail || 'Failed to update user');
            }
        } catch (err) {
            toast.error('Failed to update user');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!selectedUser) return;
        
        setSaving(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const response = await fetch(`${API_URL}/api/users/${selectedUser.id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                toast.success('User deleted');
                setDeleteDialogOpen(false);
                setSelectedUser(null);
                loadData();
            } else {
                const error = await response.json();
                toast.error(error.detail || 'Failed to delete user');
            }
        } catch (err) {
            toast.error('Failed to delete user');
        } finally {
            setSaving(false);
        }
    };

    const toggleBrand = (brandId) => {
        setEditForm(prev => ({
            ...prev,
            brand_scope_ids: prev.brand_scope_ids.includes(brandId)
                ? prev.brand_scope_ids.filter(id => id !== brandId)
                : [...prev.brand_scope_ids, brandId]
        }));
    };

    const selectAllBrands = () => {
        setEditForm(prev => ({
            ...prev,
            brand_scope_ids: brands.map(b => b.id)
        }));
    };

    const clearAllBrands = () => {
        setEditForm(prev => ({
            ...prev,
            brand_scope_ids: []
        }));
    };

    const getRoleBadgeClass = (role) => {
        switch (role) {
            case 'super_admin':
                return 'border-red-500 text-red-500';
            case 'admin':
                return 'border-blue-500 text-blue-500';
            default:
                return 'border-zinc-500 text-zinc-500';
        }
    };

    const getBrandNames = (brandIds) => {
        if (!brandIds || brandIds.length === 0) return [];
        return brandIds
            .map(id => brands.find(b => b.id === id)?.name)
            .filter(Boolean);
    };

    if (!isSuperAdmin) {
        return (
            <Layout>
                <div className="text-center py-16">
                    <p className="text-zinc-400">Access denied. Super Admin only.</p>
                </div>
            </Layout>
        );
    }

    if (loading) {
        return (
            <Layout>
                <div className="flex items-center justify-center h-96">
                    <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
                </div>
            </Layout>
        );
    }

    return (
        <Layout>
            <div data-testid="users-page">
                {/* Header */}
                <div className="page-header">
                    <h1 className="page-title">Users</h1>
                    <p className="page-subtitle">
                        {users.length} user{users.length !== 1 ? 's' : ''} registered
                    </p>
                </div>

                {/* Users Table */}
                <div className="data-table-container" data-testid="users-table">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>User</TableHead>
                                <TableHead>Email</TableHead>
                                <TableHead>Role</TableHead>
                                <TableHead>Brand Access</TableHead>
                                <TableHead>Joined</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {users.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={6} className="h-32 text-center">
                                        <div className="empty-state py-8">
                                            <Users className="empty-state-icon mx-auto" />
                                            <p className="empty-state-title">No users yet</p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                users.map((user) => (
                                    <TableRow key={user.id} className="table-row-hover" data-testid={`user-row-${user.id}`}>
                                        <TableCell>
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-medium text-sm">
                                                    {user.name?.charAt(0).toUpperCase()}
                                                </div>
                                                <span className="font-medium">{user.name}</span>
                                                {user.id === currentUser?.id && (
                                                    <Badge variant="outline" className="text-xs">You</Badge>
                                                )}
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-zinc-400">
                                            {user.email}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline" className={getRoleBadgeClass(user.role)}>
                                                <Shield className="h-3 w-3 mr-1" />
                                                {ROLE_LABELS[user.role]}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            {user.role === 'super_admin' ? (
                                                <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                                                    <Building2 className="h-3 w-3 mr-1" />
                                                    All Brands
                                                </Badge>
                                            ) : user.brand_scope_ids?.length > 0 ? (
                                                <div className="flex flex-wrap gap-1 max-w-[200px]">
                                                    {getBrandNames(user.brand_scope_ids).slice(0, 2).map((name, idx) => (
                                                        <Badge key={idx} variant="outline" className="text-xs">
                                                            {name}
                                                        </Badge>
                                                    ))}
                                                    {user.brand_scope_ids.length > 2 && (
                                                        <Badge variant="outline" className="text-xs text-zinc-500">
                                                            +{user.brand_scope_ids.length - 2} more
                                                        </Badge>
                                                    )}
                                                </div>
                                            ) : (
                                                <Badge variant="outline" className="text-red-400 border-red-400">
                                                    No brands
                                                </Badge>
                                            )}
                                        </TableCell>
                                        <TableCell className="text-zinc-500 text-sm">
                                            {formatDate(user.created_at)}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex items-center justify-end gap-1">
                                                {user.id !== currentUser?.id && (
                                                    <>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => openEditDialog(user)}
                                                            className="h-8 w-8 hover:bg-blue-500/10 hover:text-blue-500"
                                                            data-testid={`edit-user-${user.id}`}
                                                        >
                                                            <Edit className="h-4 w-4" />
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => {
                                                                setSelectedUser(user);
                                                                setDeleteDialogOpen(true);
                                                            }}
                                                            className="h-8 w-8 hover:bg-red-500/10 hover:text-red-500"
                                                            data-testid={`delete-user-${user.id}`}
                                                        >
                                                            <Trash2 className="h-4 w-4" />
                                                        </Button>
                                                    </>
                                                )}
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>

                {/* Edit User Dialog */}
                <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-lg">
                        <DialogHeader>
                            <DialogTitle>Edit User</DialogTitle>
                            <DialogDescription>
                                Update role and brand access for {selectedUser?.name}
                            </DialogDescription>
                        </DialogHeader>
                        
                        <div className="space-y-6 py-4">
                            {/* Role Selection */}
                            <div className="space-y-2">
                                <Label>Role</Label>
                                <Select 
                                    value={editForm.role} 
                                    onValueChange={(value) => setEditForm(prev => ({ ...prev, role: value }))}
                                >
                                    <SelectTrigger data-testid="edit-role-select">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="super_admin">Super Admin</SelectItem>
                                        <SelectItem value="admin">Admin</SelectItem>
                                        <SelectItem value="viewer">Viewer</SelectItem>
                                    </SelectContent>
                                </Select>
                                {editForm.role === 'super_admin' && (
                                    <p className="text-xs text-zinc-500">Super Admin has access to all brands</p>
                                )}
                            </div>

                            {/* Brand Access (only for non-super-admin) */}
                            {editForm.role !== 'super_admin' && (
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <Label>Allowed Brands</Label>
                                        <div className="flex gap-2">
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                onClick={selectAllBrands}
                                                className="text-xs h-7"
                                            >
                                                Select All
                                            </Button>
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                onClick={clearAllBrands}
                                                className="text-xs h-7"
                                            >
                                                Clear
                                            </Button>
                                        </div>
                                    </div>
                                    
                                    <div className="border border-zinc-800 rounded-md p-3 max-h-48 overflow-y-auto space-y-2">
                                        {brands.length === 0 ? (
                                            <p className="text-zinc-500 text-sm">No brands available</p>
                                        ) : (
                                            brands.map((brand) => (
                                                <div key={brand.id} className="flex items-center space-x-2">
                                                    <Checkbox
                                                        id={`brand-${brand.id}`}
                                                        checked={editForm.brand_scope_ids.includes(brand.id)}
                                                        onCheckedChange={() => toggleBrand(brand.id)}
                                                    />
                                                    <label 
                                                        htmlFor={`brand-${brand.id}`}
                                                        className="text-sm cursor-pointer flex items-center gap-2"
                                                    >
                                                        <Building2 className="h-4 w-4 text-zinc-500" />
                                                        {brand.name}
                                                        {brand.status === 'archived' && (
                                                            <Badge variant="outline" className="text-xs text-zinc-500">Archived</Badge>
                                                        )}
                                                    </label>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                    
                                    {editForm.brand_scope_ids.length === 0 && (
                                        <p className="text-xs text-red-400">At least one brand is required</p>
                                    )}
                                </div>
                            )}
                        </div>

                        <DialogFooter>
                            <Button
                                variant="outline"
                                onClick={() => setEditDialogOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleUpdateUser}
                                disabled={saving || (editForm.role !== 'super_admin' && editForm.brand_scope_ids.length === 0)}
                                data-testid="save-user-btn"
                            >
                                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                Save Changes
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Delete Confirmation Dialog */}
                <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-md">
                        <DialogHeader>
                            <DialogTitle>Delete User</DialogTitle>
                        </DialogHeader>
                        <p className="text-zinc-400">
                            Are you sure you want to delete <span className="text-white font-medium">{selectedUser?.name}</span> ({selectedUser?.email})?
                            This action cannot be undone.
                        </p>
                        <DialogFooter>
                            <Button
                                variant="outline"
                                onClick={() => setDeleteDialogOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleDelete}
                                disabled={saving}
                                className="bg-red-600 hover:bg-red-700"
                                data-testid="confirm-delete-user-btn"
                            >
                                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                Delete
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </Layout>
    );
}
