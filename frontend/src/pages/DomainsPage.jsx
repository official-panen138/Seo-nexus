import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../lib/auth';
import { domainsAPI, brandsAPI, groupsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { DomainDetailPanel } from '../components/DomainDetailPanel';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { toast } from 'sonner';
import { 
    Plus, 
    Search, 
    Edit, 
    Trash2, 
    Loader2, 
    Globe,
    ExternalLink,
    Filter,
    X,
    Eye
} from 'lucide-react';
import { 
    TIER_LABELS, 
    STATUS_LABELS, 
    INDEX_STATUS_LABELS, 
    getTierBadgeClass, 
    formatDate,
    debounce
} from '../lib/utils';

const INITIAL_FORM = {
    domain_name: '',
    brand_id: '',
    domain_status: 'canonical',
    index_status: 'index',
    tier_level: 'tier_5',
    group_id: '',
    parent_domain_id: '',
    notes: ''
};

export default function DomainsPage() {
    const { canEdit } = useAuth();
    const [domains, setDomains] = useState([]);
    const [brands, setBrands] = useState([]);
    const [groups, setGroups] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [selectedDomain, setSelectedDomain] = useState(null);
    const [form, setForm] = useState(INITIAL_FORM);
    
    // Detail panel state
    const [detailPanelOpen, setDetailPanelOpen] = useState(false);
    const [detailDomain, setDetailDomain] = useState(null);
    
    // Filters
    const [searchQuery, setSearchQuery] = useState('');
    const [filterBrand, setFilterBrand] = useState('all');
    const [filterStatus, setFilterStatus] = useState('all');
    const [filterIndex, setFilterIndex] = useState('all');
    const [filterTier, setFilterTier] = useState('all');
    const [filterGroup, setFilterGroup] = useState('all');
    const [showFilters, setShowFilters] = useState(false);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            const [domainsRes, brandsRes, groupsRes] = await Promise.all([
                domainsAPI.getAll(),
                brandsAPI.getAll(),
                groupsAPI.getAll()
            ]);
            setDomains(domainsRes.data);
            setBrands(brandsRes.data);
            setGroups(groupsRes.data);
        } catch (err) {
            toast.error('Failed to load domains');
        } finally {
            setLoading(false);
        }
    };

    // Filtered domains
    const filteredDomains = useMemo(() => {
        return domains.filter(domain => {
            if (searchQuery && !domain.domain_name.toLowerCase().includes(searchQuery.toLowerCase())) {
                return false;
            }
            if (filterBrand !== 'all' && domain.brand_id !== filterBrand) return false;
            if (filterStatus !== 'all' && domain.domain_status !== filterStatus) return false;
            if (filterIndex !== 'all' && domain.index_status !== filterIndex) return false;
            if (filterTier !== 'all' && domain.tier_level !== filterTier) return false;
            if (filterGroup !== 'all') {
                if (filterGroup === 'none' && domain.group_id) return false;
                if (filterGroup !== 'none' && domain.group_id !== filterGroup) return false;
            }
            return true;
        });
    }, [domains, searchQuery, filterBrand, filterStatus, filterIndex, filterTier, filterGroup]);

    // Potential parent domains (same group, higher tier)
    const parentDomainOptions = useMemo(() => {
        if (!form.group_id || !form.tier_level) return [];
        
        const currentTierValue = {
            'tier_5': 5, 'tier_4': 4, 'tier_3': 3, 'tier_2': 2, 'tier_1': 1, 'lp_money_site': 0
        }[form.tier_level];
        
        return domains.filter(d => {
            if (d.id === selectedDomain?.id) return false;
            if (d.group_id !== form.group_id) return false;
            const dTierValue = {
                'tier_5': 5, 'tier_4': 4, 'tier_3': 3, 'tier_2': 2, 'tier_1': 1, 'lp_money_site': 0
            }[d.tier_level];
            return dTierValue < currentTierValue;
        });
    }, [domains, form.group_id, form.tier_level, selectedDomain]);

    const handleSearchChange = debounce((value) => {
        setSearchQuery(value);
    }, 300);

    const openCreateDialog = () => {
        setSelectedDomain(null);
        setForm(INITIAL_FORM);
        setDialogOpen(true);
    };

    const openEditDialog = (domain) => {
        setSelectedDomain(domain);
        setForm({
            domain_name: domain.domain_name,
            brand_id: domain.brand_id,
            domain_status: domain.domain_status,
            index_status: domain.index_status,
            tier_level: domain.tier_level,
            group_id: domain.group_id || '',
            parent_domain_id: domain.parent_domain_id || '',
            notes: domain.notes || ''
        });
        setDialogOpen(true);
    };

    const openDetailPanel = (domain) => {
        setDetailDomain(domain);
        setDetailPanelOpen(true);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.domain_name || !form.brand_id) {
            toast.error('Domain name and brand are required');
            return;
        }

        setSaving(true);
        try {
            const payload = {
                ...form,
                group_id: form.group_id || null,
                parent_domain_id: form.parent_domain_id || null
            };

            if (selectedDomain) {
                await domainsAPI.update(selectedDomain.id, payload);
                toast.success('Domain updated');
            } else {
                await domainsAPI.create(payload);
                toast.success('Domain created');
            }
            setDialogOpen(false);
            loadData();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to save domain');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!selectedDomain) return;
        
        setSaving(true);
        try {
            await domainsAPI.delete(selectedDomain.id);
            toast.success('Domain deleted');
            setDeleteDialogOpen(false);
            setSelectedDomain(null);
            loadData();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to delete domain');
        } finally {
            setSaving(false);
        }
    };

    const clearFilters = () => {
        setSearchQuery('');
        setFilterBrand('all');
        setFilterStatus('all');
        setFilterIndex('all');
        setFilterTier('all');
        setFilterGroup('all');
    };

    const hasActiveFilters = filterBrand !== 'all' || filterStatus !== 'all' || 
        filterIndex !== 'all' || filterTier !== 'all' || filterGroup !== 'all';

    // Refresh detail panel when data updates
    const handleDetailUpdate = () => {
        loadData();
        // Also refresh the detail domain data
        if (detailDomain) {
            domainsAPI.getOne(detailDomain.id).then(res => {
                setDetailDomain(res.data);
            }).catch(() => {
                setDetailPanelOpen(false);
            });
        }
    };

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
            <div data-testid="domains-page">
                {/* Header */}
                <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="page-title">Domains</h1>
                        <p className="page-subtitle">
                            {filteredDomains.length} of {domains.length} domains
                        </p>
                    </div>
                    {canEdit() && (
                        <Button 
                            onClick={openCreateDialog}
                            className="bg-white text-black hover:bg-zinc-200"
                            data-testid="add-domain-btn"
                        >
                            <Plus className="h-4 w-4 mr-2" />
                            Add Domain
                        </Button>
                    )}
                </div>

                {/* Search and Filters */}
                <div className="mb-6 space-y-4">
                    <div className="flex flex-col sm:flex-row gap-3">
                        <div className="relative flex-1">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                            <Input
                                placeholder="Search domains..."
                                defaultValue={searchQuery}
                                onChange={(e) => handleSearchChange(e.target.value)}
                                className="pl-10 bg-card border-border"
                                data-testid="domain-search-input"
                            />
                        </div>
                        <Button
                            variant="outline"
                            onClick={() => setShowFilters(!showFilters)}
                            className={showFilters ? 'border-blue-500' : ''}
                            data-testid="toggle-filters-btn"
                        >
                            <Filter className="h-4 w-4 mr-2" />
                            Filters
                            {hasActiveFilters && (
                                <Badge variant="secondary" className="ml-2 h-5 px-1.5">
                                    {[filterBrand, filterStatus, filterIndex, filterTier, filterGroup]
                                        .filter(f => f !== 'all').length}
                                </Badge>
                            )}
                        </Button>
                    </div>

                    {showFilters && (
                        <div className="filters-bar animate-fade-in">
                            <Select value={filterBrand} onValueChange={setFilterBrand}>
                                <SelectTrigger className="w-[150px] bg-black border-border" data-testid="filter-brand">
                                    <SelectValue placeholder="Brand" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All Brands</SelectItem>
                                    {brands.map(b => (
                                        <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            <Select value={filterStatus} onValueChange={setFilterStatus}>
                                <SelectTrigger className="w-[150px] bg-black border-border" data-testid="filter-status">
                                    <SelectValue placeholder="Status" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All Status</SelectItem>
                                    {Object.entries(STATUS_LABELS).map(([k, v]) => (
                                        <SelectItem key={k} value={k}>{v}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            <Select value={filterIndex} onValueChange={setFilterIndex}>
                                <SelectTrigger className="w-[150px] bg-black border-border" data-testid="filter-index">
                                    <SelectValue placeholder="Index" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All Index</SelectItem>
                                    {Object.entries(INDEX_STATUS_LABELS).map(([k, v]) => (
                                        <SelectItem key={k} value={k}>{v}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            <Select value={filterTier} onValueChange={setFilterTier}>
                                <SelectTrigger className="w-[150px] bg-black border-border" data-testid="filter-tier">
                                    <SelectValue placeholder="Tier" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All Tiers</SelectItem>
                                    {Object.entries(TIER_LABELS).map(([k, v]) => (
                                        <SelectItem key={k} value={k}>{v}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            <Select value={filterGroup} onValueChange={setFilterGroup}>
                                <SelectTrigger className="w-[150px] bg-black border-border" data-testid="filter-group">
                                    <SelectValue placeholder="Network" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All Networks</SelectItem>
                                    <SelectItem value="none">No Network</SelectItem>
                                    {groups.map(g => (
                                        <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            {hasActiveFilters && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={clearFilters}
                                    className="text-zinc-400 hover:text-white"
                                    data-testid="clear-filters-btn"
                                >
                                    <X className="h-4 w-4 mr-1" />
                                    Clear
                                </Button>
                            )}
                        </div>
                    )}
                </div>

                {/* Domains Table */}
                <div className="data-table-container" data-testid="domains-table">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Domain</TableHead>
                                <TableHead>Brand</TableHead>
                                <TableHead>Tier</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Index</TableHead>
                                <TableHead>Network</TableHead>
                                <TableHead>Created</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filteredDomains.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={8} className="h-32 text-center">
                                        <div className="empty-state py-8">
                                            <Globe className="empty-state-icon mx-auto" />
                                            <p className="empty-state-title">No domains found</p>
                                            <p className="empty-state-description">
                                                {domains.length === 0 
                                                    ? 'Add your first domain to get started'
                                                    : 'Try adjusting your filters'}
                                            </p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                filteredDomains.map((domain) => (
                                    <TableRow key={domain.id} className="table-row-hover" data-testid={`domain-row-${domain.id}`}>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                <span className="font-mono text-sm">{domain.domain_name}</span>
                                                <a 
                                                    href={`https://${domain.domain_name}`} 
                                                    target="_blank" 
                                                    rel="noopener noreferrer"
                                                    className="text-zinc-500 hover:text-blue-500"
                                                >
                                                    <ExternalLink className="h-3 w-3" />
                                                </a>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline" className="font-normal">
                                                {domain.brand_name || '-'}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <span className={`badge-tier ${getTierBadgeClass(domain.tier_level)}`}>
                                                {TIER_LABELS[domain.tier_level]}
                                            </span>
                                        </TableCell>
                                        <TableCell>
                                            <span className="text-sm text-zinc-400">
                                                {STATUS_LABELS[domain.domain_status]}
                                            </span>
                                        </TableCell>
                                        <TableCell>
                                            <span className={`text-xs px-2 py-1 rounded-full font-mono uppercase ${
                                                domain.index_status === 'index' 
                                                    ? 'status-indexed' 
                                                    : 'status-noindex'
                                            }`}>
                                                {domain.index_status}
                                            </span>
                                        </TableCell>
                                        <TableCell>
                                            <span className="text-sm text-zinc-400">
                                                {domain.group_name || '-'}
                                            </span>
                                        </TableCell>
                                        <TableCell>
                                            <span className="text-sm text-zinc-500">
                                                {formatDate(domain.created_at)}
                                            </span>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex items-center justify-end gap-1">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => openDetailPanel(domain)}
                                                    className="h-8 px-2 hover:bg-blue-500/10 hover:text-blue-400 text-zinc-400"
                                                    data-testid={`show-detail-${domain.id}`}
                                                >
                                                    <Eye className="h-4 w-4 mr-1" />
                                                    Detail
                                                </Button>
                                                {canEdit() && (
                                                    <>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => openEditDialog(domain)}
                                                            className="h-8 w-8 hover:bg-white/5"
                                                            data-testid={`edit-domain-${domain.id}`}
                                                        >
                                                            <Edit className="h-4 w-4" />
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => {
                                                                setSelectedDomain(domain);
                                                                setDeleteDialogOpen(true);
                                                            }}
                                                            className="h-8 w-8 hover:bg-red-500/10 hover:text-red-500"
                                                            data-testid={`delete-domain-${domain.id}`}
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

                {/* Domain Detail Panel */}
                <DomainDetailPanel
                    domain={detailDomain}
                    isOpen={detailPanelOpen}
                    onClose={() => {
                        setDetailPanelOpen(false);
                        setDetailDomain(null);
                    }}
                    onUpdate={handleDetailUpdate}
                    allDomains={domains}
                    brands={brands}
                    groups={groups}
                />

                {/* Create/Edit Dialog */}
                <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-lg">
                        <DialogHeader>
                            <DialogTitle>
                                {selectedDomain ? 'Edit Domain' : 'Add Domain'}
                            </DialogTitle>
                        </DialogHeader>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="space-y-2">
                                <Label>Domain Name *</Label>
                                <Input
                                    value={form.domain_name}
                                    onChange={(e) => setForm({...form, domain_name: e.target.value})}
                                    placeholder="example.com"
                                    className="bg-black border-border"
                                    data-testid="domain-name-input"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Brand *</Label>
                                    <Select 
                                        value={form.brand_id} 
                                        onValueChange={(v) => setForm({...form, brand_id: v})}
                                    >
                                        <SelectTrigger className="bg-black border-border" data-testid="domain-brand-select">
                                            <SelectValue placeholder="Select brand" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {brands.map(b => (
                                                <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-2">
                                    <Label>Tier Level</Label>
                                    <Select 
                                        value={form.tier_level} 
                                        onValueChange={(v) => setForm({...form, tier_level: v, parent_domain_id: ''})}
                                    >
                                        <SelectTrigger className="bg-black border-border" data-testid="domain-tier-select">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {Object.entries(TIER_LABELS).map(([k, v]) => (
                                                <SelectItem key={k} value={k}>{v}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Domain Status</Label>
                                    <Select 
                                        value={form.domain_status} 
                                        onValueChange={(v) => setForm({...form, domain_status: v})}
                                    >
                                        <SelectTrigger className="bg-black border-border" data-testid="domain-status-select">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {Object.entries(STATUS_LABELS).map(([k, v]) => (
                                                <SelectItem key={k} value={k}>{v}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-2">
                                    <Label>Index Status</Label>
                                    <Select 
                                        value={form.index_status} 
                                        onValueChange={(v) => setForm({...form, index_status: v})}
                                    >
                                        <SelectTrigger className="bg-black border-border" data-testid="domain-index-select">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {Object.entries(INDEX_STATUS_LABELS).map(([k, v]) => (
                                                <SelectItem key={k} value={k}>{v}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Network</Label>
                                    <Select 
                                        value={form.group_id || 'none'} 
                                        onValueChange={(v) => setForm({...form, group_id: v === 'none' ? '' : v, parent_domain_id: ''})}
                                    >
                                        <SelectTrigger className="bg-black border-border" data-testid="domain-group-select">
                                            <SelectValue placeholder="None" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="none">None</SelectItem>
                                            {groups.map(g => (
                                                <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-2">
                                    <Label>Parent Domain</Label>
                                    <Select 
                                        value={form.parent_domain_id || 'none'} 
                                        onValueChange={(v) => setForm({...form, parent_domain_id: v === 'none' ? '' : v})}
                                        disabled={!form.group_id || form.tier_level === 'lp_money_site'}
                                    >
                                        <SelectTrigger className="bg-black border-border" data-testid="domain-parent-select">
                                            <SelectValue placeholder="None" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="none">None</SelectItem>
                                            {parentDomainOptions.map(d => (
                                                <SelectItem key={d.id} value={d.id}>
                                                    {d.domain_name} ({TIER_LABELS[d.tier_level]})
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label>Notes</Label>
                                <Textarea
                                    value={form.notes}
                                    onChange={(e) => setForm({...form, notes: e.target.value})}
                                    placeholder="Optional notes..."
                                    className="bg-black border-border resize-none"
                                    rows={3}
                                    data-testid="domain-notes-input"
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
                                    data-testid="save-domain-btn"
                                >
                                    {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                    {selectedDomain ? 'Update' : 'Create'}
                                </Button>
                            </DialogFooter>
                        </form>
                    </DialogContent>
                </Dialog>

                {/* Delete Confirmation Dialog */}
                <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-md">
                        <DialogHeader>
                            <DialogTitle>Delete Domain</DialogTitle>
                        </DialogHeader>
                        <p className="text-zinc-400">
                            Are you sure you want to delete <span className="text-white font-mono">{selectedDomain?.domain_name}</span>?
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
                                data-testid="confirm-delete-btn"
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
