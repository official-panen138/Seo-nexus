import { useState, useEffect, useMemo, useRef } from 'react';
import { useAuth } from '../lib/auth';
import { domainsAPI, brandsAPI, groupsAPI, categoriesAPI, assetDomainsAPI, networksAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { DomainDetailPanel } from '../components/DomainDetailPanel';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Switch } from '../components/ui/switch';
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
    Eye,
    RefreshCw,
    Upload,
    FileSpreadsheet,
    CheckCircle,
    XCircle,
    AlertCircle
} from 'lucide-react';
import { 
    TIER_LABELS, 
    STATUS_LABELS, 
    INDEX_STATUS_LABELS, 
    getTierBadgeClass, 
    formatDate,
    debounce
} from '../lib/utils';
import axios from 'axios';

// V3 Asset Status
const ASSET_STATUS_LABELS = {
    'active': 'Active',
    'inactive': 'Inactive',
    'pending': 'Pending',
    'expired': 'Expired'
};

const ASSET_STATUS_COLORS = {
    'active': 'text-emerald-400 border-emerald-400/30',
    'inactive': 'text-zinc-400 border-zinc-400/30',
    'pending': 'text-amber-400 border-amber-400/30',
    'expired': 'text-red-400 border-red-400/30'
};

const INITIAL_FORM = {
    domain_name: '',
    brand_id: '',
    category_id: '',
    registrar: '',
    expiration_date: '',
    auto_renew: false,
    status: 'active',
    monitoring_enabled: false,
    monitoring_interval: '1hour',
    notes: ''
};

