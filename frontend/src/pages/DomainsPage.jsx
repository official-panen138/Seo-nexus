import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { domainsAPI, brandsAPI, groupsAPI, categoriesAPI, assetDomainsAPI, networksAPI, registrarsAPI, exportAPI, monitoringAPI } from '../lib/api';
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
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '../components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from '../components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
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
    AlertCircle,
    ChevronsUpDown,
    Check,
    Download,
    Network,
    ChevronLeft,
    ChevronRight,
    MoreHorizontal,
    Archive,
    ShieldAlert,
    ShieldOff,
    Clock,
    Ban,
    Activity
} from 'lucide-react';
import { 
    TIER_LABELS, 
    STATUS_LABELS, 
    INDEX_STATUS_LABELS, 
    getTierBadgeClass, 
    formatDate,
    debounce,
    cn
} from '../lib/utils';

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

// Domain Lifecycle Status
const LIFECYCLE_STATUS_LABELS = {
    'active': 'Active',
    'expired_pending': 'Expired (Pending Decision)',
    'expired_released': 'Released (Not Renewed)',
    'inactive': 'Inactive',
    'archived': 'Archived'
};

const LIFECYCLE_STATUS_COLORS = {
    'active': 'text-emerald-400 border-emerald-400/30 bg-emerald-500/10',
    'expired_pending': 'text-amber-400 border-amber-400/30 bg-amber-500/10',
    'expired_released': 'text-zinc-400 border-zinc-400/30 bg-zinc-500/10',
    'inactive': 'text-zinc-400 border-zinc-400/30 bg-zinc-500/10',
    'archived': 'text-zinc-500 border-zinc-500/30 bg-zinc-600/10'
};

// Quarantine Categories
const QUARANTINE_CATEGORY_LABELS = {
    'spam_murni': 'Spam Murni',
    'dmca': 'DMCA',
    'rollback_restore': 'Rollback Restore',
    'penalized': 'Penalized',
    'manual_review': 'Manual Review',
    'custom': 'Custom'
};

// SEO Networks Badges Component
const SeoNetworksBadges = ({ networks }) => {
    if (!networks || networks.length === 0) {
        return <span className="text-zinc-500 text-sm">—</span>;
    }
    
    const visibleNetworks = networks.slice(0, 2);
    const hiddenCount = networks.length - 2;
    
    const getRoleBadgeClass = (role) => {
        return role === 'main' 
            ? 'bg-green-500/10 text-green-400 border-green-400/30' 
            : 'bg-purple-500/10 text-purple-400 border-purple-400/30';
    };
    
    return (
        <TooltipProvider>
            <div className="flex flex-wrap items-center gap-1">
                {visibleNetworks.map((network, idx) => (
                    <Tooltip key={network.network_id + idx}>
                        <TooltipTrigger asChild>
                            <Link to={`/groups/${network.network_id}`}>
                                <Badge 
                                    variant="outline" 
                                    className={`cursor-pointer hover:opacity-80 text-xs ${getRoleBadgeClass(network.role)}`}
                                    data-testid={`network-badge-${network.network_id}`}
                                >
                                    <Network className="h-3 w-3 mr-1" />
                                    {network.network_name}
                                </Badge>
                            </Link>
                        </TooltipTrigger>
                        <TooltipContent>
                            <div className="text-xs">
                                <p className="font-medium">{network.network_name}</p>
                                <p className="text-zinc-400">Role: {network.role === 'main' ? 'Main' : 'Supporting'}</p>
                                {network.optimized_path && (
                                    <p className="text-zinc-400">Path: {network.optimized_path}</p>
                                )}
                            </div>
                        </TooltipContent>
                    </Tooltip>
                ))}
                {hiddenCount > 0 && (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Badge variant="outline" className="text-xs text-zinc-400 border-zinc-400/30 cursor-default">
                                +{hiddenCount} more
                            </Badge>
                        </TooltipTrigger>
                        <TooltipContent>
                            <div className="text-xs space-y-1">
                                {networks.slice(2).map((network, idx) => (
                                    <div key={network.network_id + idx}>
                                        <span className="font-medium">{network.network_name}</span>
                                        <span className="text-zinc-400"> ({network.role})</span>
                                    </div>
                                ))}
                            </div>
                        </TooltipContent>
                    </Tooltip>
                )}
            </div>
        </TooltipProvider>
    );
};

