import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { groupsAPI, networksAPI, structureAPI, assetDomainsAPI, exportAPI, importAPI, changeLogsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { NetworkGraph } from '../components/NetworkGraph';
import { ChangeNoteInput } from '../components/ChangeNoteInput';
import { OptimizationsTab } from '../components/OptimizationsTab';
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
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from '../components/ui/dropdown-menu';
import { ScrollArea } from '../components/ui/scroll-area';
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
    Trash2,
    History,
    Bell,
    User,
    Clock,
    ChevronRight,
    ChevronDown,
    ChevronUp,
    Eye,
    Check,
    X,
    Crown,
    MoreVertical,
    ArrowRightLeft,
    Filter,
    Calendar,
    Layers,
    List,
    FileText
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

// SEO Status options for SUPPORTING nodes
const SEO_STATUS_OPTIONS_SUPPORTING = [
    { value: 'canonical', label: 'Canonical' },
    { value: '301_redirect', label: '301 Redirect' },
    { value: '302_redirect', label: '302 Redirect' },
    { value: 'restore', label: 'Restore' }
];

// SEO Status options for MAIN nodes (no redirect/canonical)
const SEO_STATUS_OPTIONS_MAIN = [
    { value: 'primary', label: 'Primary Target' }
];

const INDEX_OPTIONS = [
    { value: 'index', label: 'Index' },
    { value: 'noindex', label: 'Noindex' }
];

const ROLE_OPTIONS = [
    { value: 'main', label: 'Main (LP/Money Site)' },
    { value: 'supporting', label: 'Supporting' }
];

// SEO Change Action Types - human readable labels
const ACTION_TYPE_LABELS = {
    'create_node': 'Created',
    'update_node': 'Updated',
    'delete_node': 'Deleted',
    'relink_node': 'Relinked',
    'change_role': 'Role Changed',
    'change_path': 'Path Changed'
};

const ACTION_TYPE_COLORS = {
    'create_node': 'bg-emerald-500/20 text-emerald-400',
    'update_node': 'bg-blue-500/20 text-blue-400',
    'delete_node': 'bg-red-500/20 text-red-400',
    'relink_node': 'bg-purple-500/20 text-purple-400',
    'change_role': 'bg-orange-500/20 text-orange-400',
    'change_path': 'bg-cyan-500/20 text-cyan-400'
};

const NOTIFICATION_TYPE_LABELS = {
    'main_domain_change': 'Main Domain Changed',
    'node_deleted': 'Node Deleted',
    'target_relinked': 'Target Relinked',
    'orphan_detected': 'Orphan Detected',
    'seo_conflict': 'SEO Conflict',
    'high_tier_noindex': 'High Tier NoIndex'
};

export default function GroupDetailPage() {
    const { groupId } = useParams();
    const navigate = useNavigate();
    const [network, setNetwork] = useState(null);
    const [tierData, setTierData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedEntry, setSelectedEntry] = useState(null);
    const [sheetOpen, setSheetOpen] = useState(false);
    const [useV3, setUseV3] = useState(true);
    
    // Change History state
    const [changeHistory, setChangeHistory] = useState([]);
    const [changeHistoryLoading, setChangeHistoryLoading] = useState(false);
    const [selectedChangeLog, setSelectedChangeLog] = useState(null);
    const [changeDetailOpen, setChangeDetailOpen] = useState(false);
    const [highlightedNodeId, setHighlightedNodeId] = useState(null);  // For D3 highlighting
    
    // Network Notifications state
    const [notifications, setNotifications] = useState([]);
    const [notificationsLoading, setNotificationsLoading] = useState(false);
    const [unreadCount, setUnreadCount] = useState(0);
    
    // Active tab state (for coordinating between alerts and change history)
    const [activeTab, setActiveTab] = useState('graph');
    
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
    
    // Switch Main Target state
    const [switchMainDialogOpen, setSwitchMainDialogOpen] = useState(false);
    const [entryToPromote, setEntryToPromote] = useState(null);
    const [switchMainChangeNote, setSwitchMainChangeNote] = useState('');
    const [switching, setSwitching] = useState(false);
    
    // Add node state
    const [addNodeDialogOpen, setAddNodeDialogOpen] = useState(false);
    const [availableDomains, setAvailableDomains] = useState([]);
    const [addNodeForm, setAddNodeForm] = useState({
        asset_domain_id: '',
        optimized_path: '',
        domain_role: 'supporting',
        domain_status: 'canonical',
        target_entry_id: '',
        change_note: ''  // Required for SEO change logging
    });
    
    // Import dialog state
    const [importDialogOpen, setImportDialogOpen] = useState(false);
    const [importData, setImportData] = useState([]);
    const [importing, setImporting] = useState(false);
    const [createMissingDomains, setCreateMissingDomains] = useState(false);
    const fileInputRef = useRef(null);
    
    // Timeline filters state
    const [timelineFilters, setTimelineFilters] = useState({
        actor: '',
        action: '',
        node: '',
        dateFrom: '',
        dateTo: ''
    });
    const [isFilterOpen, setIsFilterOpen] = useState(false);
    
    // Domain List view mode: 'grouped' or 'flat'
    const [domainListView, setDomainListView] = useState('grouped');
    
    // Tier groups for grouped view
    const tierGroups = useMemo(() => {
        if (!network?.entries) return {};
        
        const groups = {
            0: { label: 'LP / Money Site', entries: [], expanded: true },
            1: { label: 'Tier 1', entries: [], expanded: true },
            2: { label: 'Tier 2', entries: [], expanded: false },
            3: { label: 'Tier 3', entries: [], expanded: false },
            4: { label: 'Tier 4+', entries: [], expanded: false }
        };
        
        network.entries.forEach(entry => {
            const tier = entry.calculated_tier || 0;
            const groupKey = tier >= 4 ? 4 : tier;
            if (groups[groupKey]) {
                groups[groupKey].entries.push(entry);
            }
        });
        
        // Sort entries within each tier: main first, then alphabetical by node_label
        Object.values(groups).forEach(group => {
            group.entries.sort((a, b) => {
                // Main nodes first
                if (a.domain_role === 'main' && b.domain_role !== 'main') return -1;
                if (a.domain_role !== 'main' && b.domain_role === 'main') return 1;
                // Then alphabetical by node_label
                const labelA = a.node_label || a.domain_name || '';
                const labelB = b.node_label || b.domain_name || '';
                return labelA.localeCompare(labelB);
            });
        });
        
        return groups;
    }, [network?.entries]);
    
    // Collapsed state for tier groups
    const [collapsedTiers, setCollapsedTiers] = useState({ 2: true, 3: true, 4: true });
    
    const toggleTierCollapse = (tier) => {
        setCollapsedTiers(prev => ({ ...prev, [tier]: !prev[tier] }));
    };

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

    // Load change history for the network with optional filters
    const loadChangeHistory = useCallback(async (filters = {}) => {
        if (!groupId) return;
        
        setChangeHistoryLoading(true);
        try {
            const params = {
                limit: 100,
                ...(filters.actor && { actor_email: filters.actor }),
                ...(filters.action && { action_type: filters.action }),
                ...(filters.node && { affected_node: filters.node }),
                ...(filters.dateFrom && { date_from: filters.dateFrom }),
                ...(filters.dateTo && { date_to: filters.dateTo })
            };
            const { data } = await changeLogsAPI.getNetworkHistory(groupId, params);
            setChangeHistory(data || []);
        } catch (err) {
            console.error('Failed to load change history:', err);
            setChangeHistory([]);
        } finally {
            setChangeHistoryLoading(false);
        }
    }, [groupId]);
    
    // Apply timeline filters
    const applyTimelineFilters = () => {
        loadChangeHistory(timelineFilters);
    };
    
    // Clear timeline filters
    const clearTimelineFilters = () => {
        setTimelineFilters({ actor: '', action: '', node: '', dateFrom: '', dateTo: '' });
        loadChangeHistory({});
    };

    // Load notifications for the network
    const loadNotifications = useCallback(async () => {
        if (!groupId) return;
        
        setNotificationsLoading(true);
        try {
            const { data } = await changeLogsAPI.getNetworkNotifications(groupId, { limit: 50 });
            setNotifications(data || []);
            setUnreadCount((data || []).filter(n => !n.read).length);
        } catch (err) {
            console.error('Failed to load notifications:', err);
            setNotifications([]);
        } finally {
            setNotificationsLoading(false);
        }
    }, [groupId]);

    // Mark notification as read
    const handleMarkNotificationRead = async (notificationId) => {
        try {
            await changeLogsAPI.markNotificationRead(groupId, notificationId);
            setNotifications(prev => prev.map(n => 
                n.id === notificationId ? { ...n, read: true } : n
            ));
            setUnreadCount(prev => Math.max(0, prev - 1));
        } catch (err) {
            console.error('Failed to mark notification as read:', err);
        }
    };

    // Mark all notifications as read
    const handleMarkAllNotificationsRead = async () => {
        try {
            await changeLogsAPI.markAllNotificationsRead(groupId);
            setNotifications(prev => prev.map(n => ({ ...n, read: true })));
            setUnreadCount(0);
            toast.success('All notifications marked as read');
        } catch (err) {
            toast.error('Failed to mark notifications as read');
        }
    };

    // Open change detail drawer and highlight node in graph
    const handleViewChangeDetail = (log) => {
        setSelectedChangeLog(log);
        setChangeDetailOpen(true);
        
        // Find the related entry and highlight it in the graph
        if (log.entry_id && network?.entries) {
            const entry = network.entries.find(e => e.id === log.entry_id);
            if (entry) {
                setHighlightedNodeId(entry.asset_domain_id);
            }
        }
    };

    // Handle notification click - open related change history entry
    const handleNotificationClick = (notification) => {
        // Mark as read
        if (!notification.read) {
            handleMarkNotificationRead(notification.id);
        }
        
        // If there's a related change_log_id, find and open it
        if (notification.change_log_id) {
            const relatedLog = changeHistory.find(log => log.id === notification.change_log_id);
            if (relatedLog) {
                handleViewChangeDetail(relatedLog);
            } else {
                // Log might not be loaded yet, switch to Change History tab
                setActiveTab('history');
                loadChangeHistory();
                toast.info('Switched to Change History tab');
            }
        }
    };

    // Load change history and notifications when tab changes
    useEffect(() => {
        if (activeTab === 'history' && changeHistory.length === 0) {
            loadChangeHistory();
        }
        if (activeTab === 'alerts' && notifications.length === 0) {
            loadNotifications();
        }
    }, [activeTab, loadChangeHistory, loadNotifications]);

    // Format date for display
    const formatChangeDate = (dateStr) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
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
            notes: entry.notes || '',
            change_note: ''  // Reset for each edit
        });
        loadAvailableTargets(network?.id, entry.id);
        setEditDialogOpen(true);
    };

    // Save structure entry changes
    const handleSaveEntry = async () => {
        if (!selectedEntry?.id) return;
        
        // Validate change_note (minimum 10 characters to match backend)
        if (!editForm.change_note || editForm.change_note.trim().length < 10) {
            toast.error('Change note is required (min 3 characters)');
            return;
        }
        
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
                notes: editForm.notes || null,
                change_note: editForm.change_note.trim()  // Required for SEO logging
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
        setDeleteChangeNote('');  // Reset change note
        setDeleteDialogOpen(true);
    };

    // Delete node handler
    const handleDeleteNode = async () => {
        if (!entryToDelete?.id) return;
        
        // Validate change_note
        if (!deleteChangeNote || deleteChangeNote.trim().length < 10) {
            toast.error('Change note is required (min 3 characters)');
            return;
        }
        
        setDeleting(true);
        try {
            const response = await structureAPI.delete(entryToDelete.id, {
                change_note: deleteChangeNote.trim()
            });
            
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

    // Open Switch Main Target dialog
    const openSwitchMainDialog = (entry) => {
        setEntryToPromote(entry);
        setSwitchMainChangeNote('');
        setSwitchMainDialogOpen(true);
    };

    // Handle Switch Main Target
    const handleSwitchMainTarget = async () => {
        if (!entryToPromote?.id || !network?.id) return;
        
        // Validate change_note
        if (!switchMainChangeNote || switchMainChangeNote.trim().length < 10) {
            toast.error('Change note is required (min 3 characters)');
            return;
        }
        
        setSwitching(true);
        try {
            await networksAPI.switchMainTarget(network.id, {
                new_main_entry_id: entryToPromote.id,
                change_note: switchMainChangeNote.trim()
            });
            
            toast.success('Main target switched successfully. Tiers recalculated.');
            setSwitchMainDialogOpen(false);
            setEntryToPromote(null);
            setSwitchMainChangeNote('');
            loadNetwork();
            loadChangeHistory();
            loadNotifications();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to switch main target');
        } finally {
            setSwitching(false);
        }
    };

    // Add node handler
    const handleAddNode = async () => {
        if (!addNodeForm.asset_domain_id) {
            toast.error('Please select a domain');
            return;
        }
        
        // Validate change_note (minimum 10 characters to match backend)
        if (!addNodeForm.change_note || addNodeForm.change_note.trim().length < 10) {
            toast.error('Change note is required (min 3 characters)');
            return;
        }
        
        setSaving(true);
        try {
            await structureAPI.create({
                network_id: network.id,
                asset_domain_id: addNodeForm.asset_domain_id,
                optimized_path: addNodeForm.optimized_path || null,
                domain_role: addNodeForm.domain_role,
                domain_status: addNodeForm.domain_status || (addNodeForm.domain_role === 'main' ? 'primary' : 'canonical'),
                target_entry_id: addNodeForm.domain_role === 'main' ? null : (addNodeForm.target_entry_id || null),
                change_note: addNodeForm.change_note.trim()  // Required for SEO logging
            });
            
            toast.success('Node added to network');
            setAddNodeDialogOpen(false);
            // Reset form
            setAddNodeForm({
                asset_domain_id: '',
                optimized_path: '',
                domain_role: 'supporting',
                domain_status: 'canonical',
                target_entry_id: '',
                change_note: ''
            });
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
                <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
                    <TabsList className="bg-card border border-border">
                        <TabsTrigger value="graph" data-testid="graph-tab">Visual Graph</TabsTrigger>
                        <TabsTrigger value="list" data-testid="list-tab">Domain List</TabsTrigger>
                        <TabsTrigger value="history" data-testid="history-tab" className="flex items-center gap-2">
                            <History className="h-4 w-4" />
                            Change History
                        </TabsTrigger>
                        <TabsTrigger value="alerts" data-testid="alerts-tab" className="flex items-center gap-2 relative">
                            <Bell className="h-4 w-4" />
                            Alerts
                            {unreadCount > 0 && (
                                <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-4 w-4 flex items-center justify-center">
                                    {unreadCount}
                                </span>
                            )}
                        </TabsTrigger>
                    </TabsList>

                    {/* Graph View */}
                    <TabsContent value="graph">
                        <div className="network-graph-container h-[600px]" data-testid="network-graph">
                            {displayData && displayData.length > 0 ? (
                                <NetworkGraph 
                                    domains={useV3 ? null : network.domains}
                                    entries={useV3 ? network.entries : null}
                                    onNodeClick={handleNodeClick}
                                    selectedNodeId={highlightedNodeId || (useV3 ? selectedEntry?.asset_domain_id : selectedEntry?.id)}
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

                    {/* List View - Tier Grouped */}
                    <TabsContent value="list">
                        {/* View Toggle */}
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <span className="text-sm text-zinc-500">View:</span>
                                <div className="flex items-center bg-card border border-border rounded-lg overflow-hidden">
                                    <button
                                        className={`px-3 py-1.5 text-sm flex items-center gap-1.5 ${
                                            domainListView === 'grouped' 
                                                ? 'bg-white/10 text-white' 
                                                : 'text-zinc-400 hover:text-white'
                                        }`}
                                        onClick={() => setDomainListView('grouped')}
                                        data-testid="grouped-view-btn"
                                    >
                                        <Layers className="h-3.5 w-3.5" />
                                        Grouped
                                    </button>
                                    <button
                                        className={`px-3 py-1.5 text-sm flex items-center gap-1.5 ${
                                            domainListView === 'flat' 
                                                ? 'bg-white/10 text-white' 
                                                : 'text-zinc-400 hover:text-white'
                                        }`}
                                        onClick={() => setDomainListView('flat')}
                                        data-testid="flat-view-btn"
                                    >
                                        <List className="h-3.5 w-3.5" />
                                        Flat
                                    </button>
                                </div>
                            </div>
                            
                            {/* Tier Legend */}
                            <div className="flex items-center gap-3 text-xs">
                                {[0, 1, 2, 3, 4].map(tier => (
                                    <div key={tier} className="flex items-center gap-1">
                                        <div 
                                            className="w-3 h-3 rounded-full"
                                            style={{ backgroundColor: V3_TIER_COLORS[tier] || '#6B7280' }}
                                        />
                                        <span className="text-zinc-500">
                                            {tier === 0 ? 'LP' : tier === 4 ? 'T4+' : `T${tier}`}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {domainListView === 'grouped' && useV3 ? (
                            /* Grouped View by Tier */
                            <div className="space-y-4" data-testid="tier-grouped-view">
                                {Object.entries(tierGroups).map(([tierKey, tierGroup]) => {
                                    if (tierGroup.entries.length === 0) return null;
                                    const tier = parseInt(tierKey);
                                    const isCollapsed = collapsedTiers[tier];
                                    
                                    return (
                                        <Card key={tierKey} className="bg-card border-border overflow-hidden">
                                            <button
                                                className="w-full flex items-center justify-between px-4 py-3 hover:bg-zinc-900/50 transition-colors"
                                                onClick={() => toggleTierCollapse(tier)}
                                                data-testid={`tier-header-${tier}`}
                                            >
                                                <div className="flex items-center gap-3">
                                                    <div 
                                                        className="w-4 h-4 rounded-full"
                                                        style={{ backgroundColor: V3_TIER_COLORS[tier] || '#6B7280' }}
                                                    />
                                                    <span className="font-medium text-white">{tierGroup.label}</span>
                                                    <Badge variant="outline" className="text-xs">
                                                        {tierGroup.entries.length} {tierGroup.entries.length === 1 ? 'node' : 'nodes'}
                                                    </Badge>
                                                </div>
                                                {isCollapsed ? <ChevronRight className="h-4 w-4 text-zinc-500" /> : <ChevronDown className="h-4 w-4 text-zinc-500" />}
                                            </button>
                                            {!isCollapsed && (
                                                <div className="border-t border-border">
                                                    <Table>
                                                        <TableBody>
                                                            {tierGroup.entries.map((entry) => {
                                                                const isOrphan = entry.domain_role !== 'main' && !entry.target_entry_id;
                                                                const isMainNode = entry.domain_role === 'main';
                                                                return (
                                                                    <TableRow key={entry.id} className={`table-row-hover ${isOrphan ? 'bg-red-950/10' : ''}`}>
                                                                        <TableCell className="w-[40%]">
                                                                            <div className="flex items-center gap-2">
                                                                                {isMainNode && <Crown className="h-4 w-4 text-amber-400" />}
                                                                                {isOrphan && <AlertTriangle className="h-4 w-4 text-red-500" />}
                                                                                <span className="font-mono text-sm">{entry.node_label || entry.domain_name}</span>
                                                                                {entry.optimized_path && entry.optimized_path !== '/' && <Badge variant="outline" className="text-xs text-zinc-500">Path</Badge>}
                                                                            </div>
                                                                        </TableCell>
                                                                        <TableCell className="w-[15%]"><Badge variant="outline" className={isMainNode ? 'text-amber-400 border-amber-400/30' : ''}>{isMainNode ? 'Main' : 'Supporting'}</Badge></TableCell>
                                                                        <TableCell className="w-[15%] text-sm text-zinc-400">{entry.domain_status === 'primary' ? 'Primary' : entry.domain_status === '301_redirect' ? '301' : entry.domain_status === '302_redirect' ? '302' : entry.domain_status || 'Canonical'}</TableCell>
                                                                        <TableCell className="w-[15%] text-sm text-zinc-400 font-mono">{isMainNode ? '—' : (entry.target_node_label || '-')}</TableCell>
                                                                        <TableCell className="w-[15%] text-right">
                                                                            <div className="flex items-center justify-end gap-1">
                                                                                <Button variant="ghost" size="sm" onClick={() => handleNodeClick(entry)} className="h-7 px-2 text-zinc-400 hover:text-white">View</Button>
                                                                                <DropdownMenu>
                                                                                    <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" onClick={(e) => e.stopPropagation()} className="h-7 w-7"><MoreVertical className="h-3.5 w-3.5" /></Button></DropdownMenuTrigger>
                                                                                    <DropdownMenuContent align="end">
                                                                                        <DropdownMenuItem onClick={() => openEditDialog(entry)}><Edit className="h-4 w-4 mr-2" />Edit</DropdownMenuItem>
                                                                                        {!isMainNode && <DropdownMenuItem onClick={() => openSwitchMainDialog(entry)} className="text-amber-400"><Crown className="h-4 w-4 mr-2" />Make Main</DropdownMenuItem>}
                                                                                        <DropdownMenuSeparator />
                                                                                        <DropdownMenuItem onClick={() => openDeleteDialog(entry)} className="text-red-400"><Trash2 className="h-4 w-4 mr-2" />Delete</DropdownMenuItem>
                                                                                    </DropdownMenuContent>
                                                                                </DropdownMenu>
                                                                            </div>
                                                                        </TableCell>
                                                                    </TableRow>
                                                                );
                                                            })}
                                                        </TableBody>
                                                    </Table>
                                                </div>
                                            )}
                                        </Card>
                                    );
                                })}
                            </div>
                        ) : (
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
                                                            <DropdownMenu>
                                                                <DropdownMenuTrigger asChild>
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="icon"
                                                                        onClick={(e) => e.stopPropagation()}
                                                                        className="h-7 w-7"
                                                                    >
                                                                        <MoreVertical className="h-3.5 w-3.5" />
                                                                    </Button>
                                                                </DropdownMenuTrigger>
                                                                <DropdownMenuContent align="end">
                                                                    <DropdownMenuItem onClick={() => openEditDialog(entry)}>
                                                                        <Edit className="h-4 w-4 mr-2" />
                                                                        Edit Node
                                                                    </DropdownMenuItem>
                                                                    {entry.domain_role !== 'main' && (
                                                                        <DropdownMenuItem 
                                                                            onClick={() => openSwitchMainDialog(entry)}
                                                                            className="text-amber-400"
                                                                        >
                                                                            <Crown className="h-4 w-4 mr-2" />
                                                                            Switch to Main Target
                                                                        </DropdownMenuItem>
                                                                    )}
                                                                    <DropdownMenuSeparator />
                                                                    <DropdownMenuItem 
                                                                        onClick={() => openDeleteDialog(entry)}
                                                                        className="text-red-400"
                                                                    >
                                                                        <Trash2 className="h-4 w-4 mr-2" />
                                                                        Delete Node
                                                                    </DropdownMenuItem>
                                                                </DropdownMenuContent>
                                                            </DropdownMenu>
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
                        )}
                    </TabsContent>

                    {/* Change History Tab */}
                    <TabsContent value="history" className="mt-0">
                        <Card className="bg-card border-border">
                            <CardHeader className="pb-4 flex flex-row items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <CardTitle className="text-lg flex items-center gap-2">
                                        <History className="h-5 w-5" />
                                        SEO Change History
                                    </CardTitle>
                                    {/* Filter Toggle */}
                                    <Button
                                        variant={isFilterOpen ? "secondary" : "outline"}
                                        size="sm"
                                        onClick={() => setIsFilterOpen(!isFilterOpen)}
                                    >
                                        <Filter className="h-4 w-4 mr-1" />
                                        Filters
                                        {(timelineFilters.actor || timelineFilters.action || timelineFilters.node || timelineFilters.dateFrom) && (
                                            <Badge className="ml-1 bg-amber-500 text-black">Active</Badge>
                                        )}
                                    </Button>
                                </div>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => loadChangeHistory(timelineFilters)}
                                    disabled={changeHistoryLoading}
                                >
                                    {changeHistoryLoading ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <RefreshCw className="h-4 w-4" />
                                    )}
                                </Button>
                            </CardHeader>
                            
                            {/* Filter Panel */}
                            {isFilterOpen && (
                                <div className="px-6 pb-4 border-b border-border">
                                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                                        <div className="space-y-1">
                                            <Label className="text-xs text-zinc-500">User</Label>
                                            <Input
                                                placeholder="Email..."
                                                value={timelineFilters.actor}
                                                onChange={(e) => setTimelineFilters({...timelineFilters, actor: e.target.value})}
                                                className="h-8 bg-black border-border"
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <Label className="text-xs text-zinc-500">Action</Label>
                                            <Select 
                                                value={timelineFilters.action || 'all'} 
                                                onValueChange={(v) => setTimelineFilters({...timelineFilters, action: v === 'all' ? '' : v})}
                                            >
                                                <SelectTrigger className="h-8 bg-black border-border">
                                                    <SelectValue placeholder="All" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="all">All Actions</SelectItem>
                                                    <SelectItem value="create_node">Created</SelectItem>
                                                    <SelectItem value="update_node">Updated</SelectItem>
                                                    <SelectItem value="delete_node">Deleted</SelectItem>
                                                    <SelectItem value="relink_node">Relinked</SelectItem>
                                                    <SelectItem value="change_role">Role Changed</SelectItem>
                                                    <SelectItem value="change_path">Path Changed</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-1">
                                            <Label className="text-xs text-zinc-500">Node</Label>
                                            <Input
                                                placeholder="Domain or path..."
                                                value={timelineFilters.node}
                                                onChange={(e) => setTimelineFilters({...timelineFilters, node: e.target.value})}
                                                className="h-8 bg-black border-border"
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <Label className="text-xs text-zinc-500">From Date</Label>
                                            <Input
                                                type="date"
                                                value={timelineFilters.dateFrom}
                                                onChange={(e) => setTimelineFilters({...timelineFilters, dateFrom: e.target.value})}
                                                className="h-8 bg-black border-border"
                                            />
                                        </div>
                                        <div className="flex items-end gap-2">
                                            <Button size="sm" onClick={applyTimelineFilters} className="h-8">
                                                Apply
                                            </Button>
                                            <Button size="sm" variant="ghost" onClick={clearTimelineFilters} className="h-8">
                                                Clear
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            )}
                            
                            <CardContent>
                                {changeHistoryLoading ? (
                                    <div className="flex items-center justify-center py-12">
                                        <Loader2 className="h-8 w-8 animate-spin text-zinc-500" />
                                    </div>
                                ) : changeHistory.length === 0 ? (
                                    <div className="text-center py-12">
                                        <History className="h-12 w-12 text-zinc-700 mx-auto mb-3" />
                                        <p className="text-zinc-500">No change history yet</p>
                                        <p className="text-sm text-zinc-600 mt-1">
                                            Changes will appear here when you modify SEO structure
                                        </p>
                                    </div>
                                ) : (
                                    <div className="data-table-container" data-testid="change-history-table">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead className="w-[140px]">Date</TableHead>
                                                    <TableHead className="w-[160px]">User</TableHead>
                                                    <TableHead>Domain / Path</TableHead>
                                                    <TableHead className="w-[120px]">Action</TableHead>
                                                    <TableHead>Note</TableHead>
                                                    <TableHead className="w-[80px] text-right">Details</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {changeHistory.map((log) => (
                                                    <TableRow 
                                                        key={log.id} 
                                                        className="table-row-hover cursor-pointer"
                                                        onClick={() => handleViewChangeDetail(log)}
                                                        data-testid={`change-log-${log.id}`}
                                                    >
                                                        <TableCell className="text-xs text-zinc-400">
                                                            <div className="flex items-center gap-1">
                                                                <Clock className="h-3 w-3" />
                                                                {formatChangeDate(log.created_at)}
                                                            </div>
                                                        </TableCell>
                                                        <TableCell>
                                                            <div className="flex items-center gap-2">
                                                                <div className="h-6 w-6 rounded-full bg-zinc-700 flex items-center justify-center">
                                                                    <User className="h-3 w-3 text-zinc-400" />
                                                                </div>
                                                                <span className="text-sm text-zinc-300 truncate max-w-[120px]">
                                                                    {log.actor_email?.split('@')[0] || 'Unknown'}
                                                                </span>
                                                            </div>
                                                        </TableCell>
                                                        <TableCell>
                                                            <span className="font-mono text-sm text-white">
                                                                {log.affected_node}
                                                            </span>
                                                        </TableCell>
                                                        <TableCell>
                                                            <Badge className={`text-xs ${ACTION_TYPE_COLORS[log.action_type] || 'bg-zinc-500/20 text-zinc-400'}`}>
                                                                {ACTION_TYPE_LABELS[log.action_type] || log.action_type}
                                                            </Badge>
                                                        </TableCell>
                                                        <TableCell>
                                                            <span className="text-sm text-zinc-400 line-clamp-1">
                                                                {log.change_note}
                                                            </span>
                                                        </TableCell>
                                                        <TableCell className="text-right">
                                                            <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                                                                <Eye className="h-4 w-4" />
                                                            </Button>
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Alerts Tab */}
                    <TabsContent value="alerts" className="mt-0">
                        <Card className="bg-card border-border">
                            <CardHeader className="pb-4 flex flex-row items-center justify-between">
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <Bell className="h-5 w-5" />
                                    Network Alerts
                                    {unreadCount > 0 && (
                                        <Badge className="bg-red-500 text-white">{unreadCount} unread</Badge>
                                    )}
                                </CardTitle>
                                <div className="flex items-center gap-2">
                                    {unreadCount > 0 && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={handleMarkAllNotificationsRead}
                                        >
                                            <Check className="h-4 w-4 mr-1" />
                                            Mark all read
                                        </Button>
                                    )}
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={loadNotifications}
                                        disabled={notificationsLoading}
                                    >
                                        {notificationsLoading ? (
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                        ) : (
                                            <RefreshCw className="h-4 w-4" />
                                        )}
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {notificationsLoading ? (
                                    <div className="flex items-center justify-center py-12">
                                        <Loader2 className="h-8 w-8 animate-spin text-zinc-500" />
                                    </div>
                                ) : notifications.length === 0 ? (
                                    <div className="text-center py-12">
                                        <Bell className="h-12 w-12 text-zinc-700 mx-auto mb-3" />
                                        <p className="text-zinc-500">No alerts yet</p>
                                        <p className="text-sm text-zinc-600 mt-1">
                                            Important SEO changes will generate alerts here
                                        </p>
                                    </div>
                                ) : (
                                    <ScrollArea className="h-[500px] pr-4">
                                        <div className="space-y-3" data-testid="alerts-list">
                                            {notifications.map((notification) => (
                                                <div
                                                    key={notification.id}
                                                    className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                                                        notification.read 
                                                            ? 'bg-card border-border hover:bg-zinc-900/50' 
                                                            : 'bg-blue-500/5 border-blue-500/30 hover:bg-blue-500/10'
                                                    }`}
                                                    onClick={() => handleNotificationClick(notification)}
                                                    data-testid={`notification-${notification.id}`}
                                                >
                                                    <div className="flex items-start justify-between gap-3">
                                                        <div className="flex-1">
                                                            <div className="flex items-center gap-2 mb-1">
                                                                {!notification.read && (
                                                                    <div className="h-2 w-2 rounded-full bg-blue-500" />
                                                                )}
                                                                <span className="font-medium text-white">
                                                                    {NOTIFICATION_TYPE_LABELS[notification.notification_type] || notification.title}
                                                                </span>
                                                            </div>
                                                            <p className="text-sm text-zinc-400 mb-2">{notification.message}</p>
                                                            {notification.affected_node && (
                                                                <div className="text-xs font-mono text-zinc-500 mb-2">
                                                                    Node: {notification.affected_node}
                                                                </div>
                                                            )}
                                                            <div className="flex items-center gap-3 text-xs text-zinc-500">
                                                                <span className="flex items-center gap-1">
                                                                    <Clock className="h-3 w-3" />
                                                                    {formatChangeDate(notification.created_at)}
                                                                </span>
                                                                {notification.actor_email && (
                                                                    <span className="flex items-center gap-1">
                                                                        <User className="h-3 w-3" />
                                                                        {notification.actor_email.split('@')[0]}
                                                                    </span>
                                                                )}
                                                            </div>
                                                            {notification.change_note && (
                                                                <div className="mt-2 p-2 bg-black/30 rounded text-xs text-zinc-400">
                                                                    <span className="text-amber-400">Note:</span> {notification.change_note}
                                                                </div>
                                                            )}
                                                        </div>
                                                        <Button variant="ghost" size="sm" className="h-8 w-8 p-0 shrink-0">
                                                            <ChevronRight className="h-4 w-4" />
                                                        </Button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </ScrollArea>
                                )}
                            </CardContent>
                        </Card>
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

                {/* Change Detail Sheet */}
                <Sheet open={changeDetailOpen} onOpenChange={(open) => {
                    setChangeDetailOpen(open);
                    if (!open) {
                        setHighlightedNodeId(null);  // Clear highlight when closing
                    }
                }}>
                    <SheetContent className="bg-card border-border w-full sm:max-w-lg">
                        <SheetHeader>
                            <SheetTitle className="font-mono text-lg flex items-center gap-2">
                                <History className="h-5 w-5" />
                                Change Details
                            </SheetTitle>
                        </SheetHeader>
                        
                        {selectedChangeLog && (
                            <div className="mt-6 space-y-6">
                                {/* Action Badge */}
                                <Badge className={`text-sm ${ACTION_TYPE_COLORS[selectedChangeLog.action_type] || 'bg-zinc-500/20 text-zinc-400'}`}>
                                    {ACTION_TYPE_LABELS[selectedChangeLog.action_type] || selectedChangeLog.action_type}
                                </Badge>

                                {/* Quick Info */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Affected Node</span>
                                        <span className="font-mono text-sm text-white">
                                            {selectedChangeLog.affected_node}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Changed by</span>
                                        <span className="text-sm text-zinc-300">
                                            {selectedChangeLog.actor_email}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Date</span>
                                        <span className="text-sm text-zinc-300">
                                            {new Date(selectedChangeLog.created_at).toLocaleString()}
                                        </span>
                                    </div>
                                </div>

                                {/* Change Note */}
                                <div className="space-y-2">
                                    <Label className="text-amber-400">Change Note</Label>
                                    <div className="p-3 bg-amber-500/10 border border-amber-400/30 rounded-lg">
                                        <p className="text-sm text-zinc-300">{selectedChangeLog.change_note}</p>
                                    </div>
                                </div>

                                {/* Before/After Snapshot - Human Readable */}
                                {(selectedChangeLog.before_snapshot || selectedChangeLog.after_snapshot) && (
                                    <div className="space-y-4">
                                        <Label className="text-zinc-400">Before / After (Human Readable)</Label>
                                        
                                        <div className="grid grid-cols-2 gap-4">
                                            {/* Before */}
                                            <div className="space-y-2">
                                                <div className="text-xs text-red-400 uppercase font-medium">Before</div>
                                                <div className="p-3 bg-red-500/5 border border-red-500/20 rounded-lg">
                                                    {selectedChangeLog.before_snapshot ? (
                                                        <div className="space-y-2 text-xs">
                                                            {selectedChangeLog.before_snapshot.domain_role_label && (
                                                                <div><span className="text-zinc-500">Role:</span> <span className="text-red-300">{selectedChangeLog.before_snapshot.domain_role_label}</span></div>
                                                            )}
                                                            {selectedChangeLog.before_snapshot.optimized_path && (
                                                                <div><span className="text-zinc-500">Path:</span> <span className="font-mono">{selectedChangeLog.before_snapshot.optimized_path}</span></div>
                                                            )}
                                                            {selectedChangeLog.before_snapshot.domain_status_label && (
                                                                <div><span className="text-zinc-500">Status:</span> {selectedChangeLog.before_snapshot.domain_status_label}</div>
                                                            )}
                                                            {selectedChangeLog.before_snapshot.index_status_label && (
                                                                <div><span className="text-zinc-500">Index:</span> {selectedChangeLog.before_snapshot.index_status_label}</div>
                                                            )}
                                                            {selectedChangeLog.before_snapshot.target_node_label ? (
                                                                <div><span className="text-zinc-500">Target:</span> <span className="font-mono text-red-300">{selectedChangeLog.before_snapshot.target_node_label}</span></div>
                                                            ) : selectedChangeLog.before_snapshot.target_entry_id && (
                                                                <div><span className="text-zinc-500">Target:</span> <span className="font-mono">{selectedChangeLog.before_snapshot.target_entry_id.slice(0, 8)}...</span></div>
                                                            )}
                                                        </div>
                                                    ) : (
                                                        <span className="text-zinc-500 text-xs">N/A (New)</span>
                                                    )}
                                                </div>
                                            </div>
                                            
                                            {/* After */}
                                            <div className="space-y-2">
                                                <div className="text-xs text-emerald-400 uppercase font-medium">After</div>
                                                <div className="p-3 bg-emerald-500/5 border border-emerald-500/20 rounded-lg">
                                                    {selectedChangeLog.after_snapshot ? (
                                                        <div className="space-y-2 text-xs">
                                                            {selectedChangeLog.after_snapshot.domain_role_label && (
                                                                <div><span className="text-zinc-500">Role:</span> <span className="text-emerald-300">{selectedChangeLog.after_snapshot.domain_role_label}</span></div>
                                                            )}
                                                            {selectedChangeLog.after_snapshot.optimized_path && (
                                                                <div><span className="text-zinc-500">Path:</span> <span className="font-mono">{selectedChangeLog.after_snapshot.optimized_path}</span></div>
                                                            )}
                                                            {selectedChangeLog.after_snapshot.domain_status_label && (
                                                                <div><span className="text-zinc-500">Status:</span> {selectedChangeLog.after_snapshot.domain_status_label}</div>
                                                            )}
                                                            {selectedChangeLog.after_snapshot.index_status_label && (
                                                                <div><span className="text-zinc-500">Index:</span> {selectedChangeLog.after_snapshot.index_status_label}</div>
                                                            )}
                                                            {selectedChangeLog.after_snapshot.target_node_label ? (
                                                                <div><span className="text-zinc-500">Target:</span> <span className="font-mono text-emerald-300">{selectedChangeLog.after_snapshot.target_node_label}</span></div>
                                                            ) : selectedChangeLog.after_snapshot.target_entry_id && (
                                                                <div><span className="text-zinc-500">Target:</span> <span className="font-mono">{selectedChangeLog.after_snapshot.target_entry_id.slice(0, 8)}...</span></div>
                                                            )}
                                                        </div>
                                                    ) : (
                                                        <span className="text-zinc-500 text-xs">N/A (Deleted)</span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Action Button - View in Graph */}
                                {(selectedChangeLog.entry_id || selectedChangeLog.after_snapshot?.id) && (
                                    <Button
                                        variant="outline"
                                        className="w-full"
                                        data-testid="view-node-graph-btn"
                                        onClick={() => {
                                            // Find the entry and highlight it in the graph
                                            // Support both entry_id (new format) and after_snapshot.id (fallback)
                                            const entryId = selectedChangeLog.entry_id || selectedChangeLog.after_snapshot?.id;
                                            const entry = network?.entries?.find(e => e.id === entryId);
                                            if (entry) {
                                                setHighlightedNodeId(entry.asset_domain_id);
                                                setActiveTab('graph');
                                                setChangeDetailOpen(false);
                                                toast.success('Node highlighted in graph');
                                            } else {
                                                toast.info('Node no longer exists in this network');
                                            }
                                        }}
                                    >
                                        <Eye className="h-4 w-4 mr-2" />
                                        View Node in Graph
                                    </Button>
                                )}
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
                                                    onValueChange={(v) => setEditForm({
                                                        ...editForm, 
                                                        domain_role: v,
                                                        // Auto-update status when role changes
                                                        domain_status: v === 'main' ? 'primary' : (editForm.domain_status === 'primary' ? 'canonical' : editForm.domain_status),
                                                        // Clear target when switching to main
                                                        target_entry_id: v === 'main' ? '' : editForm.target_entry_id
                                                    })}
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
                                                    disabled={editForm.domain_role === 'main'}
                                                >
                                                    <SelectTrigger className="bg-black border-border">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {(editForm.domain_role === 'main' 
                                                            ? SEO_STATUS_OPTIONS_MAIN 
                                                            : SEO_STATUS_OPTIONS_SUPPORTING
                                                        ).map(opt => (
                                                            <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                                {editForm.domain_role === 'main' && (
                                                    <p className="text-xs text-amber-400">Main nodes have Primary status (no redirect)</p>
                                                )}
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

                                    {/* Change Note (Required) - Enhanced UX */}
                                    <ChangeNoteInput
                                        value={editForm.change_note}
                                        onChange={(value) => setEditForm({...editForm, change_note: value})}
                                        label="Change Note"
                                        placeholder="Explain the reason for this change. Include: what, why, and expected impact..."
                                        required={true}
                                        variant="default"
                                    />
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
                                    disabled={saving || !editForm.change_note || editForm.change_note.trim().length < 10}
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
                    <DialogContent className="bg-card border-border max-w-lg">
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

                        {/* Change Note (Required for Delete) - Enhanced UX */}
                        <ChangeNoteInput
                            value={deleteChangeNote}
                            onChange={setDeleteChangeNote}
                            label="Reason for Deletion"
                            placeholder="Why are you deleting this node? Include business context and any alternative strategies considered..."
                            required={true}
                            variant="delete"
                        />

                        <DialogFooter>
                            <Button
                                variant="outline"
                                onClick={() => setDeleteDialogOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleDeleteNode}
                                disabled={deleting || !deleteChangeNote || deleteChangeNote.trim().length < 10}
                                className="bg-red-600 hover:bg-red-700"
                            >
                                {deleting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                Delete Node
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Switch Main Target Dialog */}
                <Dialog open={switchMainDialogOpen} onOpenChange={setSwitchMainDialogOpen}>
                    <DialogContent className="bg-card border-border max-w-lg">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <Crown className="h-5 w-5 text-amber-400" />
                                Switch Main Target
                            </DialogTitle>
                            <DialogDescription>
                                This will safely transfer the main target role to a new node.
                            </DialogDescription>
                        </DialogHeader>
                        
                        {entryToPromote && (
                            <div className="space-y-4">
                                <div className="p-4 bg-emerald-500/10 border border-emerald-400/30 rounded-lg">
                                    <div className="text-xs text-emerald-400 uppercase font-medium mb-1">New Main Target</div>
                                    <div className="font-mono text-lg text-white">
                                        {entryToPromote.node_label || entryToPromote.domain_name}
                                    </div>
                                    <div className="text-sm text-zinc-400 mt-1">
                                        {entryToPromote.optimized_path 
                                            ? `Path: ${entryToPromote.optimized_path}` 
                                            : 'Root domain (no path)'}
                                    </div>
                                </div>

                                <div className="p-3 bg-zinc-900 rounded-lg text-sm text-zinc-400">
                                    <p className="font-medium text-white mb-2">What will happen:</p>
                                    <ul className="space-y-1 list-disc list-inside">
                                        <li>Current main node → Supporting (canonical to new main)</li>
                                        <li>Selected node → Main (primary status, no target)</li>
                                        <li>All tiers will be recalculated via BFS</li>
                                        <li>All other nodes remain unchanged</li>
                                    </ul>
                                </div>

                                {/* Change Note (Required) */}
                                <ChangeNoteInput
                                    value={switchMainChangeNote}
                                    onChange={setSwitchMainChangeNote}
                                    label="Reason for Change"
                                    placeholder="Why are you switching the main target? Include: strategic reasoning, expected SEO impact, and any optimization goals..."
                                    required={true}
                                    variant="default"
                                />
                            </div>
                        )}

                        <DialogFooter>
                            <Button
                                variant="outline"
                                onClick={() => setSwitchMainDialogOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleSwitchMainTarget}
                                disabled={switching || !switchMainChangeNote || switchMainChangeNote.trim().length < 10}
                                className="bg-amber-600 hover:bg-amber-700"
                            >
                                {switching && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                <ArrowRightLeft className="h-4 w-4 mr-2" />
                                Switch Main Target
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

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Role</Label>
                                    <Select 
                                        value={addNodeForm.domain_role} 
                                        onValueChange={(v) => setAddNodeForm({
                                            ...addNodeForm, 
                                            domain_role: v,
                                            // Auto-set status based on role
                                            domain_status: v === 'main' ? 'primary' : 'canonical',
                                            // Clear target if switching to main
                                            target_entry_id: v === 'main' ? '' : addNodeForm.target_entry_id
                                        })}
                                    >
                                        <SelectTrigger className="bg-black border-border">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="supporting">Supporting</SelectItem>
                                            <SelectItem value="main">Main (LP/Money Site)</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-2">
                                    <Label>Status</Label>
                                    <Select 
                                        value={addNodeForm.domain_status} 
                                        onValueChange={(v) => setAddNodeForm({...addNodeForm, domain_status: v})}
                                        disabled={addNodeForm.domain_role === 'main'}
                                    >
                                        <SelectTrigger className="bg-black border-border">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {addNodeForm.domain_role === 'main' ? (
                                                <SelectItem value="primary">Primary Target</SelectItem>
                                            ) : (
                                                <>
                                                    <SelectItem value="canonical">Canonical</SelectItem>
                                                    <SelectItem value="301_redirect">301 Redirect</SelectItem>
                                                    <SelectItem value="302_redirect">302 Redirect</SelectItem>
                                                    <SelectItem value="restore">Restore</SelectItem>
                                                </>
                                            )}
                                        </SelectContent>
                                    </Select>
                                </div>
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
                                {addNodeForm.domain_role === 'main' && (
                                    <p className="text-xs text-amber-400">
                                        Main nodes are the primary target - they don't point to other nodes.
                                    </p>
                                )}
                            </div>

                            {/* Change Note (Required) - Enhanced UX */}
                            <ChangeNoteInput
                                value={addNodeForm.change_note}
                                onChange={(value) => setAddNodeForm({...addNodeForm, change_note: value})}
                                label="Change Note"
                                placeholder="Why are you adding this node? Include: strategic purpose, target keywords, expected impact..."
                                required={true}
                                variant="add"
                            />
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
                                disabled={saving || !addNodeForm.asset_domain_id || !addNodeForm.change_note || addNodeForm.change_note.trim().length < 10}
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
