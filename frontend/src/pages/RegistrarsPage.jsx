import { useState, useEffect } from 'react';
import { Layout } from '@/components/Layout';
import { registrarsAPI } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Plus, Search, Pencil, Trash2, Globe, Building, ExternalLink } from 'lucide-react';

export default function RegistrarsPage() {
    const [registrars, setRegistrars] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [selectedRegistrar, setSelectedRegistrar] = useState(null);
    const [formData, setFormData] = useState({
        name: '',
        website: '',
        status: 'active',
        notes: ''
    });

    const user = JSON.parse(localStorage.getItem('seo_nexus_user') || '{}');
    const isSuperAdmin = user.role === 'super_admin';

    useEffect(() => {
        loadRegistrars();
    }, [search, statusFilter]);

    const loadRegistrars = async () => {
        try {
            setLoading(true);
            const params = {};
            if (search) params.search = search;
            if (statusFilter) params.status = statusFilter;
            
            const { data } = await registrarsAPI.getAll(params);
            setRegistrars(data);
        } catch (error) {
            console.error('Failed to load registrars:', error);
            toast.error('Failed to load registrars');
        } finally {
            setLoading(false);
        }
    };

    const handleAdd = () => {
        setSelectedRegistrar(null);
        setFormData({ name: '', website: '', status: 'active', notes: '' });
        setDialogOpen(true);
    };

    const handleEdit = (registrar) => {
        setSelectedRegistrar(registrar);
        setFormData({
            name: registrar.name || '',
            website: registrar.website || '',
            status: registrar.status || 'active',
            notes: registrar.notes || ''
        });
        setDialogOpen(true);
    };

    const handleDelete = (registrar) => {
        setSelectedRegistrar(registrar);
        setDeleteDialogOpen(true);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        if (!formData.name.trim()) {
            toast.error('Registrar name is required');
            return;
        }

        try {
            if (selectedRegistrar) {
                await registrarsAPI.update(selectedRegistrar.id, formData);
                toast.success('Registrar updated');
            } else {
                await registrarsAPI.create(formData);
                toast.success('Registrar created');
            }
            setDialogOpen(false);
            loadRegistrars();
        } catch (error) {
            const msg = error.response?.data?.detail || 'Failed to save registrar';
            toast.error(msg);
        }
    };

    const confirmDelete = async () => {
        try {
            await registrarsAPI.delete(selectedRegistrar.id);
            toast.success('Registrar deleted');
            setDeleteDialogOpen(false);
            loadRegistrars();
        } catch (error) {
            const msg = error.response?.data?.detail || 'Failed to delete registrar';
            toast.error(msg);
        }
    };

    return (
        <Layout>
            <div className="space-y-6" data-testid="registrars-page">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-semibold text-slate-900">Registrar Management</h1>
                        <p className="text-sm text-slate-500 mt-1">
                            Manage domain registrar master data
                        </p>
                    </div>
                    {isSuperAdmin && (
                        <Button 
                            onClick={handleAdd}
                            className="gap-2"
                            data-testid="add-registrar-btn"
                        >
                            <Plus className="h-4 w-4" />
                            Add Registrar
                        </Button>
                    )}
                </div>

                {/* Filters */}
                <Card>
                    <CardContent className="py-4">
                        <div className="flex gap-4 flex-wrap">
                            <div className="relative flex-1 min-w-[200px]">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                                <Input
                                    placeholder="Search registrars..."
                                    value={search}
                                    onChange={(e) => setSearch(e.target.value)}
                                    className="pl-10"
                                    data-testid="search-registrars"
                                />
                            </div>
                            <Select value={statusFilter} onValueChange={setStatusFilter}>
                                <SelectTrigger className="w-[160px]" data-testid="status-filter">
                                    <SelectValue placeholder="All Status" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All Status</SelectItem>
                                    <SelectItem value="active">Active</SelectItem>
                                    <SelectItem value="inactive">Inactive</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </CardContent>
                </Card>

                {/* Table */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Building className="h-5 w-5" />
                            Registrars ({registrars.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {loading ? (
                            <div className="text-center py-8 text-slate-500">Loading...</div>
                        ) : registrars.length === 0 ? (
                            <div className="text-center py-8 text-slate-500">
                                No registrars found. {isSuperAdmin && 'Click "Add Registrar" to create one.'}
                            </div>
                        ) : (
                            <Table data-testid="registrars-table">
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Name</TableHead>
                                        <TableHead>Website</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead className="text-center">Domains</TableHead>
                                        <TableHead>Notes</TableHead>
                                        {isSuperAdmin && <TableHead className="text-right">Actions</TableHead>}
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {registrars.map((registrar) => (
                                        <TableRow key={registrar.id} data-testid={`registrar-row-${registrar.id}`}>
                                            <TableCell className="font-medium">{registrar.name}</TableCell>
                                            <TableCell>
                                                {registrar.website ? (
                                                    <a 
                                                        href={registrar.website.startsWith('http') ? registrar.website : `https://${registrar.website}`}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="flex items-center gap-1 text-blue-600 hover:underline"
                                                    >
                                                        <Globe className="h-3 w-3" />
                                                        {registrar.website}
                                                        <ExternalLink className="h-3 w-3" />
                                                    </a>
                                                ) : (
                                                    <span className="text-slate-400">-</span>
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant={registrar.status === 'active' ? 'default' : 'secondary'}>
                                                    {registrar.status}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="text-center">
                                                <Badge variant="outline">{registrar.domain_count || 0}</Badge>
                                            </TableCell>
                                            <TableCell className="max-w-[200px] truncate">
                                                {registrar.notes || '-'}
                                            </TableCell>
                                            {isSuperAdmin && (
                                                <TableCell className="text-right">
                                                    <div className="flex justify-end gap-2">
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => handleEdit(registrar)}
                                                            data-testid={`edit-registrar-${registrar.id}`}
                                                        >
                                                            <Pencil className="h-4 w-4" />
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => handleDelete(registrar)}
                                                            disabled={registrar.domain_count > 0}
                                                            data-testid={`delete-registrar-${registrar.id}`}
                                                        >
                                                            <Trash2 className="h-4 w-4 text-red-500" />
                                                        </Button>
                                                    </div>
                                                </TableCell>
                                            )}
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        )}
                    </CardContent>
                </Card>

                {/* Add/Edit Dialog */}
                <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                    <DialogContent data-testid="registrar-dialog">
                        <DialogHeader>
                            <DialogTitle>
                                {selectedRegistrar ? 'Edit Registrar' : 'Add Registrar'}
                            </DialogTitle>
                            <DialogDescription>
                                {selectedRegistrar 
                                    ? 'Update the registrar information below.' 
                                    : 'Add a new domain registrar to the master data.'}
                            </DialogDescription>
                        </DialogHeader>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="name">Name *</Label>
                                <Input
                                    id="name"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    placeholder="e.g., GoDaddy, Namecheap"
                                    data-testid="registrar-name-input"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="website">Website</Label>
                                <Input
                                    id="website"
                                    value={formData.website}
                                    onChange={(e) => setFormData({ ...formData, website: e.target.value })}
                                    placeholder="https://www.example.com"
                                    data-testid="registrar-website-input"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="status">Status</Label>
                                <Select 
                                    value={formData.status} 
                                    onValueChange={(v) => setFormData({ ...formData, status: v })}
                                >
                                    <SelectTrigger data-testid="registrar-status-select">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="active">Active</SelectItem>
                                        <SelectItem value="inactive">Inactive</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="notes">Notes</Label>
                                <Textarea
                                    id="notes"
                                    value={formData.notes}
                                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                                    placeholder="Optional notes about this registrar"
                                    data-testid="registrar-notes-input"
                                />
                            </div>
                            <DialogFooter>
                                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                                    Cancel
                                </Button>
                                <Button type="submit" data-testid="registrar-submit-btn">
                                    {selectedRegistrar ? 'Update' : 'Create'}
                                </Button>
                            </DialogFooter>
                        </form>
                    </DialogContent>
                </Dialog>

                {/* Delete Confirmation Dialog */}
                <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                    <DialogContent data-testid="delete-registrar-dialog">
                        <DialogHeader>
                            <DialogTitle>Delete Registrar</DialogTitle>
                            <DialogDescription>
                                Are you sure you want to delete "{selectedRegistrar?.name}"? 
                                This action cannot be undone.
                            </DialogDescription>
                        </DialogHeader>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
                                Cancel
                            </Button>
                            <Button 
                                variant="destructive" 
                                onClick={confirmDelete}
                                data-testid="confirm-delete-registrar"
                            >
                                Delete
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </Layout>
    );
}
