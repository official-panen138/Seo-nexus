import { useState, useEffect } from 'react';
import { Layout } from '../components/Layout';
import { conflictsAPI } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import {
    AlertTriangle,
    Clock,
    CheckCircle,
    TrendingUp,
    Users,
    RefreshCw,
    BarChart3,
    Target,
    Repeat,
    ArrowRight,
    ExternalLink
} from 'lucide-react';

// Status colors and flow
const STATUS_FLOW = {
    detected: { 
        label: 'Detected', 
        color: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
        description: 'Conflict detected, optimization task created'
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

// Conflict type labels
const CONFLICT_TYPE_LABELS = {
    keyword_cannibalization: "Keyword Cannibalization",
    competing_targets: "Competing Targets",
    canonical_mismatch: "Canonical Mismatch",
    tier_inversion: "Tier Inversion",
    redirect_loop: "Redirect Loop",
    multiple_parents_to_main: "Multiple Parents to Main",
    canonical_redirect_conflict: "Canonical-Redirect Conflict",
    index_noindex_mismatch: "Index/Noindex Mismatch",
    orphan: "Orphan Node",
    noindex_high_tier: "Noindex High Tier",
};

// Severity colors
const SEVERITY_COLORS = {
    critical: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' },
    high: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30' },
    medium: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30' },
    low: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30' },
};

export default function ConflictDashboardPage() {
    const [metrics, setMetrics] = useState(null);
    const [storedConflicts, setStoredConflicts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [creatingTask, setCreatingTask] = useState(null);
    const [periodDays, setPeriodDays] = useState('30');

    useEffect(() => {
        loadData();
    }, [periodDays]);

    const loadData = async () => {
        setLoading(true);
        try {
            const [metricsRes, conflictsRes] = await Promise.all([
                conflictsAPI.getMetrics({ days: parseInt(periodDays) }),
                conflictsAPI.getStored({ limit: 50 })
            ]);
            
            setMetrics(metricsRes.data);
            setStoredConflicts(conflictsRes.data?.conflicts || []);
        } catch (err) {
            console.error('Failed to load conflict data:', err);
            toast.error('Failed to load conflict metrics');
        } finally {
            setLoading(false);
        }
    };

    const handleCreateTaskForConflict = async (conflictId) => {
        setCreatingTask(conflictId);
        try {
            const res = await conflictsAPI.createOptimization(conflictId);
            if (res.data?.optimization_id) {
                toast.success('Optimization task created successfully');
                loadData(); // Refresh data
            }
        } catch (err) {
            console.error('Failed to create task for conflict:', err);
            toast.error('Failed to create optimization task');
        } finally {
            setCreatingTask(null);
        }
    };

    const formatHours = (hours) => {
        if (!hours || hours === 0) return 'N/A';
        if (hours < 1) return `${Math.round(hours * 60)} min`;
        if (hours < 24) return `${hours.toFixed(1)} hrs`;
        return `${(hours / 24).toFixed(1)} days`;
    };

    const getResolutionRate = () => {
        if (!metrics || metrics.total_conflicts === 0) return 0;
        return ((metrics.resolved_count / metrics.total_conflicts) * 100).toFixed(1);
    };

    // Get recurring conflicts
    const recurringConflicts = storedConflicts.filter(c => c.recurrence_count > 0);

    // Get top resolvers from metrics
    const topResolvers = metrics?.by_resolver 
        ? Object.entries(metrics.by_resolver)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
        : [];

    if (loading) {
        return (
            <Layout>
                <div className="p-6 space-y-6">
                    <Skeleton className="h-8 w-64" />
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {[1, 2, 3, 4].map(i => (
                            <Skeleton key={i} className="h-32" />
                        ))}
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <Skeleton className="h-64" />
                        <Skeleton className="h-64" />
                    </div>
                </div>
            </Layout>
        );
    }

    return (
        <Layout>
            <div className="p-6 space-y-6" data-testid="conflict-dashboard">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                            <BarChart3 className="h-7 w-7 text-amber-400" />
                            Conflict Resolution Dashboard
                        </h1>
                        <p className="text-zinc-400 mt-1">
                            Track and analyze SEO conflict resolution performance
                        </p>
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
                            onClick={loadData}
                            data-testid="refresh-metrics-btn"
                        >
                            <RefreshCw className="h-4 w-4 mr-2" />
                            Refresh
                        </Button>
                    </div>
                </div>

                {/* Key Metrics Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {/* Total Conflicts */}
                    <Card className="bg-card border-border" data-testid="total-conflicts-card">
                        <CardContent className="pt-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">Total Conflicts</p>
                                    <p className="text-3xl font-bold text-white mt-1">
                                        {metrics?.total_conflicts || 0}
                                    </p>
                                    <div className="flex items-center gap-2 mt-2">
                                        <Badge variant="outline" className="text-emerald-400 border-emerald-500/30">
                                            {metrics?.resolved_count || 0} resolved
                                        </Badge>
                                        <Badge variant="outline" className="text-amber-400 border-amber-500/30">
                                            {metrics?.open_count || 0} open
                                        </Badge>
                                    </div>
                                </div>
                                <div className="h-12 w-12 rounded-full bg-amber-500/20 flex items-center justify-center">
                                    <AlertTriangle className="h-6 w-6 text-amber-400" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Resolution Rate */}
                    <Card className="bg-card border-border" data-testid="resolution-rate-card">
                        <CardContent className="pt-6">
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
                                <div className="h-12 w-12 rounded-full bg-emerald-500/20 flex items-center justify-center">
                                    <CheckCircle className="h-6 w-6 text-emerald-400" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Avg Resolution Time */}
                    <Card className="bg-card border-border" data-testid="avg-resolution-card">
                        <CardContent className="pt-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">Avg Resolution Time</p>
                                    <p className="text-3xl font-bold text-white mt-1">
                                        {formatHours(metrics?.avg_resolution_time_hours)}
                                    </p>
                                    <p className="text-xs text-zinc-500 mt-2">
                                        Time from detection to resolved
                                    </p>
                                </div>
                                <div className="h-12 w-12 rounded-full bg-blue-500/20 flex items-center justify-center">
                                    <Clock className="h-6 w-6 text-blue-400" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Recurring Conflicts */}
                    <Card className="bg-card border-border" data-testid="recurring-conflicts-card">
                        <CardContent className="pt-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">Recurring Conflicts</p>
                                    <p className="text-3xl font-bold text-white mt-1">
                                        {metrics?.recurring_conflicts || 0}
                                    </p>
                                    <p className="text-xs text-zinc-500 mt-2">
                                        Conflicts that reappeared after resolution
                                    </p>
                                </div>
                                <div className="h-12 w-12 rounded-full bg-red-500/20 flex items-center justify-center">
                                    <Repeat className="h-6 w-6 text-red-400" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Charts Section */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Conflicts by Severity */}
                    <Card className="bg-card border-border" data-testid="severity-breakdown-card">
                        <CardHeader>
                            <CardTitle className="text-white flex items-center gap-2">
                                <Target className="h-5 w-5 text-amber-400" />
                                Conflicts by Severity
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {metrics?.by_severity && Object.keys(metrics.by_severity).length > 0 ? (
                                <div className="space-y-4">
                                    {Object.entries(metrics.by_severity).map(([severity, data]) => {
                                        const colors = SEVERITY_COLORS[severity] || SEVERITY_COLORS.medium;
                                        const percentage = metrics.total_conflicts > 0 
                                            ? (data.total / metrics.total_conflicts) * 100 
                                            : 0;
                                        
                                        return (
                                            <div key={severity} className="space-y-2">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <Badge className={`${colors.bg} ${colors.text} ${colors.border}`}>
                                                            {severity.toUpperCase()}
                                                        </Badge>
                                                        <span className="text-sm text-zinc-400">
                                                            {data.total} total
                                                        </span>
                                                    </div>
                                                    <span className="text-sm text-zinc-400">
                                                        {data.resolved} resolved
                                                    </span>
                                                </div>
                                                <div className="h-3 bg-zinc-800 rounded-full overflow-hidden">
                                                    <div 
                                                        className={`h-full ${colors.bg.replace('/20', '')} transition-all duration-500`}
                                                        style={{ width: `${percentage}%` }}
                                                    />
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            ) : (
                                <div className="text-center py-8 text-zinc-500">
                                    <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                    <p>No severity data available</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Conflicts by Type */}
                    <Card className="bg-card border-border" data-testid="type-breakdown-card">
                        <CardHeader>
                            <CardTitle className="text-white flex items-center gap-2">
                                <BarChart3 className="h-5 w-5 text-blue-400" />
                                Conflicts by Type
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {metrics?.by_type && Object.keys(metrics.by_type).length > 0 ? (
                                <div className="space-y-3">
                                    {Object.entries(metrics.by_type)
                                        .sort((a, b) => b[1].total - a[1].total)
                                        .map(([type, data]) => {
                                            const label = CONFLICT_TYPE_LABELS[type] || type.replace(/_/g, ' ');
                                            const percentage = metrics.total_conflicts > 0 
                                                ? (data.total / metrics.total_conflicts) * 100 
                                                : 0;
                                            
                                            return (
                                                <div key={type} className="flex items-center gap-3">
                                                    <div className="flex-1">
                                                        <div className="flex items-center justify-between mb-1">
                                                            <span className="text-sm text-white truncate">
                                                                {label}
                                                            </span>
                                                            <span className="text-xs text-zinc-500">
                                                                {data.total} ({percentage.toFixed(0)}%)
                                                            </span>
                                                        </div>
                                                        <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                                                            <div 
                                                                className="h-full bg-blue-500 transition-all duration-500"
                                                                style={{ width: `${percentage}%` }}
                                                            />
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                </div>
                            ) : (
                                <div className="text-center py-8 text-zinc-500">
                                    <BarChart3 className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                    <p>No type data available</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Bottom Section */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Top Resolvers */}
                    <Card className="bg-card border-border" data-testid="top-resolvers-card">
                        <CardHeader>
                            <CardTitle className="text-white flex items-center gap-2">
                                <Users className="h-5 w-5 text-emerald-400" />
                                Top Resolvers
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {topResolvers.length > 0 ? (
                                <div className="space-y-3">
                                    {topResolvers.map(([userId, count], index) => (
                                        <div 
                                            key={userId} 
                                            className="flex items-center gap-3 p-2 rounded-lg bg-zinc-800/50"
                                        >
                                            <div className={`
                                                w-8 h-8 rounded-full flex items-center justify-center text-white font-bold
                                                ${index === 0 ? 'bg-amber-500' : index === 1 ? 'bg-zinc-400' : index === 2 ? 'bg-amber-700' : 'bg-zinc-600'}
                                            `}>
                                                {index + 1}
                                            </div>
                                            <div className="flex-1">
                                                <p className="text-sm text-white truncate">
                                                    {userId === 'system' ? 'System (Auto)' : userId}
                                                </p>
                                            </div>
                                            <Badge variant="outline" className="text-emerald-400 border-emerald-500/30">
                                                {count} resolved
                                            </Badge>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center py-8 text-zinc-500">
                                    <Users className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                    <p>No resolvers yet</p>
                                    <p className="text-xs mt-1">Resolve conflicts to see rankings</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Recurring Conflicts List */}
                    <Card className="bg-card border-border" data-testid="recurring-list-card">
                        <CardHeader>
                            <CardTitle className="text-white flex items-center gap-2">
                                <Repeat className="h-5 w-5 text-red-400" />
                                Recurring Conflicts
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {recurringConflicts.length > 0 ? (
                                <div className="space-y-3 max-h-[250px] overflow-y-auto">
                                    {recurringConflicts.map((conflict) => (
                                        <div 
                                            key={conflict.id}
                                            className="p-3 rounded-lg bg-zinc-800/50 border border-red-500/20"
                                        >
                                            <div className="flex items-start justify-between">
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 mb-1">
                                                        <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
                                                            {conflict.recurrence_count}x recurred
                                                        </Badge>
                                                        <Badge variant="outline" className="text-xs">
                                                            {CONFLICT_TYPE_LABELS[conflict.conflict_type] || conflict.conflict_type}
                                                        </Badge>
                                                    </div>
                                                    <p className="text-sm text-white truncate">
                                                        {conflict.node_a_label}
                                                    </p>
                                                    <p className="text-xs text-zinc-500 mt-1">
                                                        Network: {conflict.network_name || 'Unknown'}
                                                    </p>
                                                </div>
                                                {conflict.linked_optimization && (
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => window.location.href = `/optimizations/${conflict.linked_optimization.id}`}
                                                    >
                                                        <ExternalLink className="h-4 w-4" />
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center py-8 text-zinc-500">
                                    <CheckCircle className="h-8 w-8 mx-auto mb-2 opacity-50 text-emerald-500" />
                                    <p>No recurring conflicts</p>
                                    <p className="text-xs mt-1">Great! Resolved conflicts haven't reappeared</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Recent Conflicts Table */}
                <Card className="bg-card border-border" data-testid="recent-conflicts-card">
                    <CardHeader className="flex flex-row items-center justify-between">
                        <CardTitle className="text-white flex items-center gap-2">
                            <TrendingUp className="h-5 w-5 text-purple-400" />
                            Recent Conflicts
                        </CardTitle>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => window.location.href = '/alerts'}
                        >
                            View All
                            <ArrowRight className="h-4 w-4 ml-2" />
                        </Button>
                    </CardHeader>
                    <CardContent>
                        {storedConflicts.length > 0 ? (
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead>
                                        <tr className="border-b border-zinc-800">
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Type</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Severity</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Status</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Node</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Network</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Detected</th>
                                            <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 uppercase">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {storedConflicts.slice(0, 10).map((conflict) => {
                                            const colors = SEVERITY_COLORS[conflict.severity] || SEVERITY_COLORS.medium;
                                            const statusInfo = STATUS_FLOW[conflict.status] || STATUS_FLOW.detected;
                                            
                                            return (
                                                <tr key={conflict.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
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
                                                            {conflict.node_a_label?.substring(0, 30)}
                                                            {conflict.node_a_label?.length > 30 ? '...' : ''}
                                                        </code>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        <span className="text-sm text-zinc-400">
                                                            {conflict.network_name || 'N/A'}
                                                        </span>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        <span className="text-xs text-zinc-500">
                                                            {new Date(conflict.detected_at).toLocaleDateString()}
                                                        </span>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        {conflict.linked_optimization ? (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() => window.location.href = `/optimizations/${conflict.linked_optimization.id}`}
                                                                className="text-xs"
                                                            >
                                                                View Task
                                                            </Button>
                                                        ) : conflict.status === 'detected' ? (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() => handleCreateTaskForConflict(conflict.id)}
                                                                className="text-xs border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
                                                                data-testid={`create-task-${conflict.id}`}
                                                            >
                                                                Create Task
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
                            </div>
                        ) : (
                            <div className="text-center py-8 text-zinc-500">
                                <CheckCircle className="h-8 w-8 mx-auto mb-2 opacity-50 text-emerald-500" />
                                <p>No conflicts tracked yet</p>
                                <p className="text-xs mt-1">Process conflicts from the Alert Center to see them here</p>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </Layout>
    );
}
