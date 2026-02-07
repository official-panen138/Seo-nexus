import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { brandsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { toast } from 'sonner';
import { Plus, Edit, Trash2, Loader2, Tag } from 'lucide-react';
import { formatDate } from '../lib/utils';

export default function BrandsPage() {
    const { isSuperAdmin } = useAuth();
    const [brands, setBrands] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [selectedBrand, setSelectedBrand] = useState(null);
    const [form, setForm] = useState({ name: '', description: '' });

    useEffect(() => {
        loadBrands();
    }, []);

    const loadBrands = async () => {
        try {
            const res = await brandsAPI.getAll();
            setBrands(res.data);
        } catch (err) {
            toast.error('Failed to load brands');
        } finally {
            setLoading(false);
        }
    };

    const openCreateDialog = () => {
        setSelectedBrand(null);
        setForm({ name: '', description: '' });
        setDialogOpen(true);
    };

    const openEditDialog = (brand) => {
        setSelectedBrand(brand);
        setForm({ name: brand.name, description: brand.description || '' });
        setDialogOpen(true);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.name) {
            toast.error('Brand name is required');
            return;
        }

        setSaving(true);
        try {
            if (selectedBrand) {
                await brandsAPI.update(selectedBrand.id, form);
                toast.success('Brand updated');
            } else {
                await brandsAPI.create(form);
                toast.success('Brand created');
            }
            setDialogOpen(false);
            loadBrands();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to save brand');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!selectedBrand) return;
        
        setSaving(true);
        try {
            await brandsAPI.delete(selectedBrand.id);
            toast.success('Brand deleted');
            setDeleteDialogOpen(false);
            setSelectedBrand(null);
            loadBrands();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to delete brand');
        } finally {
            setSaving(false);
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
            <div data-testid="brands-page">
                {/* Header */}
                <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="page-title">Brands</h1>
                        <p className="page-subtitle">
                            {brands.length} brand{brands.length !== 1 ? 's' : ''} configured
                        </p>
                    </div>
                    <Button 
                        onClick={openCreateDialog}
                        className="bg-white text-black hover:bg-zinc-200"
                        data-testid="add-brand-btn"
                    >
                        <Plus className="h-4 w-4 mr-2" />
                        Add Brand
                    </Button>
                </div>

                {/* Brands Table */}
                <div className="data-table-container" data-testid="brands-table">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Brand Name</TableHead>
                                <TableHead>Description</TableHead>
                                <TableHead>Created</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {brands.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={4} className="h-32 text-center">
                                        <div className="empty-state py-8">
                                            <Tag className="empty-state-icon mx-auto" />
                                            <p className="empty-state-title">No brands yet</p>
                                            <p className="empty-state-description">
                                                Create your first brand to categorize domains
                                            </p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                brands.map((brand) => (
                                    <TableRow key={brand.id} className="table-row-hover" data-testid={`brand-row-${brand.id}`}>
                                        <TableCell>
                                            <div className="flex items-center gap-3">
                                                <div className="p-1.5 rounded bg-amber-500/10">
                                                    <Tag className="h-4 w-4 text-amber-500" />
                                                </div>
                                                <span className="font-medium">{brand.name}</span>
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-zinc-400 max-w-md truncate">
                                            {brand.description || '-'}
                                        </TableCell>
                                        <TableCell className="text-zinc-500 text-sm">
                                            {formatDate(brand.created_at)}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex items-center justify-end gap-1">
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => openEditDialog(brand)}
                                                    className="h-8 w-8 hover:bg-white/5"
                                                    data-testid={`edit-brand-${brand.id}`}
                                                >
                                                    <Edit className="h-4 w-4" />
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => {
                                                        setSelectedBrand(brand);
                                                        setDeleteDialogOpen(true);
                                                    }}
                                                    className="h-8 w-8 hover:bg-red-500/10 hover:text-red-500"
                                                    data-testid={`delete-brand-${brand.id}`}
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>

                {/* Create/Edit Dialog */}
                <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-md">
                        <DialogHeader>
                            <DialogTitle>
                                {selectedBrand ? 'Edit Brand' : 'Create Brand'}
                            </DialogTitle>
                        </DialogHeader>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="space-y-2">
                                <Label>Brand Name *</Label>
                                <Input
                                    value={form.name}
                                    onChange={(e) => setForm({...form, name: e.target.value})}
                                    placeholder="e.g., Panen138"
                                    className="bg-black border-border"
                                    data-testid="brand-name-input"
                                />
                            </div>

                            <div className="space-y-2">
                                <Label>Description</Label>
                                <Textarea
                                    value={form.description}
                                    onChange={(e) => setForm({...form, description: e.target.value})}
                                    placeholder="Optional description..."
                                    className="bg-black border-border resize-none"
                                    rows={3}
                                    data-testid="brand-description-input"
                                />
                            </div>

                            <DialogFooter>
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => setDialogOpen(false)}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    type="submit"
                                    disabled={saving}
                                    className="bg-white text-black hover:bg-zinc-200"
                                    data-testid="save-brand-btn"
                                >
                                    {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                    {selectedBrand ? 'Update' : 'Create'}
                                </Button>
                            </DialogFooter>
                        </form>
                    </DialogContent>
                </Dialog>

                {/* Delete Confirmation Dialog */}
                <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-md">
                        <DialogHeader>
                            <DialogTitle>Delete Brand</DialogTitle>
                        </DialogHeader>
                        <p className="text-zinc-400">
                            Are you sure you want to delete <span className="text-white font-medium">{selectedBrand?.name}</span>?
                            This action cannot be undone.
                        </p>
                        <p className="text-sm text-amber-500">
                            Note: Brands with associated domains cannot be deleted.
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
                                data-testid="confirm-delete-brand-btn"
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
