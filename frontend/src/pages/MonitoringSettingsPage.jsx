import { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
    Settings, Activity, Clock, AlertTriangle, CheckCircle, XCircle, 
    RefreshCw, Calendar, Globe, Loader2, Play, ExternalLink, FlaskConical, 
    Send, History, Shield
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { forcedMonitoringAPI, domainsAPI } from '../lib/api';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function MonitoringSettingsPage() {
    const { toast } = useToast();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [settings, setSettings] = useState(null);
    const [stats, setStats] = useState(null);
    const [expiringDomains, setExpiringDomains] = useState([]);
    const [downDomains, setDownDomains] = useState([]);
    const [runningCheck, setRunningCheck] = useState(null);
    
    // Test alerts state
    const [testAlertDomain, setTestAlertDomain] = useState('');
    const [testAlertIssueType, setTestAlertIssueType] = useState('DOWN');
    const [testAlertReason, setTestAlertReason] = useState('Timeout');
    const [testAlertSeverity, setTestAlertSeverity] = useState('');
    const [sendingTestAlert, setSendingTestAlert] = useState(false);
    const [testAlertHistory, setTestAlertHistory] = useState([]);
    
    // Forced monitoring state
    const [unmonitoredDomains, setUnmonitoredDomains] = useState([]);
    const [seoMonitoringSummary, setSeoMonitoringSummary] = useState(null);
    const [domainSuggestions, setDomainSuggestions] = useState([]);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const headers = { 'Authorization': `Bearer ${token}` };

            // Load settings, stats, expiring and down domains in parallel
            const [settingsRes, statsRes, expiringRes, downRes] = await Promise.all([
                fetch(`${API_URL}/api/v3/monitoring/settings`, { headers }),
                fetch(`${API_URL}/api/v3/monitoring/stats`, { headers }),
                fetch(`${API_URL}/api/v3/monitoring/expiring-domains?days=30`, { headers }),
                fetch(`${API_URL}/api/v3/monitoring/down-domains`, { headers })
            ]);

            if (settingsRes.ok) {
                const data = await settingsRes.json();
                setSettings(data);
            }

            if (statsRes.ok) {
                const data = await statsRes.json();
                setStats(data);
            }

            if (expiringRes.ok) {
                const data = await expiringRes.json();
                setExpiringDomains(data.domains || []);
            }

            if (downRes.ok) {
                const data = await downRes.json();
                setDownDomains(data.domains || []);
            }
            
            // Load forced monitoring data
            try {
                const [unmonitoredRes, summaryRes, historyRes] = await Promise.all([
                    forcedMonitoringAPI.getUnmonitoredInSeo(),
                    forcedMonitoringAPI.getSeoDomainsMonitoringSummary(),
                    forcedMonitoringAPI.getTestAlertHistory(20)
                ]);
                
                setUnmonitoredDomains(unmonitoredRes.data.unmonitored_domains || []);
                setSeoMonitoringSummary(summaryRes.data);
                setTestAlertHistory(historyRes.data.history || []);
            } catch (e) {
                console.error('Failed to load forced monitoring data:', e);
            }
        } catch (error) {
            toast({ title: 'Error', description: 'Failed to load monitoring data', variant: 'destructive' });
        } finally {
            setLoading(false);
        }
    };

    const saveSettings = async () => {
        setSaving(true);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const response = await fetch(`${API_URL}/api/v3/monitoring/settings`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(settings)
            });

            if (response.ok) {
                toast({ title: 'Success', description: 'Monitoring settings saved' });
            } else {
                const error = await response.json();
                toast({ title: 'Error', description: error.detail || 'Failed to save settings', variant: 'destructive' });
            }
        } catch (error) {
            toast({ title: 'Error', description: 'Failed to save settings', variant: 'destructive' });
        } finally {
            setSaving(false);
        }
    };

    const runManualCheck = async (type) => {
        setRunningCheck(type);
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const endpoint = type === 'expiration' 
                ? `${API_URL}/api/v3/monitoring/check-expiration`
                : `${API_URL}/api/v3/monitoring/check-availability`;

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                toast({ 
                    title: 'Check Started', 
                    description: `${type === 'expiration' ? 'Expiration' : 'Availability'} check is running in background`
                });
                // Refresh stats after a delay
                setTimeout(loadData, 3000);
            } else {
                const error = await response.json();
                toast({ title: 'Error', description: error.detail || 'Failed to start check', variant: 'destructive' });
            }
        } catch (error) {
            toast({ title: 'Error', description: 'Failed to start check', variant: 'destructive' });
        } finally {
            setRunningCheck(null);
        }
    };

    const sendTestAlert = async () => {
        if (!testAlertDomain.trim()) {
            toast({ title: 'Error', description: 'Please enter a domain name', variant: 'destructive' });
            return;
        }
        
        setSendingTestAlert(true);
        try {
            const response = await forcedMonitoringAPI.sendTestDomainDownAlert({
                domain: testAlertDomain.trim(),
                issue_type: testAlertIssueType,
                reason: testAlertReason,
                force_severity: testAlertSeverity || null
            });
            
            if (response.data.success) {
                toast({ 
                    title: 'Test Alert Sent', 
                    description: `Test ${testAlertIssueType} alert sent for ${testAlertDomain}`
                });
                // Refresh history
                const historyRes = await forcedMonitoringAPI.getTestAlertHistory(20);
                setTestAlertHistory(historyRes.data.history || []);
            } else {
                toast({ title: 'Warning', description: 'Test alert may not have been sent - check Telegram', variant: 'destructive' });
            }
        } catch (error) {
            toast({ 
                title: 'Error', 
                description: error.response?.data?.detail || 'Failed to send test alert', 
                variant: 'destructive' 
            });
        } finally {
            setSendingTestAlert(false);
        }
    };

    const loadDomainSuggestions = async (search) => {
        if (search.length < 2) {
            setDomainSuggestions([]);
            return;
        }
        
        try {
            const response = await domainsAPI.getAll({ search, limit: 10 });
            setDomainSuggestions(response.data.map(d => d.domain_name));
        } catch (e) {
            console.error('Failed to load domain suggestions:', e);
        }
    };

    const updateSetting = (category, key, value) => {
        setSettings(prev => ({
            ...prev,
            [category]: {
                ...prev[category],
                [key]: value
            }
        }));
    };

    if (loading) {
        return (
            <Layout>
                <div className="flex items-center justify-center h-64">
                    <Loader2 className="h-8 w-8 animate-spin text-zinc-500" />
                </div>
            </Layout>
        );
    }

    return (
        <Layout>
            <div className="space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                            <Activity className="h-6 w-6 text-emerald-500" />
                            Monitoring Settings
                        </h1>
                        <p className="text-zinc-400 mt-1">Configure domain monitoring and alerts</p>
                    </div>
                    <div className="flex gap-2">
                        <Button 
                            variant="outline" 
                            onClick={loadData}
                            data-testid="refresh-monitoring"
                        >
                            <RefreshCw className="h-4 w-4 mr-2" />
                            Refresh
                        </Button>
                        <Button 
                            onClick={saveSettings} 
                            disabled={saving}
                            data-testid="save-monitoring-settings"
                        >
                            {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Settings className="h-4 w-4 mr-2" />}
                            Save Settings
                        </Button>
                    </div>
                </div>

                {/* Stats Cards */}
                {stats && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {/* Availability Stats */}
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-zinc-400">Availability</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex items-center justify-between">
                                    <div className="space-y-1">
                                        <div className="flex items-center gap-2">
                                            <CheckCircle className="h-4 w-4 text-emerald-500" />
                                            <span className="text-white">{stats.availability?.up || 0} up</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <XCircle className="h-4 w-4 text-red-500" />
                                            <span className="text-white">{stats.availability?.down || 0} down</span>
                                        </div>
                                    </div>
                                    <div className="text-3xl font-bold text-white">
                                        {stats.availability?.total_monitored || 0}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Expiration Stats */}
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-zinc-400">Expiring Soon</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex items-center justify-between">
                                    <div className="space-y-1">
                                        <div className="flex items-center gap-2">
                                            <AlertTriangle className="h-4 w-4 text-yellow-500" />
                                            <span className="text-white">{stats.expiration?.expiring_7_days || 0} in 7 days</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Calendar className="h-4 w-4 text-orange-500" />
                                            <span className="text-white">{stats.expiration?.expiring_30_days || 0} in 30 days</span>
                                        </div>
                                    </div>
                                    <div className="text-3xl font-bold text-red-500">
                                        {stats.expiration?.expired || 0}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Alerts Stats */}
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-zinc-400">Active Alerts</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <span className="text-zinc-400">Monitoring</span>
                                        <Badge variant={stats.alerts?.monitoring_unacknowledged > 0 ? 'destructive' : 'secondary'}>
                                            {stats.alerts?.monitoring_unacknowledged || 0}
                                        </Badge>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-zinc-400">Expiration</span>
                                        <Badge variant={stats.alerts?.expiration_unacknowledged > 0 ? 'destructive' : 'secondary'}>
                                            {stats.alerts?.expiration_unacknowledged || 0}
                                        </Badge>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Manual Check Actions */}
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-zinc-400">Manual Check</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-2">
                                    <Button 
                                        variant="outline" 
                                        size="sm" 
                                        className="w-full"
                                        onClick={() => runManualCheck('expiration')}
                                        disabled={runningCheck !== null}
                                        data-testid="run-expiration-check"
                                    >
                                        {runningCheck === 'expiration' ? (
                                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                        ) : (
                                            <Calendar className="h-4 w-4 mr-2" />
                                        )}
                                        Check Expirations
                                    </Button>
                                    <Button 
                                        variant="outline" 
                                        size="sm" 
                                        className="w-full"
                                        onClick={() => runManualCheck('availability')}
                                        disabled={runningCheck !== null}
                                        data-testid="run-availability-check"
                                    >
                                        {runningCheck === 'availability' ? (
                                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                        ) : (
                                            <Globe className="h-4 w-4 mr-2" />
                                        )}
                                        Check Availability
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                )}

                {/* Settings Tabs */}
                <Tabs defaultValue="expiration" className="space-y-4">
                    <TabsList className="bg-zinc-900">
                        <TabsTrigger value="expiration" data-testid="expiration-tab">
                            <Calendar className="h-4 w-4 mr-2" />
                            Expiration Monitoring
                        </TabsTrigger>
                        <TabsTrigger value="availability" data-testid="availability-tab">
                            <Globe className="h-4 w-4 mr-2" />
                            Availability Monitoring
                        </TabsTrigger>
                        <TabsTrigger value="expiring-list" data-testid="expiring-list-tab">
                            <AlertTriangle className="h-4 w-4 mr-2" />
                            Expiring Domains ({expiringDomains.length})
                        </TabsTrigger>
                        <TabsTrigger value="down-list" data-testid="down-list-tab">
                            <XCircle className="h-4 w-4 mr-2" />
                            Down Domains ({downDomains.length})
                        </TabsTrigger>
                        <TabsTrigger value="test-alerts" data-testid="test-alerts-tab">
                            <FlaskConical className="h-4 w-4 mr-2" />
                            Test Alerts
                        </TabsTrigger>
                        <TabsTrigger value="forced-monitoring" data-testid="forced-monitoring-tab">
                            <Shield className="h-4 w-4 mr-2 text-amber-500" />
                            SEO Monitoring
                            {unmonitoredDomains.length > 0 && (
                                <Badge className="ml-2 bg-amber-500 text-black">{unmonitoredDomains.length}</Badge>
                            )}
                        </TabsTrigger>
                    </TabsList>

                    {/* Expiration Settings */}
                    <TabsContent value="expiration">
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardHeader>
                                <CardTitle>Expiration Monitoring Settings</CardTitle>
                                <CardDescription>Configure how domain expiration alerts are sent</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <Label>Enable Expiration Monitoring</Label>
                                        <p className="text-sm text-zinc-500">Send alerts when domains are about to expire</p>
                                    </div>
                                    <Switch
                                        checked={settings?.expiration?.enabled ?? true}
                                        onCheckedChange={(checked) => updateSetting('expiration', 'enabled', checked)}
                                        data-testid="expiration-enabled-toggle"
                                    />
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>Alert Window (days)</Label>
                                        <p className="text-sm text-zinc-500">Alert when expiration is within this many days</p>
                                        <Select
                                            value={String(settings?.expiration?.alert_window_days ?? 7)}
                                            onValueChange={(val) => updateSetting('expiration', 'alert_window_days', parseInt(val))}
                                        >
                                            <SelectTrigger data-testid="alert-window-select">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="7">7 days</SelectItem>
                                                <SelectItem value="14">14 days</SelectItem>
                                                <SelectItem value="30">30 days</SelectItem>
                                                <SelectItem value="60">60 days</SelectItem>
                                                <SelectItem value="90">90 days</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <Label>Include Auto-Renew Domains</Label>
                                        <p className="text-sm text-zinc-500">Also alert for domains with auto-renew enabled</p>
                                        <div className="pt-2">
                                            <Switch
                                                checked={settings?.expiration?.include_auto_renew ?? false}
                                                onCheckedChange={(checked) => updateSetting('expiration', 'include_auto_renew', checked)}
                                                data-testid="include-auto-renew-toggle"
                                            />
                                        </div>
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <Label>Alert Thresholds (days)</Label>
                                    <p className="text-sm text-zinc-500">Send alerts at these specific day markers</p>
                                    <div className="flex flex-wrap gap-2 pt-2">
                                        {[30, 14, 7, 3, 1, 0].map((day) => (
                                            <Badge 
                                                key={day}
                                                variant={settings?.expiration?.alert_thresholds?.includes(day) ? 'default' : 'outline'}
                                                className="cursor-pointer"
                                                onClick={() => {
                                                    const current = settings?.expiration?.alert_thresholds || [30, 14, 7, 3, 1, 0];
                                                    const newThresholds = current.includes(day) 
                                                        ? current.filter(d => d !== day)
                                                        : [...current, day].sort((a, b) => b - a);
                                                    updateSetting('expiration', 'alert_thresholds', newThresholds);
                                                }}
                                            >
                                                {day === 0 ? 'Expired' : `${day} days`}
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Availability Settings */}
                    <TabsContent value="availability">
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardHeader>
                                <CardTitle>Availability Monitoring Settings</CardTitle>
                                <CardDescription>Configure ping/HTTP health check alerts</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <Label>Enable Availability Monitoring</Label>
                                        <p className="text-sm text-zinc-500">Check domain health and send alerts on status changes</p>
                                    </div>
                                    <Switch
                                        checked={settings?.availability?.enabled ?? true}
                                        onCheckedChange={(checked) => updateSetting('availability', 'enabled', checked)}
                                        data-testid="availability-enabled-toggle"
                                    />
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>Default Check Interval</Label>
                                        <p className="text-sm text-zinc-500">How often to check domains (global default)</p>
                                        <Select
                                            value={String(settings?.availability?.default_interval_seconds ?? 300)}
                                            onValueChange={(val) => updateSetting('availability', 'default_interval_seconds', parseInt(val))}
                                        >
                                            <SelectTrigger data-testid="interval-select">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="60">1 minute</SelectItem>
                                                <SelectItem value="300">5 minutes</SelectItem>
                                                <SelectItem value="900">15 minutes</SelectItem>
                                                <SelectItem value="3600">1 hour</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <Label>Connection Timeout</Label>
                                        <p className="text-sm text-zinc-500">Seconds to wait before marking as down</p>
                                        <Select
                                            value={String(settings?.availability?.timeout_seconds ?? 15)}
                                            onValueChange={(val) => updateSetting('availability', 'timeout_seconds', parseInt(val))}
                                        >
                                            <SelectTrigger data-testid="timeout-select">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="5">5 seconds</SelectItem>
                                                <SelectItem value="10">10 seconds</SelectItem>
                                                <SelectItem value="15">15 seconds</SelectItem>
                                                <SelectItem value="30">30 seconds</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="flex items-center justify-between p-4 bg-zinc-800 rounded-lg">
                                        <div>
                                            <Label>Alert on DOWN</Label>
                                            <p className="text-sm text-zinc-500">Send alert when UP → DOWN</p>
                                        </div>
                                        <Switch
                                            checked={settings?.availability?.alert_on_down ?? true}
                                            onCheckedChange={(checked) => updateSetting('availability', 'alert_on_down', checked)}
                                            data-testid="alert-on-down-toggle"
                                        />
                                    </div>

                                    <div className="flex items-center justify-between p-4 bg-zinc-800 rounded-lg">
                                        <div>
                                            <Label>Alert on Recovery</Label>
                                            <p className="text-sm text-zinc-500">Send alert when DOWN → UP</p>
                                        </div>
                                        <Switch
                                            checked={settings?.availability?.alert_on_recovery ?? false}
                                            onCheckedChange={(checked) => updateSetting('availability', 'alert_on_recovery', checked)}
                                            data-testid="alert-on-recovery-toggle"
                                        />
                                    </div>
                                </div>

                                <div className="flex items-center justify-between p-4 bg-zinc-800 rounded-lg">
                                    <div>
                                        <Label>Follow Redirects</Label>
                                        <p className="text-sm text-zinc-500">Follow HTTP redirects when checking</p>
                                    </div>
                                    <Switch
                                        checked={settings?.availability?.follow_redirects ?? true}
                                        onCheckedChange={(checked) => updateSetting('availability', 'follow_redirects', checked)}
                                        data-testid="follow-redirects-toggle"
                                    />
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Expiring Domains List */}
                    <TabsContent value="expiring-list">
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardHeader>
                                <CardTitle>Domains Expiring Soon</CardTitle>
                                <CardDescription>Domains expiring within the next 30 days</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {expiringDomains.length === 0 ? (
                                    <div className="text-center py-8 text-zinc-500">
                                        <CheckCircle className="h-12 w-12 mx-auto mb-4 text-emerald-500" />
                                        <p>No domains expiring soon</p>
                                    </div>
                                ) : (
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Domain</TableHead>
                                                <TableHead>Brand</TableHead>
                                                <TableHead>Expiration</TableHead>
                                                <TableHead>Days Left</TableHead>
                                                <TableHead>Auto-Renew</TableHead>
                                                <TableHead>Status</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {expiringDomains.map((domain) => (
                                                <TableRow key={domain.id}>
                                                    <TableCell>
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-mono text-sm">{domain.domain_name}</span>
                                                            <a 
                                                                href={`https://${domain.domain_name}`}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="text-zinc-500 hover:text-blue-500"
                                                            >
                                                                <ExternalLink className="h-3 w-3" />
                                                            </a>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="text-zinc-400">{domain.brand_name || '-'}</TableCell>
                                                    <TableCell className="text-zinc-400">{domain.expiration_date}</TableCell>
                                                    <TableCell>
                                                        <span className={`font-mono ${
                                                            domain.days_remaining <= 0 ? 'text-red-500' :
                                                            domain.days_remaining <= 3 ? 'text-orange-500' :
                                                            domain.days_remaining <= 7 ? 'text-yellow-500' :
                                                            'text-zinc-300'
                                                        }`}>
                                                            {domain.days_remaining < 0 ? 'EXPIRED' : domain.days_remaining}
                                                        </span>
                                                    </TableCell>
                                                    <TableCell>
                                                        {domain.auto_renew ? (
                                                            <Badge variant="secondary" className="bg-emerald-500/20 text-emerald-400">Yes</Badge>
                                                        ) : (
                                                            <Badge variant="outline" className="text-zinc-500">No</Badge>
                                                        )}
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge variant={
                                                            domain.status === 'expired' ? 'destructive' :
                                                            domain.status === 'critical' ? 'destructive' :
                                                            domain.status === 'warning' ? 'secondary' : 'outline'
                                                        }>
                                                            {domain.status}
                                                        </Badge>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Down Domains List */}
                    <TabsContent value="down-list">
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardHeader>
                                <CardTitle>Down Domains</CardTitle>
                                <CardDescription>Domains currently unreachable</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {downDomains.length === 0 ? (
                                    <div className="text-center py-8 text-zinc-500">
                                        <CheckCircle className="h-12 w-12 mx-auto mb-4 text-emerald-500" />
                                        <p>All monitored domains are up</p>
                                    </div>
                                ) : (
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Domain</TableHead>
                                                <TableHead>Brand</TableHead>
                                                <TableHead>HTTP Code</TableHead>
                                                <TableHead>Last Check</TableHead>
                                                <TableHead>Network</TableHead>
                                                <TableHead>Role</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {downDomains.map((domain) => (
                                                <TableRow key={domain.id}>
                                                    <TableCell>
                                                        <div className="flex items-center gap-2">
                                                            <XCircle className="h-4 w-4 text-red-500" />
                                                            <span className="font-mono text-sm">{domain.domain_name}</span>
                                                            <a 
                                                                href={`https://${domain.domain_name}`}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="text-zinc-500 hover:text-blue-500"
                                                            >
                                                                <ExternalLink className="h-3 w-3" />
                                                            </a>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="text-zinc-400">{domain.brand_name || '-'}</TableCell>
                                                    <TableCell>
                                                        <Badge variant="destructive">
                                                            {domain.last_http_code || 'Error'}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell className="text-zinc-400 text-sm">
                                                        {domain.last_checked_at ? new Date(domain.last_checked_at).toLocaleString() : '-'}
                                                    </TableCell>
                                                    <TableCell className="text-zinc-400">{domain.network_name || '-'}</TableCell>
                                                    <TableCell>
                                                        {domain.domain_role && (
                                                            <Badge variant={domain.domain_role === 'main' ? 'default' : 'outline'}>
                                                                {domain.domain_role}
                                                            </Badge>
                                                        )}
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            </div>
        </Layout>
    );
}
