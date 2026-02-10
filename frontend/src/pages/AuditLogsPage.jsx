import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { auditAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { Loader2, Activity, RefreshCw, AlertTriangle, CheckCircle2, XCircle, Info, AlertCircle } from 'lucide-react';
import { formatDateTime } from '../lib/utils';

export default function AuditLogsPage() {
    const { isSuperAdmin } = useAuth();
    const [logs, setLogs] = useState([]);
    const [stats, setStats] = useState(null);
    const [eventTypes, setEventTypes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [eventFilter, setEventFilter] = useState('all');
    const [severityFilter, setSeverityFilter] = useState('all');
    const [successFilter, setSuccessFilter] = useState('all');

    useEffect(() => {
        loadInitialData();
    }, []);

    useEffect(() => {
        loadLogs();
    }, [eventFilter, severityFilter, successFilter]);

    const loadInitialData = async () => {
        try {
            const [statsRes, typesRes] = await Promise.all([
                auditAPI.getStats(7).catch(() => ({ data: null })),
                auditAPI.getEventTypes().catch(() => ({ data: { event_types: [], severities: [] } })),
            ]);
            setStats(statsRes.data);
            setEventTypes(typesRes.data?.event_types || []);
        } catch (err) {
            console.error('Failed to load initial data:', err);
        }
    };

    const loadLogs = async () => {
        try {
            setLoading(true);
            const eventType = eventFilter === 'all' ? null : eventFilter;
            const severity = severityFilter === 'all' ? null : severityFilter;
            const success = successFilter === 'all' ? null : successFilter === 'true';
            
            const res = await auditAPI.getLogs(100, null, eventType, severity, success);
            setLogs(res.data?.logs || []);
        } catch (err) {
            toast.error('Failed to load audit logs');
            setLogs([]);
        } finally {
            setLoading(false);
        }
    };

    const getSeverityBadge = (severity) => {
        switch (severity) {
            case 'critical':
                return <Badge className="bg-red-500/10 text-red-500 border-red-500/30"><AlertCircle className="h-3 w-3 mr-1" />Critical</Badge>;
            case 'error':
                return <Badge className="bg-red-500/10 text-red-400 border-red-500/30"><XCircle className="h-3 w-3 mr-1" />Error</Badge>;
            case 'warning':
                return <Badge className="bg-amber-500/10 text-amber-400 border-amber-500/30"><AlertTriangle className="h-3 w-3 mr-1" />Warning</Badge>;
            default:
                return <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/30"><Info className="h-3 w-3 mr-1" />Info</Badge>;
        }
    };

    const getSuccessBadge = (success) => {
        if (success) {
            return <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30"><CheckCircle2 className="h-3 w-3 mr-1" />Success</Badge>;
        }
        return <Badge className="bg-red-500/10 text-red-400 border-red-500/30"><XCircle className="h-3 w-3 mr-1" />Failed</Badge>;
    };

    if (!isSuperAdmin()) {
        return (
            <Layout>
                <div className="text-center py-16">
                    <p className="text-zinc-400">Access denied. Super Admin only.</p>
                </div>
            </Layout>
        );
    }

    return (
        <Layout>
            <div data-testid="audit-logs-page" className="space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                            <Activity className="h-6 w-6 text-blue-400" />
                            Audit Logs
                        </h1>
                        <p className="text-zinc-400 mt-1">Track all system changes and security events</p>
                    </div>
                    <Button onClick={loadLogs} variant="outline" disabled={loading}>
                        <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>

                {/* Stats Cards */}
                {stats && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <Card className="bg-card border-border">
                            <CardContent className="pt-4">
                                <p className="text-xs text-zinc-400">Total Events (7d)</p>
                                <p className="text-2xl font-bold text-white">{stats.total_events || 0}</p>
                            </CardContent>
                        </Card>
                        <Card className="bg-card border-border">
                            <CardContent className="pt-4">
                                <p className="text-xs text-zinc-400">Failures</p>
                                <p className="text-2xl font-bold text-red-400">{stats.failures || 0}</p>
                            </CardContent>
                        </Card>
                        <Card className="bg-card border-border">
                            <CardContent className="pt-4">
                                <p className="text-xs text-amber-400">Permission Violations</p>
                                <p className="text-2xl font-bold text-amber-400">{stats.permission_violations || 0}</p>
                            </CardContent>
                        </Card>
                        <Card className="bg-card border-border">
                            <CardContent className="pt-4">
                                <p className="text-xs text-zinc-400">Notification Failures</p>
                                <p className="text-2xl font-bold text-zinc-400">{stats.notification_failures || 0}</p>
                            </CardContent>
                        </Card>
                    </div>
                )}

                {/* Filters */}
                <div className="flex flex-wrap gap-3">
                    <Select value={eventFilter} onValueChange={setEventFilter}>
                        <SelectTrigger className="w-[180px] bg-card border-border">
                            <SelectValue placeholder="All Event Types" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Event Types</SelectItem>
                            {eventTypes.map((et) => (
                                <SelectItem key={et.value} value={et.value}>{et.label}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <Select value={severityFilter} onValueChange={setSeverityFilter}>
                        <SelectTrigger className="w-[140px] bg-card border-border">
                            <SelectValue placeholder="All Severities" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Severities</SelectItem>
                            <SelectItem value="info">Info</SelectItem>
                            <SelectItem value="warning">Warning</SelectItem>
                            <SelectItem value="error">Error</SelectItem>
                            <SelectItem value="critical">Critical</SelectItem>
                        </SelectContent>
                    </Select>

                    <Select value={successFilter} onValueChange={setSuccessFilter}>
                        <SelectTrigger className="w-[140px] bg-card border-border">
                            <SelectValue placeholder="All Status" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Status</SelectItem>
                            <SelectItem value="true">Success</SelectItem>
                            <SelectItem value="false">Failed</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* Logs Table */}
                <Card className="bg-card border-border">
                    <CardContent className="p-0">
                        {loading ? (
                            <div className="flex items-center justify-center h-64">
                                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
                            </div>
                        ) : (
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Timestamp</TableHead>
                                        <TableHead>Actor</TableHead>
                                        <TableHead>Event Type</TableHead>
                                        <TableHead>Resource</TableHead>
                                        <TableHead>Severity</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Details</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {logs.length === 0 ? (
                                        <TableRow>
                                            <TableCell colSpan={7} className="h-32 text-center">
                                                <div className="py-8">
                                                    <Activity className="h-12 w-12 text-zinc-600 mx-auto mb-3" />
                                                    <p className="text-zinc-400 font-medium">No audit logs found</p>
                                                    <p className="text-zinc-500 text-sm">
                                                        Activity will appear here as changes are made
                                                    </p>
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    ) : (
                                        logs.map((log) => (
                                            <TableRow key={log.id} className="hover:bg-zinc-800/50" data-testid={`audit-log-${log.id}`}>
                                                <TableCell className="text-zinc-400 text-sm whitespace-nowrap">
                                                    {formatDateTime(log.created_at)}
                                                </TableCell>
                                                <TableCell>
                                                    <span className="text-sm text-zinc-300">{log.actor_email || 'System'}</span>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="outline" className="text-xs capitalize">
                                                        {(log.event_type || '').replace(/_/g, ' ')}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    <span className="text-xs text-zinc-400">
                                                        {log.resource_type && (
                                                            <Badge variant="outline" className="mr-1 text-xs">
                                                                {log.resource_type}
                                                            </Badge>
                                                        )}
                                                        {log.resource_id && (
                                                            <code className="text-zinc-500">{log.resource_id}</code>
                                                        )}
                                                    </span>
                                                </TableCell>
                                                <TableCell>
                                                    {getSeverityBadge(log.severity)}
                                                </TableCell>
                                                <TableCell>
                                                    {getSuccessBadge(log.success)}
                                                </TableCell>
                                                <TableCell className="max-w-xs">
                                                    {log.error_message ? (
                                                        <span className="text-xs text-red-400">{log.error_message}</span>
                                                    ) : log.details && Object.keys(log.details).length > 0 ? (
                                                        <code className="text-xs text-zinc-500 block truncate max-w-[200px]">
                                                            {JSON.stringify(log.details)}
                                                        </code>
                                                    ) : (
                                                        <span className="text-xs text-zinc-600">-</span>
                                                    )}
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    )}
                                </TableBody>
                            </Table>
                        )}
                    </CardContent>
                </Card>
            </div>
        </Layout>
    );
}
