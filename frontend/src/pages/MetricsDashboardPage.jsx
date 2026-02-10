import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { metricsAPI, auditAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { 
    Loader2, 
    TrendingUp, 
    Clock, 
    AlertTriangle, 
    CheckCircle2, 
    XCircle,
    BarChart3,
    Activity,
    Bell,
    RefreshCw,
    ChevronRight
} from 'lucide-react';

export default function MetricsDashboardPage() {
    const { isSuperAdmin, isManager } = useAuth();
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [dashboard, setDashboard] = useState(null);
    const [reminderMetrics, setReminderMetrics] = useState(null);
    const [conflictAging, setConflictAging] = useState(null);
    const [conflictResolution, setConflictResolution] = useState(null);
    const [auditStats, setAuditStats] = useState(null);
    const [reminderDays, setReminderDays] = useState('30');
    const [resolutionDays, setResolutionDays] = useState('30');

    useEffect(() => {
        loadAllMetrics();
    }, []);

    const loadAllMetrics = async () => {
        try {
            setLoading(true);
            const [dashRes, reminderRes, agingRes, resolutionRes, auditRes] = await Promise.all([
                metricsAPI.getDashboard().catch(() => ({ data: null })),
                metricsAPI.getReminderEffectiveness(parseInt(reminderDays)).catch(() => ({ data: null })),
                metricsAPI.getConflictAging().catch(() => ({ data: null })),
                metricsAPI.getConflictResolution(parseInt(resolutionDays)).catch(() => ({ data: null })),
                auditAPI.getStats(7).catch(() => ({ data: null })),
            ]);
            
            setDashboard(dashRes.data);
            setReminderMetrics(reminderRes.data);
            setConflictAging(agingRes.data);
            setConflictResolution(resolutionRes.data);
            setAuditStats(auditRes.data);
        } catch (err) {
            toast.error('Failed to load metrics');
        } finally {
            setLoading(false);
        }
    };

    const handleRefresh = async () => {
        setRefreshing(true);
        await loadAllMetrics();
        setRefreshing(false);
        toast.success('Metrics refreshed');
    };

    const loadReminderMetrics = async (days) => {
        try {
            const res = await metricsAPI.getReminderEffectiveness(parseInt(days));
            setReminderMetrics(res.data);
        } catch (err) {
            toast.error('Failed to load reminder metrics');
        }
    };

    const loadResolutionMetrics = async (days) => {
        try {
            const res = await metricsAPI.getConflictResolution(parseInt(days));
            setConflictResolution(res.data);
        } catch (err) {
            toast.error('Failed to load resolution metrics');
        }
    };

    if (!isSuperAdmin() && !isManager()) {
        return (
            <Layout>
                <div className="text-center py-16">
                    <p className="text-zinc-400">Access denied. Requires Manager or Super Admin role.</p>
                </div>
            </Layout>
        );
    }

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
            <div className="space-y-6" data-testid="metrics-dashboard-page">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                            <BarChart3 className="h-6 w-6 text-blue-400" />
                            Metrics Dashboard
                        </h1>
                        <p className="text-zinc-400 mt-1">Track system performance and effectiveness</p>
                    </div>
                    <Button 
                        onClick={handleRefresh} 
                        variant="outline" 
                        disabled={refreshing}
                        data-testid="refresh-metrics-btn"
                    >
                        <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>

                {/* Quick Stats Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <Card className="bg-card border-border">
                        <CardContent className="pt-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">Response Rate</p>
                                    <p className="text-2xl font-bold text-white">
                                        {dashboard?.reminder_effectiveness?.response_rate_percent || 0}%
                                    </p>
                                </div>
                                <div className="h-12 w-12 rounded-full bg-emerald-500/10 flex items-center justify-center">
                                    <TrendingUp className="h-6 w-6 text-emerald-400" />
                                </div>
                            </div>
                            <p className="text-xs text-zinc-500 mt-2">
                                {dashboard?.reminder_effectiveness?.total_reminders_7d || 0} reminders sent (7d)
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="bg-card border-border">
                        <CardContent className="pt-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">Avg Response Time</p>
                                    <p className="text-2xl font-bold text-white">
                                        {dashboard?.reminder_effectiveness?.avg_response_time_hours || 0}h
                                    </p>
                                </div>
                                <div className="h-12 w-12 rounded-full bg-blue-500/10 flex items-center justify-center">
                                    <Clock className="h-6 w-6 text-blue-400" />
                                </div>
                            </div>
                            <p className="text-xs text-zinc-500 mt-2">Hours to respond to reminders</p>
                        </CardContent>
                    </Card>

                    <Card className="bg-card border-border">
                        <CardContent className="pt-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">Open Conflicts</p>
                                    <p className="text-2xl font-bold text-white">
                                        {dashboard?.conflict_aging?.total_open || 0}
                                    </p>
                                </div>
                                <div className="h-12 w-12 rounded-full bg-amber-500/10 flex items-center justify-center">
                                    <AlertTriangle className="h-6 w-6 text-amber-400" />
                                </div>
                            </div>
                            <p className="text-xs text-zinc-500 mt-2">
                                {dashboard?.conflict_aging?.critical_count || 0} critical (&gt;7 days)
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="bg-card border-border">
                        <CardContent className="pt-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-zinc-400">Avg Resolution</p>
                                    <p className="text-2xl font-bold text-white">
                                        {dashboard?.conflict_resolution?.avg_resolution_time_days || 0}d
                                    </p>
                                </div>
                                <div className="h-12 w-12 rounded-full bg-purple-500/10 flex items-center justify-center">
                                    <CheckCircle2 className="h-6 w-6 text-purple-400" />
                                </div>
                            </div>
                            <p className="text-xs text-zinc-500 mt-2">
                                {dashboard?.conflict_resolution?.total_resolved_30d || 0} resolved (30d)
                            </p>
                        </CardContent>
                    </Card>
                </div>

                {/* Detailed Metrics */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Reminder Effectiveness */}
                    <Card className="bg-card border-border">
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="text-lg flex items-center gap-2">
                                        <Bell className="h-5 w-5 text-emerald-400" />
                                        Reminder Effectiveness
                                    </CardTitle>
                                    <CardDescription>How effective are optimization reminders?</CardDescription>
                                </div>
                                <Select value={reminderDays} onValueChange={(v) => { setReminderDays(v); loadReminderMetrics(v); }}>
                                    <SelectTrigger className="w-24">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="7">7 days</SelectItem>
                                        <SelectItem value="30">30 days</SelectItem>
                                        <SelectItem value="90">90 days</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {reminderMetrics ? (
                                <>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Total Sent</p>
                                            <p className="text-xl font-bold text-white">{reminderMetrics.total_reminders}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Responded</p>
                                            <p className="text-xl font-bold text-emerald-400">{reminderMetrics.responded}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Response Rate</p>
                                            <p className="text-xl font-bold text-blue-400">{reminderMetrics.response_rate_percent}%</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Avg Response</p>
                                            <p className="text-xl font-bold text-amber-400">{reminderMetrics.avg_response_time_hours}h</p>
                                        </div>
                                    </div>
                                    
                                    {/* By Type Breakdown */}
                                    {Object.keys(reminderMetrics.by_type || {}).length > 0 && (
                                        <div>
                                            <p className="text-sm font-medium text-zinc-400 mb-2">By Reminder Type</p>
                                            <div className="space-y-2">
                                                {Object.entries(reminderMetrics.by_type).map(([type, data]) => (
                                                    <div key={type} className="flex items-center justify-between p-2 rounded bg-zinc-800/30">
                                                        <span className="text-sm text-zinc-300 capitalize">{type.replace('_', ' ')}</span>
                                                        <div className="flex items-center gap-2">
                                                            <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400">
                                                                {data.responded} responded
                                                            </Badge>
                                                            <Badge variant="outline" className="bg-zinc-500/10 text-zinc-400">
                                                                {data.total} total
                                                            </Badge>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* By Action Breakdown */}
                                    {Object.keys(reminderMetrics.by_action || {}).length > 0 && (
                                        <div>
                                            <p className="text-sm font-medium text-zinc-400 mb-2">Response Actions</p>
                                            <div className="flex flex-wrap gap-2">
                                                {Object.entries(reminderMetrics.by_action).map(([action, count]) => (
                                                    <Badge key={action} variant="outline" className="bg-blue-500/10 text-blue-400">
                                                        {action}: {count}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </>
                            ) : (
                                <p className="text-zinc-500 text-center py-8">No reminder data available</p>
                            )}
                        </CardContent>
                    </Card>

                    {/* Conflict Aging */}
                    <Card className="bg-card border-border">
                        <CardHeader>
                            <CardTitle className="text-lg flex items-center gap-2">
                                <AlertTriangle className="h-5 w-5 text-amber-400" />
                                Conflict Aging Analysis
                            </CardTitle>
                            <CardDescription>How long have complaints been open?</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {conflictAging ? (
                                <>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Total Open</p>
                                            <p className="text-xl font-bold text-white">{conflictAging.total_open}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                                            <p className="text-xs text-red-400">Critical (&gt;7d)</p>
                                            <p className="text-xl font-bold text-red-400">{conflictAging.critical_count}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Avg Age</p>
                                            <p className="text-xl font-bold text-amber-400">{conflictAging.avg_age_days} days</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Max Age</p>
                                            <p className="text-xl font-bold text-red-400">{conflictAging.max_age_days} days</p>
                                        </div>
                                    </div>

                                    {/* Age Distribution */}
                                    {conflictAging.by_age_bucket && (
                                        <div>
                                            <p className="text-sm font-medium text-zinc-400 mb-2">Age Distribution</p>
                                            <div className="space-y-2">
                                                {Object.entries(conflictAging.by_age_bucket).map(([bucket, count]) => {
                                                    const total = conflictAging.total_open || 1;
                                                    const pct = Math.round((count / total) * 100);
                                                    const isOld = bucket.includes('15') || bucket.includes('30+');
                                                    return (
                                                        <div key={bucket} className="flex items-center gap-3">
                                                            <span className="text-xs text-zinc-400 w-20">{bucket.replace('_', ' ')}</span>
                                                            <div className="flex-1 h-5 bg-zinc-800 rounded-full overflow-hidden">
                                                                <div 
                                                                    className={`h-full ${isOld ? 'bg-red-500' : 'bg-blue-500'} transition-all`}
                                                                    style={{ width: `${pct}%` }}
                                                                />
                                                            </div>
                                                            <span className={`text-sm font-medium w-12 text-right ${isOld ? 'text-red-400' : 'text-zinc-300'}`}>
                                                                {count}
                                                            </span>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    )}

                                    {/* Oldest Complaints */}
                                    {conflictAging.oldest_complaints?.length > 0 && (
                                        <div>
                                            <p className="text-sm font-medium text-zinc-400 mb-2">Oldest Open Complaints</p>
                                            <div className="space-y-1 max-h-40 overflow-y-auto">
                                                {conflictAging.oldest_complaints.slice(0, 5).map((c) => (
                                                    <div key={c.id} className="flex items-center justify-between p-2 rounded bg-zinc-800/30 text-sm">
                                                        <span className="text-zinc-300 truncate max-w-[200px]">{c.title || c.id}</span>
                                                        <Badge variant="outline" className={c.age_days > 7 ? 'bg-red-500/10 text-red-400' : 'bg-amber-500/10 text-amber-400'}>
                                                            {c.age_days}d old
                                                        </Badge>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </>
                            ) : (
                                <p className="text-zinc-500 text-center py-8">No conflict data available</p>
                            )}
                        </CardContent>
                    </Card>

                    {/* Conflict Resolution */}
                    <Card className="bg-card border-border">
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="text-lg flex items-center gap-2">
                                        <CheckCircle2 className="h-5 w-5 text-purple-400" />
                                        Resolution Metrics
                                    </CardTitle>
                                    <CardDescription>How quickly are complaints being resolved?</CardDescription>
                                </div>
                                <Select value={resolutionDays} onValueChange={(v) => { setResolutionDays(v); loadResolutionMetrics(v); }}>
                                    <SelectTrigger className="w-24">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="7">7 days</SelectItem>
                                        <SelectItem value="30">30 days</SelectItem>
                                        <SelectItem value="90">90 days</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {conflictResolution ? (
                                <>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Total Resolved</p>
                                            <p className="text-xl font-bold text-emerald-400">{conflictResolution.total_resolved}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Avg Time</p>
                                            <p className="text-xl font-bold text-blue-400">{conflictResolution.avg_resolution_time_days}d</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Fastest</p>
                                            <p className="text-xl font-bold text-emerald-400">{conflictResolution.min_resolution_time_days}d</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Slowest</p>
                                            <p className="text-xl font-bold text-amber-400">{conflictResolution.max_resolution_time_days}d</p>
                                        </div>
                                    </div>

                                    {/* Time Distribution */}
                                    {conflictResolution.by_time_bucket && (
                                        <div>
                                            <p className="text-sm font-medium text-zinc-400 mb-2">Resolution Time Distribution</p>
                                            <div className="space-y-2">
                                                {Object.entries(conflictResolution.by_time_bucket).map(([bucket, count]) => {
                                                    const total = conflictResolution.total_resolved || 1;
                                                    const pct = Math.round((count / total) * 100);
                                                    const isFast = bucket === 'same_day' || bucket === '1-2_days';
                                                    return (
                                                        <div key={bucket} className="flex items-center gap-3">
                                                            <span className="text-xs text-zinc-400 w-20">{bucket.replace('_', ' ')}</span>
                                                            <div className="flex-1 h-5 bg-zinc-800 rounded-full overflow-hidden">
                                                                <div 
                                                                    className={`h-full ${isFast ? 'bg-emerald-500' : 'bg-amber-500'} transition-all`}
                                                                    style={{ width: `${pct}%` }}
                                                                />
                                                            </div>
                                                            <span className={`text-sm font-medium w-12 text-right ${isFast ? 'text-emerald-400' : 'text-amber-400'}`}>
                                                                {count}
                                                            </span>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    )}
                                </>
                            ) : (
                                <p className="text-zinc-500 text-center py-8">No resolution data available</p>
                            )}
                        </CardContent>
                    </Card>

                    {/* Audit Stats */}
                    <Card className="bg-card border-border">
                        <CardHeader>
                            <CardTitle className="text-lg flex items-center gap-2">
                                <Activity className="h-5 w-5 text-blue-400" />
                                Audit Log Summary (7 days)
                            </CardTitle>
                            <CardDescription>System activity and security events</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {auditStats ? (
                                <>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Total Events</p>
                                            <p className="text-xl font-bold text-white">{auditStats.total_events}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                                            <p className="text-xs text-red-400">Failures</p>
                                            <p className="text-xl font-bold text-red-400">{auditStats.failures}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                                            <p className="text-xs text-amber-400">Permission Violations</p>
                                            <p className="text-xl font-bold text-amber-400">{auditStats.permission_violations}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-zinc-800/50">
                                            <p className="text-xs text-zinc-400">Notification Failures</p>
                                            <p className="text-xl font-bold text-zinc-400">{auditStats.notification_failures}</p>
                                        </div>
                                    </div>

                                    {/* By Event Type */}
                                    {Object.keys(auditStats.by_event_type || {}).length > 0 && (
                                        <div>
                                            <p className="text-sm font-medium text-zinc-400 mb-2">By Event Type</p>
                                            <div className="space-y-1 max-h-40 overflow-y-auto">
                                                {Object.entries(auditStats.by_event_type).map(([type, data]) => (
                                                    <div key={type} className="flex items-center justify-between p-2 rounded bg-zinc-800/30 text-sm">
                                                        <span className="text-zinc-300 capitalize">{type.replace('_', ' ')}</span>
                                                        <div className="flex items-center gap-2">
                                                            <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400">
                                                                {data.success} ok
                                                            </Badge>
                                                            {data.failed > 0 && (
                                                                <Badge variant="outline" className="bg-red-500/10 text-red-400">
                                                                    {data.failed} fail
                                                                </Badge>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    <Button 
                                        variant="outline" 
                                        className="w-full"
                                        onClick={() => window.location.href = '/audit-logs'}
                                    >
                                        View Full Audit Logs
                                        <ChevronRight className="h-4 w-4 ml-2" />
                                    </Button>
                                </>
                            ) : (
                                <p className="text-zinc-500 text-center py-8">No audit data available</p>
                            )}
                        </CardContent>
                    </Card>
                </div>
            </div>
        </Layout>
    );
}
