import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { groupsAPI, networksAPI, structureAPI, assetDomainsAPI, exportAPI, importAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { NetworkGraph } from '../components/NetworkGraph';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../components/ui/sheet';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { Switch } from '../components/ui/switch';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../components/ui/dropdown-menu';
import { toast } from 'sonner';
import { 
    ArrowLeft, 
    Loader2, 
    Globe,
    ExternalLink,
    Network,
    AlertTriangle,
    RefreshCw,
    Edit,
    TrendingUp,
    Target,
    Search,
    Download,
    Upload,
    FileSpreadsheet,
    Plus,
    Trash2
} from 'lucide-react';
import { 
    TIER_LABELS, 
    STATUS_LABELS, 
    INDEX_STATUS_LABELS, 
    getTierBadgeClass, 
    TIER_COLORS,
    formatDate 
} from '../lib/utils';

// V3 tier colors
const V3_TIER_COLORS = {
    0: '#F97316',
    1: '#EAB308',
    2: '#22C55E',
    3: '#3B82F6',
    4: '#8B5CF6',
    5: '#6B7280'
};

// SEO Status options
const SEO_STATUS_OPTIONS = [
    { value: 'canonical', label: 'Canonical' },
    { value: '301_redirect', label: '301 Redirect' },
    { value: '302_redirect', label: '302 Redirect' },
    { value: 'restore', label: 'Restore' }
];

const INDEX_OPTIONS = [
    { value: 'index', label: 'Index' },
    { value: 'noindex', label: 'Noindex' }
];

const ROLE_OPTIONS = [
    { value: 'main', label: 'Main (Money Site)' },
    { value: 'supporting', label: 'Supporting' }
];

export default function GroupDetailPage() {
    const { groupId } = useParams();
    const navigate = useNavigate();
    const [network, setNetwork] = useState(null);
    const [tierData, setTierData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedEntry, setSelectedEntry] = useState(null);
    const [sheetOpen, setSheetOpen] = useState(false);
    const [useV3, setUseV3] = useState(true);
    
    // Edit dialog state
    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [editForm, setEditForm] = useState({
        domain_role: 'supporting',
        domain_status: 'canonical',
        index_status: 'index',
        optimized_path: '',
        target_entry_id: '',
        target_asset_domain_id: '',
        ranking_url: '',
        primary_keyword: '',
        ranking_position: '',
        notes: '',
        change_note: ''  // Required for SEO change logging
    });
    const [saving, setSaving] = useState(false);
    const [availableTargets, setAvailableTargets] = useState([]);
    
    // Delete confirmation state
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [entryToDelete, setEntryToDelete] = useState(null);
    const [deleting, setDeleting] = useState(false);
    const [deleteChangeNote, setDeleteChangeNote] = useState('');  // Required for delete
    
    // Add node state
    const [addNodeDialogOpen, setAddNodeDialogOpen] = useState(false);
    const [availableDomains, setAvailableDomains] = useState([]);
    const [addNodeForm, setAddNodeForm] = useState({
        asset_domain_id: '',
        optimized_path: '',
        domain_role: 'supporting',
        target_entry_id: '',
        change_note: ''  // Required for SEO change logging
    });
    
    // Import dialog state
    const [importDialogOpen, setImportDialogOpen] = useState(false);
    const [importData, setImportData] = useState([]);
    const [importing, setImporting] = useState(false);
    const [createMissingDomains, setCreateMissingDomains] = useState(false);
    const fileInputRef = useRef(null);

    useEffect(() => {
        loadNetwork();
    }, [groupId]);

    // Load available target entries (nodes) for the network
    const loadAvailableTargets = async (networkId, currentEntryId) => {
        try {
            // Use API to get available targets (brand-scoped, same network only)
            const { data } = await networksAPI.getAvailableTargets(networkId, currentEntryId);
            setAvailableTargets(data);
        } catch (err) {
            console.error('Failed to load targets:', err);
            // Fallback to local filter
            const networkEntries = network?.entries || [];
            const targets = networkEntries.filter(e => e.id !== currentEntryId);
            setAvailableTargets(targets);
        }
    };
    
    // Load available domains (brand-scoped) for adding nodes
    const loadAvailableDomains = async (networkId) => {
        try {
            const { data } = await networksAPI.getAvailableDomains(networkId);
            setAvailableDomains(data);
        } catch (err) {
            console.error('Failed to load available domains:', err);
        }
    };

    // Export network structure
    const handleExport = async (format) => {
        if (!network?.id) return;
        try {
            toast.info(`Exporting network as ${format.toUpperCase()}...`);
            const response = await exportAPI.network(network.id, format);
            
            if (format === 'csv') {
                const blob = new Blob([response.data], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `network_${network.name.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.csv`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                toast.success('CSV exported');
            } else {
                const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `network_${network.name.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.json`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                toast.success(`JSON exported (${response.data.total_entries} entries)`);
            }
        } catch (err) {
            toast.error('Export failed');
            console.error(err);
        }
    };

    // Import nodes - parse CSV
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
                        optimized_path: values[headers.indexOf('optimized_path')] || '',
                        domain_role: values[headers.indexOf('domain_role')] || 'supporting',
                        domain_status: values[headers.indexOf('domain_status')] || 'canonical',
                        index_status: values[headers.indexOf('index_status')] || 'index',
                        target_domain: values[headers.indexOf('target_domain')] || '',
                        target_path: values[headers.indexOf('target_path')] || '',
                        primary_keyword: values[headers.indexOf('primary_keyword')] || '',
                        notes: values[headers.indexOf('notes')] || ''
                    });
                }
            }
            
            setImportData(data);
            toast.success(`Parsed ${data.length} nodes from CSV`);
        };
        reader.readAsText(file);
    };

    // Execute import
    const handleImportSubmit = async () => {
        if (!network?.id || importData.length === 0) return;
        
        setImporting(true);
        try {
            const response = await importAPI.nodes({
                network_id: network.id,
                nodes: importData,
                create_missing_domains: createMissingDomains
            });
            
            const { summary } = response.data;
            toast.success(`Imported ${summary.imported} nodes (${summary.skipped} skipped, ${summary.errors} errors)`);
            
            if (summary.domains_created > 0) {
                toast.info(`${summary.domains_created} new domains created`);
            }
            
            setImportDialogOpen(false);
            setImportData([]);
            loadNetwork();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Import failed');
        } finally {
            setImporting(false);
        }
    };

    const loadNetwork = async () => {
        setLoading(true);
        try {
            // Try V3 API first (uses legacy_id mapping)
            const v3Networks = await networksAPI.getAll();
            const v3Network = v3Networks.data.find(n => n.legacy_id === groupId || n.id === groupId);
            
            if (v3Network) {
                // Found V3 network - load with tiers
                const [networkRes, tiersRes] = await Promise.all([
                    networksAPI.getOne(v3Network.id),
                    networksAPI.getTiers(v3Network.id)
                ]);
                setNetwork(networkRes.data);
                setTierData(tiersRes.data);
                setUseV3(true);
            } else {
                // Fallback to V2 API
                const res = await groupsAPI.getOne(groupId);
                setNetwork(res.data);
                setUseV3(false);
            }
        } catch (err) {
            console.error('Failed to load network:', err);
            toast.error('Failed to load network');
            navigate('/groups');
        } finally {
            setLoading(false);
        }
    };

    const handleNodeClick = (node) => {
        setSelectedEntry(node);
        setSheetOpen(true);
    };

    // Open edit dialog for a structure entry
    const openEditDialog = (entry) => {
        setSelectedEntry(entry);
        setEditForm({
            domain_role: entry.domain_role || 'supporting',
            domain_status: entry.domain_status || 'canonical',
            index_status: entry.index_status || 'index',
            optimized_path: entry.optimized_path || '',
            target_entry_id: entry.target_entry_id || '',
            target_asset_domain_id: entry.target_asset_domain_id || '',
            ranking_url: entry.ranking_url || '',
            primary_keyword: entry.primary_keyword || '',
            ranking_position: entry.ranking_position || '',
            notes: entry.notes || ''
        });
        loadAvailableTargets(network?.id, entry.id);
        setEditDialogOpen(true);
    };

    // Save structure entry changes
    const handleSaveEntry = async () => {
        if (!selectedEntry?.id) return;
        
        setSaving(true);
        try {
            const payload = {
                domain_role: editForm.domain_role,
                domain_status: editForm.domain_status,
                index_status: editForm.index_status,
                optimized_path: editForm.optimized_path || null,
                target_entry_id: editForm.target_entry_id || null,
                target_asset_domain_id: editForm.target_asset_domain_id || null,
                ranking_url: editForm.ranking_url || null,
                primary_keyword: editForm.primary_keyword || null,
                ranking_position: editForm.ranking_position ? parseInt(editForm.ranking_position) : null,
                notes: editForm.notes || null
            };
            
            await structureAPI.update(selectedEntry.id, payload);
            toast.success('Structure entry updated');
            setEditDialogOpen(false);
            loadNetwork(); // Refresh data
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to update entry');
        } finally {
            setSaving(false);
        }
    };

    // Open delete confirmation dialog
    const openDeleteDialog = (entry) => {
        setEntryToDelete(entry);
        setDeleteDialogOpen(true);
    };

    // Delete node handler
    const handleDeleteNode = async () => {
        if (!entryToDelete?.id) return;
        
        setDeleting(true);
        try {
            const response = await structureAPI.delete(entryToDelete.id);
            
            if (response.data.orphaned_entries > 0) {
                toast.warning(`Node deleted. ${response.data.orphaned_entries} entries are now orphaned.`);
            } else {
                toast.success('Node deleted');
            }
            
            setDeleteDialogOpen(false);
            setEntryToDelete(null);
            loadNetwork(); // Refresh data
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to delete node');
        } finally {
            setDeleting(false);
        }
    };

    // Open add node dialog
    const openAddNodeDialog = () => {
        setAddNodeForm({
            asset_domain_id: '',
            optimized_path: '',
            domain_role: 'supporting',
            target_entry_id: ''
        });
        loadAvailableDomains(network?.id);
        loadAvailableTargets(network?.id, null);
        setAddNodeDialogOpen(true);
    };

    // Add node handler
    const handleAddNode = async () => {
        if (!addNodeForm.asset_domain_id) {
            toast.error('Please select a domain');
            return;
        }
        
        setSaving(true);
        try {
            await structureAPI.create({
                network_id: network.id,
                asset_domain_id: addNodeForm.asset_domain_id,
                optimized_path: addNodeForm.optimized_path || null,
                domain_role: addNodeForm.domain_role,
                target_entry_id: addNodeForm.target_entry_id || null
            });
            
            toast.success('Node added to network');
            setAddNodeDialogOpen(false);
            loadNetwork();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to add node');
        } finally {
            setSaving(false);
        }
    };

    // Calculate stats based on V3 or V2 data
    const stats = (() => {
        if (useV3 && network?.entries) {
            const entries = network.entries;
            return {
                total: entries.length,
                indexed: entries.filter(e => e.index_status === 'index').length,
                orphans: tierData?.issues?.orphans?.length || 0,
                main: entries.filter(e => e.domain_role === 'main').length,
                tierDistribution: tierData?.distribution || {}
            };
        } else if (network?.domains) {
            return {
                total: network.domains.length,
                indexed: network.domains.filter(d => d.index_status === 'index').length,
                orphans: network.domains.filter(d => d.tier_level !== 'lp_money_site' && !d.parent_domain_id).length,
                main: network.domains.filter(d => d.tier_level === 'lp_money_site').length,
                tierDistribution: network.domains.reduce((acc, d) => {
                    const label = TIER_LABELS[d.tier_level] || 'Unknown';
                    acc[label] = (acc[label] || 0) + 1;
                    return acc;
                }, {})
            };
        }
        return null;
    })();

    // Get entries/domains for display
    const displayData = useV3 ? network?.entries : network?.domains;

    if (loading) {
        return (
            <Layout>
                <div className="flex items-center justify-center h-96">
                    <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
                </div>
            </Layout>
        );
    }

    if (!network) {
        return (
            <Layout>
                <div className="text-center py-16">
                    <p className="text-zinc-400">Network not found</p>
                </div>
            </Layout>
        );
    }

    return (
        <Layout>
            <div data-testid="group-detail-page">
                {/* Header */}
                <div className="page-header">
                    <Button
                        variant="ghost"
                        onClick={() => navigate('/groups')}
                        className="mb-4 text-zinc-400 hover:text-white"
                        data-testid="back-btn"
                    >
                        <ArrowLeft className="h-4 w-4 mr-2" />
                        Back to Networks
                    </Button>
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div>
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-md bg-purple-500/10">
                                    <Network className="h-6 w-6 text-purple-500" />
                                </div>
                                <h1 className="page-title">{network.name}</h1>
                                {useV3 && (
                                    <Badge variant="outline" className="text-emerald-400 border-emerald-400/30">
                                        V3
                                    </Badge>
                                )}
                            </div>
                            {network.description && (
                                <p className="page-subtitle mt-2">{network.description}</p>
                            )}
                        </div>
                        <div className="flex items-center gap-2">
                            {/* Export dropdown */}
                            {useV3 && (
                                <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                        <Button variant="outline" size="sm" data-testid="export-network-btn">
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
                            
                            {/* Import nodes */}
                            {useV3 && (
                                <Button 
                                    variant="outline" 
                                    size="sm"
                                    onClick={() => setImportDialogOpen(true)}
                                    data-testid="import-nodes-btn"
                                >
                                    <Upload className="h-4 w-4 mr-2" />
                                    Import Nodes
                                </Button>
                            )}
                            
                            {/* Add Node Button */}
                            {useV3 && (
                                <Button 
                                    variant="outline" 
                                    size="sm"
                                    onClick={openAddNodeDialog}
                                    className="bg-green-500/10 border-green-500/30 text-green-400 hover:bg-green-500/20"
                                    data-testid="add-node-btn"
                                >
                                    <Plus className="h-4 w-4 mr-2" />
                                    Add Node
                                </Button>
                            )}
                            
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={loadNetwork}
                                className="text-zinc-400"
                            >
                                <RefreshCw className="h-4 w-4 mr-2" />
                                Refresh
                            </Button>
                        </div>
                    </div>
                </div>

                {/* Stats */}
                {stats && (
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
                        <Card className="bg-card border-border">
                            <CardContent className="pt-4">
                                <div className="text-sm text-zinc-500 mb-1">Total Nodes</div>
                                <div className="text-2xl font-bold font-mono">{stats.total}</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-card border-border">
                            <CardContent className="pt-4">
                                <div className="text-sm text-zinc-500 mb-1">Main Nodes</div>
                                <div className="text-2xl font-bold font-mono text-orange-500">{stats.main}</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-card border-border">
                            <CardContent className="pt-4">
                                <div className="text-sm text-zinc-500 mb-1">Indexed</div>
                                <div className="text-2xl font-bold font-mono text-emerald-500">
                                    {stats.indexed}
                                    <span className="text-sm font-normal text-zinc-500 ml-1">
                                        ({stats.total > 0 ? Math.round(stats.indexed / stats.total * 100) : 0}%)
                                    </span>
                                </div>
                            </CardContent>
                        </Card>
                        <Card className="bg-card border-border">
                            <CardContent className="pt-4">
                                <div className="text-sm text-zinc-500 mb-1">Noindex</div>
                                <div className="text-2xl font-bold font-mono text-zinc-400">
                                    {stats.total - stats.indexed}
                                </div>
                            </CardContent>
                        </Card>
                        <Card className={`border-border ${stats.orphans > 0 ? 'bg-red-950/20 border-red-900/50' : 'bg-card'}`}>
                            <CardContent className="pt-4">
                                <div className="text-sm text-zinc-500 mb-1 flex items-center gap-1">
                                    {stats.orphans > 0 && <AlertTriangle className="h-3 w-3 text-red-500" />}
                                    Orphans
                                </div>
                                <div className={`text-2xl font-bold font-mono ${stats.orphans > 0 ? 'text-red-500' : 'text-zinc-400'}`}>
                                    {stats.orphans}
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                )}

                {/* Tier Distribution (V3) */}
                {useV3 && stats?.tierDistribution && Object.keys(stats.tierDistribution).length > 0 && (
                    <Card className="bg-card border-border mb-6">
                        <CardContent className="pt-4">
                            <div className="text-sm text-zinc-500 mb-3">Tier Distribution (Derived)</div>
                            <div className="flex flex-wrap gap-3">
                                {Object.entries(stats.tierDistribution).map(([tier, count]) => (
                                    <div key={tier} className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 rounded-md">
                                        <div 
                                            className="w-2 h-2 rounded-full" 
                                            style={{ backgroundColor: V3_TIER_COLORS[tier === 'LP/Money Site' ? 0 : parseInt(tier.replace(/[^0-9]/g, '')) || 5] }}
                                        />
                                        <span className="text-sm text-zinc-300">{tier}</span>
                                        <span className="text-sm font-mono text-white">{count}</span>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Tabs */}
                <Tabs defaultValue="graph" className="space-y-4">
                    <TabsList className="bg-card border border-border">
                        <TabsTrigger value="graph" data-testid="graph-tab">Visual Graph</TabsTrigger>
                        <TabsTrigger value="list" data-testid="list-tab">Domain List</TabsTrigger>
                    </TabsList>

                    {/* Graph View */}
                    <TabsContent value="graph">
                        <div className="network-graph-container h-[600px]" data-testid="network-graph">
                            {displayData && displayData.length > 0 ? (
                                <NetworkGraph 
                                    domains={useV3 ? null : network.domains}
                                    entries={useV3 ? network.entries : null}
                                    onNodeClick={handleNodeClick}
                                    selectedNodeId={useV3 ? selectedEntry?.asset_domain_id : selectedEntry?.id}
                                    useV3={useV3}
                                />
                            ) : (
                                <div className="flex items-center justify-center h-full">
                                    <div className="text-center">
                                        <Globe className="h-12 w-12 text-zinc-700 mx-auto mb-3" />
                                        <p className="text-zinc-500">No domains in this network</p>
                                        <p className="text-sm text-zinc-600 mt-1">
                                            Add domains and assign them to this network
                                        </p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </TabsContent>

                    {/* List View */}
                    <TabsContent value="list">
                        <div className="data-table-container" data-testid="domains-list">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Domain</TableHead>
                                        <TableHead>Tier</TableHead>
                                        <TableHead>Role</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Index</TableHead>
                                        <TableHead>Target</TableHead>
                                        <TableHead>Ranking</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {!displayData?.length ? (
                                        <TableRow>
                                            <TableCell colSpan={8} className="h-32 text-center text-zinc-500">
                                                No domains in this network
                                            </TableCell>
                                        </TableRow>
                                    ) : useV3 ? (
                                        // V3 entries
                                        network.entries?.map((entry) => {
                                            // V3: Orphan detection uses target_entry_id (node-to-node)
                                            const isOrphan = entry.domain_role !== 'main' && !entry.target_entry_id;
                                            
                                            return (
                                                <TableRow 
                                                    key={entry.id} 
                                                    className={`table-row-hover ${isOrphan ? 'bg-red-950/10' : ''}`}
                                                    data-testid={`entry-row-${entry.id}`}
                                                >
                                                    <TableCell>
                                                        <div className="flex items-center gap-2">
                                                            {isOrphan && <AlertTriangle className="h-4 w-4 text-red-500" />}
                                                            {/* Show node_label (domain + path) */}
                                                            <span className="font-mono text-sm">{entry.node_label || entry.domain_name}</span>
                                                            <a 
                                                                href={`https://${entry.domain_name}${entry.optimized_path || ''}`}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                onClick={(e) => e.stopPropagation()}
                                                                className="text-zinc-500 hover:text-blue-500"
                                                            >
                                                                <ExternalLink className="h-3 w-3" />
                                                            </a>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <span 
                                                            className="text-xs px-2 py-1 rounded-full font-mono"
                                                            style={{ 
                                                                backgroundColor: `${V3_TIER_COLORS[entry.calculated_tier]}20`,
                                                                color: V3_TIER_COLORS[entry.calculated_tier]
                                                            }}
                                                        >
                                                            {entry.tier_label}
                                                        </span>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge 
                                                            variant={entry.domain_role === 'main' ? 'default' : 'outline'}
                                                            className={entry.domain_role === 'main' ? 'bg-orange-500' : ''}
                                                        >
                                                            {entry.domain_role}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell className="text-zinc-400 text-sm">
                                                        {STATUS_LABELS[entry.domain_status] || entry.domain_status}
                                                    </TableCell>
                                                    <TableCell>
                                                        <span className={`text-xs px-2 py-1 rounded-full font-mono uppercase ${
                                                            entry.index_status === 'index' ? 'status-indexed' : 'status-noindex'
                                                        }`}>
                                                            {entry.index_status}
                                                        </span>
                                                    </TableCell>
                                                    <TableCell className="text-zinc-400 text-sm font-mono">
                                                        {/* Show target node label (domain + path) */}
                                                        {entry.target_domain_name 
                                                            ? `${entry.target_domain_name}${entry.target_entry_path || ''}`
                                                            : '-'}
                                                    </TableCell>
                                                    <TableCell>
                                                        {entry.primary_keyword ? (
                                                            <div className="flex items-center gap-2">
                                                                <Target className="h-3 w-3 text-emerald-500" />
                                                                <span className="text-xs text-zinc-300">{entry.primary_keyword}</span>
                                                                {entry.ranking_position && (
                                                                    <Badge variant="outline" className="text-xs px-1.5 py-0">
                                                                        #{entry.ranking_position}
                                                                    </Badge>
                                                                )}
                                                            </div>
                                                        ) : (
                                                            <span className="text-zinc-600 text-xs">-</span>
                                                        )}
                                                    </TableCell>
                                                    <TableCell className="text-right">
                                                        <div className="flex items-center justify-end gap-1">
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                onClick={() => handleNodeClick(entry)}
                                                                className="h-7 px-2 text-zinc-400 hover:text-white"
                                                            >
                                                                View
                                                            </Button>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    openEditDialog(entry);
                                                                }}
                                                                className="h-7 w-7 hover:bg-blue-500/10 hover:text-blue-400"
                                                                data-testid={`edit-entry-${entry.id}`}
                                                            >
                                                                <Edit className="h-3.5 w-3.5" />
                                                            </Button>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    openDeleteDialog(entry);
                                                                }}
                                                                className="h-7 w-7 hover:bg-red-500/10 hover:text-red-400"
                                                                data-testid={`delete-entry-${entry.id}`}
                                                            >
                                                                <Trash2 className="h-3.5 w-3.5" />
                                                            </Button>
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })
                                    ) : (
                                        // V2 domains (fallback)
                                        network.domains?.map((domain) => {
                                            const parent = network.domains.find(d => d.id === domain.parent_domain_id);
                                            const isOrphan = domain.tier_level !== 'lp_money_site' && !domain.parent_domain_id;
                                            
                                            return (
                                                <TableRow 
                                                    key={domain.id} 
                                                    className={`table-row-hover cursor-pointer ${isOrphan ? 'bg-red-950/10' : ''}`}
                                                    onClick={() => handleNodeClick(domain)}
                                                    data-testid={`domain-list-row-${domain.id}`}
                                                >
                                                    <TableCell>
                                                        <div className="flex items-center gap-2">
                                                            {isOrphan && <AlertTriangle className="h-4 w-4 text-red-500" />}
                                                            <span className="font-mono text-sm">{domain.domain_name}</span>
                                                            <a 
                                                                href={`https://${domain.domain_name}`}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                onClick={(e) => e.stopPropagation()}
                                                                className="text-zinc-500 hover:text-blue-500"
                                                            >
                                                                <ExternalLink className="h-3 w-3" />
                                                            </a>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <span className={`badge-tier ${getTierBadgeClass(domain.tier_level)}`}>
                                                            {TIER_LABELS[domain.tier_level]}
                                                        </span>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge variant="outline">
                                                            {domain.tier_level === 'lp_money_site' ? 'main' : 'supporting'}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell className="text-zinc-400 text-sm">
                                                        {STATUS_LABELS[domain.domain_status]}
                                                    </TableCell>
                                                    <TableCell>
                                                        <span className={`text-xs px-2 py-1 rounded-full font-mono uppercase ${
                                                            domain.index_status === 'index' ? 'status-indexed' : 'status-noindex'
                                                        }`}>
                                                            {domain.index_status}
                                                        </span>
                                                    </TableCell>
                                                    <TableCell className="text-zinc-400 text-sm font-mono">
                                                        {parent?.domain_name || '-'}
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge variant="outline" className="font-normal">
                                                            {domain.brand_name || '-'}
                                                        </Badge>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })
                                    )}
                                </TableBody>
                            </Table>
                        </div>
                    </TabsContent>
                </Tabs>

                {/* Entry/Domain Detail Sheet */}
                <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
                    <SheetContent className="bg-card border-border w-full sm:max-w-md">
                        <SheetHeader>
                            <SheetTitle className="font-mono text-lg">
                                {selectedEntry?.domain_name}
                            </SheetTitle>
                        </SheetHeader>
                        
                        {selectedEntry && (
                            <div className="mt-6 space-y-6">
                                {/* Quick Info */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Tier</span>
                                        {useV3 ? (
                                            <span 
                                                className="font-mono font-medium"
                                                style={{ color: V3_TIER_COLORS[selectedEntry.calculated_tier] }}
                                            >
                                                {selectedEntry.tier_label} (Derived)
                                            </span>
                                        ) : (
                                            <span 
                                                className="font-mono font-medium"
                                                style={{ color: TIER_COLORS[selectedEntry.tier_level] }}
                                            >
                                                {TIER_LABELS[selectedEntry.tier_level]}
                                            </span>
                                        )}
                                    </div>
                                    {useV3 && (
                                        <div className="flex items-center justify-between">
                                            <span className="text-sm text-zinc-500">Role</span>
                                            <Badge 
                                                variant={selectedEntry.domain_role === 'main' ? 'default' : 'outline'}
                                                className={selectedEntry.domain_role === 'main' ? 'bg-orange-500' : ''}
                                            >
                                                {selectedEntry.domain_role}
                                            </Badge>
                                        </div>
                                    )}
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Index Status</span>
                                        <span className={`text-xs px-2 py-1 rounded-full font-mono uppercase ${
                                            selectedEntry.index_status === 'index' ? 'status-indexed' : 'status-noindex'
                                        }`}>
                                            {selectedEntry.index_status}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Domain Status</span>
                                        <span className="text-sm text-white">
                                            {STATUS_LABELS[selectedEntry.domain_status] || selectedEntry.domain_status}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Brand</span>
                                        <Badge variant="outline">{selectedEntry.brand_name || '-'}</Badge>
                                    </div>
                                </div>

                                {/* Target/Parent Domain */}
                                {(useV3 ? selectedEntry.target_domain_name : selectedEntry.parent_domain_id) && (
                                    <div className="pt-4 border-t border-border">
                                        <span className="text-sm text-zinc-500 block mb-2">
                                            {useV3 ? 'Target Domain' : 'Parent Domain'}
                                        </span>
                                        <div className="bg-black rounded-md p-3">
                                            <span className="font-mono text-sm text-blue-400">
                                                {useV3 
                                                    ? selectedEntry.target_domain_name
                                                    : network.domains?.find(d => d.id === selectedEntry.parent_domain_id)?.domain_name || 'Unknown'
                                                }
                                            </span>
                                        </div>
                                    </div>
                                )}

                                {/* Child Nodes (find entries pointing to this one) */}
                                {useV3 && (() => {
                                    // V3: Use target_entry_id to find nodes pointing to this entry
                                    const children = network.entries?.filter(e => e.target_entry_id === selectedEntry.id) || [];
                                    if (children.length === 0) return null;
                                    
                                    return (
                                        <div className="pt-4 border-t border-border">
                                            <span className="text-sm text-zinc-500 block mb-2">Pointing Nodes ({children.length})</span>
                                            <div className="space-y-2 max-h-40 overflow-y-auto">
                                                {children.map(child => (
                                                    <div key={child.id} className="bg-black rounded-md p-3 flex items-center justify-between">
                                                        {/* Show node_label (domain + path) */}
                                                        <span className="font-mono text-sm">{child.node_label || child.domain_name}</span>
                                                        <span 
                                                            className="text-xs px-2 py-0.5 rounded-full"
                                                            style={{ 
                                                                backgroundColor: `${V3_TIER_COLORS[child.calculated_tier]}20`,
                                                                color: V3_TIER_COLORS[child.calculated_tier]
                                                            }}
                                                        >
                                                            {child.tier_label}
                                                        </span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    );
                                })()}

                                {/* V2 Child Domains */}
                                {!useV3 && network.domains?.filter(d => d.parent_domain_id === selectedEntry.id).length > 0 && (
                                    <div className="pt-4 border-t border-border">
                                        <span className="text-sm text-zinc-500 block mb-2">Child Domains</span>
                                        <div className="space-y-2">
                                            {network.domains
                                                .filter(d => d.parent_domain_id === selectedEntry.id)
                                                .map(child => (
                                                    <div key={child.id} className="bg-black rounded-md p-3 flex items-center justify-between">
                                                        <span className="font-mono text-sm">{child.domain_name}</span>
                                                        <span className={`badge-tier ${getTierBadgeClass(child.tier_level)}`}>
                                                            {TIER_LABELS[child.tier_level]}
                                                        </span>
                                                    </div>
                                                ))
                                            }
                                        </div>
                                    </div>
                                )}

                                {/* Notes */}
                                {selectedEntry.notes && (
                                    <div className="pt-4 border-t border-border">
                                        <span className="text-sm text-zinc-500 block mb-2">Notes</span>
                                        <p className="text-sm text-zinc-300">{selectedEntry.notes}</p>
                                    </div>
                                )}

                                {/* Timestamps */}
                                <div className="pt-4 border-t border-border text-xs text-zinc-600">
                                    <p>Created: {formatDate(selectedEntry.created_at)}</p>
                                    <p>Updated: {formatDate(selectedEntry.updated_at)}</p>
                                </div>

                                {/* Actions */}
                                <div className="pt-4">
                                    <a 
                                        href={`https://${selectedEntry.domain_name}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="w-full"
                                    >
                                        <Button variant="outline" className="w-full">
                                            <ExternalLink className="h-4 w-4 mr-2" />
                                            Open Domain
                                        </Button>
                                    </a>
                                </div>
                            </div>
                        )}
                    </SheetContent>
                </Sheet>

                {/* Edit Structure Entry Dialog */}
                {useV3 && (
                    <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                        <DialogContent className="bg-card border-border max-w-lg max-h-[90vh] overflow-y-auto">
                            <DialogHeader>
                                <DialogTitle className="flex items-center gap-2">
                                    <Edit className="h-5 w-5" />
                                    Edit Structure Entry
                                </DialogTitle>
                            </DialogHeader>
                            
                            {selectedEntry && (
                                <div className="space-y-6">
                                    {/* Domain Info */}
                                    <div className="bg-black rounded-lg p-4">
                                        <div className="text-xs text-zinc-500 mb-1">Node</div>
                                        <div className="font-mono text-lg">
                                            {selectedEntry.node_label || selectedEntry.domain_name}
                                        </div>
                                        {selectedEntry.optimized_path && (
                                            <div className="text-sm text-zinc-400 mt-1">
                                                Path: {selectedEntry.optimized_path}
                                            </div>
                                        )}
                                        <div className="flex items-center gap-2 mt-2">
                                            <span 
                                                className="text-xs px-2 py-0.5 rounded-full"
                                                style={{ 
                                                    backgroundColor: `${V3_TIER_COLORS[selectedEntry.calculated_tier]}20`,
                                                    color: V3_TIER_COLORS[selectedEntry.calculated_tier]
                                                }}
                                            >
                                                {selectedEntry.tier_label}
                                            </span>
                                            <span className="text-xs text-zinc-500">Derived from hierarchy</span>
                                        </div>
                                    </div>

                                    {/* Path Configuration */}
                                    <div className="space-y-4">
                                        <h3 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
                                            <Target className="h-4 w-4" />
                                            Path Configuration
                                        </h3>
                                        
                                        <div className="space-y-2">
                                            <Label>Optimized Path (optional)</Label>
                                            <Input
                                                value={editForm.optimized_path}
                                                onChange={(e) => setEditForm({...editForm, optimized_path: e.target.value})}
                                                placeholder="/blog/best-product or /landing-page"
                                                className="bg-black border-border font-mono"
                                            />
                                            <p className="text-xs text-zinc-500">
                                                Leave empty for domain-level. Add path for page-level SEO targeting.
                                            </p>
                                        </div>
                                    </div>

                                    {/* SEO Structure Settings */}
                                    <div className="space-y-4">
                                        <h3 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
                                            <Network className="h-4 w-4" />
                                            SEO Structure
                                        </h3>
                                        
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="space-y-2">
                                                <Label>Role</Label>
                                                <Select 
                                                    value={editForm.domain_role} 
                                                    onValueChange={(v) => setEditForm({...editForm, domain_role: v})}
                                                >
                                                    <SelectTrigger className="bg-black border-border">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {ROLE_OPTIONS.map(opt => (
                                                            <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>

                                            <div className="space-y-2">
                                                <Label>Index Status</Label>
                                                <Select 
                                                    value={editForm.index_status} 
                                                    onValueChange={(v) => setEditForm({...editForm, index_status: v})}
                                                >
                                                    <SelectTrigger className="bg-black border-border">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {INDEX_OPTIONS.map(opt => (
                                                            <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="space-y-2">
                                                <Label>Domain Status</Label>
                                                <Select 
                                                    value={editForm.domain_status} 
                                                    onValueChange={(v) => setEditForm({...editForm, domain_status: v})}
                                                >
                                                    <SelectTrigger className="bg-black border-border">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {SEO_STATUS_OPTIONS.map(opt => (
                                                            <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>

                                            <div className="space-y-2">
                                                <Label>Target Node</Label>
                                                <Select 
                                                    value={editForm.target_entry_id || 'none'} 
                                                    onValueChange={(v) => setEditForm({...editForm, target_entry_id: v === 'none' ? '' : v})}
                                                    disabled={editForm.domain_role === 'main'}
                                                >
                                                    <SelectTrigger className="bg-black border-border">
                                                        <SelectValue placeholder="Select target node" />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="none">None (Orphan)</SelectItem>
                                                        {availableTargets.map(t => (
                                                            <SelectItem key={t.id} value={t.id}>
                                                                {t.node_label || t.domain_name}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Ranking & Path Tracking */}
                                    <div className="space-y-4">
                                        <h3 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
                                            <TrendingUp className="h-4 w-4" />
                                            Ranking & Path Tracking
                                        </h3>
                                        
                                        <div className="space-y-2">
                                            <Label>Ranking URL (specific path)</Label>
                                            <Input
                                                value={editForm.ranking_url}
                                                onChange={(e) => setEditForm({...editForm, ranking_url: e.target.value})}
                                                placeholder="/blog/best-product-review"
                                                className="bg-black border-border font-mono text-sm"
                                            />
                                            <p className="text-xs text-zinc-500">The specific URL path that ranks for your keyword</p>
                                        </div>

                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="space-y-2">
                                                <Label>Primary Keyword</Label>
                                                <Input
                                                    value={editForm.primary_keyword}
                                                    onChange={(e) => setEditForm({...editForm, primary_keyword: e.target.value})}
                                                    placeholder="best product 2026"
                                                    className="bg-black border-border"
                                                />
                                            </div>

                                            <div className="space-y-2">
                                                <Label>Ranking Position</Label>
                                                <Input
                                                    type="number"
                                                    min="1"
                                                    max="100"
                                                    value={editForm.ranking_position}
                                                    onChange={(e) => setEditForm({...editForm, ranking_position: e.target.value})}
                                                    placeholder="1-100"
                                                    className="bg-black border-border"
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    {/* Notes */}
                                    <div className="space-y-2">
                                        <Label>Notes</Label>
                                        <Textarea
                                            value={editForm.notes}
                                            onChange={(e) => setEditForm({...editForm, notes: e.target.value})}
                                            placeholder="SEO strategy notes..."
                                            className="bg-black border-border resize-none"
                                            rows={3}
                                        />
                                    </div>
                                </div>
                            )}

                            <DialogFooter>
                                <Button
                                    variant="outline"
                                    onClick={() => setEditDialogOpen(false)}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    onClick={handleSaveEntry}
                                    disabled={saving}
                                    className="bg-white text-black hover:bg-zinc-200"
                                >
                                    {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                    Save Changes
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                )}

                {/* Import Nodes Dialog */}
                <Dialog open={importDialogOpen} onOpenChange={setImportDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-2xl">
                        <DialogHeader>
                            <DialogTitle>Import Nodes (Path-Level SEO)</DialogTitle>
                            <DialogDescription>
                                Import nodes from a CSV file. Each node is a domain + optional path combination.
                            </DialogDescription>
                        </DialogHeader>
                        
                        <div className="space-y-4">
                            {/* File upload */}
                            <div className="space-y-2">
                                <Label>CSV File</Label>
                                <div className="flex items-center gap-2">
                                    <Input
                                        type="file"
                                        accept=".csv"
                                        onChange={handleFileSelect}
                                        ref={fileInputRef}
                                        className="bg-black border-border"
                                    />
                                </div>
                                <p className="text-xs text-zinc-500">
                                    Required columns: domain_name. Optional: optimized_path, domain_role, target_domain, target_path, etc.
                                </p>
                            </div>

                            {/* Options */}
                            <div className="flex items-center gap-2 p-3 bg-black rounded-lg">
                                <Switch 
                                    checked={createMissingDomains}
                                    onCheckedChange={setCreateMissingDomains}
                                    id="create-domains"
                                />
                                <Label htmlFor="create-domains" className="text-sm">
                                    Create missing domains automatically
                                </Label>
                            </div>

                            {/* Preview */}
                            {importData.length > 0 && (
                                <div className="space-y-2">
                                    <Label>Preview ({importData.length} nodes)</Label>
                                    <div className="max-h-[200px] overflow-auto bg-black rounded-lg p-2">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead className="text-xs">Domain</TableHead>
                                                    <TableHead className="text-xs">Path</TableHead>
                                                    <TableHead className="text-xs">Role</TableHead>
                                                    <TableHead className="text-xs">Target</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {importData.slice(0, 10).map((node, i) => (
                                                    <TableRow key={i}>
                                                        <TableCell className="text-xs font-mono">{node.domain_name}</TableCell>
                                                        <TableCell className="text-xs font-mono">{node.optimized_path || '-'}</TableCell>
                                                        <TableCell className="text-xs">
                                                            <Badge variant={node.domain_role === 'main' ? 'default' : 'secondary'} className="text-xs">
                                                                {node.domain_role}
                                                            </Badge>
                                                        </TableCell>
                                                        <TableCell className="text-xs font-mono">
                                                            {node.target_domain ? `${node.target_domain}${node.target_path || ''}` : '-'}
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                        {importData.length > 10 && (
                                            <p className="text-xs text-zinc-500 text-center mt-2">
                                                ... and {importData.length - 10} more
                                            </p>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>

                        <DialogFooter>
                            <Button
                                variant="outline"
                                onClick={() => {
                                    setImportDialogOpen(false);
                                    setImportData([]);
                                }}
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleImportSubmit}
                                disabled={importing || importData.length === 0}
                                className="bg-white text-black hover:bg-zinc-200"
                            >
                                {importing && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                Import {importData.length} Nodes
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Delete Node Confirmation Dialog */}
                <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-md">
                        <DialogHeader>
                            <DialogTitle>Delete Node</DialogTitle>
                            <DialogDescription>
                                Are you sure you want to delete this node?
                            </DialogDescription>
                        </DialogHeader>
                        
                        {entryToDelete && (
                            <div className="p-4 bg-black rounded-lg">
                                <div className="font-mono text-lg text-white">
                                    {entryToDelete.node_label || entryToDelete.domain_name}
                                </div>
                                <div className="text-sm text-zinc-400 mt-1">
                                    {entryToDelete.domain_role === 'main' 
                                        ? 'Main node - cannot delete while other nodes exist' 
                                        : `Supporting node - Tier ${entryToDelete.calculated_tier || '?'}`}
                                </div>
                            </div>
                        )}

                        <p className="text-sm text-zinc-400">
                            If other nodes are targeting this node, they will become orphans.
                        </p>

                        <DialogFooter>
                            <Button
                                variant="outline"
                                onClick={() => setDeleteDialogOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleDeleteNode}
                                disabled={deleting}
                                className="bg-red-600 hover:bg-red-700"
                            >
                                {deleting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                Delete Node
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Add Node Dialog */}
                <Dialog open={addNodeDialogOpen} onOpenChange={setAddNodeDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-lg">
                        <DialogHeader>
                            <DialogTitle>Add Node to Network</DialogTitle>
                            <DialogDescription>
                                Add a new supporting node. Only domains from the same brand are available.
                            </DialogDescription>
                        </DialogHeader>
                        
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <Label>Asset Domain *</Label>
                                <Select 
                                    value={addNodeForm.asset_domain_id} 
                                    onValueChange={(v) => setAddNodeForm({...addNodeForm, asset_domain_id: v})}
                                >
                                    <SelectTrigger className="bg-black border-border">
                                        <SelectValue placeholder="Select domain..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {availableDomains.length === 0 ? (
                                            <div className="p-2 text-sm text-zinc-500">
                                                No available domains
                                            </div>
                                        ) : (
                                            availableDomains.map(d => (
                                                <SelectItem key={d.id} value={d.id}>
                                                    <div className="flex items-center gap-2">
                                                        <span>{d.domain_name}</span>
                                                        {!d.root_available && (
                                                            <Badge variant="outline" className="text-xs">root used</Badge>
                                                        )}
                                                    </div>
                                                </SelectItem>
                                            ))
                                        )}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="space-y-2">
                                <Label>Optimized Path (optional)</Label>
                                <Input
                                    value={addNodeForm.optimized_path}
                                    onChange={(e) => setAddNodeForm({...addNodeForm, optimized_path: e.target.value})}
                                    placeholder="/blog/article or leave empty for root"
                                    className="bg-black border-border font-mono"
                                />
                                <p className="text-xs text-zinc-500">
                                    Leave empty for domain-level node. Enter path for page-level targeting.
                                </p>
                            </div>

                            <div className="space-y-2">
                                <Label>Role</Label>
                                <Select 
                                    value={addNodeForm.domain_role} 
                                    onValueChange={(v) => setAddNodeForm({...addNodeForm, domain_role: v})}
                                >
                                    <SelectTrigger className="bg-black border-border">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="supporting">Supporting</SelectItem>
                                        <SelectItem value="main">Main</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="space-y-2">
                                <Label>Target Node</Label>
                                <Select 
                                    value={addNodeForm.target_entry_id || 'none'} 
                                    onValueChange={(v) => setAddNodeForm({...addNodeForm, target_entry_id: v === 'none' ? '' : v})}
                                    disabled={addNodeForm.domain_role === 'main'}
                                >
                                    <SelectTrigger className="bg-black border-border">
                                        <SelectValue placeholder="Select target..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">None (Orphan)</SelectItem>
                                        {availableTargets.map(t => (
                                            <SelectItem key={t.id} value={t.id}>
                                                {t.node_label || t.domain_name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <DialogFooter>
                            <Button
                                variant="outline"
                                onClick={() => setAddNodeDialogOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleAddNode}
                                disabled={saving || !addNodeForm.asset_domain_id}
                                className="bg-white text-black hover:bg-zinc-200"
                            >
                                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                Add Node
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </Layout>
    );
}
