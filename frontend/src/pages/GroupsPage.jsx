import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { groupsAPI, networksAPI, brandsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { 
    Plus, 
    Network, 
    Edit, 
    Trash2, 
    Loader2, 
    Eye,
    Globe,
    Tag,
    Filter
} from 'lucide-react';
import { formatDate } from '../lib/utils';

export default function GroupsPage() {
    const { canEdit } = useAuth();
    const [networks, setNetworks] = useState([]);
    const [brands, setBrands] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [selectedNetwork, setSelectedNetwork] = useState(null);
    const [form, setForm] = useState({ name: '', brand_id: '', description: '' });
    
    // Filter state
    const [filterBrand, setFilterBrand] = useState('all');

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            const [networksRes, brandsRes] = await Promise.all([
                networksAPI.getAll(),
                brandsAPI.getAll()
            ]);
            setNetworks(networksRes.data);
            setBrands(brandsRes.data);
        } catch (err) {
            console.error('Failed to load data:', err);
            toast.error('Failed to load networks');
        } finally {
            setLoading(false);
        }
    };

    const openCreateDialog = () => {
        setSelectedNetwork(null);
        setForm({ name: '', brand_id: '', description: '' });
        setDialogOpen(true);
    };

    const openEditDialog = (network, e) => {
        e.preventDefault();
        e.stopPropagation();
        setSelectedNetwork(network);
        setForm({ 
            name: network.name, 
            brand_id: network.brand_id || '',
            description: network.description || '' 
        });
        setDialogOpen(true);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.name) {
            toast.error('Network name is required');
            return;
        }
        if (!form.brand_id) {
            toast.error('Brand is required');
            return;
        }

        setSaving(true);
        try {
            if (selectedNetwork) {
                await networksAPI.update(selectedNetwork.id, form);
                toast.success('Network updated');
            } else {
                await networksAPI.create(form);
                toast.success('Network created');
            }
            setDialogOpen(false);
            loadData();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to save network');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!selectedNetwork) return;
        
        setSaving(true);
        try {
            await networksAPI.delete(selectedNetwork.id);
            toast.success('Network deleted');
            setDeleteDialogOpen(false);
            setSelectedNetwork(null);
            loadData();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to delete network');
        } finally {
            setSaving(false);
        }
    };

    const openDeleteDialog = (network, e) => {
        e.preventDefault();
        e.stopPropagation();
        setSelectedNetwork(network);
        setDeleteDialogOpen(true);
    };

    // Filter networks by brand
    const filteredNetworks = networks.filter(n => {
        if (filterBrand !== 'all' && n.brand_id !== filterBrand) return false;
        return true;
    });

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
            <div data-testid="groups-page">
                {/* Header */}
                <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="page-title">SEO Networks</h1>
                        <p className="page-subtitle">
                            {filteredNetworks.length} network{filteredNetworks.length !== 1 ? 's' : ''}
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        {/* Brand Filter */}
                        <Select value={filterBrand} onValueChange={setFilterBrand}>
                            <SelectTrigger className="w-[180px] bg-black border-border" data-testid="brand-filter">
                                <Filter className="h-4 w-4 mr-2 opacity-50" />
                                <SelectValue placeholder="All Brands" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Brands</SelectItem>
                                {brands.map(b => (
                                    <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        
                        {canEdit() && (
                            <Button 
                                onClick={openCreateDialog}
                                className="bg-white text-black hover:bg-zinc-200"
                                data-testid="add-network-btn"
                            >
                                <Plus className="h-4 w-4 mr-2" />
                                Add Network
                            </Button>
                        )}
                    </div>
                </div>

                {/* Networks Grid */}
                {filteredNetworks.length === 0 ? (
                    <div className="empty-state mt-16">
                        <Network className="empty-state-icon" />
                        <p className="empty-state-title">No networks yet</p>
                        <p className="empty-state-description">
                            Create your first network to organize domains into SEO structures
                        </p>
                        {canEdit() && (
                            <Button 
                                onClick={openCreateDialog}
                                className="mt-4 bg-white text-black hover:bg-zinc-200"
                            >
                                <Plus className="h-4 w-4 mr-2" />
                                Create Network
                            </Button>
                        )}
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="networks-grid">
                        {filteredNetworks.map((network, index) => (
                            <Link 
                                key={network.id} 
                                to={`/groups/${network.id}`}
                                className={`animate-fade-in stagger-${(index % 5) + 1}`}
                                data-testid={`network-card-${network.id}`}
                            >
                                <Card className="bg-card border-border card-hover h-full">
                                    <CardHeader className="pb-3">
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className="p-2 rounded-md bg-purple-500/10">
                                                    <Network className="h-5 w-5 text-purple-500" />
                                                </div>
                                                <div>
                                                    <CardTitle className="text-base">{network.name}</CardTitle>
                                                    {network.brand_name && (
                                                        <Badge variant="outline" className="mt-1 text-xs">
                                                            <Tag className="h-3 w-3 mr-1" />
                                                            {network.brand_name}
                                                        </Badge>
                                                    )}
                                                </div>
                                            </div>
                                            {canEdit() && (
                                                <div className="flex gap-1">
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        onClick={(e) => openEditDialog(network, e)}
                                                        className="h-8 w-8 hover:bg-white/5"
                                                        data-testid={`edit-network-${network.id}`}
                                                    >
                                                        <Edit className="h-4 w-4" />
                                                    </Button>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        onClick={(e) => openDeleteDialog(network, e)}
                                                        className="h-8 w-8 hover:bg-red-500/10 hover:text-red-500"
                                                        data-testid={`delete-network-${network.id}`}
                                                    >
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            )}
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        {network.description && (
                                            <p className="text-sm text-zinc-500 mb-4 line-clamp-2">
                                                {network.description}
                                            </p>
                                        )}
                                        <div className="flex items-center justify-between text-sm">
                                            <div className="flex items-center gap-2 text-zinc-400">
                                                <Globe className="h-4 w-4" />
                                                <span>{network.domain_count || 0} domain{network.domain_count !== 1 ? 's' : ''}</span>
                                            </div>
                                            <div className="flex items-center gap-1 text-blue-500">
                                                <Eye className="h-4 w-4" />
                                                <span>View</span>
                                            </div>
                                        </div>
                                        <div className="mt-3 pt-3 border-t border-border">
                                            <span className="text-xs text-zinc-600">
                                                Created {formatDate(network.created_at)}
                                            </span>
                                        </div>
                                    </CardContent>
                                </Card>
                            </Link>
                        ))}
                    </div>
                )}

                {/* Create/Edit Dialog */}
                <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-md">
                        <DialogHeader>
                            <DialogTitle>
                                {selectedNetwork ? 'Edit Network' : 'Create Network'}
                            </DialogTitle>
                            <DialogDescription>
                                {selectedNetwork 
                                    ? 'Update network details below.' 
                                    : 'Create a new SEO network. You can add domains to it later.'}
                            </DialogDescription>
                        </DialogHeader>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="space-y-2">
                                <Label>Network Name *</Label>
                                <Input
                                    value={form.name}
                                    onChange={(e) => setForm({...form, name: e.target.value})}
                                    placeholder="Main SEO Network"
                                    className="bg-black border-border"
                                    data-testid="network-name-input"
                                />
                            </div>
                            
                            <div className="space-y-2">
                                <Label>Brand *</Label>
                                <Select 
                                    value={form.brand_id} 
                                    onValueChange={(v) => setForm({...form, brand_id: v})}
                                >
                                    <SelectTrigger className="bg-black border-border" data-testid="network-brand-select">
                                        <SelectValue placeholder="Select brand..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {brands.map(b => (
                                            <SelectItem key={b.id} value={b.id}>
                                                {b.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="space-y-2">
                                <Label>Description</Label>
                                <Textarea
                                    value={form.description}
                                    onChange={(e) => setForm({...form, description: e.target.value})}
                                    placeholder="Optional description..."
                                    className="bg-black border-border resize-none"
                                    rows={3}
                                    data-testid="network-description-input"
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
                                    data-testid="save-network-btn"
                                >
                                    {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                    {selectedGroup ? 'Update' : 'Create'}
                                </Button>
                            </DialogFooter>
                        </form>
                    </DialogContent>
                </Dialog>

                {/* Delete Confirmation Dialog */}
                <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-md">
                        <DialogHeader>
                            <DialogTitle>Delete Network</DialogTitle>
                        </DialogHeader>
                        <p className="text-zinc-400">
                            Are you sure you want to delete <span className="text-white font-medium">{selectedGroup?.name}</span>?
                            All domains will be removed from this network (but not deleted).
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
                                data-testid="confirm-delete-network-btn"
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
