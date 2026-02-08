import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { categoriesAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { toast } from 'sonner';
import { Plus, Edit, Trash2, Loader2, Folder } from 'lucide-react';
import { formatDate } from '../lib/utils';

export default function CategoriesPage() {
    const { isSuperAdmin } = useAuth();
    const [categories, setCategories] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [selectedCategory, setSelectedCategory] = useState(null);
    const [form, setForm] = useState({ name: '', description: '' });

    useEffect(() => {
        loadCategories();
    }, []);

    const loadCategories = async () => {
        try {
            const res = await categoriesAPI.getAll();
            setCategories(res.data);
        } catch (err) {
            toast.error('Failed to load categories');
        } finally {
            setLoading(false);
        }
    };

    const openCreateDialog = () => {
        setSelectedCategory(null);
        setForm({ name: '', description: '' });
        setDialogOpen(true);
    };

    const openEditDialog = (category) => {
        setSelectedCategory(category);
        setForm({ name: category.name, description: category.description || '' });
        setDialogOpen(true);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.name) {
            toast.error('Category name is required');
            return;
        }

        setSaving(true);
        try {
            if (selectedCategory) {
                await categoriesAPI.update(selectedCategory.id, form);
                toast.success('Category updated');
            } else {
                await categoriesAPI.create(form);
                toast.success('Category created');
            }
            setDialogOpen(false);
            loadCategories();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to save category');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!selectedCategory) return;
        
        setSaving(true);
        try {
            await categoriesAPI.delete(selectedCategory.id);
            toast.success('Category deleted');
            setDeleteDialogOpen(false);
            setSelectedCategory(null);
            loadCategories();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to delete category');
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
            <div data-testid="categories-page">
                {/* Header */}
                <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="page-title">Domain Categories</h1>
                        <p className="page-subtitle">
                            {categories.length} categor{categories.length !== 1 ? 'ies' : 'y'} configured
                        </p>
                    </div>
                    <Button 
                        onClick={openCreateDialog}
                        className="bg-white text-black hover:bg-zinc-200"
                        data-testid="add-category-btn"
                    >
                        <Plus className="h-4 w-4 mr-2" />
                        Add Category
                    </Button>
                </div>

                {/* Categories Table */}
                <div className="data-table-container" data-testid="categories-table">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Category Name</TableHead>
                                <TableHead>Description</TableHead>
                                <TableHead>Created</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {categories.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={4} className="h-32 text-center">
                                        <div className="empty-state py-8">
                                            <Folder className="empty-state-icon mx-auto" />
                                            <p className="empty-state-title">No categories yet</p>
                                            <p className="empty-state-description">
                                                Create categories to organize domains
                                            </p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                categories.map((category) => (
                                    <TableRow key={category.id} className="table-row-hover" data-testid={`category-row-${category.id}`}>
                                        <TableCell>
                                            <div className="flex items-center gap-3">
                                                <div className="p-1.5 rounded bg-teal-500/10">
                                                    <Folder className="h-4 w-4 text-teal-500" />
                                                </div>
                                                <span className="font-medium">{category.name}</span>
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-zinc-400 max-w-md truncate">
                                            {category.description || '-'}
                                        </TableCell>
                                        <TableCell className="text-zinc-500 text-sm">
                                            {formatDate(category.created_at)}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex items-center justify-end gap-1">
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => openEditDialog(category)}
                                                    className="h-8 w-8 hover:bg-white/5"
                                                    data-testid={`edit-category-${category.id}`}
                                                >
                                                    <Edit className="h-4 w-4" />
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => {
                                                        setSelectedCategory(category);
                                                        setDeleteDialogOpen(true);
                                                    }}
                                                    className="h-8 w-8 hover:bg-red-500/10 hover:text-red-500"
                                                    data-testid={`delete-category-${category.id}`}
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
                                {selectedCategory ? 'Edit Category' : 'Create Category'}
                            </DialogTitle>
                        </DialogHeader>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="space-y-2">
                                <Label>Category Name *</Label>
                                <Input
                                    value={form.name}
                                    onChange={(e) => setForm({...form, name: e.target.value})}
                                    placeholder="e.g., Money Site"
                                    className="bg-black border-border"
                                    data-testid="category-name-input"
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
                                    data-testid="category-description-input"
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
                                    data-testid="save-category-btn"
                                >
                                    {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                    {selectedCategory ? 'Update' : 'Create'}
                                </Button>
                            </DialogFooter>
                        </form>
                    </DialogContent>
                </Dialog>

                {/* Delete Confirmation Dialog */}
                <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-md">
                        <DialogHeader>
                            <DialogTitle>Delete Category</DialogTitle>
                        </DialogHeader>
                        <p className="text-zinc-400">
                            Are you sure you want to delete <span className="text-white font-medium">{selectedCategory?.name}</span>?
                            Domains will have their category unset but will not be deleted.
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
                                data-testid="confirm-delete-category-btn"
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