// Legacy form for V2
const INITIAL_FORM_V2 = {
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
    const [assets, setAssets] = useState([]);
    const [domains, setDomains] = useState([]); // V2 fallback
    const [brands, setBrands] = useState([]);
    const [groups, setGroups] = useState([]);
    const [networks, setNetworks] = useState([]);
    const [categories, setCategories] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [selectedAsset, setSelectedAsset] = useState(null);
    const [form, setForm] = useState(INITIAL_FORM);
    
    // V3 mode
    const [useV3, setUseV3] = useState(true);
    
    // Detail panel state
    const [detailPanelOpen, setDetailPanelOpen] = useState(false);
    const [detailDomain, setDetailDomain] = useState(null);
    
    // Import state
    const [importDialogOpen, setImportDialogOpen] = useState(false);
    const [importData, setImportData] = useState([]);
    const [importResult, setImportResult] = useState(null);
    const [importing, setImporting] = useState(false);
    const fileInputRef = useRef(null);
    
    // Filters
    const [searchQuery, setSearchQuery] = useState('');
    const [filterBrand, setFilterBrand] = useState('all');
    const [filterStatus, setFilterStatus] = useState('all');
    const [filterMonitoring, setFilterMonitoring] = useState('all');
    const [showFilters, setShowFilters] = useState(false);

    useEffect(() => {
        loadData();
    }, [useV3]);

    const loadData = async () => {
        setLoading(true);
        try {
            if (useV3) {
                const [assetsRes, brandsRes, networksRes, categoriesRes] = await Promise.all([
                    assetDomainsAPI.getAll(),
                    brandsAPI.getAll(),
                    networksAPI.getAll(),
                    categoriesAPI.getAll()
                ]);
                setAssets(assetsRes.data);
                setBrands(brandsRes.data);
                setNetworks(networksRes.data);
                setCategories(categoriesRes.data);
            } else {
                // V2 fallback
                const [domainsRes, brandsRes, groupsRes, categoriesRes] = await Promise.all([
                    domainsAPI.getAll(),
                    brandsAPI.getAll(),
                    groupsAPI.getAll(),
                    categoriesAPI.getAll()
                ]);
                setDomains(domainsRes.data);
                setBrands(brandsRes.data);
                setGroups(groupsRes.data);
                setCategories(categoriesRes.data);
            }
        } catch (err) {
            console.error('Failed to load data:', err);
            toast.error('Failed to load domains');
            // Try V2 fallback if V3 fails
            if (useV3) {
                setUseV3(false);
            }
        } finally {
            setLoading(false);
        }
    };

    // Filtered data
    const filteredData = useMemo(() => {
        const data = useV3 ? assets : domains;
        return data.filter(item => {
            if (searchQuery && !item.domain_name.toLowerCase().includes(searchQuery.toLowerCase())) {
                return false;
            }
            if (filterBrand !== 'all' && item.brand_id !== filterBrand) return false;
            
            if (useV3) {
                if (filterStatus !== 'all' && item.status !== filterStatus) return false;
                if (filterMonitoring !== 'all') {
                    if (filterMonitoring === 'enabled' && !item.monitoring_enabled) return false;
                    if (filterMonitoring === 'disabled' && item.monitoring_enabled) return false;
                }
            } else {
                if (filterStatus !== 'all' && item.domain_status !== filterStatus) return false;
            }
            
            return true;
        });
    }, [assets, domains, searchQuery, filterBrand, filterStatus, filterMonitoring, useV3]);

    const handleSearchChange = debounce((value) => {
        setSearchQuery(value);
    }, 300);

    const openCreateDialog = () => {
        setSelectedAsset(null);
        setForm(useV3 ? INITIAL_FORM : INITIAL_FORM_V2);
        setDialogOpen(true);
    };

    const openEditDialog = (item) => {
        setSelectedAsset(item);
        if (useV3) {
            setForm({
                domain_name: item.domain_name,
                brand_id: item.brand_id || '',
                category_id: item.category_id || '',
                registrar: item.registrar || '',
                expiration_date: item.expiration_date ? item.expiration_date.split('T')[0] : '',
                auto_renew: item.auto_renew || false,
                status: item.status || 'active',
                monitoring_enabled: item.monitoring_enabled || false,
                monitoring_interval: item.monitoring_interval || '1hour',
                notes: item.notes || ''
            });
        } else {
            setForm({
                domain_name: item.domain_name,
                brand_id: item.brand_id,
                domain_status: item.domain_status,
                index_status: item.index_status,
                tier_level: item.tier_level,
                group_id: item.group_id || '',
                parent_domain_id: item.parent_domain_id || '',
                notes: item.notes || ''
            });
        }
        setDialogOpen(true);
    };

    const openDetailPanel = (item) => {
        setDetailDomain(item);
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
            if (useV3) {
                const payload = {
                    domain_name: form.domain_name,
                    brand_id: form.brand_id,
                    category_id: form.category_id || null,
                    registrar: form.registrar || null,
                    expiration_date: form.expiration_date ? new Date(form.expiration_date).toISOString() : null,
                    auto_renew: form.auto_renew,
                    status: form.status,
                    monitoring_enabled: form.monitoring_enabled,
                    monitoring_interval: form.monitoring_interval,
                    notes: form.notes
                };

                if (selectedAsset) {
                    await assetDomainsAPI.update(selectedAsset.id, payload);
                    toast.success('Asset domain updated');
                } else {
                    await assetDomainsAPI.create(payload);
                    toast.success('Asset domain created');
                }
            } else {
                // V2 logic
                const payload = {
                    ...form,
                    group_id: form.group_id || null,
                    parent_domain_id: form.parent_domain_id || null
                };

                if (selectedAsset) {
                    await domainsAPI.update(selectedAsset.id, payload);
                    toast.success('Domain updated');
                } else {
                    await domainsAPI.create(payload);
                    toast.success('Domain created');
                }
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
        if (!selectedAsset) return;
        
        setSaving(true);
        try {
            if (useV3) {
                await assetDomainsAPI.delete(selectedAsset.id);
            } else {
                await domainsAPI.delete(selectedAsset.id);
            }
            toast.success('Domain deleted');
            setDeleteDialogOpen(false);
            setSelectedAsset(null);
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
        setFilterMonitoring('all');
    };

    const hasActiveFilters = filterBrand !== 'all' || filterStatus !== 'all' || filterMonitoring !== 'all';

    // CSV Import handlers
    const handleFileSelect = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = (event) => {
            const text = event.target.result;
            const lines = text.split('\n').filter(line => line.trim());
            
            if (lines.length < 2) {
                toast.error('CSV must have header row and at least one data row');
                return;
            }
            
            const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
            const domainIndex = headers.indexOf('domain_name');
            
            if (domainIndex === -1) {
                toast.error('CSV must have a "domain_name" column');
                return;
            }
            
            const data = [];
            for (let i = 1; i < lines.length; i++) {
                const values = lines[i].split(',').map(v => v.trim());
                if (values[domainIndex]) {
                    data.push({
                        domain_name: values[domainIndex],
                        brand_name: values[headers.indexOf('brand_name')] || '',
                        registrar: values[headers.indexOf('registrar')] || '',
                        expiration_date: values[headers.indexOf('expiration_date')] || '',
                        status: values[headers.indexOf('status')] || 'active',
                        notes: values[headers.indexOf('notes')] || ''
                    });
                }
            }
            
            setImportData(data);
            setImportResult(null);
        };
        reader.readAsText(file);
    };

    const handleImport = async () => {
        if (importData.length === 0) {
            toast.error('No data to import');
            return;
        }
        
        setImporting(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const response = await axios.post(
                `${process.env.REACT_APP_BACKEND_URL}/api/v3/import/domains`,
                { domains: importData, skip_duplicates: true },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            
            setImportResult(response.data);
            
            if (response.data.imported > 0) {
                toast.success(`Imported ${response.data.imported} domains`);
                loadData();
            }
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Import failed');
        } finally {
            setImporting(false);
        }
    };

    const resetImport = () => {
        setImportData([]);
        setImportResult(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const downloadTemplate = () => {
        const csv = 'domain_name,brand_name,registrar,expiration_date,status,notes\nexample.com,MyBrand,GoDaddy,2026-12-31,active,Main site\nexample2.com,MyBrand,Namecheap,2027-06-15,active,Secondary site';
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'domains_import_template.csv';
        a.click();
    };

    // Refresh detail panel when data updates
    const handleDetailUpdate = () => {
        loadData();
        if (detailDomain) {
            if (useV3) {
                assetDomainsAPI.getOne(detailDomain.id).then(res => {
                    setDetailDomain(res.data);
                }).catch(() => {
                    setDetailPanelOpen(false);
                });
            } else {
                domainsAPI.getOne(detailDomain.id).then(res => {
                    setDetailDomain(res.data);
                }).catch(() => {
                    setDetailPanelOpen(false);
                });
            }
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
                        <div className="flex items-center gap-3">
                            <h1 className="page-title">Asset Domains</h1>
                            <Badge 
                                variant="outline" 
                                className={useV3 ? 'text-emerald-400 border-emerald-400/30' : 'text-zinc-400 border-zinc-400/30'}
                            >
                                {useV3 ? 'V3' : 'V2 Legacy'}
                            </Badge>
                        </div>
                        <p className="page-subtitle">
                            {filteredData.length} of {useV3 ? assets.length : domains.length} domains
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <Button 
                            variant="ghost"
                            size="sm"
                            onClick={loadData}
                            className="text-zinc-400"
                        >
                            <RefreshCw className="h-4 w-4 mr-1" />
                            Refresh
                        </Button>
                        {canEdit() && useV3 && (
                            <Button 
                                variant="outline"
                                onClick={() => setImportDialogOpen(true)}
                                data-testid="import-csv-btn"
                            >
                                <Upload className="h-4 w-4 mr-2" />
                                Import CSV
                            </Button>
                        )}
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
                                    {[filterBrand, filterStatus, filterMonitoring]
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
                                    {useV3 ? (
                                        Object.entries(ASSET_STATUS_LABELS).map(([k, v]) => (
                                            <SelectItem key={k} value={k}>{v}</SelectItem>
                                        ))
                                    ) : (
                                        Object.entries(STATUS_LABELS).map(([k, v]) => (
                                            <SelectItem key={k} value={k}>{v}</SelectItem>
                                        ))
                                    )}
                                </SelectContent>
                            </Select>

                            {useV3 && (
                                <Select value={filterMonitoring} onValueChange={setFilterMonitoring}>
                                    <SelectTrigger className="w-[150px] bg-black border-border" data-testid="filter-monitoring">
                                        <SelectValue placeholder="Monitoring" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="all">All</SelectItem>
                                        <SelectItem value="enabled">Monitored</SelectItem>
                                        <SelectItem value="disabled">Not Monitored</SelectItem>
                                    </SelectContent>
                                </Select>
                            )}

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
                                <TableHead>Status</TableHead>
                                {useV3 ? (
                                    <>
                                        <TableHead>Monitoring</TableHead>
                                        <TableHead>Expiration</TableHead>
                                    </>
                                ) : (
                                    <>
                                        <TableHead>Tier</TableHead>
                                        <TableHead>Index</TableHead>
                                        <TableHead>Network</TableHead>
                                    </>
                                )}
                                <TableHead>Created</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filteredData.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={useV3 ? 7 : 8} className="h-32 text-center">
                                        <div className="empty-state py-8">
                                            <Globe className="empty-state-icon mx-auto" />
                                            <p className="empty-state-title">No domains found</p>
                                            <p className="empty-state-description">
                                                {(useV3 ? assets : domains).length === 0 
                                                    ? 'Add your first domain to get started'
                                                    : 'Try adjusting your filters'}
                                            </p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                filteredData.map((item) => (
                                    <TableRow key={item.id} className="table-row-hover" data-testid={`domain-row-${item.id}`}>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                <span className="font-mono text-sm">{item.domain_name}</span>
                                                <a 
                                                    href={`https://${item.domain_name}`} 
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
                                                {item.brand_name || '-'}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            {useV3 ? (
                                                <Badge variant="outline" className={ASSET_STATUS_COLORS[item.status] || ''}>
                                                    {ASSET_STATUS_LABELS[item.status] || item.status}
                                                </Badge>
                                            ) : (
                                                <span className="text-sm text-zinc-400">
                                                    {STATUS_LABELS[item.domain_status]}
                                                </span>
                                            )}
                                        </TableCell>
                                        {useV3 ? (
                                            <>
                                                <TableCell>
                                                    <span className={`text-xs px-2 py-1 rounded-full ${
                                                        item.monitoring_enabled 
                                                            ? 'bg-emerald-500/10 text-emerald-400' 
                                                            : 'bg-zinc-500/10 text-zinc-500'
                                                    }`}>
                                                        {item.monitoring_enabled ? (item.ping_status === 'up' ? '● UP' : item.ping_status === 'down' ? '● DOWN' : 'ON') : 'OFF'}
                                                    </span>
                                                </TableCell>
                                                <TableCell>
                                                    <span className="text-sm text-zinc-400">
                                                        {item.expiration_date ? formatDate(item.expiration_date) : '-'}
                                                    </span>
                                                </TableCell>
                                            </>
                                        ) : (
                                            <>
                                                <TableCell>
                                                    <span className={`badge-tier ${getTierBadgeClass(item.tier_level)}`}>
                                                        {TIER_LABELS[item.tier_level]}
                                                    </span>
                                                </TableCell>
                                                <TableCell>
                                                    <span className={`text-xs px-2 py-1 rounded-full font-mono uppercase ${
                                                        item.index_status === 'index' 
                                                            ? 'status-indexed' 
                                                            : 'status-noindex'
                                                    }`}>
                                                        {item.index_status}
                                                    </span>
                                                </TableCell>
                                                <TableCell>
                                                    <span className="text-sm text-zinc-400">
                                                        {item.group_name || '-'}
                                                    </span>
                                                </TableCell>
                                            </>
                                        )}
                                        <TableCell>
                                            <span className="text-sm text-zinc-500">
                                                {formatDate(item.created_at)}
                                            </span>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex items-center justify-end gap-1">
                                                {!useV3 && (
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => openDetailPanel(item)}
                                                        className="h-8 px-2 hover:bg-blue-500/10 hover:text-blue-400 text-zinc-400"
                                                        data-testid={`show-detail-${item.id}`}
                                                    >
                                                        <Eye className="h-4 w-4 mr-1" />
                                                        Detail
                                                    </Button>
                                                )}
                                                {canEdit() && (
                                                    <>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => openEditDialog(item)}
                                                            className="h-8 w-8 hover:bg-white/5"
                                                            data-testid={`edit-domain-${item.id}`}
                                                        >
                                                            <Edit className="h-4 w-4" />
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => {
                                                                setSelectedAsset(item);
                                                                setDeleteDialogOpen(true);
                                                            }}
                                                            className="h-8 w-8 hover:bg-red-500/10 hover:text-red-500"
                                                            data-testid={`delete-domain-${item.id}`}
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

                {/* Domain Detail Panel (V2 only) */}
                {!useV3 && (
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
                        categories={categories}
                    />
                )}

                {/* Create/Edit Dialog */}
                <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-lg max-h-[90vh] overflow-y-auto">
                        <DialogHeader>
                            <DialogTitle>
                                {selectedAsset ? 'Edit Domain' : 'Add Domain'}
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

                                {useV3 ? (
                                    <div className="space-y-2">
                                        <Label>Status</Label>
                                        <Select 
                                            value={form.status} 
                                            onValueChange={(v) => setForm({...form, status: v})}
                                        >
                                            <SelectTrigger className="bg-black border-border">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {Object.entries(ASSET_STATUS_LABELS).map(([k, v]) => (
                                                    <SelectItem key={k} value={k}>{v}</SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                ) : (
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
                                )}
                            </div>

                            {useV3 ? (
                                <>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>Category</Label>
                                            <Select 
                                                value={form.category_id || 'none'} 
                                                onValueChange={(v) => setForm({...form, category_id: v === 'none' ? '' : v})}
                                            >
                                                <SelectTrigger className="bg-black border-border">
                                                    <SelectValue placeholder="None" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="none">None</SelectItem>
                                                    {categories.map(c => (
                                                        <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>

                                        <div className="space-y-2">
                                            <Label>Registrar</Label>
                                            <Input
                                                value={form.registrar}
                                                onChange={(e) => setForm({...form, registrar: e.target.value})}
                                                placeholder="GoDaddy, Namecheap..."
                                                className="bg-black border-border"
                                            />
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>Expiration Date</Label>
                                            <Input
                                                type="date"
                                                value={form.expiration_date}
                                                onChange={(e) => setForm({...form, expiration_date: e.target.value})}
                                                className="bg-black border-border"
                                            />
                                        </div>

                                        <div className="space-y-2">
                                            <Label>Auto-Renew</Label>
                                            <div className="flex items-center gap-2 py-2">
                                                <Switch 
                                                    checked={form.auto_renew} 
                                                    onCheckedChange={(v) => setForm({...form, auto_renew: v})} 
                                                />
                                                <span className="text-sm text-zinc-400">{form.auto_renew ? 'Enabled' : 'Disabled'}</span>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>Enable Monitoring</Label>
                                            <div className="flex items-center gap-2 py-2">
                                                <Switch 
                                                    checked={form.monitoring_enabled} 
                                                    onCheckedChange={(v) => setForm({...form, monitoring_enabled: v})} 
                                                />
                                                <span className="text-sm text-zinc-400">{form.monitoring_enabled ? 'Active' : 'Inactive'}</span>
                                            </div>
                                        </div>

                                        {form.monitoring_enabled && (
                                            <div className="space-y-2">
                                                <Label>Check Interval</Label>
                                                <Select 
                                                    value={form.monitoring_interval} 
                                                    onValueChange={(v) => setForm({...form, monitoring_interval: v})}
                                                >
                                                    <SelectTrigger className="bg-black border-border">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="5min">Every 5 min</SelectItem>
                                                        <SelectItem value="15min">Every 15 min</SelectItem>
                                                        <SelectItem value="1hour">Every hour</SelectItem>
                                                        <SelectItem value="daily">Daily</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        )}
                                    </div>
                                </>
                            ) : (
                                <>
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
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                </>
                            )}

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
                                    {selectedAsset ? 'Update' : 'Create'}
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
                            Are you sure you want to delete <span className="text-white font-mono">{selectedAsset?.domain_name}</span>?
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

                {/* CSV Import Dialog */}
                <Dialog open={importDialogOpen} onOpenChange={(open) => {
                    setImportDialogOpen(open);
                    if (!open) resetImport();
                }}>
                    <DialogContent className="bg-card border-border max-w-2xl max-h-[85vh] overflow-y-auto">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <FileSpreadsheet className="h-5 w-5" />
                                Import Domains from CSV
                            </DialogTitle>
                            <DialogDescription>
                                Upload a CSV file to bulk import domains. Download the template for the correct format.
                            </DialogDescription>
                        </DialogHeader>

                        <div className="space-y-6">
                            {/* Template Download */}
                            <div className="flex items-center justify-between p-4 bg-zinc-900 rounded-lg">
                                <div>
                                    <p className="text-sm font-medium">CSV Template</p>
                                    <p className="text-xs text-zinc-500">Required column: domain_name</p>
                                </div>
                                <Button variant="outline" size="sm" onClick={downloadTemplate}>
                                    Download Template
                                </Button>
                            </div>

                            {/* File Upload */}
                            <div className="space-y-2">
                                <Label>Select CSV File</Label>
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".csv"
                                    onChange={handleFileSelect}
                                    className="block w-full text-sm text-zinc-400
                                        file:mr-4 file:py-2 file:px-4
                                        file:rounded-md file:border-0
                                        file:text-sm file:font-medium
                                        file:bg-zinc-800 file:text-white
                                        hover:file:bg-zinc-700
                                        cursor-pointer"
                                />
                            </div>

                            {/* Preview */}
                            {importData.length > 0 && !importResult && (
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <Label>Preview ({importData.length} domains)</Label>
                                        <Button variant="ghost" size="sm" onClick={resetImport}>
                                            <X className="h-4 w-4 mr-1" />
                                            Clear
                                        </Button>
                                    </div>
                                    <div className="max-h-60 overflow-y-auto border border-border rounded-md">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Domain</TableHead>
                                                    <TableHead>Brand</TableHead>
                                                    <TableHead>Status</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {importData.slice(0, 10).map((item, i) => (
                                                    <TableRow key={i}>
                                                        <TableCell className="font-mono text-sm">{item.domain_name}</TableCell>
                                                        <TableCell className="text-sm">{item.brand_name || '-'}</TableCell>
                                                        <TableCell className="text-sm">{item.status}</TableCell>
                                                    </TableRow>
                                                ))}
                                                {importData.length > 10 && (
                                                    <TableRow>
                                                        <TableCell colSpan={3} className="text-center text-zinc-500">
                                                            ...and {importData.length - 10} more
                                                        </TableCell>
                                                    </TableRow>
                                                )}
                                            </TableBody>
                                        </Table>
                                    </div>
                                </div>
                            )}

                            {/* Import Results */}
                            {importResult && (
                                <div className="space-y-4">
                                    <div className="grid grid-cols-3 gap-4">
                                        <div className="p-4 bg-emerald-500/10 rounded-lg text-center">
                                            <CheckCircle className="h-6 w-6 text-emerald-500 mx-auto mb-1" />
                                            <p className="text-2xl font-bold text-emerald-500">{importResult.imported}</p>
                                            <p className="text-xs text-zinc-500">Imported</p>
                                        </div>
                                        <div className="p-4 bg-amber-500/10 rounded-lg text-center">
                                            <AlertCircle className="h-6 w-6 text-amber-500 mx-auto mb-1" />
                                            <p className="text-2xl font-bold text-amber-500">{importResult.skipped}</p>
                                            <p className="text-xs text-zinc-500">Skipped</p>
                                        </div>
                                        <div className="p-4 bg-red-500/10 rounded-lg text-center">
                                            <XCircle className="h-6 w-6 text-red-500 mx-auto mb-1" />
                                            <p className="text-2xl font-bold text-red-500">{importResult.errors?.length || 0}</p>
                                            <p className="text-xs text-zinc-500">Errors</p>
                                        </div>
                                    </div>

                                    {importResult.errors?.length > 0 && (
                                        <div className="max-h-32 overflow-y-auto border border-red-900/50 rounded-md p-2">
                                            {importResult.errors.map((err, i) => (
                                                <p key={i} className="text-xs text-red-400">
                                                    {err.domain}: {err.error}
                                                </p>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        <DialogFooter>
                            <Button
                                variant="outline"
                                onClick={() => {
                                    setImportDialogOpen(false);
                                    resetImport();
                                }}
                            >
                                {importResult ? 'Close' : 'Cancel'}
                            </Button>
                            {!importResult && (
                                <Button
                                    onClick={handleImport}
                                    disabled={importing || importData.length === 0}
                                    className="bg-white text-black hover:bg-zinc-200"
                                >
                                    {importing && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                    Import {importData.length} Domains
                                </Button>
                            )}
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </Layout>
    );
}
