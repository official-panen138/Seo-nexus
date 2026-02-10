import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { alertsAPI, reportsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { 
    Bell, 
    CheckCircle, 
    Loader2, 
    AlertCircle,
    AlertTriangle,
    Clock,
    Filter,
    Check,
    Network,
    ExternalLink,
    RefreshCw
} from 'lucide-react';
import { 
    SEVERITY_LABELS, 
    getSeverityBadgeClass, 
    ALERT_TYPE_LABELS,
    formatDateTime 
} from '../lib/utils';

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
    'noindex_high_tier': 'NOINDEX in High Tier'
};

export default function AlertsPage() {
    const { canEdit } = useAuth();
    const [activeTab, setActiveTab] = useState('alerts');
    
    // Alerts state
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [acknowledging, setAcknowledging] = useState(null);
    
    // Conflicts state
    const [conflicts, setConflicts] = useState([]);
    const [loadingConflicts, setLoadingConflicts] = useState(false);
    const [conflictsLoaded, setConflictsLoaded] = useState(false);
    
    // Filters
    const [filterSeverity, setFilterSeverity] = useState('all');
    const [filterType, setFilterType] = useState('all');
    const [filterAcknowledged, setFilterAcknowledged] = useState('false');

    useEffect(() => {
        loadAlerts();
    }, [filterSeverity, filterType, filterAcknowledged]);

    useEffect(() => {
        if (activeTab === 'conflicts' && !conflictsLoaded) {
            loadConflicts();
        }
    }, [activeTab]);

    const loadAlerts = async () => {
        try {
            const params = { limit: 200 };
            if (filterSeverity !== 'all') params.severity = filterSeverity;
            if (filterType !== 'all') params.alert_type = filterType;
            if (filterAcknowledged !== 'all') params.acknowledged = filterAcknowledged === 'true';
            
            const res = await alertsAPI.getAll(params);
            setAlerts(res.data);
        } catch (err) {
            toast.error('Failed to load alerts');
        } finally {
            setLoading(false);
        }
    };

    const loadConflicts = async () => {
        setLoadingConflicts(true);
        try {
            const res = await reportsAPI.getConflicts();
            setConflicts(res.data || []);
            setConflictsLoaded(true);
        } catch (err) {
            console.error('Failed to load conflicts:', err);
            toast.error('Failed to load conflicts');
        } finally {
            setLoadingConflicts(false);
        }
    };

    const handleAcknowledge = async (alertId) => {
        setAcknowledging(alertId);
        try {
            await alertsAPI.acknowledge(alertId);
            toast.success('Alert acknowledged');
            loadAlerts();
        } catch (err) {
            toast.error('Failed to acknowledge alert');
        } finally {
            setAcknowledging(null);
        }
    };

    // Stats
    const stats = {
        total: alerts.length,
        critical: alerts.filter(a => a.severity === 'critical' && !a.acknowledged).length,
        high: alerts.filter(a => a.severity === 'high' && !a.acknowledged).length,
        unacknowledged: alerts.filter(a => !a.acknowledged).length
    };

    // Conflict stats
    const conflictStats = {
        total: conflicts.length,
        critical: conflicts.filter(c => c.severity === 'critical').length,
        high: conflicts.filter(c => c.severity === 'high').length,
        byType: conflicts.reduce((acc, c) => {
            const type = c.conflict_type || 'unknown';
            acc[type] = (acc[type] || 0) + 1;
            return acc;
        }, {})
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
            <div data-testid="alerts-page">
                {/* Header */}
                <div className="page-header">
                    <div className="flex items-center gap-3">
                        <Bell className="h-7 w-7 text-amber-500" />
                        <div>
                            <h1 className="page-title">Alert Center</h1>
                            <p className="page-subtitle">
                                Monitor and manage system alerts
                            </p>
                        </div>
                    </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <Card className="bg-card border-border">
                        <CardContent className="pt-4">
                            <div className="text-sm text-zinc-500 mb-1">Total Alerts</div>
                            <div className="text-2xl font-bold font-mono">{stats.total}</div>
                        </CardContent>
                    </Card>
                    <Card className={`bg-card border-border ${stats.critical > 0 ? 'border-red-900/50' : ''}`}>
                        <CardContent className="pt-4">
                            <div className="text-sm text-zinc-500 mb-1">Critical</div>
                            <div className={`text-2xl font-bold font-mono ${stats.critical > 0 ? 'text-red-500' : 'text-zinc-400'}`}>
                                {stats.critical}
                            </div>
                        </CardContent>
                    </Card>
                    <Card className={`bg-card border-border ${stats.high > 0 ? 'border-amber-900/50' : ''}`}>
                        <CardContent className="pt-4">
                            <div className="text-sm text-zinc-500 mb-1">High Priority</div>
                            <div className={`text-2xl font-bold font-mono ${stats.high > 0 ? 'text-amber-500' : 'text-zinc-400'}`}>
                                {stats.high}
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="bg-card border-border">
                        <CardContent className="pt-4">
                            <div className="text-sm text-zinc-500 mb-1">Unacknowledged</div>
                            <div className={`text-2xl font-bold font-mono ${stats.unacknowledged > 0 ? 'text-amber-500' : 'text-emerald-500'}`}>
                                {stats.unacknowledged}
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Filters */}
                <div className="flex flex-wrap items-center gap-3 mb-6">
                    <Filter className="h-4 w-4 text-zinc-500" />
                    
                    <Select value={filterSeverity} onValueChange={setFilterSeverity}>
                        <SelectTrigger className="w-[140px] bg-card border-border" data-testid="filter-severity">
                            <SelectValue placeholder="Severity" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Severity</SelectItem>
                            <SelectItem value="critical">Critical</SelectItem>
                            <SelectItem value="high">High</SelectItem>
                            <SelectItem value="medium">Medium</SelectItem>
                            <SelectItem value="low">Low</SelectItem>
                        </SelectContent>
                    </Select>

                    <Select value={filterType} onValueChange={setFilterType}>
                        <SelectTrigger className="w-[140px] bg-card border-border" data-testid="filter-type">
                            <SelectValue placeholder="Type" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Types</SelectItem>
                            <SelectItem value="monitoring">Monitoring</SelectItem>
                            <SelectItem value="expiration">Expiration</SelectItem>
                            <SelectItem value="seo_conflict">SEO Conflict</SelectItem>
                        </SelectContent>
                    </Select>

                    <Select value={filterAcknowledged} onValueChange={setFilterAcknowledged}>
                        <SelectTrigger className="w-[160px] bg-card border-border" data-testid="filter-acknowledged">
                            <SelectValue placeholder="Status" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Status</SelectItem>
                            <SelectItem value="false">Unacknowledged</SelectItem>
                            <SelectItem value="true">Acknowledged</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* Alerts Table */}
                <div className="data-table-container" data-testid="alerts-table">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Severity</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>Domain</TableHead>
                                <TableHead>Issue</TableHead>
                                <TableHead>Time</TableHead>
                                <TableHead>Status</TableHead>
                                {canEdit() && <TableHead className="text-right">Action</TableHead>}
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {alerts.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={canEdit() ? 7 : 6} className="h-32 text-center">
                                        <div className="empty-state py-8">
                                            <CheckCircle className="empty-state-icon mx-auto text-emerald-500" />
                                            <p className="empty-state-title">No alerts</p>
                                            <p className="empty-state-description">
                                                All systems operating normally
                                            </p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                alerts.map((alert) => (
                                    <TableRow 
                                        key={alert.id} 
                                        className={`table-row-hover ${!alert.acknowledged && alert.severity === 'critical' ? 'bg-red-950/10' : ''}`}
                                        data-testid={`alert-row-${alert.id}`}
                                    >
                                        <TableCell>
                                            <Badge variant="outline" className={`text-xs ${getSeverityBadgeClass(alert.severity)}`}>
                                                {SEVERITY_LABELS[alert.severity]}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline" className="text-xs font-normal">
                                                {ALERT_TYPE_LABELS[alert.alert_type] || alert.alert_type}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <div>
                                                <span className="font-mono text-sm">{alert.domain_name}</span>
                                                {alert.brand_name && (
                                                    <span className="text-xs text-zinc-500 block">{alert.brand_name}</span>
                                                )}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <div>
                                                <span className="text-sm font-medium">{alert.title}</span>
                                                <span className="text-xs text-zinc-500 block truncate max-w-xs">
                                                    {alert.message}
                                                </span>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-1 text-xs text-zinc-500">
                                                <Clock className="h-3 w-3" />
                                                {formatDateTime(alert.created_at)}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            {alert.acknowledged ? (
                                                <div className="text-xs">
                                                    <span className="text-emerald-500 flex items-center gap-1">
                                                        <Check className="h-3 w-3" /> Acknowledged
                                                    </span>
                                                    <span className="text-zinc-600 block">
                                                        by {alert.acknowledged_by}
                                                    </span>
                                                </div>
                                            ) : (
                                                <Badge variant="outline" className="text-xs border-amber-500/30 text-amber-400">
                                                    Pending
                                                </Badge>
                                            )}
                                        </TableCell>
                                        {canEdit() && (
                                            <TableCell className="text-right">
                                                {!alert.acknowledged && (
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => handleAcknowledge(alert.id)}
                                                        disabled={acknowledging === alert.id}
                                                        className="text-xs"
                                                        data-testid={`ack-alert-${alert.id}`}
                                                    >
                                                        {acknowledging === alert.id ? (
                                                            <Loader2 className="h-3 w-3 animate-spin" />
                                                        ) : (
                                                            <>
                                                                <Check className="h-3 w-3 mr-1" />
                                                                Ack
                                                            </>
                                                        )}
                                                    </Button>
                                                )}
                                            </TableCell>
                                        )}
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>
            </div>
        </Layout>
    );
}
