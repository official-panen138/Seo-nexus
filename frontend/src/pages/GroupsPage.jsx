import { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { networksAPI, brandsAPI, assetDomainsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
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
    Filter,
    ArrowRight,
    ArrowLeft,
    Target,
    CheckCircle,
    Search,
    X,
    ExternalLink,
    TrendingUp,
    BarChart3,
    Activity,
    Lock,
    Users,
    AlertCircle,
    Clock,
    ShieldAlert,
    AlertTriangle,
    Archive,
    RefreshCw
} from 'lucide-react';
import { formatDate, debounce } from '../lib/utils';

export default function GroupsPage() {
    const { canEdit } = useAuth();
    const navigate = useNavigate();
    const [networks, setNetworks] = useState([]);
    const [brands, setBrands] = useState([]);
    const [domains, setDomains] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [selectedNetwork, setSelectedNetwork] = useState(null);
    
    // Search state
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [searchLoading, setSearchLoading] = useState(false);
    const [searchOpen, setSearchOpen] = useState(false);
    const [highlightedNetworkIds, setHighlightedNetworkIds] = useState([]);
    const searchInputRef = useRef(null);
    
    // Multi-step form state
    const [createStep, setCreateStep] = useState(1);
    const [form, setForm] = useState({ 
        name: '', 
        brand_id: '', 
        description: '',
        main_domain_id: '',
        main_path: ''
    });
    
    // Filtered domains based on selected brand
    const [brandDomains, setBrandDomains] = useState([]);
    
    // Domains already used as main nodes (without paths)
    const [usedMainDomainIds, setUsedMainDomainIds] = useState([]);
    
    // Filter state
    const [filterBrand, setFilterBrand] = useState('all');
    const [filterRankingStatus, setFilterRankingStatus] = useState('all');
    const [sortBy, setSortBy] = useState('default');
    
    // PHASE 6: View mode and archived networks
    const [viewMode, setViewMode] = useState('active'); // 'active' or 'archived'
    const [archivedNetworks, setArchivedNetworks] = useState([]);
    const [archivedLoading, setArchivedLoading] = useState(false);
    const { user } = useAuth();
    const isSuperAdmin = user?.role === 'super_admin';

    // Ranking status badge helper
    const getRankingStatusBadge = (status) => {
        switch (status) {
            case 'ranking':
                return { label: 'Ranking', className: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', icon: TrendingUp };
            case 'tracking':
                return { label: 'Tracking', className: 'bg-amber-500/20 text-amber-400 border-amber-500/30', icon: Activity };
            default:
                return { label: 'No Ranking', className: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30', icon: BarChart3 };
        }
    };

    // Manager summary badge helper
    const getManagerBadge = (network) => {
        const mode = network.visibility_mode || 'brand_based';
        const cache = network.manager_summary_cache || { count: 0, names: [] };
        
        switch (mode) {
            case 'restricted':
                return {
                    icon: Lock,
                    label: `Restricted`,
                    userCount: cache.count,
                    userNames: cache.names,
                    className: 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                };
            default:
                return {
                    icon: Users,
                    label: 'Brand Based',
                    userCount: cache.count > 0 ? cache.count : null,
                    userNames: cache.names,
                    className: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20'
                };
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    // Filter domains when brand changes - exclude domains already used as main nodes
    useEffect(() => {
        if (form.brand_id && domains.length > 0) {
            // Filter by brand AND exclude domains used as main nodes (without paths)
            const filtered = domains.filter(d => {
                // Must belong to selected brand
                if (d.brand_id !== form.brand_id) return false;
                
                // Exclude if used as main node without a path
                // (domains with paths can still be reused with different paths)
                if (usedMainDomainIds.includes(d.id)) return false;
                
                return true;
            });
            setBrandDomains(filtered);
            // Reset domain selection if not in filtered list
            if (form.main_domain_id && !filtered.find(d => d.id === form.main_domain_id)) {
                setForm(prev => ({ ...prev, main_domain_id: '' }));
            }
        } else {
            setBrandDomains([]);
        }
    }, [form.brand_id, domains, usedMainDomainIds]);

    const loadData = async () => {
        try {
            const [networksRes, brandsRes, eligibleRes] = await Promise.all([
                networksAPI.getAll(),
                brandsAPI.getAll(),
                assetDomainsAPI.getEligibleForSeo() // PHASE 1: Get only eligible domains
            ]);
            
            setNetworks(Array.isArray(networksRes.data) ? networksRes.data : networksRes.data?.data || []);
            setBrands(Array.isArray(brandsRes.data) ? brandsRes.data : brandsRes.data?.data || []);
            
            // PHASE 1: Use eligible domains (excludes Released, Not Renewed, Quarantined)
            const eligibleDomains = eligibleRes.data?.eligible_domains || [];
            const usedIds = eligibleRes.data?.used_as_main_ids || [];
            
            setDomains(eligibleDomains);
            setUsedMainDomainIds(usedIds);
            
        } catch (err) {
            console.error('Failed to load data:', err);
            toast.error('Failed to load networks');
        } finally {
            setLoading(false);
        }
    };

    // PHASE 6: Load archived networks
    const loadArchivedNetworks = async () => {
        setArchivedLoading(true);
        try {
            const response = await networksAPI.getArchived({ search: searchQuery || undefined });
            setArchivedNetworks(response.data?.data || response.data || []);
        } catch (err) {
            console.error('Failed to load archived networks:', err);
            toast.error('Failed to load archived networks');
            setArchivedNetworks([]);
        } finally {
            setArchivedLoading(false);
        }
    };

    // PHASE 6: Restore archived network
    const handleRestoreNetwork = async (network) => {
        if (!isSuperAdmin) {
            toast.error('Only Super Admin can restore archived networks');
            return;
        }
        setSaving(true);
        try {
            await networksAPI.restore(network.id);
            toast.success(`Network "${network.name}" restored successfully`);
            loadArchivedNetworks();
            loadData();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to restore network');
        } finally {
            setSaving(false);
        }
    };

    // Load archived networks when view mode changes
    useEffect(() => {
        if (viewMode === 'archived') {
            loadArchivedNetworks();
        }
    }, [viewMode]);

    // Debounced search function
    const performSearch = useCallback(
        debounce(async (query) => {
            if (!query || query.length < 1) {
                setSearchResults([]);
                setSearchLoading(false);
                return;
            }
            
            setSearchLoading(true);
            try {
                const response = await networksAPI.search(query);
                setSearchResults(response.data.results || []);
            } catch (err) {
                console.error('Search failed:', err);
                setSearchResults([]);
            } finally {
                setSearchLoading(false);
            }
        }, 350),
        []
    );
    
    // Handle search input change
    const handleSearchChange = (value) => {
        setSearchQuery(value);
        if (value.length >= 1) {
            setSearchOpen(true);
            performSearch(value);
        } else {
            setSearchResults([]);
            setSearchOpen(false);
            setHighlightedNetworkIds([]);
        }
    };
    
    // Handle selecting a search result
    const handleSelectSearchResult = (result, entry, action = 'filter') => {
        if (action === 'navigate') {
            // Navigate directly to network detail page
            navigate(`/groups/${entry.network_id}`);
        } else {
            // Filter/highlight networks in the list
            const networkIds = result.entries.map(e => e.network_id);
            setHighlightedNetworkIds(networkIds);
            setSearchOpen(false);
            toast.success(`Highlighting ${networkIds.length} network(s) containing "${result.domain_name}"`);
        }
    };
    
    // Clear search and highlights
    const clearSearch = () => {
        setSearchQuery('');
        setSearchResults([]);
        setSearchOpen(false);
        setHighlightedNetworkIds([]);
    };

    const openCreateDialog = () => {
        setSelectedNetwork(null);
        setCreateStep(1);
        setForm({ name: '', brand_id: '', description: '', main_domain_id: '', main_path: '' });
        setDialogOpen(true);
    };

    const openEditDialog = (network, e) => {
        e.preventDefault();
        e.stopPropagation();
        setSelectedNetwork(network);
        setForm({ 
            name: network.name, 
            brand_id: network.brand_id || '',
            description: network.description || '',
            main_domain_id: '',
            main_path: ''
        });
        setDialogOpen(true);
    };

    const handleNextStep = () => {
        if (createStep === 1) {
            if (!form.name.trim()) {
                toast.error('Network name is required');
                return;
            }
            if (!form.brand_id) {
                toast.error('Brand is required');
                return;
            }
            setCreateStep(2);
        }
    };

    const handlePrevStep = () => {
        if (createStep > 1) {
            setCreateStep(createStep - 1);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        // For edit mode - just update network
        if (selectedNetwork) {
            setSaving(true);
            try {
                await networksAPI.update(selectedNetwork.id, {
                    name: form.name,
                    brand_id: form.brand_id,
                    description: form.description
                });
                toast.success('Network updated');
                setDialogOpen(false);
                loadData();
            } catch (err) {
                toast.error(err.response?.data?.detail || 'Failed to update network');
            } finally {
                setSaving(false);
            }
            return;
        }
        
        // For create mode - validate main domain
        if (!form.main_domain_id) {
            toast.error('Main domain is required');
            return;
        }

        setSaving(true);
        try {
            const payload = {
                name: form.name,
                brand_id: form.brand_id,
                description: form.description,
                main_node: {
                    asset_domain_id: form.main_domain_id,
                    optimized_path: form.main_path || null
                }
            };
            
            const response = await networksAPI.create(payload);
            toast.success('Network created with main node');
            setDialogOpen(false);
            
            // Redirect to the new network's detail page
            navigate(`/groups/${response.data.id}`);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to create network');
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

    // Filter networks by brand and ranking status
    const filteredNetworks = networks.filter(n => {
        if (filterBrand !== 'all' && n.brand_id !== filterBrand) return false;
        if (filterRankingStatus !== 'all' && n.ranking_status !== filterRankingStatus) return false;
        return true;
    }).sort((a, b) => {
        // Apply sorting
        if (sortBy === 'best_position') {
            // Sort by best position (ascending), null values at end
            const posA = a.best_ranking_position ?? 999;
            const posB = b.best_ranking_position ?? 999;
            return posA - posB;
        } else if (sortBy === 'ranking_nodes') {
            // Sort by ranking nodes count (descending)
            return (b.ranking_nodes_count || 0) - (a.ranking_nodes_count || 0);
        }
        return 0; // Default: no sorting (default value)
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
                        
                        {/* Ranking Status Filter */}
                        <Select value={filterRankingStatus} onValueChange={setFilterRankingStatus}>
                            <SelectTrigger className="w-[160px] bg-black border-border" data-testid="ranking-filter">
                                <TrendingUp className="h-4 w-4 mr-2 opacity-50" />
                                <SelectValue placeholder="All Status" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Status</SelectItem>
                                <SelectItem value="ranking">
                                    <span className="flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                                        Ranking
                                    </span>
                                </SelectItem>
                                <SelectItem value="tracking">
                                    <span className="flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                                        Tracking
                                    </span>
                                </SelectItem>
                                <SelectItem value="none">
                                    <span className="flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-zinc-500"></span>
                                        No Ranking
                                    </span>
                                </SelectItem>
                            </SelectContent>
                        </Select>
                        
                        {/* Sort By */}
                        <Select value={sortBy} onValueChange={setSortBy}>
                            <SelectTrigger className="w-[180px] bg-black border-border" data-testid="sort-select">
                                <BarChart3 className="h-4 w-4 mr-2 opacity-50" />
                                <SelectValue placeholder="Sort by..." />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="default">Default</SelectItem>
                                <SelectItem value="best_position">Best Position</SelectItem>
                                <SelectItem value="ranking_nodes">Most Ranking Nodes</SelectItem>
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

                {/* PHASE 6: View Mode Tabs - Active vs Archived */}
                <Tabs value={viewMode} onValueChange={setViewMode} className="mb-6">
                    <TabsList className="bg-zinc-900">
                        <TabsTrigger value="active" data-testid="tab-active-networks">
                            <Network className="h-4 w-4 mr-2" />
                            Active Networks
                        </TabsTrigger>
                        <TabsTrigger value="archived" data-testid="tab-archived-networks" className="text-purple-400 data-[state=active]:text-purple-400">
                            <Archive className="h-4 w-4 mr-2" />
                            Archived
                        </TabsTrigger>
                    </TabsList>
                </Tabs>

                {/* Domain Search with Auto-suggest - Only for active view */}
                {viewMode === 'active' && (
                <div className="mb-6">
                    <Popover open={searchOpen && searchResults.length > 0} onOpenChange={setSearchOpen}>
                        <PopoverTrigger asChild>
                            <div className="relative max-w-md">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                                <Input
                                    ref={searchInputRef}
                                    value={searchQuery}
                                    onChange={(e) => handleSearchChange(e.target.value)}
                                    onFocus={() => searchResults.length > 0 && setSearchOpen(true)}
                                    placeholder="Search domains or paths..."
                                    className="pl-10 pr-10 bg-card border-border"
                                    data-testid="domain-search-input"
                                />
                                {searchLoading && (
                                    <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-zinc-500" />
                                )}
                                {searchQuery && !searchLoading && (
                                    <button
                                        onClick={clearSearch}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white"
                                    >
                                        <X className="h-4 w-4" />
                                    </button>
                                )}
                            </div>
                        </PopoverTrigger>
                        <PopoverContent className="w-[400px] p-0" align="start">
                            <div className="max-h-[300px] overflow-y-auto">
                                {searchResults.map((result) => (
                                    <div key={result.asset_domain_id} className="border-b border-border last:border-b-0">
                                        <div className="px-4 py-2 bg-zinc-900/50">
                                            <span className="font-mono text-sm text-white">{result.domain_name}</span>
                                        </div>
                                        <div className="divide-y divide-border/50">
                                            {result.entries.map((entry, idx) => (
                                                <div 
                                                    key={entry.entry_id || idx}
                                                    className="px-4 py-2 hover:bg-zinc-800/50 cursor-pointer flex items-center justify-between gap-2"
                                                    onClick={() => handleSelectSearchResult(result, entry, 'filter')}
                                                    data-testid={`search-result-${entry.network_id}`}
                                                >
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-mono text-xs text-zinc-400">
                                                                {entry.optimized_path}
                                                            </span>
                                                            <span className="text-zinc-500">→</span>
                                                            <span className={`text-xs px-1.5 py-0.5 rounded ${
                                                                entry.role === 'main' 
                                                                    ? 'bg-green-500/10 text-green-400' 
                                                                    : 'bg-purple-500/10 text-purple-400'
                                                            }`}>
                                                                {entry.role === 'main' ? 'Main' : 'Support'}
                                                            </span>
                                                        </div>
                                                        <div className="text-sm text-zinc-300 truncate mt-0.5">
                                                            {entry.network_name}
                                                        </div>
                                                    </div>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="h-7 px-2 text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleSelectSearchResult(result, entry, 'navigate');
                                                        }}
                                                        data-testid={`navigate-to-${entry.network_id}`}
                                                    >
                                                        <ExternalLink className="h-3 w-3 mr-1" />
                                                        Open
                                                    </Button>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </PopoverContent>
                    </Popover>
                    
                    {/* Highlight indicator */}
                    {highlightedNetworkIds.length > 0 && (
                        <div className="mt-2 flex items-center gap-2 text-sm text-amber-400">
                            <Badge variant="outline" className="text-amber-400 border-amber-400/30">
                                {highlightedNetworkIds.length} highlighted
                            </Badge>
                            <button
                                onClick={clearSearch}
                                className="text-zinc-500 hover:text-white underline"
                            >
                                Clear filter
                            </button>
                        </div>
                    )}
                </div>
                )}

                {/* Networks Grid - Active View */}
                {viewMode === 'active' && (
                <>
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
                        {filteredNetworks.map((network, index) => {
                            const isHighlighted = highlightedNetworkIds.includes(network.id);
                            const rankingBadge = getRankingStatusBadge(network.ranking_status);
                            const RankingIcon = rankingBadge.icon;
                            const managerBadge = getManagerBadge(network);
                            const ManagerIcon = managerBadge.icon;
                            return (
                            <Link 
                                key={network.id} 
                                to={`/groups/${network.id}`}
                                className={`animate-fade-in stagger-${(index % 5) + 1}`}
                                data-testid={`network-card-${network.id}`}
                            >
                                <Card className={`bg-card border-border card-hover h-full transition-all ${
                                    isHighlighted 
                                        ? 'ring-2 ring-amber-400 border-amber-400/50' 
                                        : highlightedNetworkIds.length > 0 
                                            ? 'opacity-40' 
                                            : network.ranking_status === 'ranking'
                                                ? 'border-emerald-500/30'
                                                : ''
                                }`}>
                                    <CardHeader className="pb-3">
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className={`p-2 rounded-md ${
                                                    isHighlighted ? 'bg-amber-500/20' 
                                                        : network.ranking_status === 'ranking' ? 'bg-emerald-500/10'
                                                        : 'bg-purple-500/10'
                                                }`}>
                                                    <Network className={`h-5 w-5 ${
                                                        network.ranking_status === 'ranking' ? 'text-emerald-500' : 'text-purple-500'
                                                    }`} />
                                                </div>
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <CardTitle className="text-base">{network.name}</CardTitle>
                                                        {/* Ranking Status Badge */}
                                                        <Badge className={`text-[10px] px-1.5 py-0 ${rankingBadge.className}`} data-testid={`ranking-badge-${network.id}`}>
                                                            <RankingIcon className="h-3 w-3 mr-1" />
                                                            {rankingBadge.label}
                                                        </Badge>
                                                    </div>
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
                                        
                                        {/* Manager Summary Badge */}
                                        <div className={`flex items-center gap-2 p-2 rounded-md mb-3 ${managerBadge.className}`} data-testid={`manager-badge-${network.id}`}>
                                            <ManagerIcon className="h-4 w-4 flex-shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <span className="text-xs font-medium">{managerBadge.label}</span>
                                                {managerBadge.userCount !== null && managerBadge.userCount > 0 && (
                                                    <span className="text-xs ml-1">· {managerBadge.userCount} manager{managerBadge.userCount !== 1 ? 's' : ''}</span>
                                                )}
                                                {/* Open Complaints Badge */}
                                                {network.open_complaints_count > 0 && (
                                                    <span className="text-xs ml-2 text-red-400 font-medium">
                                                        · {network.open_complaints_count} complaint{network.open_complaints_count !== 1 ? 's' : ''}
                                                    </span>
                                                )}
                                                {managerBadge.userNames && managerBadge.userNames.length > 0 && (
                                                    <div className="text-[10px] opacity-80 truncate">
                                                        {managerBadge.userNames.slice(0, 2).join(', ')}
                                                        {managerBadge.userCount > 2 && ` +${managerBadge.userCount - 2}`}
                                                    </div>
                                                )}
                                            </div>
                                            {/* Complaints Alert Icon */}
                                            {network.open_complaints_count > 0 && (
                                                <div className="flex items-center" title={`${network.open_complaints_count} open complaint${network.open_complaints_count !== 1 ? 's' : ''}`}>
                                                    <AlertCircle className="h-4 w-4 text-red-400" />
                                                </div>
                                            )}
                                        </div>
                                        
                                        {/* Main domain indicator */}
                                        {network.main_domain_name && (
                                            <div className="flex items-center gap-2 text-xs text-green-500 mb-2">
                                                <Target className="h-3 w-3" />
                                                <span className="font-mono">{network.main_domain_name}</span>
                                            </div>
                                        )}
                                        
                                        <div className="flex items-center justify-between text-sm">
                                            <div className="flex items-center gap-2 text-zinc-400">
                                                <Globe className="h-4 w-4" />
                                                <span>{network.domain_count || 0} node{network.domain_count !== 1 ? 's' : ''}</span>
                                            </div>
                                            <div className="flex items-center gap-1 text-blue-500">
                                                <Eye className="h-4 w-4" />
                                                <span>View</span>
                                            </div>
                                        </div>
                                        
                                        {/* Domain Health Indicators */}
                                        {(network.expired_domains_count > 0 || network.quarantined_domains_count > 0) && (
                                            <div className="mt-2 flex items-center gap-3">
                                                {network.expired_domains_count > 0 && (
                                                    <div 
                                                        className="flex items-center gap-1 text-xs text-red-400 px-2 py-1 bg-red-500/10 rounded-md" 
                                                        title={`${network.expired_domains_count} expired domain${network.expired_domains_count !== 1 ? 's' : ''}`}
                                                        data-testid={`expired-indicator-${network.id}`}
                                                    >
                                                        <AlertTriangle className="h-3 w-3" />
                                                        <span>{network.expired_domains_count} expired</span>
                                                    </div>
                                                )}
                                                {network.quarantined_domains_count > 0 && (
                                                    <div 
                                                        className="flex items-center gap-1 text-xs text-orange-400 px-2 py-1 bg-orange-500/10 rounded-md" 
                                                        title={`${network.quarantined_domains_count} quarantined domain${network.quarantined_domains_count !== 1 ? 's' : ''}`}
                                                        data-testid={`quarantined-indicator-${network.id}`}
                                                    >
                                                        <ShieldAlert className="h-3 w-3" />
                                                        <span>{network.quarantined_domains_count} quarantined</span>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                        
                                        {/* Ranking Mini Metrics */}
                                        {(network.ranking_nodes_count > 0 || network.tracked_urls_count > 0) && (
                                            <div className="mt-3 pt-3 border-t border-border flex items-center gap-4 text-xs">
                                                {network.ranking_nodes_count > 0 && (
                                                    <div className="flex items-center gap-1 text-emerald-400" title="Nodes with ranking position">
                                                        <TrendingUp className="h-3 w-3" />
                                                        <span>{network.ranking_nodes_count} ranking</span>
                                                    </div>
                                                )}
                                                {network.best_ranking_position && (
                                                    <div className="flex items-center gap-1 text-amber-400" title="Best ranking position">
                                                        <span className="font-semibold">#{network.best_ranking_position}</span>
                                                    </div>
                                                )}
                                                {network.tracked_urls_count > 0 && (
                                                    <div className="flex items-center gap-1 text-zinc-400" title="Tracked URLs">
                                                        <Activity className="h-3 w-3" />
                                                        <span>{network.tracked_urls_count} tracked</span>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                        
                                        <div className="mt-3 pt-3 border-t border-border flex items-center justify-between">
                                            <span className="text-xs text-zinc-600">
                                                Created {formatDate(network.created_at)}
                                            </span>
                                            {network.last_optimization_at && (
                                                <span className="text-xs text-zinc-500 flex items-center gap-1" title="Last optimization activity">
                                                    <Clock className="h-3 w-3" />
                                                    Last activity {formatDate(network.last_optimization_at)}
                                                </span>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            </Link>
                        );
                        })}
                    </div>
                )}
                </>
                )}

                {/* PHASE 6: Archived Networks View */}
                {viewMode === 'archived' && (
                    <div className="space-y-4">
                        {archivedLoading ? (
                            <div className="flex items-center justify-center h-48">
                                <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
                            </div>
                        ) : archivedNetworks.length === 0 ? (
                            <div className="empty-state mt-16">
                                <Archive className="empty-state-icon text-purple-500" />
                                <p className="empty-state-title">No archived networks</p>
                                <p className="empty-state-description">
                                    Deleted networks will appear here for recovery
                                </p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="archived-networks-grid">
                                {archivedNetworks.map((network, index) => (
                                    <Card 
                                        key={network.id} 
                                        className={`bg-card border-border border-purple-500/30 h-full animate-fade-in stagger-${(index % 5) + 1}`}
                                        data-testid={`archived-network-card-${network.id}`}
                                    >
                                        <CardHeader className="pb-3">
                                            <div className="flex items-start justify-between">
                                                <div className="flex items-center gap-3">
                                                    <div className="p-2 rounded-md bg-purple-500/10">
                                                        <Archive className="h-5 w-5 text-purple-500" />
                                                    </div>
                                                    <div>
                                                        <CardTitle className="text-base text-zinc-400">{network.name}</CardTitle>
                                                        {network.brand_name && (
                                                            <Badge variant="outline" className="mt-1 text-xs text-zinc-500">
                                                                <Tag className="h-3 w-3 mr-1" />
                                                                {network.brand_name}
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </div>
                                                <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/30">
                                                    Archived
                                                </Badge>
                                            </div>
                                        </CardHeader>
                                        <CardContent className="pt-0">
                                            <div className="space-y-2 text-sm text-zinc-500">
                                                <div className="flex items-center gap-2">
                                                    <Clock className="h-4 w-4" />
                                                    <span>
                                                        Archived: {network.deleted_at 
                                                            ? formatDate(network.deleted_at) 
                                                            : 'Unknown'}
                                                    </span>
                                                </div>
                                                {network.description && (
                                                    <p className="text-xs text-zinc-600 mt-2">{network.description}</p>
                                                )}
                                            </div>
                                            
                                            {/* Restore button - Super Admin only */}
                                            {isSuperAdmin && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    className="w-full mt-4 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                                                    onClick={() => handleRestoreNetwork(network)}
                                                    disabled={saving}
                                                    data-testid={`restore-network-${network.id}`}
                                                >
                                                    {saving ? (
                                                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                    ) : (
                                                        <RefreshCw className="h-4 w-4 mr-2" />
                                                    )}
                                                    Restore Network
                                                </Button>
                                            )}
                                            
                                            {!isSuperAdmin && (
                                                <p className="text-xs text-zinc-600 mt-4 text-center">
                                                    Only Super Admin can restore archived networks
                                                </p>
                                            )}
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Multi-Step Create / Edit Dialog */}
                <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-lg">
                        <DialogHeader>
                            <DialogTitle>
                                {selectedNetwork ? 'Edit Network' : (
                                    createStep === 1 ? 'Create Network - Step 1' : 'Create Network - Step 2'
                                )}
                            </DialogTitle>
                            <DialogDescription>
                                {selectedNetwork 
                                    ? 'Update network details below.' 
                                    : createStep === 1 
                                        ? 'Define network name, brand, and description.'
                                        : 'Configure the main (money) node for this network.'}
                            </DialogDescription>
                        </DialogHeader>
                        
                        {/* Step Indicator for Create mode */}
                        {!selectedNetwork && (
                            <div className="flex items-center justify-center gap-2 py-2">
                                <div className={`flex items-center gap-1 px-3 py-1 rounded-full text-sm ${createStep === 1 ? 'bg-blue-500/20 text-blue-400' : 'bg-zinc-800 text-zinc-500'}`}>
                                    <span>1</span>
                                    <span className="hidden sm:inline">Network Info</span>
                                </div>
                                <ArrowRight className="h-4 w-4 text-zinc-600" />
                                <div className={`flex items-center gap-1 px-3 py-1 rounded-full text-sm ${createStep === 2 ? 'bg-blue-500/20 text-blue-400' : 'bg-zinc-800 text-zinc-500'}`}>
                                    <span>2</span>
                                    <span className="hidden sm:inline">Main Node</span>
                                </div>
                            </div>
                        )}

                        <form onSubmit={handleSubmit} className="space-y-4">
                            {/* Step 1: Network Info (always visible for edit, step 1 for create) */}
                            {(selectedNetwork || createStep === 1) && (
                                <>
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
                                            disabled={selectedNetwork}
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
                                        {!selectedNetwork && (
                                            <p className="text-xs text-zinc-500">
                                                Only domains from this brand will be available for selection.
                                            </p>
                                        )}
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
                                </>
                            )}

                            {/* Step 2: Main Node Config (create mode only) */}
                            {!selectedNetwork && createStep === 2 && (
                                <>
                                    <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                                        <div className="flex items-center gap-2 text-green-400 mb-2">
                                            <Target className="h-5 w-5" />
                                            <span className="font-medium">Main Node Configuration</span>
                                        </div>
                                        <p className="text-sm text-zinc-400">
                                            Every SEO Network requires a main (money) node. This is the primary target for your link building strategy.
                                        </p>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <Label>Main Asset Domain *</Label>
                                        <Select 
                                            value={form.main_domain_id} 
                                            onValueChange={(v) => setForm({...form, main_domain_id: v})}
                                        >
                                            <SelectTrigger className="bg-black border-border" data-testid="main-domain-select">
                                                <SelectValue placeholder="Select main domain..." />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {brandDomains.length === 0 ? (
                                                    <div className="p-2 text-sm text-zinc-500">
                                                        No domains found for this brand
                                                    </div>
                                                ) : (
                                                    brandDomains.map(d => (
                                                        <SelectItem key={d.id} value={d.id}>
                                                            {d.domain_name}
                                                        </SelectItem>
                                                    ))
                                                )}
                                            </SelectContent>
                                        </Select>
                                        <p className="text-xs text-zinc-500">
                                            Only domains belonging to "{brands.find(b => b.id === form.brand_id)?.name}" are shown.
                                        </p>
                                    </div>

                                    <div className="space-y-2">
                                        <Label>Optimized Path (optional)</Label>
                                        <Input
                                            value={form.main_path}
                                            onChange={(e) => setForm({...form, main_path: e.target.value})}
                                            placeholder="/best-product or leave empty for root"
                                            className="bg-black border-border font-mono"
                                            data-testid="main-path-input"
                                        />
                                        <p className="text-xs text-zinc-500">
                                            Leave empty to target the root domain (/). Enter a path for page-level targeting.
                                        </p>
                                    </div>
                                </>
                            )}

                            <DialogFooter className="flex gap-2">
                                {/* Back button for step 2 */}
                                {!selectedNetwork && createStep === 2 && (
                                    <Button
                                        type="button"
                                        variant="outline"
                                        onClick={handlePrevStep}
                                    >
                                        <ArrowLeft className="h-4 w-4 mr-2" />
                                        Back
                                    </Button>
                                )}
                                
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => setDialogOpen(false)}
                                >
                                    Cancel
                                </Button>
                                
                                {/* Next or Submit button */}
                                {!selectedNetwork && createStep === 1 ? (
                                    <Button
                                        type="button"
                                        onClick={handleNextStep}
                                        className="bg-white text-black hover:bg-zinc-200"
                                    >
                                        Next
                                        <ArrowRight className="h-4 w-4 ml-2" />
                                    </Button>
                                ) : (
                                    <Button
                                        type="submit"
                                        disabled={saving}
                                        className="bg-white text-black hover:bg-zinc-200"
                                        data-testid="save-network-btn"
                                    >
                                        {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                        {selectedNetwork ? 'Update' : (
                                            <>
                                                <CheckCircle className="h-4 w-4 mr-2" />
                                                Create Network
                                            </>
                                        )}
                                    </Button>
                                )}
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
                            Are you sure you want to delete <span className="text-white font-medium">{selectedNetwork?.name}</span>?
                            All nodes will be removed from this network.
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