const INITIAL_FORM = {
    domain_name: '',
    brand_id: '',
    category_id: '',
    registrar_id: '',
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
    const { canEdit, user } = useAuth();
    const isSuperAdmin = user?.role === 'super_admin';
    const [searchParams, setSearchParams] = useSearchParams();
    const [assets, setAssets] = useState([]);
    const [domains, setDomains] = useState([]); // V2 fallback
    const [brands, setBrands] = useState([]);
    const [groups, setGroups] = useState([]);
    const [networks, setNetworks] = useState([]);
    const [categories, setCategories] = useState([]);
    const [registrars, setRegistrars] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [selectedAsset, setSelectedAsset] = useState(null);
    const [form, setForm] = useState(INITIAL_FORM);
    
    // Registrar combobox state
    const [registrarSearchOpen, setRegistrarSearchOpen] = useState(false);
    
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
    
    // NEW: View mode tabs (all, released, quarantined, unmonitored)
    const [viewMode, setViewMode] = useState('all');
    const [filterLifecycle, setFilterLifecycle] = useState('all');
    const [filterQuarantine, setFilterQuarantine] = useState('all');
    const [filterUsedInSeo, setFilterUsedInSeo] = useState('all');
    
    // NEW: SEO Monitoring Coverage Stats
    const [coverageStats, setCoverageStats] = useState(null);
    const [loadingCoverage, setLoadingCoverage] = useState(false);
    
    // NEW: Lifecycle/Quarantine action dialogs
    const [lifecycleDialogOpen, setLifecycleDialogOpen] = useState(false);
    const [quarantineDialogOpen, setQuarantineDialogOpen] = useState(false);
    const [releaseDialogOpen, setReleaseDialogOpen] = useState(false);
    const [quarantineCategories, setQuarantineCategories] = useState([]);
    const [selectedQuarantineCategory, setSelectedQuarantineCategory] = useState('');
    const [quarantineNote, setQuarantineNote] = useState('');
    const [releaseReason, setReleaseReason] = useState('');
    const [selectedLifecycle, setSelectedLifecycle] = useState('');
    const [lifecycleReason, setLifecycleReason] = useState('');
    
    // SERVER-SIDE PAGINATION STATE
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(25);
    const [totalItems, setTotalItems] = useState(0);
    const [totalPages, setTotalPages] = useState(1);
    
    // Debounced search for server-side
    const [debouncedSearch, setDebouncedSearch] = useState('');

    // Reset to page 1 when filters change
    useEffect(() => {
        setCurrentPage(1);
    }, [debouncedSearch, filterBrand, filterStatus, filterMonitoring, pageSize, viewMode, filterLifecycle, filterQuarantine, filterUsedInSeo]);

    // Load data when pagination or filters change
    useEffect(() => {
        if (useV3) {
            loadPaginatedData();
        }
    }, [useV3, currentPage, pageSize, debouncedSearch, filterBrand, filterStatus, filterMonitoring, viewMode, filterLifecycle, filterQuarantine, filterUsedInSeo]);

    // Load reference data and coverage stats once
    useEffect(() => {
        loadReferenceData();
        loadCoverageStats();
        loadQuarantineCategories();
    }, [useV3]);

    // Debounce search input
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(searchQuery);
        }, 400);
        return () => clearTimeout(timer);
    }, [searchQuery]);

    // Load coverage stats
    const loadCoverageStats = async () => {
        if (!useV3) return;
        setLoadingCoverage(true);
        try {
            const response = await monitoringAPI.getCoverage();
            setCoverageStats(response.data);
        } catch (err) {
            console.error('Failed to load coverage stats:', err);
        } finally {
            setLoadingCoverage(false);
        }
    };

    // Load quarantine categories
    const loadQuarantineCategories = async () => {
        try {
            const response = await assetDomainsAPI.getQuarantineCategories();
            setQuarantineCategories(response.data.categories || []);
        } catch (err) {
            console.error('Failed to load quarantine categories:', err);
        }
    };

    // Handle 'edit' URL parameter to open edit dialog directly
    useEffect(() => {
        const editDomainId = searchParams.get('edit');
        if (editDomainId && !loading && assets.length > 0) {
            // Find the domain by ID
            const domainToEdit = assets.find(d => d.id === editDomainId);
            if (domainToEdit) {
                openEditDialog(domainToEdit);
                // Remove the edit param from URL to prevent re-triggering
                setSearchParams({}, { replace: true });
            } else {
                // Domain not found in current page, try to fetch it directly
                assetDomainsAPI.getOne(editDomainId)
                    .then(response => {
                        if (response.data) {
                            openEditDialog(response.data);
                        } else {
                            toast.error('Domain not found');
                        }
                        setSearchParams({}, { replace: true });
                    })
                    .catch(() => {
                        toast.error('Failed to load domain');
                        setSearchParams({}, { replace: true });
                    });
            }
        }
    }, [searchParams, loading, assets]);

    const loadReferenceData = async () => {
        try {
            if (useV3) {
                const [brandsRes, networksRes, categoriesRes, registrarsRes] = await Promise.all([
                    brandsAPI.getAll(),
                    networksAPI.getAll(),
                    categoriesAPI.getAll(),
                    registrarsAPI.getAll({ status: 'active' })
                ]);
                setBrands(brandsRes.data);
                setNetworks(networksRes.data);
                setCategories(categoriesRes.data);
                setRegistrars(registrarsRes.data);
            } else {
                const [brandsRes, groupsRes, categoriesRes] = await Promise.all([
                    brandsAPI.getAll(),
                    groupsAPI.getAll(),
                    categoriesAPI.getAll()
                ]);
                setBrands(brandsRes.data);
                setGroups(groupsRes.data);
                setCategories(categoriesRes.data);
            }
        } catch (err) {
            console.error('Failed to load reference data:', err);
        }
    };

    const loadPaginatedData = async () => {
        setLoading(true);
        try {
            // Build params for server-side filtering and pagination
            const params = {
                page: currentPage,
                limit: pageSize
            };
            
            if (debouncedSearch) params.search = debouncedSearch;
            if (filterBrand !== 'all') params.brand_id = filterBrand;
            if (filterStatus !== 'all') params.status = filterStatus;
            if (filterMonitoring === 'enabled') params.monitoring_enabled = true;
            if (filterMonitoring === 'disabled') params.monitoring_enabled = false;
            
            // NEW: Lifecycle and quarantine filters
            if (filterLifecycle !== 'all') params.lifecycle_status = filterLifecycle;
            if (filterQuarantine !== 'all') {
                if (filterQuarantine === 'quarantined') {
                    params.is_quarantined = true;
                } else if (filterQuarantine === 'not_quarantined') {
                    params.is_quarantined = false;
                } else {
                    params.quarantine_category = filterQuarantine;
                }
            }
            if (filterUsedInSeo !== 'all') {
                params.used_in_seo = filterUsedInSeo === 'yes';
            }
            
            // NEW: Special view modes
            if (viewMode !== 'all') {
                params.view_mode = viewMode;
            }
            
            const response = await assetDomainsAPI.getAll(params);
            
            // Handle paginated response
            if (response.data?.data && response.data?.meta) {
                setAssets(response.data.data);
                setTotalItems(response.data.meta.total);
                setTotalPages(response.data.meta.total_pages);
            } else {
                // Fallback for old response format (array)
                setAssets(Array.isArray(response.data) ? response.data : []);
                setTotalItems(response.data?.length || 0);
                setTotalPages(1);
            }
        } catch (err) {
            console.error('Failed to load domains:', err);
            toast.error('Failed to load domains');
            if (useV3) {
                setUseV3(false);
            }
        } finally {
            setLoading(false);
        }
    };

    const loadData = async () => {
        if (useV3) {
            await loadPaginatedData();
        } else {
            // V2 fallback - load all
            setLoading(true);
            try {
                const domainsRes = await domainsAPI.getAll();
                setDomains(domainsRes.data);
            } catch (err) {
                console.error('Failed to load V2 data:', err);
                toast.error('Failed to load domains');
            } finally {
                setLoading(false);
            }
        }
    };

    // For V2 mode, use client-side filtering
    const filteredData = useMemo(() => {
        if (useV3) {
            // V3 uses server-side filtering, just return assets
            return assets;
        }
        // V2 client-side filtering
        return domains.filter(item => {
            if (searchQuery && !item.domain_name.toLowerCase().includes(searchQuery.toLowerCase())) {
                return false;
            }
            if (filterBrand !== 'all' && item.brand_id !== filterBrand) return false;
            if (filterStatus !== 'all' && item.domain_status !== filterStatus) return false;
            return true;
        });
    }, [assets, domains, searchQuery, filterBrand, filterStatus, useV3]);

    const handleSearchChange = (value) => {
        setSearchQuery(value);
        // Debouncing is handled by useEffect
    };

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
                registrar_id: item.registrar_id || '',
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
                    registrar_id: form.registrar_id || null,
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
        setCurrentPage(1); // Reset to first page when clearing filters
    };

    const hasActiveFilters = filterBrand !== 'all' || filterStatus !== 'all' || filterMonitoring !== 'all' || searchQuery !== '';

    // Export handlers
    const handleExport = async (format) => {
        try {
            toast.info(`Exporting domains as ${format.toUpperCase()}...`);
            const params = {};
            if (filterBrand !== 'all') params.brand_id = filterBrand;
            if (filterStatus !== 'all') params.status = filterStatus;
            
            const response = await exportAPI.assetDomains(format, params);
            
            if (format === 'csv') {
                // Download CSV blob
                const blob = new Blob([response.data], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `asset_domains_export_${new Date().toISOString().split('T')[0]}.csv`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                toast.success('CSV exported successfully');
            } else {
                // Download JSON
                const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `asset_domains_export_${new Date().toISOString().split('T')[0]}.json`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                toast.success(`JSON exported (${response.data.total} domains)`);
            }
        } catch (err) {
            toast.error('Export failed');
            console.error(err);
        }
    };

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

    // Loading skeleton for table rows
    const TableSkeleton = () => (
        <>
            {[...Array(pageSize > 10 ? 10 : pageSize)].map((_, i) => (
                <TableRow key={i}>
                    <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                </TableRow>
            ))}
        </>
    );

    // Initial loading (reference data not loaded yet)
    const isInitialLoading = loading && brands.length === 0;

    if (isInitialLoading) {
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
                            {useV3 
                                ? `${totalItems.toLocaleString()} domains total` 
                                : `${filteredData.length} of ${domains.length} domains`}
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
                        
                        {/* Export dropdown */}
                        {useV3 && (
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="outline" size="sm" data-testid="export-btn">
                                        <Download className="h-4 w-4 mr-2" />
                                        Export
                                    </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent>
                                    <DropdownMenuItem onClick={() => handleExport('csv')}>
                                        <FileSpreadsheet className="h-4 w-4 mr-2" />
                                        Export as CSV
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={() => handleExport('json')}>
                                        <Download className="h-4 w-4 mr-2" />
                                        Export as JSON
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        )}
                        
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
                                        <TableHead>SEO Networks</TableHead>
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
                            {loading ? (
                                <TableSkeleton />
                            ) : filteredData.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={useV3 ? 8 : 8} className="h-32 text-center">
                                        <div className="empty-state py-8">
                                            <Globe className="empty-state-icon mx-auto" />
                                            <p className="empty-state-title">No domains found</p>
                                            <p className="empty-state-description">
                                                {totalItems === 0 
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
                                                    <SeoNetworksBadges networks={item.seo_networks || []} />
                                                </TableCell>
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

                {/* PAGINATION CONTROLS (V3 only) */}
                {useV3 && (
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 py-4 border-t border-border mt-4" data-testid="pagination-controls">
                        {/* Left: Showing X of Y */}
                        <div className="text-sm text-zinc-400">
                            {loading ? (
                                <Skeleton className="h-4 w-40" />
                            ) : (
                                <>
                                    Showing {((currentPage - 1) * pageSize) + 1} - {Math.min(currentPage * pageSize, totalItems)} of{' '}
                                    <span className="font-medium text-zinc-200">{totalItems.toLocaleString()}</span> domains
                                </>
                            )}
                        </div>
                        
                        {/* Center: Page navigation */}
                        <div className="flex items-center gap-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                disabled={currentPage === 1 || loading}
                                className="h-8"
                                data-testid="prev-page-btn"
                            >
                                <ChevronLeft className="h-4 w-4 mr-1" />
                                Prev
                            </Button>
                            
                            <div className="flex items-center gap-1 px-2">
                                <span className="text-sm text-zinc-400">Page</span>
                                <span className="text-sm font-medium text-zinc-200 px-2 py-1 bg-zinc-800 rounded">
                                    {currentPage}
                                </span>
                                <span className="text-sm text-zinc-400">of {totalPages}</span>
                            </div>
                            
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                disabled={currentPage >= totalPages || loading}
                                className="h-8"
                                data-testid="next-page-btn"
                            >
                                Next
                                <ChevronRight className="h-4 w-4 ml-1" />
                            </Button>
                        </div>
                        
                        {/* Right: Page size selector */}
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-zinc-400">Show</span>
                            <Select
                                value={pageSize.toString()}
                                onValueChange={(v) => setPageSize(parseInt(v))}
                            >
                                <SelectTrigger className="w-20 h-8 bg-black border-border" data-testid="page-size-select">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="25">25</SelectItem>
                                    <SelectItem value="50">50</SelectItem>
                                    <SelectItem value="100">100</SelectItem>
                                </SelectContent>
                            </Select>
                            <span className="text-sm text-zinc-400">per page</span>
                        </div>
                    </div>
                )}

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
                                            <Popover open={registrarSearchOpen} onOpenChange={setRegistrarSearchOpen}>
                                                <PopoverTrigger asChild>
                                                    <Button
                                                        variant="outline"
                                                        role="combobox"
                                                        aria-expanded={registrarSearchOpen}
                                                        className="w-full justify-between bg-black border-border"
                                                        data-testid="registrar-combobox"
                                                    >
                                                        {form.registrar_id
                                                            ? registrars.find((r) => r.id === form.registrar_id)?.name
                                                            : "Select registrar..."}
                                                        <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                                                    </Button>
                                                </PopoverTrigger>
                                                <PopoverContent className="w-[300px] p-0">
                                                    <Command>
                                                        <CommandInput placeholder="Search registrar..." />
                                                        <CommandList>
                                                            <CommandEmpty>No registrar found.</CommandEmpty>
                                                            <CommandGroup>
                                                                {registrars.map((registrar) => (
                                                                    <CommandItem
                                                                        key={registrar.id}
                                                                        value={registrar.name}
                                                                        onSelect={() => {
                                                                            setForm({...form, registrar_id: registrar.id});
                                                                            setRegistrarSearchOpen(false);
                                                                        }}
                                                                    >
                                                                        <Check
                                                                            className={cn(
                                                                                "mr-2 h-4 w-4",
                                                                                form.registrar_id === registrar.id ? "opacity-100" : "opacity-0"
                                                                            )}
                                                                        />
                                                                        {registrar.name}
                                                                    </CommandItem>
                                                                ))}
                                                            </CommandGroup>
                                                        </CommandList>
                                                    </Command>
                                                </PopoverContent>
                                            </Popover>
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
