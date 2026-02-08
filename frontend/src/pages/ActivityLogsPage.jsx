import { useState, useEffect } from 'react';
import { activityLogsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent } from '../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../components/ui/sheet';
import { toast } from 'sonner';
import { 
    Loader2, 
    History, 
    RefreshCw,
    Filter,
    ChevronLeft,
    ChevronRight,
    Eye,
    Plus,
    Edit,
    Trash2,
    ArrowRightLeft,
    User,
    Bot
} from 'lucide-react';
import { formatDate } from '../lib/utils';

// Action type icons and colors
const ACTION_CONFIG = {
    create: { icon: Plus, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    update: { icon: Edit, color: 'text-blue-400', bg: 'bg-blue-500/10' },
    delete: { icon: Trash2, color: 'text-red-400', bg: 'bg-red-500/10' },
    migrate: { icon: ArrowRightLeft, color: 'text-purple-400', bg: 'bg-purple-500/10' }
};

// Entity type labels
const ENTITY_LABELS = {
    asset_domain: 'Asset Domain',
    seo_network: 'SEO Network',
    seo_structure_entry: 'Structure Entry',
    brand: 'Brand',
    category: 'Category',
    user: 'User'
};

export default function ActivityLogsPage() {
    const [logs, setLogs] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedLog, setSelectedLog] = useState(null);
    const [sheetOpen, setSheetOpen] = useState(false);
    
    // Filters
    const [filterEntity, setFilterEntity] = useState('all');
    const [filterAction, setFilterAction] = useState('all');
    const [filterActor, setFilterActor] = useState('all');
    
    // Pagination
    const [page, setPage] = useState(0);
    const pageSize = 50;

    useEffect(() => {
        loadData();
    }, [page, filterEntity, filterAction, filterActor]);

    const loadData = async () => {
        setLoading(true);
        try {
            const params = {
                skip: page * pageSize,
                limit: pageSize
            };
            
            if (filterEntity !== 'all') params.entity_type = filterEntity;
            if (filterAction !== 'all') params.action_type = filterAction;
            if (filterActor !== 'all') params.actor = filterActor;
            
            const [logsRes, statsRes] = await Promise.all([
                activityLogsAPI.getAll(params),
                activityLogsAPI.getStats()
            ]);
            
            setLogs(logsRes.data);
            setStats(statsRes.data);
        } catch (err) {
            console.error('Failed to load activity logs:', err);
            toast.error('Failed to load activity logs');
        } finally {
            setLoading(false);
        }
    };

    const viewLogDetail = (log) => {
        setSelectedLog(log);
        setSheetOpen(true);
    };

    const getActorDisplay = (actor) => {
        if (actor?.startsWith('system:')) {
            return {
                isSystem: true,
                label: actor.replace('system:', '').replace('_', ' ').toUpperCase()
            };
        }
        return { isSystem: false, label: actor };
    };

    const formatJsonValue = (value) => {
        if (!value) return null;
        try {
            return JSON.stringify(value, null, 2);
        } catch {
            return String(value);
        }
    };

    if (loading && logs.length === 0) {
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
            <div data-testid="activity-logs-page">
                {/* Header */}
                <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-md bg-amber-500/10">
                                <History className="h-6 w-6 text-amber-500" />
                            </div>
                            <h1 className="page-title">Activity Logs</h1>
                        </div>
                        <p className="page-subtitle">
                            {stats ? `${stats.total_logs} total logs • ${stats.migration_logs} migration` : 'Loading...'}
                        </p>
                    </div>
                    <Button 
                        variant="ghost"
                        size="sm"
                        onClick={loadData}
                        disabled={loading}
                        className="text-zinc-400"
                    >
                        <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>

                {/* Stats Cards */}
                {stats && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        {Object.entries(stats.by_action || {}).map(([action, count]) => {
                            const config = ACTION_CONFIG[action] || ACTION_CONFIG.update;
                            const Icon = config.icon;
                            return (
                                <Card key={action} className={`bg-card border-border ${config.bg}`}>
                                    <CardContent className="pt-4">
                                        <div className="flex items-center gap-2 mb-1">
                                            <Icon className={`h-4 w-4 ${config.color}`} />
                                            <span className="text-sm text-zinc-500 capitalize">{action}</span>
                                        </div>
                                        <div className={`text-2xl font-bold font-mono ${config.color}`}>{count}</div>
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                )}

                {/* Filters */}
                <div className="filters-bar mb-6">
                    <Select value={filterEntity} onValueChange={setFilterEntity}>
                        <SelectTrigger className="w-[180px] bg-black border-border">
                            <SelectValue placeholder="Entity Type" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Entities</SelectItem>
                            {Object.entries(ENTITY_LABELS).map(([k, v]) => (
                                <SelectItem key={k} value={k}>{v}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <Select value={filterAction} onValueChange={setFilterAction}>
                        <SelectTrigger className="w-[150px] bg-black border-border">
                            <SelectValue placeholder="Action" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Actions</SelectItem>
                            <SelectItem value="create">Create</SelectItem>
                            <SelectItem value="update">Update</SelectItem>
                            <SelectItem value="delete">Delete</SelectItem>
                            <SelectItem value="migrate">Migrate</SelectItem>
                        </SelectContent>
                    </Select>

                    <Select value={filterActor} onValueChange={setFilterActor}>
                        <SelectTrigger className="w-[200px] bg-black border-border">
                            <SelectValue placeholder="Actor" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Actors</SelectItem>
                            <SelectItem value="system:migration_v3">Migration System</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* Logs Table */}
                <div className="data-table-container">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Time</TableHead>
                                <TableHead>Actor</TableHead>
                                <TableHead>Action</TableHead>
                                <TableHead>Entity</TableHead>
                                <TableHead>Entity ID</TableHead>
                                <TableHead className="text-right">Details</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {logs.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={6} className="h-32 text-center text-zinc-500">
                                        No activity logs found
                                    </TableCell>
                                </TableRow>
                            ) : (
                                logs.map((log) => {
                                    const config = ACTION_CONFIG[log.action_type] || ACTION_CONFIG.update;
                                    const Icon = config.icon;
                                    const actor = getActorDisplay(log.actor);
                                    
                                    return (
                                        <TableRow key={log.id} className="table-row-hover">
                                            <TableCell className="text-sm text-zinc-400">
                                                {formatDate(log.created_at)}
                                            </TableCell>
                                            <TableCell>
                                                <div className="flex items-center gap-2">
                                                    {actor.isSystem ? (
                                                        <Bot className="h-4 w-4 text-purple-400" />
                                                    ) : (
                                                        <User className="h-4 w-4 text-zinc-500" />
                                                    )}
                                                    <span className={`text-sm ${actor.isSystem ? 'text-purple-400' : 'text-white'}`}>
                                                        {actor.label}
                                                    </span>
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant="outline" className={`${config.color} border-current/30`}>
                                                    <Icon className="h-3 w-3 mr-1" />
                                                    {log.action_type}
                                                </Badge>
                                            </TableCell>
                                            <TableCell>
                                                <span className="text-sm text-zinc-300">
                                                    {ENTITY_LABELS[log.entity_type] || log.entity_type}
                                                </span>
                                            </TableCell>
                                            <TableCell>
                                                <span className="font-mono text-xs text-zinc-500">
                                                    {log.entity_id?.substring(0, 8)}...
                                                </span>
                                            </TableCell>
                                            <TableCell className="text-right">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => viewLogDetail(log)}
                                                    className="h-8 px-2 text-zinc-400 hover:text-white"
                                                >
                                                    <Eye className="h-4 w-4 mr-1" />
                                                    View
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    );
                                })
                            )}
                        </TableBody>
                    </Table>
                </div>

                {/* Pagination */}
                <div className="flex items-center justify-between mt-4">
                    <p className="text-sm text-zinc-500">
                        Showing {page * pageSize + 1} - {page * pageSize + logs.length}
                    </p>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setPage(p => Math.max(0, p - 1))}
                            disabled={page === 0}
                        >
                            <ChevronLeft className="h-4 w-4" />
                            Previous
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setPage(p => p + 1)}
                            disabled={logs.length < pageSize}
                        >
                            Next
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    </div>
                </div>

                {/* Log Detail Sheet */}
                <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
                    <SheetContent className="bg-card border-border w-full sm:max-w-xl overflow-y-auto">
                        <SheetHeader>
                            <SheetTitle className="flex items-center gap-2">
                                <History className="h-5 w-5" />
                                Activity Log Detail
                            </SheetTitle>
                        </SheetHeader>

                        {selectedLog && (
                            <div className="mt-6 space-y-6">
                                {/* Basic Info */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Time</span>
                                        <span className="text-sm">{formatDate(selectedLog.created_at)}</span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Actor</span>
                                        <span className={`text-sm ${selectedLog.actor?.startsWith('system:') ? 'text-purple-400' : ''}`}>
                                            {selectedLog.actor}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Action</span>
                                        <Badge variant="outline" className={`${ACTION_CONFIG[selectedLog.action_type]?.color || ''}`}>
                                            {selectedLog.action_type}
                                        </Badge>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Entity Type</span>
                                        <span className="text-sm">{ENTITY_LABELS[selectedLog.entity_type] || selectedLog.entity_type}</span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Entity ID</span>
                                        <span className="font-mono text-xs">{selectedLog.entity_id}</span>
                                    </div>
                                </div>

                                {/* Metadata */}
                                {selectedLog.metadata && Object.keys(selectedLog.metadata).length > 0 && (
                                    <div className="pt-4 border-t border-border">
                                        <h4 className="text-sm font-medium text-zinc-400 mb-2">Metadata</h4>
                                        <pre className="bg-black rounded-md p-3 text-xs overflow-x-auto">
                                            {formatJsonValue(selectedLog.metadata)}
                                        </pre>
                                    </div>
                                )}

                                {/* Before Value */}
                                {selectedLog.before_value && (
                                    <div className="pt-4 border-t border-border">
                                        <h4 className="text-sm font-medium text-red-400 mb-2">Before</h4>
                                        <pre className="bg-red-950/20 rounded-md p-3 text-xs overflow-x-auto max-h-60">
                                            {formatJsonValue(selectedLog.before_value)}
                                        </pre>
                                    </div>
                                )}

                                {/* After Value */}
                                {selectedLog.after_value && (
                                    <div className="pt-4 border-t border-border">
                                        <h4 className="text-sm font-medium text-emerald-400 mb-2">After</h4>
                                        <pre className="bg-emerald-950/20 rounded-md p-3 text-xs overflow-x-auto max-h-60">
                                            {formatJsonValue(selectedLog.after_value)}
                                        </pre>
                                    </div>
                                )}
                            </div>
                        )}
                    </SheetContent>
                </Sheet>
            </div>
        </Layout>
    );
}
