import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { assetDomainsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Loader2, Plus, Edit, Trash2, ShieldAlert } from 'lucide-react';

export default function QuarantineCategoriesPage() {
    const { isSuperAdmin } = useAuth();
    const [loading, setLoading] = useState(true);

    // Quarantine Categories state
    const [quarantineCategories, setQuarantineCategories] = useState([]);
    const [loadingCategories, setLoadingCategories] = useState(false);
    const [savingCategory, setSavingCategory] = useState(false);
    const [editingCategory, setEditingCategory] = useState(null);
    const [newCategory, setNewCategory] = useState({ value: '', label: '' });
    const [showAddCategory, setShowAddCategory] = useState(false);

    useEffect(() => {
        loadQuarantineCategories();
    }, []);

    // Load Quarantine Categories
    const loadQuarantineCategories = async () => {
        setLoadingCategories(true);
        try {
            const res = await assetDomainsAPI.getQuarantineCategories();
            setQuarantineCategories(res.data?.categories || []);
        } catch (err) {
            console.error('Failed to load quarantine categories:', err);
            toast.error('Failed to load quarantine categories');
        } finally {
            setLoadingCategories(false);
            setLoading(false);
        }
    };

    // Create Quarantine Category
    const handleCreateCategory = async () => {
        if (!newCategory.value.trim() || !newCategory.label.trim()) {
            toast.error('Both value and label are required');
            return;
        }
        setSavingCategory(true);
        try {
            await assetDomainsAPI.createQuarantineCategory({
                value: newCategory.value.trim(),
                label: newCategory.label.trim()
            });
            toast.success('Quarantine category created');
            setNewCategory({ value: '', label: '' });
            setShowAddCategory(false);
            loadQuarantineCategories();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to create category');
        } finally {
            setSavingCategory(false);
        }
    };

    // Update Quarantine Category
    const handleUpdateCategory = async () => {
        if (!editingCategory) return;
        setSavingCategory(true);
        try {
            await assetDomainsAPI.updateQuarantineCategory(editingCategory.id, {
                value: editingCategory.value,
                label: editingCategory.label
            });
            toast.success('Quarantine category updated');
            setEditingCategory(null);
            loadQuarantineCategories();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to update category');
        } finally {
            setSavingCategory(false);
        }
    };

    // Delete Quarantine Category
    const handleDeleteCategory = async (categoryId) => {
        if (!confirm('Are you sure you want to delete this category?')) return;
        try {
            await assetDomainsAPI.deleteQuarantineCategory(categoryId);
            toast.success('Quarantine category deleted');
            loadQuarantineCategories();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to delete category');
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
            <div data-testid="quarantine-categories-page">
                {/* Header */}
                <div className="page-header">
                    <div className="flex items-center gap-3">
                        <ShieldAlert className="h-7 w-7 text-orange-400" />
                        <div>
                            <h1 className="page-title">Quarantine Categories</h1>
                            <p className="page-subtitle">Manage quarantine reasons for domains</p>
                        </div>
                    </div>
                </div>

                <div className="max-w-3xl">
                    <Card className="bg-card border-border">
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="text-lg">Category Management</CardTitle>
                                    <CardDescription>
                                        Define and manage quarantine reasons that can be assigned to domains.
                                    </CardDescription>
                                </div>
                                {isSuperAdmin() && (
                                    <Button 
                                        onClick={() => setShowAddCategory(true)}
                                        className="flex items-center gap-2"
                                        data-testid="add-category-btn"
                                    >
                                        <Plus className="h-4 w-4" />
                                        Add Category
                                    </Button>
                                )}
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {/* Add Category Form */}
                            {showAddCategory && (
                                <div className="p-4 bg-zinc-900/50 border border-border rounded-lg space-y-4">
                                    <h4 className="font-medium text-sm">Add New Category</h4>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>Value (slug)</Label>
                                            <Input
                                                value={newCategory.value}
                                                onChange={(e) => setNewCategory({...newCategory, value: e.target.value.toLowerCase().replace(/\s+/g, '_')})}
                                                placeholder="e.g., hacked_site"
                                                className="bg-black border-border"
                                                data-testid="new-category-value"
                                            />
                                            <p className="text-xs text-zinc-500">Lowercase, no spaces (auto-converted)</p>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Display Label</Label>
                                            <Input
                                                value={newCategory.label}
                                                onChange={(e) => setNewCategory({...newCategory, label: e.target.value})}
                                                placeholder="e.g., Hacked Site"
                                                className="bg-black border-border"
                                                data-testid="new-category-label"
                                            />
                                        </div>
                                    </div>
                                    <div className="flex justify-end gap-2">
                                        <Button
                                            variant="ghost"
                                            onClick={() => {
                                                setShowAddCategory(false);
                                                setNewCategory({ value: '', label: '' });
                                            }}
                                        >
                                            Cancel
                                        </Button>
                                        <Button
                                            onClick={handleCreateCategory}
                                            disabled={savingCategory || !newCategory.value || !newCategory.label}
                                            data-testid="save-new-category-btn"
                                        >
                                            {savingCategory ? (
                                                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                            ) : null}
                                            Create Category
                                        </Button>
                                    </div>
                                </div>
                            )}

                            {/* Categories List */}
                            {loadingCategories ? (
                                <div className="flex justify-center py-8">
                                    <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {quarantineCategories.map((category) => (
                                        <div 
                                            key={category.id} 
                                            className="flex items-center justify-between p-3 bg-zinc-900/30 border border-border rounded-lg"
                                            data-testid={`category-row-${category.value}`}
                                        >
                                            {editingCategory?.id === category.id ? (
                                                // Edit mode
                                                <div className="flex items-center gap-4 flex-1">
                                                    <Input
                                                        value={editingCategory.value}
                                                        onChange={(e) => setEditingCategory({...editingCategory, value: e.target.value.toLowerCase().replace(/\s+/g, '_')})}
                                                        className="bg-black border-border w-40"
                                                        data-testid={`edit-category-value-${category.value}`}
                                                    />
                                                    <Input
                                                        value={editingCategory.label}
                                                        onChange={(e) => setEditingCategory({...editingCategory, label: e.target.value})}
                                                        className="bg-black border-border flex-1"
                                                        data-testid={`edit-category-label-${category.value}`}
                                                    />
                                                    <div className="flex items-center gap-2">
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => setEditingCategory(null)}
                                                        >
                                                            Cancel
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            onClick={handleUpdateCategory}
                                                            disabled={savingCategory}
                                                            data-testid={`save-category-btn-${category.value}`}
                                                        >
                                                            {savingCategory ? (
                                                                <Loader2 className="h-4 w-4 animate-spin" />
                                                            ) : 'Save'}
                                                        </Button>
                                                    </div>
                                                </div>
                                            ) : (
                                                // View mode
                                                <>
                                                    <div className="flex items-center gap-4">
                                                        <code className="text-xs bg-zinc-800 px-2 py-1 rounded text-zinc-400">
                                                            {category.value}
                                                        </code>
                                                        <span className="text-sm">{category.label}</span>
                                                        {category.is_default && (
                                                            <Badge variant="outline" className="text-xs text-zinc-500">
                                                                Default
                                                            </Badge>
                                                        )}
                                                    </div>
                                                    {isSuperAdmin() && (
                                                        <div className="flex items-center gap-2">
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                onClick={() => setEditingCategory({...category})}
                                                                data-testid={`edit-category-btn-${category.value}`}
                                                            >
                                                                <Edit className="h-4 w-4" />
                                                            </Button>
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                className="text-red-400 hover:text-red-300 hover:bg-red-900/20"
                                                                onClick={() => handleDeleteCategory(category.id)}
                                                                data-testid={`delete-category-btn-${category.value}`}
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                            </Button>
                                                        </div>
                                                    )}
                                                </>
                                            )}
                                        </div>
                                    ))}
                                    
                                    {quarantineCategories.length === 0 && (
                                        <div className="text-center py-8 text-zinc-500">
                                            No quarantine categories found. Click "Add Category" to create one.
                                        </div>
                                    )}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>
            </div>
        </Layout>
    );
}
