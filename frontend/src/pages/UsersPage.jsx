import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { usersAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Trash2, Loader2, Users, Shield } from 'lucide-react';
import { ROLE_LABELS, formatDate } from '../lib/utils';

export default function UsersPage() {
    const { user: currentUser, isSuperAdmin } = useAuth();
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [selectedUser, setSelectedUser] = useState(null);

    useEffect(() => {
        loadUsers();
    }, []);

    const loadUsers = async () => {
        try {
            const res = await usersAPI.getAll();
            setUsers(res.data);
        } catch (err) {
            toast.error('Failed to load users');
        } finally {
            setLoading(false);
        }
    };

    const handleRoleChange = async (userId, newRole) => {
        try {
            await usersAPI.update(userId, newRole);
            toast.success('User role updated');
            loadUsers();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to update role');
        }
    };

    const handleDelete = async () => {
        if (!selectedUser) return;
        
        setSaving(true);
        try {
            await usersAPI.delete(selectedUser.id);
            toast.success('User deleted');
            setDeleteDialogOpen(false);
            setSelectedUser(null);
            loadUsers();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to delete user');
        } finally {
            setSaving(false);
        }
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

    if (!isSuperAdmin()) {
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
                                <TableHead>Joined</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {users.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={5} className="h-32 text-center">
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
                                            {user.id === currentUser?.id ? (
                                                <Badge variant="outline" className={getRoleBadgeClass(user.role)}>
                                                    <Shield className="h-3 w-3 mr-1" />
                                                    {ROLE_LABELS[user.role]}
                                                </Badge>
                                            ) : (
                                                <Select 
                                                    value={user.role} 
                                                    onValueChange={(value) => handleRoleChange(user.id, value)}
                                                >
                                                    <SelectTrigger 
                                                        className="w-[140px] h-8 bg-black border-border"
                                                        data-testid={`role-select-${user.id}`}
                                                    >
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="super_admin">Super Admin</SelectItem>
                                                        <SelectItem value="admin">Admin</SelectItem>
                                                        <SelectItem value="viewer">Viewer</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                            )}
                                        </TableCell>
                                        <TableCell className="text-zinc-500 text-sm">
                                            {formatDate(user.created_at)}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            {user.id !== currentUser?.id && (
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
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>

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
