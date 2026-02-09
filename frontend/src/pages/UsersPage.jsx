import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { Trash2, Loader2, Users, Shield, Building2, Edit, UserPlus, Clock, CheckCircle, XCircle, Copy, UserX, UserCheck, MoreHorizontal, AlertTriangle } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '../components/ui/dropdown-menu';
import { formatDate } from '../lib/utils';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ROLE_LABELS = {
    'super_admin': 'Super Admin',
    'admin': 'Admin',
    'viewer': 'Viewer'
};

const STATUS_COLORS = {
    'active': 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    'pending': 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    'rejected': 'bg-red-500/20 text-red-400 border-red-500/30',
    'inactive': 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
    'suspended': 'bg-orange-500/20 text-orange-400 border-orange-500/30'
};

export default function UsersPage() {
    const { user: currentUser, hasRole } = useAuth();
    const [users, setUsers] = useState([]);
    const [pendingUsers, setPendingUsers] = useState([]);
    const [brands, setBrands] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [approveDialogOpen, setApproveDialogOpen] = useState(false);
    const [createDialogOpen, setCreateDialogOpen] = useState(false);
    const [selectedUser, setSelectedUser] = useState(null);
    const [editForm, setEditForm] = useState({ role: '', brand_scope_ids: [], telegram_username: '' });
    const [approveForm, setApproveForm] = useState({ role: 'viewer', brand_scope_ids: [] });
    const [createForm, setCreateForm] = useState({ email: '', name: '', role: 'viewer', brand_scope_ids: [], password: '', useManualPassword: false });
    const [generatedPassword, setGeneratedPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [deactivateDialogOpen, setDeactivateDialogOpen] = useState(false);
    const [activateDialogOpen, setActivateDialogOpen] = useState(false);

    const isSuperAdmin = hasRole('super_admin');

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const headers = { 'Authorization': `Bearer ${token}` };

            const [usersRes, pendingRes, brandsRes] = await Promise.all([
                fetch(`${API_URL}/api/users`, { headers }),
                fetch(`${API_URL}/api/users/pending`, { headers }),
                fetch(`${API_URL}/api/brands?include_archived=false`, { headers })
            ]);

            if (usersRes.ok) setUsers(await usersRes.json());
            if (pendingRes.ok) setPendingUsers(await pendingRes.json());
            if (brandsRes.ok) setBrands(await brandsRes.json());
        } catch (err) {
            toast.error('Failed to load data');
        } finally {
            setLoading(false);
        }
    };

    const openEditDialog = (user) => {
        setSelectedUser(user);
        setEditForm({ role: user.role, brand_scope_ids: user.brand_scope_ids || [] });
        setEditDialogOpen(true);
    };

    const openApproveDialog = (user) => {
        setSelectedUser(user);
        setApproveForm({ role: 'viewer', brand_scope_ids: [] });
        setApproveDialogOpen(true);
    };

    const handleUpdateUser = async () => {
        if (!selectedUser) return;
        if (editForm.role !== 'super_admin' && editForm.brand_scope_ids.length === 0) {
            toast.error('Admin and Viewer must have at least one brand');
            return;
        }

        setSaving(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const response = await fetch(`${API_URL}/api/users/${selectedUser.id}`, {
                method: 'PUT',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
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

    const handleApproveUser = async () => {
        if (!selectedUser) return;
        if (approveForm.brand_scope_ids.length === 0) {
            toast.error('Please assign at least one brand');
            return;
        }

        setSaving(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const response = await fetch(`${API_URL}/api/users/${selectedUser.id}/approve`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(approveForm)
            });

            if (response.ok) {
                toast.success(`User ${selectedUser.name} approved`);
                setApproveDialogOpen(false);
                loadData();
            } else {
                const error = await response.json();
                toast.error(error.detail || 'Failed to approve user');
            }
        } catch (err) {
            toast.error('Failed to approve user');
        } finally {
            setSaving(false);
        }
    };

    const handleRejectUser = async (user) => {
        if (!confirm(`Are you sure you want to reject ${user.name}?`)) return;

        setSaving(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const response = await fetch(`${API_URL}/api/users/${user.id}/reject`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                toast.success(`User ${user.name} rejected`);
                loadData();
            } else {
                const error = await response.json();
                toast.error(error.detail || 'Failed to reject user');
            }
        } catch (err) {
            toast.error('Failed to reject user');
        } finally {
            setSaving(false);
        }
    };

    const handleCreateUser = async () => {
        if (!createForm.email || !createForm.name) {
            toast.error('Please fill in email and name');
            return;
        }
        if (createForm.brand_scope_ids.length === 0) {
            toast.error('Please assign at least one brand');
            return;
        }
        if (createForm.useManualPassword && (!createForm.password || createForm.password.length < 6)) {
            toast.error('Password must be at least 6 characters');
            return;
        }

        setSaving(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const payload = {
                email: createForm.email,
                name: createForm.name,
                role: createForm.role,
                brand_scope_ids: createForm.brand_scope_ids
            };
            
            // Only include password if manual password is enabled
            if (createForm.useManualPassword && createForm.password) {
                payload.password = createForm.password;
            }
            
            const response = await fetch(`${API_URL}/api/users/create`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const data = await response.json();
                if (data.password_was_generated) {
                    setGeneratedPassword(data.generated_password);
                } else {
                    // Manual password was used, just close dialog
                    toast.success('User created successfully');
                    closeCreateDialog();
                }
                loadData();
            } else {
                const error = await response.json();
                toast.error(error.detail || 'Failed to create user');
            }
        } catch (err) {
            toast.error('Failed to create user');
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

    const handleDeactivate = async () => {
        if (!selectedUser) return;
        
        setSaving(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const response = await fetch(`${API_URL}/api/users/${selectedUser.id}/deactivate`, {
                method: 'PATCH',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                toast.success('User deactivated successfully');
                setDeactivateDialogOpen(false);
                setSelectedUser(null);
                loadData();
            } else {
                const error = await response.json();
                toast.error(error.detail || 'Failed to deactivate user');
            }
        } catch (err) {
            toast.error('Failed to deactivate user');
        } finally {
            setSaving(false);
        }
    };

    const handleActivate = async () => {
        if (!selectedUser) return;
        
        setSaving(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const response = await fetch(`${API_URL}/api/users/${selectedUser.id}/activate`, {
                method: 'PATCH',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                toast.success('User activated successfully');
                setActivateDialogOpen(false);
                setSelectedUser(null);
                loadData();
            } else {
                const error = await response.json();
                toast.error(error.detail || 'Failed to activate user');
            }
        } catch (err) {
            toast.error('Failed to activate user');
        } finally {
            setSaving(false);
        }
    };

    const toggleBrand = (brandId, formSetter) => {
        formSetter(prev => ({
            ...prev,
            brand_scope_ids: prev.brand_scope_ids.includes(brandId)
                ? prev.brand_scope_ids.filter(id => id !== brandId)
                : [...prev.brand_scope_ids, brandId]
        }));
    };

    const selectAllBrands = (formSetter) => {
        formSetter(prev => ({ ...prev, brand_scope_ids: brands.map(b => b.id) }));
    };

    const clearAllBrands = (formSetter) => {
        formSetter(prev => ({ ...prev, brand_scope_ids: [] }));
    };

    const copyPassword = () => {
        navigator.clipboard.writeText(generatedPassword);
        toast.success('Password copied to clipboard');
    };

    const closeCreateDialog = () => {
        setCreateDialogOpen(false);
        setCreateForm({ email: '', name: '', role: 'viewer', brand_scope_ids: [], password: '', useManualPassword: false });
        setGeneratedPassword('');
        setShowPassword(false);
    };

    const getRoleBadgeClass = (role) => {
        switch (role) {
            case 'super_admin': return 'border-red-500 text-red-500';
            case 'admin': return 'border-blue-500 text-blue-500';
            default: return 'border-zinc-500 text-zinc-500';
        }
    };

    const getBrandNames = (brandIds) => {
        if (!brandIds || brandIds.length === 0) return [];
        return brandIds.map(id => brands.find(b => b.id === id)?.name).filter(Boolean);
    };

    // Brand selector component
    const BrandSelector = ({ value, onChange, formSetter }) => (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <Label>Brand Access</Label>
                <div className="flex gap-2">
                    <Button type="button" variant="ghost" size="sm" onClick={() => selectAllBrands(formSetter)} className="text-xs h-7">Select All</Button>
                    <Button type="button" variant="ghost" size="sm" onClick={() => clearAllBrands(formSetter)} className="text-xs h-7">Clear</Button>
                </div>
            </div>
            <div className="border border-zinc-800 rounded-md p-3 max-h-48 overflow-y-auto space-y-2">
                {brands.length === 0 ? (
                    <p className="text-zinc-500 text-sm">No brands available</p>
                ) : brands.map((brand) => (
                    <div key={brand.id} className="flex items-center space-x-2">
                        <Checkbox id={`brand-${brand.id}`} checked={value.includes(brand.id)} onCheckedChange={() => toggleBrand(brand.id, formSetter)} />
                        <label htmlFor={`brand-${brand.id}`} className="text-sm cursor-pointer flex items-center gap-2">
                            <Building2 className="h-4 w-4 text-zinc-500" />{brand.name}
                        </label>
                    </div>
                ))}
            </div>
            {value.length === 0 && <p className="text-xs text-red-400">At least one brand is required</p>}
        </div>
    );

    if (!isSuperAdmin) {
        return <Layout><div className="text-center py-16"><p className="text-zinc-400">Access denied. Super Admin only.</p></div></Layout>;
    }

    if (loading) {
        return <Layout><div className="flex items-center justify-center h-96"><Loader2 className="h-8 w-8 animate-spin text-blue-500" /></div></Layout>;
    }

    const activeUsers = users.filter(u => u.status === 'active' || !u.status);

    return (
        <Layout>
            <div data-testid="users-page">
                <div className="page-header flex items-center justify-between">
                    <div>
                        <h1 className="page-title">Users</h1>
                        <p className="page-subtitle">{users.length} users • {pendingUsers.length} pending approval</p>
                    </div>
                    <Button onClick={() => setCreateDialogOpen(true)} className="bg-blue-600 hover:bg-blue-700" data-testid="add-user-btn">
                        <UserPlus className="h-4 w-4 mr-2" />Add User
                    </Button>
                </div>

                <Tabs defaultValue="all" className="w-full">
                    <TabsList className="mb-4">
                        <TabsTrigger value="all" className="flex items-center gap-2">
                            <Users className="h-4 w-4" />All Users
                            <Badge variant="outline" className="ml-1">{activeUsers.length}</Badge>
                        </TabsTrigger>
                        <TabsTrigger value="pending" className="flex items-center gap-2" data-testid="pending-tab">
                            <Clock className="h-4 w-4" />Pending Approvals
                            {pendingUsers.length > 0 && <Badge className="ml-1 bg-amber-500 text-black">{pendingUsers.length}</Badge>}
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="all">
                        <div className="data-table-container" data-testid="users-table">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>User</TableHead>
                                        <TableHead>Email</TableHead>
                                        <TableHead>Role</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Brand Access</TableHead>
                                        <TableHead>Joined</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {users.length === 0 ? (
                                        <TableRow><TableCell colSpan={7} className="h-32 text-center"><div className="empty-state py-8"><Users className="empty-state-icon mx-auto" /><p className="empty-state-title">No users yet</p></div></TableCell></TableRow>
                                    ) : users.map((user) => (
                                        <TableRow key={user.id} className="table-row-hover" data-testid={`user-row-${user.id}`}>
                                            <TableCell>
                                                <div className="flex items-center gap-3">
                                                    <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-medium text-sm">{user.name?.charAt(0).toUpperCase()}</div>
                                                    <span className="font-medium">{user.name}</span>
                                                    {user.id === currentUser?.id && <Badge variant="outline" className="text-xs">You</Badge>}
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-zinc-400">{user.email}</TableCell>
                                            <TableCell><Badge variant="outline" className={getRoleBadgeClass(user.role)}><Shield className="h-3 w-3 mr-1" />{ROLE_LABELS[user.role]}</Badge></TableCell>
                                            <TableCell><Badge className={STATUS_COLORS[user.status || 'active']}>{(user.status || 'active').toUpperCase()}</Badge></TableCell>
                                            <TableCell>
                                                {user.role === 'super_admin' ? (
                                                    <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30"><Building2 className="h-3 w-3 mr-1" />All Brands</Badge>
                                                ) : user.brand_scope_ids?.length > 0 ? (
                                                    <div className="flex flex-wrap gap-1 max-w-[200px]">
                                                        {getBrandNames(user.brand_scope_ids).slice(0, 2).map((name, idx) => <Badge key={idx} variant="outline" className="text-xs">{name}</Badge>)}
                                                        {user.brand_scope_ids.length > 2 && <Badge variant="outline" className="text-xs text-zinc-500">+{user.brand_scope_ids.length - 2}</Badge>}
                                                    </div>
                                                ) : <Badge variant="outline" className="text-red-400 border-red-400">No brands</Badge>}
                                            </TableCell>
                                            <TableCell className="text-zinc-500 text-sm">{formatDate(user.created_at)}</TableCell>
                                            <TableCell className="text-right">
                                                {user.id !== currentUser?.id && (
                                                    <DropdownMenu>
                                                        <DropdownMenuTrigger asChild>
                                                            <Button variant="ghost" size="icon" className="h-8 w-8" data-testid={`user-actions-${user.id}`}>
                                                                <MoreHorizontal className="h-4 w-4" />
                                                            </Button>
                                                        </DropdownMenuTrigger>
                                                        <DropdownMenuContent align="end" className="w-48">
                                                            <DropdownMenuItem onClick={() => openEditDialog(user)} className="cursor-pointer">
                                                                <Edit className="h-4 w-4 mr-2" />
                                                                Edit User
                                                            </DropdownMenuItem>
                                                            
                                                            {user.status === 'active' ? (
                                                                <DropdownMenuItem 
                                                                    onClick={() => { setSelectedUser(user); setDeactivateDialogOpen(true); }}
                                                                    className="cursor-pointer text-amber-500 focus:text-amber-500"
                                                                    data-testid={`deactivate-user-${user.id}`}
                                                                >
                                                                    <UserX className="h-4 w-4 mr-2" />
                                                                    Deactivate User
                                                                </DropdownMenuItem>
                                                            ) : (user.status === 'inactive' || user.status === 'suspended') && (
                                                                <DropdownMenuItem 
                                                                    onClick={() => { setSelectedUser(user); setActivateDialogOpen(true); }}
                                                                    className="cursor-pointer text-emerald-500 focus:text-emerald-500"
                                                                    data-testid={`activate-user-${user.id}`}
                                                                >
                                                                    <UserCheck className="h-4 w-4 mr-2" />
                                                                    Activate User
                                                                </DropdownMenuItem>
                                                            )}
                                                            
                                                            <DropdownMenuSeparator />
                                                            
                                                            <DropdownMenuItem 
                                                                onClick={() => { setSelectedUser(user); setDeleteDialogOpen(true); }}
                                                                className="cursor-pointer text-red-500 focus:text-red-500"
                                                                data-testid={`delete-user-${user.id}`}
                                                            >
                                                                <Trash2 className="h-4 w-4 mr-2" />
                                                                Delete User
                                                            </DropdownMenuItem>
                                                        </DropdownMenuContent>
                                                    </DropdownMenu>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </TabsContent>

                    <TabsContent value="pending">
                        {pendingUsers.length === 0 ? (
                            <Card className="bg-card border-border">
                                <CardContent className="py-16 text-center">
                                    <CheckCircle className="h-12 w-12 text-emerald-500 mx-auto mb-4" />
                                    <h3 className="text-lg font-medium">No Pending Approvals</h3>
                                    <p className="text-zinc-500 mt-2">All user registrations have been processed.</p>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="data-table-container" data-testid="pending-users-table">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>User</TableHead>
                                            <TableHead>Email</TableHead>
                                            <TableHead>Registration Date</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead className="text-right">Actions</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {pendingUsers.map((user) => (
                                            <TableRow key={user.id} className="table-row-hover" data-testid={`pending-user-${user.id}`}>
                                                <TableCell>
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-8 h-8 rounded-full bg-amber-600 flex items-center justify-center text-white font-medium text-sm">{user.name?.charAt(0).toUpperCase()}</div>
                                                        <span className="font-medium">{user.name}</span>
                                                    </div>
                                                </TableCell>
                                                <TableCell className="text-zinc-400">{user.email}</TableCell>
                                                <TableCell className="text-zinc-500 text-sm">{formatDate(user.created_at)}</TableCell>
                                                <TableCell><Badge className={STATUS_COLORS.pending}><Clock className="h-3 w-3 mr-1" />PENDING</Badge></TableCell>
                                                <TableCell className="text-right">
                                                    <div className="flex items-center justify-end gap-2">
                                                        <Button size="sm" onClick={() => openApproveDialog(user)} className="bg-emerald-600 hover:bg-emerald-700" data-testid={`approve-user-${user.id}`}>
                                                            <CheckCircle className="h-4 w-4 mr-1" />Approve
                                                        </Button>
                                                        <Button size="sm" variant="destructive" onClick={() => handleRejectUser(user)} data-testid={`reject-user-${user.id}`}>
                                                            <XCircle className="h-4 w-4 mr-1" />Reject
                                                        </Button>
                                                    </div>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        )}
                    </TabsContent>
                </Tabs>

                {/* Approve User Dialog */}
                <Dialog open={approveDialogOpen} onOpenChange={setApproveDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-lg">
                        <DialogHeader>
                            <DialogTitle>Approve User</DialogTitle>
                            <DialogDescription>Assign role and brand access for {selectedUser?.name} ({selectedUser?.email})</DialogDescription>
                        </DialogHeader>
                        <div className="space-y-6 py-4">
                            <div className="space-y-2">
                                <Label>Role</Label>
                                <Select value={approveForm.role} onValueChange={(value) => setApproveForm(prev => ({ ...prev, role: value }))}>
                                    <SelectTrigger data-testid="approve-role-select"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="admin">Admin</SelectItem>
                                        <SelectItem value="viewer">Viewer</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <BrandSelector value={approveForm.brand_scope_ids} onChange={(v) => setApproveForm(prev => ({ ...prev, brand_scope_ids: v }))} formSetter={setApproveForm} />
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setApproveDialogOpen(false)}>Cancel</Button>
                            <Button onClick={handleApproveUser} disabled={saving || approveForm.brand_scope_ids.length === 0} className="bg-emerald-600 hover:bg-emerald-700" data-testid="confirm-approve-btn">
                                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Approve User
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Create User Dialog */}
                <Dialog open={createDialogOpen} onOpenChange={closeCreateDialog}>
                    <DialogContent className="bg-card border-border max-w-lg">
                        <DialogHeader>
                            <DialogTitle>Create New User</DialogTitle>
                            <DialogDescription>Create a user directly. They will be active immediately.</DialogDescription>
                        </DialogHeader>
                        
                        {generatedPassword ? (
                            <div className="space-y-4 py-4">
                                <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                                    <h4 className="font-medium text-emerald-400 mb-2">User Created Successfully!</h4>
                                    <p className="text-sm text-zinc-400 mb-3">Please save this password. It will only be shown once.</p>
                                    <div className="flex items-center gap-2">
                                        <code className="flex-1 p-2 bg-black rounded font-mono text-sm">{generatedPassword}</code>
                                        <Button variant="outline" size="icon" onClick={copyPassword}><Copy className="h-4 w-4" /></Button>
                                    </div>
                                </div>
                                <Button onClick={closeCreateDialog} className="w-full">Done</Button>
                            </div>
                        ) : (
                            <>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <Label>Full Name</Label>
                                        <Input value={createForm.name} onChange={(e) => setCreateForm(prev => ({ ...prev, name: e.target.value }))} placeholder="John Doe" data-testid="create-user-name" />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Email</Label>
                                        <Input type="email" value={createForm.email} onChange={(e) => setCreateForm(prev => ({ ...prev, email: e.target.value }))} placeholder="john@example.com" data-testid="create-user-email" />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Role</Label>
                                        <Select value={createForm.role} onValueChange={(value) => setCreateForm(prev => ({ ...prev, role: value }))}>
                                            <SelectTrigger data-testid="create-user-role"><SelectValue /></SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="admin">Admin</SelectItem>
                                                <SelectItem value="viewer">Viewer</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    
                                    {/* Password Option */}
                                    <div className="space-y-3">
                                        <div className="flex items-center space-x-2">
                                            <Checkbox 
                                                id="manual-password" 
                                                checked={createForm.useManualPassword} 
                                                onCheckedChange={(checked) => setCreateForm(prev => ({ ...prev, useManualPassword: checked, password: '' }))}
                                                data-testid="manual-password-checkbox"
                                            />
                                            <label htmlFor="manual-password" className="text-sm cursor-pointer">Set password manually</label>
                                        </div>
                                        
                                        {createForm.useManualPassword ? (
                                            <div className="space-y-2">
                                                <Label>Password</Label>
                                                <div className="relative">
                                                    <Input 
                                                        type={showPassword ? "text" : "password"} 
                                                        value={createForm.password} 
                                                        onChange={(e) => setCreateForm(prev => ({ ...prev, password: e.target.value }))} 
                                                        placeholder="Enter password (min 6 characters)"
                                                        data-testid="create-user-password"
                                                    />
                                                    <Button 
                                                        type="button" 
                                                        variant="ghost" 
                                                        size="sm" 
                                                        className="absolute right-1 top-1/2 -translate-y-1/2 h-7 px-2"
                                                        onClick={() => setShowPassword(!showPassword)}
                                                    >
                                                        {showPassword ? "Hide" : "Show"}
                                                    </Button>
                                                </div>
                                                {createForm.password && createForm.password.length < 6 && (
                                                    <p className="text-xs text-red-400">Password must be at least 6 characters</p>
                                                )}
                                            </div>
                                        ) : (
                                            <p className="text-xs text-zinc-500">Password will be auto-generated and shown after creation</p>
                                        )}
                                    </div>
                                    
                                    <BrandSelector value={createForm.brand_scope_ids} onChange={(v) => setCreateForm(prev => ({ ...prev, brand_scope_ids: v }))} formSetter={setCreateForm} />
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={closeCreateDialog}>Cancel</Button>
                                    <Button 
                                        onClick={handleCreateUser} 
                                        disabled={saving || !createForm.email || !createForm.name || createForm.brand_scope_ids.length === 0 || (createForm.useManualPassword && (!createForm.password || createForm.password.length < 6))} 
                                        data-testid="confirm-create-btn"
                                    >
                                        {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Create User
                                    </Button>
                                </DialogFooter>
                            </>
                        )}
                    </DialogContent>
                </Dialog>

                {/* Edit User Dialog */}
                <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-lg">
                        <DialogHeader>
                            <DialogTitle>Edit User</DialogTitle>
                            <DialogDescription>Update role and brand access for {selectedUser?.name}</DialogDescription>
                        </DialogHeader>
                        <div className="space-y-6 py-4">
                            <div className="space-y-2">
                                <Label>Role</Label>
                                <Select value={editForm.role} onValueChange={(value) => setEditForm(prev => ({ ...prev, role: value }))}>
                                    <SelectTrigger data-testid="edit-role-select"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="super_admin">Super Admin</SelectItem>
                                        <SelectItem value="admin">Admin</SelectItem>
                                        <SelectItem value="viewer">Viewer</SelectItem>
                                    </SelectContent>
                                </Select>
                                {editForm.role === 'super_admin' && <p className="text-xs text-zinc-500">Super Admin has access to all brands</p>}
                            </div>
                            {editForm.role !== 'super_admin' && (
                                <BrandSelector value={editForm.brand_scope_ids} onChange={(v) => setEditForm(prev => ({ ...prev, brand_scope_ids: v }))} formSetter={setEditForm} />
                            )}
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>Cancel</Button>
                            <Button onClick={handleUpdateUser} disabled={saving || (editForm.role !== 'super_admin' && editForm.brand_scope_ids.length === 0)} data-testid="save-user-btn">
                                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Save Changes
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Delete Confirmation Dialog */}
                <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-md">
                        <DialogHeader><DialogTitle>Delete User</DialogTitle></DialogHeader>
                        <p className="text-zinc-400">Are you sure you want to <span className="text-red-400 font-medium">permanently delete</span> <span className="text-white font-medium">{selectedUser?.name}</span>?</p>
                        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-md mt-2">
                            <p className="text-sm text-red-400 flex items-start gap-2">
                                <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                <span>This will permanently remove the user and all their data. This action cannot be undone. Consider <strong>deactivating</strong> instead to preserve history.</span>
                            </p>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
                            <Button onClick={handleDelete} disabled={saving} className="bg-red-600 hover:bg-red-700" data-testid="confirm-delete-user-btn">
                                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Delete Permanently
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Deactivate Confirmation Dialog */}
                <Dialog open={deactivateDialogOpen} onOpenChange={setDeactivateDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-md">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <UserX className="h-5 w-5 text-amber-500" />
                                Deactivate User
                            </DialogTitle>
                        </DialogHeader>
                        <p className="text-zinc-400">
                            Are you sure you want to deactivate <span className="text-white font-medium">{selectedUser?.name}</span>?
                        </p>
                        <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-md mt-2">
                            <ul className="text-sm text-amber-400 space-y-1">
                                <li>• User will immediately lose access</li>
                                <li>• All activity history will remain intact</li>
                                <li>• User can be reactivated at any time</li>
                            </ul>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setDeactivateDialogOpen(false)}>Cancel</Button>
                            <Button onClick={handleDeactivate} disabled={saving} className="bg-amber-600 hover:bg-amber-700" data-testid="confirm-deactivate-user-btn">
                                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Deactivate
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Activate Confirmation Dialog */}
                <Dialog open={activateDialogOpen} onOpenChange={setActivateDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-md">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <UserCheck className="h-5 w-5 text-emerald-500" />
                                Activate User
                            </DialogTitle>
                        </DialogHeader>
                        <p className="text-zinc-400">
                            Are you sure you want to reactivate <span className="text-white font-medium">{selectedUser?.name}</span>?
                        </p>
                        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-md mt-2">
                            <ul className="text-sm text-emerald-400 space-y-1">
                                <li>• User will regain access based on their role</li>
                                <li>• Previous brand assignments will be restored</li>
                            </ul>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setActivateDialogOpen(false)}>Cancel</Button>
                            <Button onClick={handleActivate} disabled={saving} className="bg-emerald-600 hover:bg-emerald-700" data-testid="confirm-activate-user-btn">
                                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Activate
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </Layout>
    );
}
