import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { v3ReportsAPI, conflictsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import { 
    AlertTriangle,
    CheckCircle, 
    Loader2, 
    Network,
    ExternalLink,
    RefreshCw,
    Link2,
    ClipboardList,
    BarChart3,
    Plus,
    Clock,
    Table,
    LayoutGrid
} from 'lucide-react';

// Conflict severity badge colors
const CONFLICT_SEVERITY_CLASSES = {
    critical: 'bg-red-500/20 text-red-400 border-red-500/30',
    high: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    low: 'bg-blue-500/20 text-blue-400 border-blue-500/30'
};

// Conflict type labels
const CONFLICT_TYPE_LABELS = {
    'type_a': 'Keyword Cannibalization',
    'type_b': 'Competing Targets',
    'type_c': 'Canonical Mismatch',
    'type_d': 'Tier Inversion',
    'orphan': 'Orphan Node',
    'noindex_high_tier': 'NOINDEX in High Tier',
    'keyword_cannibalization': 'Keyword Cannibalization',
    'competing_targets': 'Competing Targets',
    'canonical_mismatch': 'Canonical Mismatch',
    'tier_inversion': 'Tier Inversion',
    'redirect_loop': 'Redirect Loop',
    'multiple_parents_to_main': 'Multiple Parents to Main',
    'canonical_redirect_conflict': 'Canonical-Redirect Conflict',
    'index_noindex_mismatch': 'Index/Noindex Mismatch'
};

// Status colors and flow for stored conflicts
const STATUS_FLOW = {
    detected: { 
        label: 'Detected', 
        color: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
        description: 'Conflict detected, awaiting resolution'
    },
    under_review: { 
        label: 'In Progress', 
        color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        description: 'Being worked on'
    },
    resolved: { 
        label: 'Resolved', 
        color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        description: 'Conflict fixed and verified'
    },
    ignored: { 
        label: 'Ignored', 
        color: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
        description: 'Marked as acceptable'
    },
};

export default function AlertsPage() {
    const [conflicts, setConflicts] = useState([]);
    const [storedConflicts, setStoredConflicts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [processing, setProcessing] = useState(false);
    const [viewMode, setViewMode] = useState('table'); // 'table' or 'cards'
    const [activeTab, setActiveTab] = useState('all'); // 'all', 'detected', 'in_progress', 'resolved'
    const [creatingTask, setCreatingTask] = useState(null);

    useEffect(() => {
        loadConflicts();
    }, []);

    const loadConflicts = async () => {
        setLoading(true);
        try {
            // Load both detected and stored conflicts
            const [detectedRes, storedRes] = await Promise.all([
                v3ReportsAPI.getConflicts(),
                conflictsAPI.getStored()
            ]);
            
            setConflicts(detectedRes.data?.conflicts || []);
            setStoredConflicts(storedRes.data?.conflicts || []);
        } catch (err) {
            console.error('Failed to load conflicts:', err);
            toast.error('Failed to load SEO conflicts');
        } finally {
            setLoading(false);
        }
    };

    const handleProcessConflicts = async () => {
        setProcessing(true);
        try {
            const res = await conflictsAPI.process();
            const data = res.data;
            
            if (data.success) {
                toast.success(
                    `Processed ${data.conflicts_processed} conflicts. Created ${data.optimizations_created} optimization tasks.`
                );
                loadConflicts(); // Reload to show updated data
            }
        } catch (err) {
            console.error('Failed to process conflicts:', err);
            toast.error('Failed to process conflicts');
        } finally {
            setProcessing(false);
        }
    };

    const handleCreateTaskForConflict = async (conflictId) => {
        setCreatingTask(conflictId);
        try {
            const res = await conflictsAPI.createOptimization(conflictId);
            if (res.data?.success) {
                toast.success('Optimization task created successfully');
                loadConflicts(); // Reload to update the view
            }
        } catch (err) {
            console.error('Failed to create task:', err);
            toast.error(err.response?.data?.detail || 'Failed to create optimization task');
        } finally {
            setCreatingTask(null);
        }
    };

    // Create a map of stored conflicts by their key for quick lookup
    const storedConflictMap = storedConflicts.reduce((acc, c) => {
        const key = `${c.network_id}|${c.conflict_type}|${c.node_a_id}|${c.node_b_id || ''}`;
        acc[key] = c;
        return acc;
    }, {});

    // Enhance detected conflicts with stored info (linked optimization)
    const enhancedConflicts = conflicts.map(c => {
        const key = `${c.network_id}|${c.conflict_type}|${c.node_a_id}|${c.node_b_id || ''}`;
        const stored = storedConflictMap[key];
        return {
            ...c,
            stored_conflict: stored,
            linked_optimization: stored?.linked_optimization
        };
    });

    // Conflict stats
    const conflictStats = {
        total: enhancedConflicts.length,
        critical: enhancedConflicts.filter(c => c.severity === 'critical').length,
        high: enhancedConflicts.filter(c => c.severity === 'high').length,
        linked: enhancedConflicts.filter(c => c.linked_optimization).length,
        byType: enhancedConflicts.reduce((acc, c) => {
            const type = c.conflict_type || 'unknown';
            acc[type] = (acc[type] || 0) + 1;
            return acc;
        }, {})
    };

    // Stored conflict stats for tabs
    const storedStats = {
        all: storedConflicts.length,
        detected: storedConflicts.filter(c => c.status === 'detected').length,
        in_progress: storedConflicts.filter(c => c.status === 'under_review').length,
        resolved: storedConflicts.filter(c => c.status === 'resolved').length
    };

    // Filter stored conflicts based on active tab
    const filteredStoredConflicts = storedConflicts.filter(c => {
        if (activeTab === 'all') return true;
        if (activeTab === 'detected') return c.status === 'detected';
        if (activeTab === 'in_progress') return c.status === 'under_review';
        if (activeTab === 'resolved') return c.status === 'resolved';
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
            <div data-testid="alerts-page">
                {/* Header */}
                <div className="page-header">
                    <div className="flex items-center justify-between w-full">
                        <div className="flex items-center gap-3">
                            <AlertTriangle className="h-7 w-7 text-amber-500" />
                            <div>
                                <h1 className="page-title">SEO Conflicts</h1>
                                <p className="page-subtitle">
                                    Detect and resolve SEO configuration issues across networks
                                </p>
                            </div>
                        </div>
                        <Button
                            variant="outline"
                            onClick={() => window.location.href = '/conflicts/dashboard'}
                            data-testid="conflict-dashboard-btn"
                        >
                            <BarChart3 className="h-4 w-4 mr-2" />
                            Resolution Dashboard
                        </Button>
                    </div>
                </div>

                {/* Stats Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <Card className="bg-card border-border">
                        <CardContent className="pt-4">
                            <div className="text-sm text-zinc-500 mb-1">Total Conflicts</div>
                            <div className="text-2xl font-bold font-mono">{conflictStats.total}</div>
                        </CardContent>
                    </Card>
                    <Card className={`bg-card border-border ${conflictStats.critical > 0 ? 'border-red-900/50' : ''}`}>
                        <CardContent className="pt-4">
                            <div className="text-sm text-zinc-500 mb-1">Critical</div>
                            <div className={`text-2xl font-bold font-mono ${conflictStats.critical > 0 ? 'text-red-500' : 'text-zinc-400'}`}>
                                {conflictStats.critical}
                            </div>
                        </CardContent>
                    </Card>
                    <Card className={`bg-card border-border ${conflictStats.high > 0 ? 'border-amber-900/50' : ''}`}>
                        <CardContent className="pt-4">
                            <div className="text-sm text-zinc-500 mb-1">High Priority</div>
                            <div className={`text-2xl font-bold font-mono ${conflictStats.high > 0 ? 'text-amber-500' : 'text-zinc-400'}`}>
                                {conflictStats.high}
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="bg-card border-border">
                        <CardContent className="pt-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <div className="text-sm text-zinc-500 mb-1">Refresh</div>
                                    <Button 
                                        variant="outline" 
                                        size="sm" 
                                        onClick={loadConflicts}
                                        disabled={loading}
                                        data-testid="refresh-conflicts-btn"
                                    >
                                        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                                    </Button>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Action Button - Only show when conflicts exist */}
                {enhancedConflicts.length > 0 && (
                    <div className="flex justify-between items-center mb-4">
                        <div className="flex items-center gap-2">
                            <Button
                                variant={viewMode === 'table' ? 'secondary' : 'outline'}
                                size="sm"
                                onClick={() => setViewMode('table')}
                                data-testid="view-table-btn"
                            >
                                <Table className="h-4 w-4 mr-1" />
                                Table
                            </Button>
                            <Button
                                variant={viewMode === 'cards' ? 'secondary' : 'outline'}
                                size="sm"
                                onClick={() => setViewMode('cards')}
                                data-testid="view-cards-btn"
                            >
                                <LayoutGrid className="h-4 w-4 mr-1" />
                                Cards
                            </Button>
                        </div>
                        <Button 
                            onClick={handleProcessConflicts}
                            disabled={processing}
                            className="bg-emerald-600 hover:bg-emerald-700"
                            data-testid="process-conflicts-btn"
                        >
                            {processing ? (
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            ) : (
                                <ClipboardList className="h-4 w-4 mr-2" />
                            )}
                            Create Optimization Tasks
                        </Button>
                    </div>
                )}

                {/* Stored Conflicts Section - Detailed Table */}
                {storedConflicts.length > 0 && (
                    <Card className="bg-card border-border mb-6" data-testid="stored-conflicts-section">
                        <CardHeader className="pb-2">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <Clock className="h-4 w-4 text-purple-400" />
                                    Tracked Conflicts
                                    <Badge variant="outline" className="ml-2">{storedStats.all}</Badge>
                                </CardTitle>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {/* Status Tabs */}
                            <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-4">
                                <TabsList className="bg-zinc-900 border border-zinc-800">
                                    <TabsTrigger value="all" className="data-[state=active]:bg-zinc-800">
                                        All ({storedStats.all})
                                    </TabsTrigger>
                                    <TabsTrigger value="detected" className="data-[state=active]:bg-amber-500/20 data-[state=active]:text-amber-400">
                                        Detected ({storedStats.detected})
                                    </TabsTrigger>
                                    <TabsTrigger value="in_progress" className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400">
                                        In Progress ({storedStats.in_progress})
                                    </TabsTrigger>
                                    <TabsTrigger value="resolved" className="data-[state=active]:bg-emerald-500/20 data-[state=active]:text-emerald-400">
                                        Resolved ({storedStats.resolved})
                                    </TabsTrigger>
                                </TabsList>
                            </Tabs>

                            {/* Detailed Table */}
                            <div className="overflow-x-auto">
                                <table className="w-full" data-testid="conflicts-table">
                                    <thead>
                                        <tr className="border-b border-zinc-800">
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Type</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Severity</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Status</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Node</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Network</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Detected</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Resolved</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {filteredStoredConflicts.map((conflict) => {
                                            const severityColors = {
                                                critical: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' },
                                                high: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30' },
                                                medium: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30' },
                                                low: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30' },
                                            };
                                            const colors = severityColors[conflict.severity] || severityColors.medium;
                                            const statusInfo = STATUS_FLOW[conflict.status] || STATUS_FLOW.detected;
                                            
                                            return (
                                                <tr key={conflict.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30" data-testid={`stored-conflict-${conflict.id}`}>
                                                    <td className="py-3 px-4">
                                                        <span className="text-sm text-white">
                                                            {CONFLICT_TYPE_LABELS[conflict.conflict_type] || conflict.conflict_type}
                                                        </span>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        <Badge className={`${colors.bg} ${colors.text} ${colors.border}`}>
                                                            {conflict.severity?.toUpperCase()}
                                                        </Badge>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        <Badge className={statusInfo.color}>
                                                            {statusInfo.label}
                                                        </Badge>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        <code className="text-xs text-zinc-400 bg-zinc-900 px-2 py-1 rounded">
                                                            {conflict.node_a_label?.substring(0, 35)}
                                                            {conflict.node_a_label?.length > 35 ? '...' : ''}
                                                        </code>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        {conflict.network_id ? (
                                                            <Button
                                                                variant="link"
                                                                size="sm"
                                                                onClick={() => window.location.href = `/groups/${conflict.network_id}`}
                                                                className="text-xs text-zinc-400 hover:text-blue-400 p-0 h-auto"
                                                            >
                                                                {conflict.network_name || 'View Network'}
                                                                <ExternalLink className="h-3 w-3 ml-1" />
                                                            </Button>
                                                        ) : (
                                                            <span className="text-sm text-zinc-500">-</span>
                                                        )}
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        <span className="text-xs text-zinc-500">
                                                            {conflict.detected_at ? new Date(conflict.detected_at).toLocaleDateString() : '-'}
                                                        </span>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        <span className="text-xs text-zinc-500">
                                                            {conflict.resolved_at ? new Date(conflict.resolved_at).toLocaleDateString() : '-'}
                                                        </span>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        {conflict.linked_optimization ? (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() => window.location.href = `/optimizations/${conflict.linked_optimization.id}`}
                                                                className="text-xs border-blue-500/30 text-blue-400 hover:bg-blue-500/10"
                                                                data-testid={`view-task-${conflict.id}`}
                                                            >
                                                                <ClipboardList className="h-3 w-3 mr-1" />
                                                                View Task
                                                            </Button>
                                                        ) : conflict.status === 'detected' ? (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() => handleCreateTaskForConflict(conflict.id)}
                                                                disabled={creatingTask === conflict.id}
                                                                className="text-xs border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
                                                                data-testid={`create-task-${conflict.id}`}
                                                            >
                                                                {creatingTask === conflict.id ? (
                                                                    <Loader2 className="h-3 w-3 animate-spin" />
                                                                ) : (
                                                                    <>
                                                                        <Plus className="h-3 w-3 mr-1" />
                                                                        Create Task
                                                                    </>
                                                                )}
                                                            </Button>
                                                        ) : (
                                                            <span className="text-xs text-zinc-500">-</span>
                                                        )}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                                {filteredStoredConflicts.length === 0 && (
                                    <div className="text-center py-8 text-zinc-500">
                                        <p>No conflicts in this category</p>
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Active Conflicts List - Dynamic */}
                <Card className="bg-card border-border" data-testid="active-conflicts-section">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <AlertTriangle className="h-4 w-4 text-amber-500" />
                            Active Conflicts
                            <Badge variant="outline" className="ml-2">{enhancedConflicts.length}</Badge>
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {enhancedConflicts.length === 0 ? (
                            <div className="py-8 text-center">
                                <CheckCircle className="h-12 w-12 text-emerald-500 mx-auto mb-3" />
                                <p className="text-lg font-medium text-white">No Conflicts Detected</p>
                                <p className="text-sm text-zinc-500 mt-1">
                                    Your SEO networks are configured correctly
                                </p>
                            </div>
                        ) : viewMode === 'table' ? (
                            /* Table View */
                            <div className="overflow-x-auto">
                                <table className="w-full" data-testid="active-conflicts-table">
                                    <thead>
                                        <tr className="border-b border-zinc-800">
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Severity</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Type</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Description</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Network</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Linked Task</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {enhancedConflicts.map((conflict, idx) => {
                                            const severityClass = CONFLICT_SEVERITY_CLASSES[conflict.severity] || CONFLICT_SEVERITY_CLASSES.medium;
                                            const typeLabel = CONFLICT_TYPE_LABELS[conflict.conflict_type] || conflict.conflict_type;
                                            const hasLinkedOpt = conflict.linked_optimization;
                                            
                                            return (
                                                <tr key={idx} className="border-b border-zinc-800/50 hover:bg-zinc-800/30" data-testid={`conflict-row-${idx}`}>
                                                    <td className="py-3 px-4">
                                                        <Badge className={severityClass}>
                                                            {(conflict.severity || 'medium').toUpperCase()}
                                                        </Badge>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        <span className="text-sm text-white">{typeLabel}</span>
                                                    </td>
                                                    <td className="py-3 px-4 max-w-xs">
                                                        <p className="text-sm text-zinc-300 truncate">
                                                            {conflict.description || conflict.message || 'SEO structure conflict detected'}
                                                        </p>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        {conflict.network_id ? (
                                                            <Button
                                                                variant="link"
                                                                size="sm"
                                                                onClick={() => window.location.href = `/groups/${conflict.network_id}`}
                                                                className="text-xs text-zinc-400 hover:text-blue-400 p-0 h-auto"
                                                            >
                                                                {conflict.network_name || 'View'}
                                                                <ExternalLink className="h-3 w-3 ml-1" />
                                                            </Button>
                                                        ) : (
                                                            <span className="text-sm text-zinc-500">-</span>
                                                        )}
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        {hasLinkedOpt ? (
                                                            <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
                                                                <Link2 className="h-3 w-3 mr-1" />
                                                                {conflict.linked_optimization.status?.toUpperCase()}
                                                            </Badge>
                                                        ) : (
                                                            <span className="text-xs text-zinc-500">Not linked</span>
                                                        )}
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        <div className="flex gap-2">
                                                            {conflict.network_id && (
                                                                <Button
                                                                    variant="outline"
                                                                    size="sm"
                                                                    onClick={() => window.location.href = `/groups/${conflict.network_id}`}
                                                                    className="text-xs"
                                                                >
                                                                    <ExternalLink className="h-3 w-3" />
                                                                </Button>
                                                            )}
                                                            {hasLinkedOpt && (
                                                                <Button
                                                                    variant="outline"
                                                                    size="sm"
                                                                    onClick={() => window.location.href = `/optimizations/${conflict.linked_optimization.id}`}
                                                                    className="text-xs border-blue-500/30 text-blue-400 hover:bg-blue-500/10"
                                                                >
                                                                    <ClipboardList className="h-3 w-3" />
                                                                </Button>
                                                            )}
                                                        </div>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            /* Cards View */
                            <div className="space-y-4" data-testid="conflicts-list">
                                {enhancedConflicts.map((conflict, idx) => {
                                    const severityClass = CONFLICT_SEVERITY_CLASSES[conflict.severity] || CONFLICT_SEVERITY_CLASSES.medium;
                                    const typeLabel = CONFLICT_TYPE_LABELS[conflict.conflict_type] || conflict.conflict_type;
                                    const hasLinkedOpt = conflict.linked_optimization;
                                    
                                    return (
                                        <Card 
                                            key={idx} 
                                            className={`bg-zinc-900/50 border-border ${conflict.severity === 'critical' ? 'border-red-500/30' : conflict.severity === 'high' ? 'border-amber-500/30' : ''}`}
                                            data-testid={`conflict-${idx}`}
                                        >
                                            <CardContent className="pt-4">
                                                <div className="flex items-start justify-between">
                                                    <div className="flex items-start gap-3">
                                                        <AlertTriangle className={`h-5 w-5 flex-shrink-0 ${
                                                            conflict.severity === 'critical' ? 'text-red-400' :
                                                            conflict.severity === 'high' ? 'text-amber-400' : 'text-yellow-400'
                                                        }`} />
                                                        <div>
                                                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                                                                <Badge className={severityClass}>
                                                                    {(conflict.severity || 'medium').toUpperCase()}
                                                                </Badge>
                                                                <Badge variant="outline" className="text-xs">
                                                                    {typeLabel}
                                                                </Badge>
                                                                {hasLinkedOpt && (
                                                                    <Badge 
                                                                        className="bg-blue-500/20 text-blue-400 border-blue-500/30 cursor-pointer"
                                                                        onClick={() => window.location.href = `/optimizations/${conflict.linked_optimization.id}`}
                                                                        data-testid={`linked-opt-badge-${idx}`}
                                                                    >
                                                                        <Link2 className="h-3 w-3 mr-1" />
                                                                        Linked Optimization
                                                                    </Badge>
                                                                )}
                                                            </div>
                                                            <p className="text-sm text-white font-medium">
                                                                {conflict.description || conflict.message || 'SEO structure conflict detected'}
                                                            </p>
                                                            {conflict.network_name && (
                                                                <p className="text-xs text-zinc-500 mt-1">
                                                                    Network: {conflict.network_name}
                                                                </p>
                                                            )}
                                                            {hasLinkedOpt && (
                                                                <div className="mt-2 p-2 bg-blue-500/10 rounded border border-blue-500/20">
                                                                    <div className="flex items-center gap-2">
                                                                        <ClipboardList className="h-4 w-4 text-blue-400" />
                                                                        <div>
                                                                            <p className="text-xs text-blue-400 font-medium">
                                                                                {conflict.linked_optimization.title}
                                                                            </p>
                                                                            <p className="text-xs text-zinc-500">
                                                                                Status: {conflict.linked_optimization.status?.toUpperCase()}
                                                                            </p>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            )}
                                                            {conflict.affected_nodes && conflict.affected_nodes.length > 0 && (
                                                                <div className="mt-2 space-y-1">
                                                                    <p className="text-xs text-zinc-500">Affected Nodes:</p>
                                                                    {conflict.affected_nodes.slice(0, 3).map((node, nIdx) => (
                                                                        <div key={nIdx} className="flex items-center gap-2">
                                                                            <Network className="h-3 w-3 text-zinc-600" />
                                                                            <code className="text-xs text-zinc-400 bg-zinc-900 px-1 rounded">
                                                                                {node.domain}{node.path || ''}
                                                                            </code>
                                                                        </div>
                                                                    ))}
                                                                    {conflict.affected_nodes.length > 3 && (
                                                                        <p className="text-xs text-zinc-600">
                                                                            +{conflict.affected_nodes.length - 3} more nodes
                                                                        </p>
                                                                    )}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <div className="flex flex-col gap-2">
                                                        {conflict.network_id && (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() => window.location.href = `/groups/${conflict.network_id}`}
                                                                className="text-xs"
                                                            >
                                                                <ExternalLink className="h-3 w-3 mr-1" />
                                                                View Network
                                                            </Button>
                                                        )}
                                                        {hasLinkedOpt && (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() => window.location.href = `/optimizations/${conflict.linked_optimization.id}`}
                                                                className="text-xs border-blue-500/30 text-blue-400 hover:bg-blue-500/10"
                                                                data-testid={`view-optimization-${idx}`}
                                                            >
                                                                <ClipboardList className="h-3 w-3 mr-1" />
                                                                View Task
                                                            </Button>
                                                        )}
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    );
                                })}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </Layout>
    );
}
