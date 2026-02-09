import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { activityTypesAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { 
    Plus, 
    Trash2, 
    Settings2, 
    Loader2,
    AlertTriangle,
    Tag,
    Hash,
    FileText
} from 'lucide-react';

export default function ActivityTypesPage() {
    const { user } = useAuth();
    const [activityTypes, setActivityTypes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [selectedType, setSelectedType] = useState(null);
    const [saving, setSaving] = useState(false);
    const [deleting, setDeleting] = useState(false);
    
    // Form state
    const [form, setForm] = useState({
        name: '',
        description: ''
    });

    const isSuperAdmin = user?.role === 'super_admin';

    useEffect(() => {
        loadActivityTypes();
    }, []);

    const loadActivityTypes = async () => {
        setLoading(true);
        try {
            const response = await activityTypesAPI.getAll();
            setActivityTypes(response.data);
        } catch (err) {
            console.error('Failed to load activity types:', err);
            toast.error('Failed to load activity types');
        } finally {
            setLoading(false);
        }
    };

    const openCreateDialog = () => {
        setSelectedType(null);
        setForm({ name: '', description: '' });
        setDialogOpen(true);
    };

    const openDeleteDialog = (type) => {
        setSelectedType(type);
        setDeleteDialogOpen(true);
    };

    const handleCreate = async () => {
        if (!form.name.trim()) {
            toast.error('Name is required');
            return;
        }

        setSaving(true);
        try {
            await activityTypesAPI.create({
                name: form.name.trim(),
                description: form.description.trim()
            });
            toast.success('Activity type created');
            setDialogOpen(false);
            loadActivityTypes();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to create activity type');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!selectedType) return;

        setDeleting(true);
        try {
            await activityTypesAPI.delete(selectedType.id);
            toast.success('Activity type deleted');
            setDeleteDialogOpen(false);
            loadActivityTypes();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to delete activity type');
        } finally {
            setDeleting(false);
        }
    };

    if (!isSuperAdmin) {
        return (
            <Layout>
                <div className="flex flex-col items-center justify-center h-64 text-zinc-500">
                    <AlertTriangle className="h-12 w-12 mb-4 text-amber-500" />
                    <p className="text-lg">Access Denied</p>
                    <p className="text-sm">Only Super Admins can manage activity types</p>
                </div>
            </Layout>
        );
    }

    return (
        <Layout>
            <div className="space-y-6" data-testid="activity-types-page">
                {/* Header */}
                <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="page-title flex items-center gap-3">
                            <Settings2 className="h-7 w-7 text-emerald-500" />
                            Optimization Activity Types
                        </h1>
                        <p className="page-subtitle">
                            Manage the types of SEO optimization activities
                        </p>
                    </div>
                    <Button onClick={openCreateDialog} className="gap-2" data-testid="add-activity-type-btn">
                        <Plus className="h-4 w-4" />
                        Add Activity Type
                    </Button>
                </div>

                {/* Activity Types Table */}
                <Card className="bg-card border-border">
                    <CardHeader>
                        <CardTitle className="text-lg">Activity Types</CardTitle>
                        <CardDescription>
                            These types are used when creating SEO optimizations
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {loading ? (
                            <div className="space-y-3">
                                {[1, 2, 3, 4, 5].map(i => (
                                    <Skeleton key={i} className="h-12 w-full" />
                                ))}
                            </div>
                        ) : activityTypes.length > 0 ? (
                            <Table data-testid="activity-types-table">
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Name</TableHead>
                                        <TableHead>Description</TableHead>
                                        <TableHead className="text-center">Usage Count</TableHead>
                                        <TableHead className="text-center">Default</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {activityTypes.map((type) => (
                                        <TableRow key={type.id} className="table-row-hover">
                                            <TableCell>
                                                <div className="flex items-center gap-2">
                                                    <Tag className="h-4 w-4 text-zinc-500" />
                                                    <span className="font-medium text-white">{type.name}</span>
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-zinc-400 max-w-xs truncate">
                                                {type.description || '-'}
                                            </TableCell>
                                            <TableCell className="text-center">
                                                <Badge variant="secondary" className="font-mono">
                                                    {type.usage_count || 0}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="text-center">
                                                {type.is_default ? (
                                                    <Badge className="bg-blue-500/20 text-blue-400">Default</Badge>
                                                ) : (
                                                    <span className="text-zinc-600">-</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-right">
                                                {!type.is_default ? (
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        onClick={() => openDeleteDialog(type)}
                                                        className="h-8 w-8 hover:bg-red-500/10 hover:text-red-400"
                                                        data-testid={`delete-type-${type.id}`}
                                                    >
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
                                                ) : (
                                                    <span className="text-xs text-zinc-600">Protected</span>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        ) : (
                            <div className="text-center py-12 text-zinc-500">
                                <Tag className="h-12 w-12 mx-auto mb-4 opacity-50" />
                                <p>No activity types found</p>
                                <Button variant="outline" onClick={openCreateDialog} className="mt-4 gap-2">
                                    <Plus className="h-4 w-4" />
                                    Create First Activity Type
                                </Button>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Info Card */}
                <Card className="bg-blue-950/20 border-blue-900/30">
                    <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                            <FileText className="h-5 w-5 text-blue-400 mt-0.5" />
                            <div className="text-sm text-blue-300/80">
                                <p className="font-medium text-blue-300 mb-1">About Activity Types</p>
                                <ul className="list-disc list-inside space-y-1 text-blue-300/70">
                                    <li>Activity types categorize SEO optimization work</li>
                                    <li>Default types cannot be deleted (Backlink, On-Page, Technical SEO, Content, Other)</li>
                                    <li>Usage count shows how many optimizations use each type</li>
                                    <li>Types with existing usage cannot be deleted</li>
                                </ul>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Create Dialog */}
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogContent className="bg-card border-border">
                    <DialogHeader>
                        <DialogTitle>Add Activity Type</DialogTitle>
                        <DialogDescription>
                            Create a new type for categorizing SEO optimizations
                        </DialogDescription>
                    </DialogHeader>
                    
                    <div className="space-y-4 py-4">
                        <div>
                            <Label>Name *</Label>
                            <Input
                                value={form.name}
                                onChange={(e) => setForm(prev => ({ ...prev, name: e.target.value }))}
                                placeholder="e.g., Link Reclamation"
                                className="mt-1 bg-black border-border"
                            />
                        </div>
                        <div>
                            <Label>Description</Label>
                            <Textarea
                                value={form.description}
                                onChange={(e) => setForm(prev => ({ ...prev, description: e.target.value }))}
                                placeholder="Brief description of this activity type..."
                                className="mt-1 bg-black border-border min-h-[80px]"
                            />
                        </div>
                    </div>
                    
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleCreate} disabled={saving || !form.name.trim()}>
                            {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Create
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Confirmation Dialog */}
            <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <DialogContent className="bg-card border-border">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2 text-red-400">
                            <AlertTriangle className="h-5 w-5" />
                            Delete Activity Type
                        </DialogTitle>
                        <DialogDescription>
                            Are you sure you want to delete "{selectedType?.name}"?
                        </DialogDescription>
                    </DialogHeader>
                    
                    <div className="py-4">
                        {selectedType?.usage_count > 0 ? (
                            <div className="p-4 rounded-lg bg-red-950/30 border border-red-900/50 text-sm text-red-300">
                                <p className="font-medium mb-1">Cannot delete this activity type</p>
                                <p className="text-red-300/70">
                                    This type is used by {selectedType.usage_count} optimization(s). 
                                    You must reassign or delete those optimizations first.
                                </p>
                            </div>
                        ) : (
                            <p className="text-zinc-400 text-sm">
                                This action cannot be undone. The activity type will be permanently removed.
                            </p>
                        )}
                    </div>
                    
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
                        <Button 
                            variant="destructive" 
                            onClick={handleDelete} 
                            disabled={deleting || (selectedType?.usage_count > 0)}
                        >
                            {deleting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Delete
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Layout>
    );
}
