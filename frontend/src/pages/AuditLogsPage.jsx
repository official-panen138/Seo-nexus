import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { auditAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Loader2, Activity } from 'lucide-react';
import { formatDateTime } from '../lib/utils';

export default function AuditLogsPage() {
    const { isSuperAdmin } = useAuth();
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [entityFilter, setEntityFilter] = useState('all');

    useEffect(() => {
        loadLogs();
    }, [entityFilter]);

    const loadLogs = async () => {
        try {
            const entityType = entityFilter === 'all' ? undefined : entityFilter;
            const res = await auditAPI.getLogs(100, entityType);
            setLogs(res.data);
        } catch (err) {
            toast.error('Failed to load audit logs');
        } finally {
            setLoading(false);
        }
    };

    const getActionBadgeClass = (action) => {
        switch (action) {
            case 'create':
                return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/30';
            case 'update':
                return 'bg-blue-500/10 text-blue-500 border-blue-500/30';
            case 'delete':
                return 'bg-red-500/10 text-red-500 border-red-500/30';
            default:
                return 'bg-zinc-500/10 text-zinc-500 border-zinc-500/30';
        }
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
            <div data-testid="audit-logs-page">
                {/* Header */}
                <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="page-title">Audit Logs</h1>
                        <p className="page-subtitle">
                            Track all system changes
                        </p>
                    </div>
                    <Select value={entityFilter} onValueChange={setEntityFilter}>
                        <SelectTrigger className="w-[150px] bg-card border-border" data-testid="entity-filter">
                            <SelectValue placeholder="All Entities" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Entities</SelectItem>
                            <SelectItem value="domain">Domains</SelectItem>
                            <SelectItem value="group">Networks</SelectItem>
                            <SelectItem value="brand">Brands</SelectItem>
                            <SelectItem value="user">Users</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* Logs Table */}
                <div className="data-table-container" data-testid="audit-logs-table">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Timestamp</TableHead>
                                <TableHead>User</TableHead>
                                <TableHead>Action</TableHead>
                                <TableHead>Entity</TableHead>
                                <TableHead>Details</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {logs.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={5} className="h-32 text-center">
                                        <div className="empty-state py-8">
                                            <Activity className="empty-state-icon mx-auto" />
                                            <p className="empty-state-title">No audit logs</p>
                                            <p className="empty-state-description">
                                                Activity will appear here as changes are made
                                            </p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                logs.map((log) => (
                                    <TableRow key={log.id} className="table-row-hover" data-testid={`audit-log-${log.id}`}>
                                        <TableCell className="text-zinc-400 text-sm whitespace-nowrap">
                                            {formatDateTime(log.created_at)}
                                        </TableCell>
                                        <TableCell>
                                            <span className="text-sm">{log.user_email}</span>
                                        </TableCell>
                                        <TableCell>
                                            <Badge 
                                                variant="outline" 
                                                className={`text-xs uppercase ${getActionBadgeClass(log.action)}`}
                                            >
                                                {log.action}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline" className="text-xs capitalize">
                                                {log.entity_type}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="max-w-xs">
                                            <code className="text-xs text-zinc-500 block truncate">
                                                {JSON.stringify(log.details)}
                                            </code>
                                        </TableCell>
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
