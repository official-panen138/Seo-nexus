import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { v3ReportsAPI, conflictsAPI, usersAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
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
    LayoutGrid,
    TrendingUp,
    Users,
    Target,
    Repeat,
    ArrowRight,
    XCircle,
    Timer,
    AlertOctagon,
    Info
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
    approved: { 
        label: 'Approved', 
        color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        description: 'Approved by Super Admin (auto-resolved)'
    },
    ignored: { 
        label: 'Ignored', 
        color: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
        description: 'Marked as acceptable'
    },
};

// Severity colors for dashboard
const SEVERITY_COLORS = {
    critical: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30', bar: 'bg-red-500' },
    high: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30', bar: 'bg-amber-500' },
    medium: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30', bar: 'bg-yellow-500' },
    low: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30', bar: 'bg-blue-500' },
};

export default function AlertsPage() {
    const { isSuperAdmin } = useAuth();
    
    // Conflicts data
    const [conflicts, setConflicts] = useState([]);
    const [storedConflicts, setStoredConflicts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [processing, setProcessing] = useState(false);
    const [viewMode, setViewMode] = useState('table');
    const [tabFilter, setTabFilter] = useState('all');
    
    // Dashboard metrics
    const [metrics, setMetrics] = useState(null);
    const [loadingMetrics, setLoadingMetrics] = useState(true);
    const [periodDays, setPeriodDays] = useState("30");
    const [topResolvers, setTopResolvers] = useState([]);
    const [recurringConflicts, setRecurringConflicts] = useState([]);

    // Compute conflict stats
    const conflictStats = {
        total: storedConflicts.length,
        critical: storedConflicts.filter(c => c.severity === 'critical').length,
        high: storedConflicts.filter(c => c.severity === 'high').length,
        detected: storedConflicts.filter(c => c.status === 'detected').length,
        inProgress: storedConflicts.filter(c => c.status === 'under_review').length,
        resolved: storedConflicts.filter(c => ['resolved', 'approved'].includes(c.status)).length
    };

    // Enhanced conflicts with network names
    const [enhancedConflicts, setEnhancedConflicts] = useState([]);

    useEffect(() => {
        loadAllData();
    }, []);

    useEffect(() => {
        loadMetrics();
    }, [periodDays]);

    const loadAllData = async () => {
        setLoading(true);
        await Promise.all([
            loadConflicts(),
            loadMetrics()
        ]);
        setLoading(false);
    };

    const loadConflicts = async () => {
        try {
            // Load stored conflicts - use getStored endpoint
            const storedRes = await conflictsAPI.getStored();
            const stored = storedRes.data?.conflicts || storedRes.data || [];
            setStoredConflicts(stored);
            setEnhancedConflicts(stored);
        } catch (err) {
            console.error('Failed to load conflicts:', err);
            toast.error('Failed to load conflicts');
        }
    };

    const loadMetrics = async () => {
        setLoadingMetrics(true);
        try {
            const metricsRes = await conflictsAPI.getMetrics({ days: parseInt(periodDays) });
            const metricsData = metricsRes.data;
            setMetrics(metricsData);
            
            // Top resolvers come from the metrics endpoint
            setTopResolvers(metricsData?.top_resolvers || []);
            
            // Recurring conflicts are tracked via recurring_conflicts count
            // No separate endpoint needed - data is in metrics
            setRecurringConflicts([]);
        } catch (err) {
            console.error('Failed to load metrics:', err);
        } finally {
            setLoadingMetrics(false);
        }
    };

    // Process conflicts to create tasks
    const handleProcessConflicts = async () => {
        const newConflicts = enhancedConflicts.filter(c => !c.status || c.status === 'detected');
        if (newConflicts.length === 0) {
            toast.info('No new conflicts to process');
            return;
        }
        
        setProcessing(true);
        try {
            // Use the process endpoint which detects and creates optimizations
            const result = await conflictsAPI.process();
            toast.success(`Processed ${result.data?.conflicts_processed || 0} conflicts, created ${result.data?.optimizations_created || 0} optimizations`);
            loadConflicts();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to create tasks');
        } finally {
            setProcessing(false);
        }
    };

    // Filter conflicts by tab
    const getFilteredConflicts = () => {
        if (tabFilter === 'all') return enhancedConflicts;
        if (tabFilter === 'detected') return enhancedConflicts.filter(c => c.status === 'detected');
        if (tabFilter === 'in_progress') return enhancedConflicts.filter(c => c.status === 'under_review');
        if (tabFilter === 'resolved') return enhancedConflicts.filter(c => ['resolved', 'approved'].includes(c.status));
        return enhancedConflicts;
    };

    // Format hours to readable string
    const formatHours = (hours) => {
        if (!hours && hours !== 0) return 'N/A';
        if (hours < 1) return `${Math.round(hours * 60)}m`;
        if (hours < 24) return `${hours.toFixed(1)}hrs`;
        return `${(hours / 24).toFixed(1)}d`;
    };

    // Get resolution rate
    const getResolutionRate = () => {
        if (!metrics?.total_conflicts) return 0;
        return Math.round((metrics.resolved_count / metrics.total_conflicts) * 100);
    };

    // Get severity distribution
    const getSeverityDistribution = () => {
        if (!metrics?.severity_breakdown) return [];
        return Object.entries(metrics.severity_breakdown)
            .map(([severity, data]) => ({
                severity,
                total: data.total || 0,
                resolved: data.resolved || 0,
                percentage: metrics.total_conflicts > 0 
                    ? Math.round((data.total / metrics.total_conflicts) * 100) 
                    : 0
            }))
            .sort((a, b) => {
                const order = { critical: 0, high: 1, medium: 2, low: 3 };
                return order[a.severity] - order[b.severity];
            });
    };

    // Get type distribution
    const getTypeDistribution = () => {
        if (!metrics?.type_breakdown) return [];
        return Object.entries(metrics.type_breakdown)
            .map(([type, data]) => ({
                type,
                label: CONFLICT_TYPE_LABELS[type] || type,
                count: data.total || 0,
                percentage: metrics.total_conflicts > 0 
                    ? Math.round((data.total / metrics.total_conflicts) * 100) 
                    : 0
            }))
            .sort((a, b) => b.count - a.count);
    };

    if (loading && storedConflicts.length === 0) {
        return (
            <Layout>
                <div className="space-y-6">
                    <Skeleton className="h-10 w-64" />
                    <div className="grid grid-cols-4 gap-4">
                        {[1,2,3,4].map(i => <Skeleton key={i} className="h-32" />)}
                    </div>
                    <Skeleton className="h-96" />
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
                        <div className="flex items-center gap-3">
                            <Select value={periodDays} onValueChange={setPeriodDays}>
                                <SelectTrigger className="w-32 bg-zinc-900 border-zinc-700">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="7">Last 7 days</SelectItem>
                                    <SelectItem value="14">Last 14 days</SelectItem>
                                    <SelectItem value="30">Last 30 days</SelectItem>
                                    <SelectItem value="90">Last 90 days</SelectItem>
                                </SelectContent>
                            </Select>
                            <Button 
                                variant="outline" 
                                onClick={loadAllData}
                                disabled={loading}
                                data-testid="refresh-conflicts-btn"
                            >
                                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            </Button>
                        </div>
                    </div>
                </div>

                {/* Key Metrics Row 1 */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    {/* Total Conflicts */}
                    <Card className="bg-card border-border" data-testid="total-conflicts-card">
                        <CardContent className="pt-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">Total Conflicts</p>
                                    <p className="text-3xl font-bold text-white mt-1">
                                        {metrics?.total_conflicts || conflictStats.total}
                                    </p>
                                    <div className="flex items-center gap-2 mt-2">
                                        <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 text-xs">
                                            {metrics?.resolved_count || conflictStats.resolved} resolved
                                        </Badge>
                                        <Badge variant="outline" className="text-amber-400 border-amber-500/30 text-xs">
                                            {metrics?.open_count || (conflictStats.detected + conflictStats.inProgress)} open
                                        </Badge>
                                    </div>
                                </div>
                                <div className="h-10 w-10 rounded-full bg-amber-500/20 flex items-center justify-center">
                                    <AlertTriangle className="h-5 w-5 text-amber-400" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Resolution Rate */}
                    <Card className="bg-card border-border" data-testid="resolution-rate-card">
                        <CardContent className="pt-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">Resolution Rate</p>
                                    <p className="text-3xl font-bold text-white mt-1">
                                        {getResolutionRate()}%
                                    </p>
                                    <p className="text-xs text-zinc-500 mt-2">
                                        {metrics?.resolved_count || 0} of {metrics?.total_conflicts || 0} resolved
                                    </p>
                                </div>
                                <div className="h-10 w-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                                    <CheckCircle className="h-5 w-5 text-emerald-400" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Avg Resolution Time */}
                    <Card className="bg-card border-border" data-testid="avg-resolution-card">
                        <CardContent className="pt-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">Avg Resolution Time</p>
                                    <p className="text-3xl font-bold text-white mt-1">
                                        {formatHours(metrics?.avg_resolution_time_hours)}
                                    </p>
                                    <p className="text-xs text-zinc-500 mt-2">
                                        From detection to completion
                                    </p>
                                </div>
                                <div className="h-10 w-10 rounded-full bg-blue-500/20 flex items-center justify-center">
                                    <Clock className="h-5 w-5 text-blue-400" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Recurring Conflicts */}
                    <Card className="bg-card border-border" data-testid="recurring-conflicts-card">
                        <CardContent className="pt-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">Recurring Conflicts</p>
                                    <p className="text-3xl font-bold text-white mt-1">
                                        {metrics?.recurring_conflicts || 0}
                                    </p>
                                    <p className="text-xs text-zinc-500 mt-2">
                                        Reappeared after resolution
                                    </p>
                                </div>
                                <div className="h-10 w-10 rounded-full bg-red-500/20 flex items-center justify-center">
                                    <Repeat className="h-5 w-5 text-red-400" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Extended Metrics Row 2 */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                    {/* False Resolution Rate */}
                    <Card className="bg-card border-border">
                        <CardContent className="pt-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">False Resolution Rate</p>
                                    <p className="text-2xl font-bold text-white mt-1">
                                        {metrics?.false_resolution_rate?.toFixed(1) || 0}%
                                    </p>
                                    <p className="text-xs text-zinc-500 mt-1">
                                        Reappeared within 7 days of resolution
                                    </p>
                                </div>
                                <div className="h-10 w-10 rounded-full bg-orange-500/20 flex items-center justify-center">
                                    <XCircle className="h-5 w-5 text-orange-400" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Avg Recurrence Interval */}
                    <Card className="bg-card border-border">
                        <CardContent className="pt-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">Avg Recurrence Interval</p>
                                    <p className="text-2xl font-bold text-white mt-1">
                                        {metrics?.avg_recurrence_interval_hours 
                                            ? formatHours(metrics.avg_recurrence_interval_hours)
                                            : 'N/A'}
                                    </p>
                                    <p className="text-xs text-zinc-500 mt-1">
                                        Time between resolution and reappearance
                                    </p>
                                </div>
                                <div className="h-10 w-10 rounded-full bg-purple-500/20 flex items-center justify-center">
                                    <Timer className="h-5 w-5 text-purple-400" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Resolution Time Breakdown */}
                    <Card className="bg-card border-border">
                        <CardContent className="pt-4">
                            <p className="text-sm text-zinc-400 mb-2">Resolution Time Breakdown</p>
                            <div className="grid grid-cols-2 gap-2">
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-emerald-500" />
                                    <span className="text-xs text-zinc-400">&lt;1 hr:</span>
                                    <span className="text-xs text-white font-medium">
                                        {metrics?.resolution_time_buckets?.under_1h || 0}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-blue-500" />
                                    <span className="text-xs text-zinc-400">1-24 hrs:</span>
                                    <span className="text-xs text-white font-medium">
                                        {metrics?.resolution_time_buckets?.['1h_24h'] || 0}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-amber-500" />
                                    <span className="text-xs text-zinc-400">1-7 days:</span>
                                    <span className="text-xs text-white font-medium">
                                        {metrics?.resolution_time_buckets?.['1d_7d'] || 0}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-red-500" />
                                    <span className="text-xs text-zinc-400">&gt;7 days:</span>
                                    <span className="text-xs text-white font-medium">
                                        {metrics?.resolution_time_buckets?.over_7d || 0}
                                    </span>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Conflicts by Severity & Type + Top Resolvers */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                    {/* Conflicts by Severity */}
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm flex items-center gap-2">
                                <Target className="h-4 w-4 text-amber-400" />
                                Conflicts by Severity
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-3">
                                {getSeverityDistribution().map(item => (
                                    <div key={item.severity}>
                                        <div className="flex items-center justify-between mb-1">
                                            <div className="flex items-center gap-2">
                                                <Badge 
                                                    className={`${SEVERITY_COLORS[item.severity]?.bg} ${SEVERITY_COLORS[item.severity]?.text} ${SEVERITY_COLORS[item.severity]?.border} uppercase text-xs`}
                                                >
                                                    {item.severity}
                                                </Badge>
                                                <span className="text-xs text-zinc-400">{item.total} total</span>
                                            </div>
                                            <span className="text-xs text-zinc-400">{item.resolved} resolved</span>
                                        </div>
                                        <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                                            <div 
                                                className={`h-full ${SEVERITY_COLORS[item.severity]?.bar}`}
                                                style={{ 
                                                    width: `${item.total > 0 ? Math.max((item.resolved / item.total) * 100, 5) : 0}%` 
                                                }}
                                            />
                                        </div>
                                    </div>
                                ))}
                                {getSeverityDistribution().length === 0 && (
                                    <p className="text-sm text-zinc-500 text-center py-4">No data available</p>
                                )}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Conflicts by Type */}
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm flex items-center gap-2">
                                <BarChart3 className="h-4 w-4 text-blue-400" />
                                Conflicts by Type
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-2">
                                {getTypeDistribution().slice(0, 5).map(item => (
                                    <div key={item.type}>
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="text-xs text-zinc-400 truncate max-w-[150px]">{item.label}</span>
                                            <span className="text-xs text-white">{item.count} ({item.percentage}%)</span>
                                        </div>
                                        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                                            <div 
                                                className="h-full bg-blue-500"
                                                style={{ width: `${item.percentage}%` }}
                                            />
                                        </div>
                                    </div>
                                ))}
                                {getTypeDistribution().length === 0 && (
                                    <p className="text-sm text-zinc-500 text-center py-4">No data available</p>
                                )}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Top Resolvers */}
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm flex items-center gap-2">
                                <Users className="h-4 w-4 text-emerald-400" />
                                Top Resolvers
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-2">
                                {topResolvers.slice(0, 5).map((resolver, index) => (
                                    <div key={resolver.user_id} className="flex items-center justify-between py-1">
                                        <div className="flex items-center gap-2">
                                            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                                                index === 0 ? 'bg-amber-500/20 text-amber-400' :
                                                index === 1 ? 'bg-zinc-400/20 text-zinc-400' :
                                                index === 2 ? 'bg-amber-700/20 text-amber-700' :
                                                'bg-zinc-800 text-zinc-500'
                                            }`}>
                                                {index + 1}
                                            </div>
                                            <div>
                                                <p className="text-sm text-white">{resolver.name || 'Unknown'}</p>
                                                <p className="text-xs text-zinc-500 truncate max-w-[120px]">{resolver.email}</p>
                                            </div>
                                        </div>
                                        <Badge variant="outline" className="text-emerald-400 border-emerald-500/30">
                                            {resolver.resolved_count} resolved
                                        </Badge>
                                    </div>
                                ))}
                                {topResolvers.length === 0 && (
                                    <p className="text-sm text-zinc-500 text-center py-4">No resolvers yet</p>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Tracked Conflicts Section */}
                <Card className="bg-card border-border">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <CardTitle className="flex items-center gap-2">
                                    <Clock className="h-5 w-5 text-blue-400" />
                                    Tracked Conflicts
                                </CardTitle>
                                <Badge variant="secondary">{enhancedConflicts.length}</Badge>
                            </div>
                            {enhancedConflicts.filter(c => c.status === 'detected').length > 0 && (
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
                            )}
                        </div>
                    </CardHeader>
                    <CardContent>
                        {/* Tabs */}
                        <Tabs value={tabFilter} onValueChange={setTabFilter} className="w-full">
                            <TabsList className="mb-4">
                                <TabsTrigger value="all" data-testid="tab-all">
                                    All ({enhancedConflicts.length})
                                </TabsTrigger>
                                <TabsTrigger value="detected" data-testid="tab-detected">
                                    Detected ({conflictStats.detected})
                                </TabsTrigger>
                                <TabsTrigger value="in_progress" data-testid="tab-in-progress">
                                    In Progress ({conflictStats.inProgress})
                                </TabsTrigger>
                                <TabsTrigger value="resolved" data-testid="tab-resolved">
                                    Resolved ({conflictStats.resolved})
                                </TabsTrigger>
                            </TabsList>

                            <TabsContent value={tabFilter} className="mt-0">
                                {/* Conflicts Table */}
                                <div className="overflow-x-auto">
                                    <table className="w-full">
                                        <thead>
                                            <tr className="text-left border-b border-border">
                                                <th className="pb-3 text-xs font-medium text-zinc-500 uppercase">Type</th>
                                                <th className="pb-3 text-xs font-medium text-zinc-500 uppercase">Severity</th>
                                                <th className="pb-3 text-xs font-medium text-zinc-500 uppercase">Status</th>
                                                <th className="pb-3 text-xs font-medium text-zinc-500 uppercase">Node</th>
                                                <th className="pb-3 text-xs font-medium text-zinc-500 uppercase">Network</th>
                                                <th className="pb-3 text-xs font-medium text-zinc-500 uppercase">Detected</th>
                                                <th className="pb-3 text-xs font-medium text-zinc-500 uppercase">Resolved</th>
                                                <th className="pb-3 text-xs font-medium text-zinc-500 uppercase">Action</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {getFilteredConflicts().map((conflict) => (
                                                <tr 
                                                    key={conflict.id || conflict.conflict_id}
                                                    className="border-b border-border/50 hover:bg-zinc-900/30"
                                                >
                                                    <td className="py-3">
                                                        <span className="text-sm text-white">
                                                            {CONFLICT_TYPE_LABELS[conflict.conflict_type] || conflict.conflict_type || 'Unknown'}
                                                        </span>
                                                    </td>
                                                    <td className="py-3">
                                                        <Badge className={`${CONFLICT_SEVERITY_CLASSES[conflict.severity]} uppercase text-xs`}>
                                                            {conflict.severity || 'medium'}
                                                        </Badge>
                                                    </td>
                                                    <td className="py-3">
                                                        <Badge className={STATUS_FLOW[conflict.status]?.color || 'bg-zinc-500/20 text-zinc-400'}>
                                                            {STATUS_FLOW[conflict.status]?.label || conflict.status || 'New'}
                                                        </Badge>
                                                    </td>
                                                    <td className="py-3">
                                                        <span className="text-sm text-zinc-400 font-mono">
                                                            {conflict.node_path || conflict.affected_node || 'None'}
                                                        </span>
                                                    </td>
                                                    <td className="py-3">
                                                        {conflict.network_name || conflict.network_id ? (
                                                            <a 
                                                                href={`/groups/${conflict.network_id}`}
                                                                className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1"
                                                            >
                                                                {conflict.network_name || 'View Network'}
                                                                <ExternalLink className="h-3 w-3" />
                                                            </a>
                                                        ) : (
                                                            <span className="text-sm text-zinc-500">-</span>
                                                        )}
                                                    </td>
                                                    <td className="py-3">
                                                        <span className="text-sm text-zinc-400">
                                                            {conflict.detected_at 
                                                                ? new Date(conflict.detected_at).toLocaleDateString()
                                                                : '-'}
                                                        </span>
                                                    </td>
                                                    <td className="py-3">
                                                        <span className="text-sm text-zinc-400">
                                                            {conflict.resolved_at 
                                                                ? new Date(conflict.resolved_at).toLocaleDateString()
                                                                : '-'}
                                                        </span>
                                                    </td>
                                                    <td className="py-3">
                                                        {(conflict.optimization_id || conflict.linked_optimization?.id) ? (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() => window.location.href = `/optimizations/${conflict.optimization_id || conflict.linked_optimization?.id}`}
                                                                data-testid={`view-task-${conflict.id}`}
                                                            >
                                                                <ClipboardList className="h-3 w-3 mr-1" />
                                                                View Task
                                                            </Button>
                                                        ) : (
                                                            <span className="text-xs text-zinc-500">No task</span>
                                                        )}
                                                    </td>
                                                </tr>
                                            ))}
                                            {getFilteredConflicts().length === 0 && (
                                                <tr>
                                                    <td colSpan={8} className="py-12 text-center">
                                                        <CheckCircle className="h-12 w-12 text-emerald-500/50 mx-auto mb-3" />
                                                        <p className="text-zinc-400">No conflicts found</p>
                                                        <p className="text-xs text-zinc-500 mt-1">
                                                            {tabFilter === 'all' 
                                                                ? 'All SEO networks are healthy' 
                                                                : `No ${tabFilter.replace('_', ' ')} conflicts`}
                                                        </p>
                                                    </td>
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            </TabsContent>
                        </Tabs>
                    </CardContent>
                </Card>
            </div>
        </Layout>
    );
}
