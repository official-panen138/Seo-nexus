import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Skeleton } from '../components/ui/skeleton';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import { 
    Clock, 
    Play, 
    Pause, 
    RefreshCw, 
    CheckCircle, 
    XCircle, 
    AlertTriangle,
    Calendar,
    History,
    Settings,
    Bell,
    Loader2,
    ChevronRight,
    Users,
    MessageSquare,
    Trash2
} from 'lucide-react';
import axios from 'axios';

// Create API client for v3 endpoints
const apiV3 = axios.create({
    baseURL: process.env.REACT_APP_BACKEND_URL + '/api/v3',
    headers: { 'Content-Type': 'application/json' }
});

apiV3.interceptors.request.use((config) => {
    const token = localStorage.getItem('seo_nexus_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export default function SchedulerDashboardPage() {
    const { user, isSuperAdmin } = useAuth();
    const [loading, setLoading] = useState(true);
    const [schedulerStatus, setSchedulerStatus] = useState(null);
    const [executionLogs, setExecutionLogs] = useState([]);
    const [reminderConfig, setReminderConfig] = useState({
        enabled: true,
        interval_days: 2
    });
    const [triggering, setTriggering] = useState(false);
    const [savingConfig, setSavingConfig] = useState(false);
    const [clearingLogs, setClearingLogs] = useState(false);

    useEffect(() => {
        if (isSuperAdmin()) {
            loadDashboardData();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const loadDashboardData = async () => {
        setLoading(true);
        try {
            const [statusRes, logsRes, configRes] = await Promise.all([
                apiV3.get('/scheduler/reminder-status'),
                apiV3.get('/scheduler/execution-logs?limit=10'),
                apiV3.get('/settings/reminder-config')
            ]);
            
            setSchedulerStatus(statusRes.data);
            setExecutionLogs(logsRes.data.logs || []);
            setReminderConfig({
                enabled: configRes.data.enabled ?? true,
                interval_days: configRes.data.interval_days ?? 2
            });
        } catch (err) {
            console.error('Failed to load dashboard data:', err);
            toast.error('Failed to load scheduler data');
        } finally {
            setLoading(false);
        }
    };

    const handleTriggerReminders = async () => {
        setTriggering(true);
        try {
            const res = await apiV3.post('/scheduler/trigger-reminders');
            toast.success('Reminder job triggered successfully');
            // Reload data to see results
            await loadDashboardData();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to trigger reminders');
        } finally {
            setTriggering(false);
        }
    };

    const handleSaveConfig = async () => {
        setSavingConfig(true);
        try {
            await apiV3.put('/settings/reminder-config', reminderConfig);
            toast.success('Reminder settings saved');
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to save settings');
        } finally {
            setSavingConfig(false);
        }
    };

    const handleClearLogs = async () => {
        if (!window.confirm('Are you sure you want to clear all execution logs? This cannot be undone.')) {
            return;
        }
        setClearingLogs(true);
        try {
            await apiV3.delete('/scheduler/execution-logs');
            setExecutionLogs([]);
            toast.success('Execution logs cleared');
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to clear logs');
        } finally {
            setClearingLogs(false);
        }
    };

    const formatDateTime = (isoString) => {
        if (!isoString) return '-';
        return new Date(isoString).toLocaleString();
    };

    const formatRelativeTime = (isoString) => {
        if (!isoString) return '-';
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = date - now;
        const diffHours = Math.round(diffMs / (1000 * 60 * 60));
        
        if (diffHours > 0) {
            return `in ${diffHours} hour${diffHours !== 1 ? 's' : ''}`;
        } else if (diffHours < 0) {
            return `${Math.abs(diffHours)} hour${Math.abs(diffHours) !== 1 ? 's' : ''} ago`;
        }
        return 'now';
    };

    if (!isSuperAdmin()) {
        return (
            <Layout>
                <div className="flex items-center justify-center h-[60vh]">
                    <Card className="bg-card border-border p-8 text-center">
                        <AlertTriangle className="h-12 w-12 text-amber-400 mx-auto mb-4" />
                        <h2 className="text-xl font-semibold text-white mb-2">Access Restricted</h2>
                        <p className="text-zinc-400">Only Super Admins can access the Scheduler Dashboard.</p>
                    </Card>
                </div>
            </Layout>
        );
    }

    if (loading) {
        return (
            <Layout>
                <div className="page-container">
                    <div className="page-header mb-8">
                        <Skeleton className="h-8 w-64" />
                        <Skeleton className="h-4 w-96 mt-2" />
                    </div>
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        <Skeleton className="h-48" />
                        <Skeleton className="h-48" />
                        <Skeleton className="h-48" />
                    </div>
                </div>
            </Layout>
        );
    }

    const scheduler = schedulerStatus?.scheduler || {};
    const lastExecution = schedulerStatus?.last_execution;

    return (
        <Layout>
            <div className="page-container">
                {/* Header */}
                <div className="page-header mb-8">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-md bg-blue-500/10">
                            <Clock className="h-6 w-6 text-blue-500" />
                        </div>
                        <div>
                            <h1 className="page-title">Scheduler Dashboard</h1>
                            <p className="page-subtitle">Manage automatic optimization reminders</p>
                        </div>
                    </div>
                </div>

                {/* Status Cards */}
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 mb-8">
                    {/* Scheduler Status Card */}
                    <Card className="bg-card border-border" data-testid="scheduler-status-card">
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base flex items-center gap-2">
                                <Settings className="h-4 w-4 text-zinc-500" />
                                Scheduler Status
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="flex items-center gap-3 mb-4">
                                {scheduler.running ? (
                                    <>
                                        <div className="h-3 w-3 rounded-full bg-emerald-500 animate-pulse" />
                                        <span className="text-emerald-400 font-medium">Running</span>
                                    </>
                                ) : (
                                    <>
                                        <div className="h-3 w-3 rounded-full bg-red-500" />
                                        <span className="text-red-400 font-medium">Stopped</span>
                                    </>
                                )}
                            </div>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-zinc-500">Job ID:</span>
                                    <span className="text-zinc-300 font-mono text-xs">{scheduler.job_id || '-'}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-zinc-500">Interval:</span>
                                    <span className="text-zinc-300">{scheduler.interval_hours || 24} hours</span>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Next Run Card */}
                    <Card className="bg-card border-border" data-testid="next-run-card">
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base flex items-center gap-2">
                                <Calendar className="h-4 w-4 text-zinc-500" />
                                Next Scheduled Run
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-semibold text-blue-400 mb-2">
                                {formatRelativeTime(scheduler.next_run_time)}
                            </div>
                            <p className="text-sm text-zinc-500">
                                {formatDateTime(scheduler.next_run_time)}
                            </p>
                        </CardContent>
                    </Card>

                    {/* Last Execution Card */}
                    <Card className="bg-card border-border" data-testid="last-execution-card">
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base flex items-center gap-2">
                                <History className="h-4 w-4 text-zinc-500" />
                                Last Execution
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {lastExecution ? (
                                <div className="space-y-2">
                                    <div className="flex items-center gap-2">
                                        {lastExecution.status === 'success' ? (
                                            <CheckCircle className="h-4 w-4 text-emerald-400" />
                                        ) : (
                                            <XCircle className="h-4 w-4 text-red-400" />
                                        )}
                                        <span className={lastExecution.status === 'success' ? 'text-emerald-400' : 'text-red-400'}>
                                            {lastExecution.status === 'success' ? 'Success' : 'Failed'}
                                        </span>
                                    </div>
                                    <p className="text-sm text-zinc-500">
                                        {formatDateTime(lastExecution.executed_at)}
                                    </p>
                                    {lastExecution.results && (
                                        <div className="mt-2 p-2 rounded bg-zinc-900 text-xs">
                                            <div className="flex justify-between">
                                                <span className="text-zinc-500">Found:</span>
                                                <span className="text-zinc-300">{lastExecution.results.total_found}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-zinc-500">Sent:</span>
                                                <span className="text-emerald-400">{lastExecution.results.reminders_sent}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-zinc-500">Failed:</span>
                                                <span className="text-red-400">{lastExecution.results.reminders_failed}</span>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <p className="text-zinc-500">No executions yet</p>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Actions & Configuration */}
                <div className="grid gap-6 lg:grid-cols-2 mb-8">
                    {/* Manual Trigger Card */}
                    <Card className="bg-card border-border" data-testid="manual-trigger-card">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Play className="h-5 w-5 text-emerald-500" />
                                Manual Trigger
                            </CardTitle>
                            <CardDescription>
                                Manually run the reminder job to send pending reminders immediately
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="p-4 rounded-lg bg-amber-950/20 border border-amber-900/30 mb-4">
                                <div className="flex items-start gap-3">
                                    <AlertTriangle className="h-5 w-5 text-amber-400 mt-0.5 flex-shrink-0" />
                                    <div className="text-sm text-amber-300/80">
                                        <p className="font-medium text-amber-300 mb-1">Note</p>
                                        <p>This will check all "In Progress" optimizations and send Telegram reminders to those that have exceeded the reminder interval.</p>
                                    </div>
                                </div>
                            </div>
                            <Button 
                                onClick={handleTriggerReminders}
                                disabled={triggering}
                                className="w-full gap-2"
                                data-testid="trigger-reminders-btn"
                            >
                                {triggering ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Play className="h-4 w-4" />
                                )}
                                {triggering ? 'Running...' : 'Trigger Reminders Now'}
                            </Button>
                        </CardContent>
                    </Card>

                    {/* Reminder Configuration Card */}
                    <Card className="bg-card border-border" data-testid="reminder-config-card">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Bell className="h-5 w-5 text-blue-500" />
                                Global Reminder Settings
                            </CardTitle>
                            <CardDescription>
                                Configure default reminder behavior for all networks
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            {/* Enable/Disable Toggle */}
                            <div className="flex items-center justify-between">
                                <div>
                                    <Label className="text-sm font-medium">Enable Reminders</Label>
                                    <p className="text-xs text-zinc-500 mt-1">
                                        Turn automatic reminders on or off globally
                                    </p>
                                </div>
                                <Switch
                                    checked={reminderConfig.enabled}
                                    onCheckedChange={(checked) => setReminderConfig(prev => ({ ...prev, enabled: checked }))}
                                    data-testid="enable-reminders-switch"
                                />
                            </div>

                            {/* Interval Setting */}
                            <div>
                                <Label className="text-sm font-medium">Reminder Interval (Days)</Label>
                                <p className="text-xs text-zinc-500 mt-1 mb-3">
                                    Send reminders for optimizations in progress for this many days
                                </p>
                                <div className="flex items-center gap-3">
                                    <Input
                                        type="number"
                                        min={1}
                                        max={30}
                                        value={reminderConfig.interval_days}
                                        onChange={(e) => setReminderConfig(prev => ({ 
                                            ...prev, 
                                            interval_days: parseInt(e.target.value) || 2 
                                        }))}
                                        className="w-24 bg-black border-border"
                                        data-testid="interval-days-input"
                                    />
                                    <span className="text-zinc-500 text-sm">days</span>
                                </div>
                            </div>

                            <Button 
                                onClick={handleSaveConfig}
                                disabled={savingConfig}
                                className="w-full gap-2"
                                data-testid="save-config-btn"
                            >
                                {savingConfig && <Loader2 className="h-4 w-4 animate-spin" />}
                                Save Settings
                            </Button>
                        </CardContent>
                    </Card>
                </div>

                {/* Execution History */}
                <Card className="bg-card border-border" data-testid="execution-history-card">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle className="flex items-center gap-2">
                                    <History className="h-5 w-5 text-zinc-500" />
                                    Execution History
                                </CardTitle>
                                <CardDescription>
                                    Recent scheduler job executions
                                </CardDescription>
                            </div>
                            <div className="flex items-center gap-2">
                                <Button 
                                    variant="outline" 
                                    size="sm" 
                                    onClick={loadDashboardData}
                                    className="gap-2"
                                    data-testid="refresh-logs-btn"
                                >
                                    <RefreshCw className="h-4 w-4" />
                                    Refresh
                                </Button>
                                {executionLogs.length > 0 && (
                                    <Button 
                                        variant="outline" 
                                        size="sm" 
                                        onClick={handleClearLogs}
                                        disabled={clearingLogs}
                                        className="gap-2 text-red-400 border-red-500/30 hover:bg-red-500/10"
                                        data-testid="clear-logs-btn"
                                    >
                                        {clearingLogs ? (
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                        ) : (
                                            <Trash2 className="h-4 w-4" />
                                        )}
                                        Clear
                                    </Button>
                                )}
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent>
                        {executionLogs.length === 0 ? (
                            <div className="text-center py-8 text-zinc-500">
                                <History className="h-12 w-12 mx-auto mb-3 opacity-50" />
                                <p>No execution history yet</p>
                                <p className="text-sm mt-1">The scheduler runs every 24 hours or when manually triggered</p>
                            </div>
                        ) : (
                            <ScrollArea className="h-[300px]">
                                <div className="space-y-3">
                                    {executionLogs.map((log, index) => (
                                        <div 
                                            key={log.executed_at || index}
                                            className="p-4 rounded-lg bg-zinc-900/50 border border-border"
                                            data-testid={`execution-log-${index}`}
                                        >
                                            <div className="flex items-start justify-between mb-2">
                                                <div className="flex items-center gap-2">
                                                    {log.status === 'success' ? (
                                                        <CheckCircle className="h-4 w-4 text-emerald-400" />
                                                    ) : (
                                                        <XCircle className="h-4 w-4 text-red-400" />
                                                    )}
                                                    <span className={`font-medium ${log.status === 'success' ? 'text-emerald-400' : 'text-red-400'}`}>
                                                        {log.status === 'success' ? 'Success' : 'Failed'}
                                                    </span>
                                                </div>
                                                <span className="text-xs text-zinc-500">
                                                    {formatDateTime(log.executed_at)}
                                                </span>
                                            </div>
                                            {log.results && (
                                                <div className="grid grid-cols-4 gap-4 mt-3 text-sm">
                                                    <div className="text-center p-2 rounded bg-zinc-800">
                                                        <div className="text-lg font-semibold text-white">{log.results.total_found}</div>
                                                        <div className="text-xs text-zinc-500">Found</div>
                                                    </div>
                                                    <div className="text-center p-2 rounded bg-zinc-800">
                                                        <div className="text-lg font-semibold text-emerald-400">{log.results.reminders_sent}</div>
                                                        <div className="text-xs text-zinc-500">Sent</div>
                                                    </div>
                                                    <div className="text-center p-2 rounded bg-zinc-800">
                                                        <div className="text-lg font-semibold text-red-400">{log.results.reminders_failed}</div>
                                                        <div className="text-xs text-zinc-500">Failed</div>
                                                    </div>
                                                    <div className="text-center p-2 rounded bg-zinc-800">
                                                        <div className="text-lg font-semibold text-blue-400">{log.results.logs_created}</div>
                                                        <div className="text-xs text-zinc-500">Logged</div>
                                                    </div>
                                                </div>
                                            )}
                                            {log.error && (
                                                <div className="mt-2 p-2 rounded bg-red-950/30 border border-red-900/30 text-sm text-red-400">
                                                    {log.error}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </ScrollArea>
                        )}
                    </CardContent>
                </Card>
            </div>
        </Layout>
    );
}
