import { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { reportsAPI, seedAPI, brandsAPI, monitoringAPI, alertsAPI, dashboardSettingsAPI, v3ReportsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { 
    Globe, 
    Network, 
    Tag, 
    TrendingUp, 
    CheckCircle,
    ArrowRight,
    Loader2,
    Database,
    Activity,
    Bell,
    AlertCircle,
    Clock,
    Zap,
    XCircle,
    RefreshCw,
    Settings,
    Building2,
    BarChart3
} from 'lucide-react';
import { 
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
    Tooltip
} from 'recharts';
import { SEVERITY_LABELS, getSeverityBadgeClass, formatDateTime } from '../lib/utils';

const MONITORING_COLORS = ['#22C55E', '#EF4444', '#6B7280'];

const REFRESH_OPTIONS = [
    { value: 0, label: 'Manual' },
    { value: 30, label: '30s' },
    { value: 60, label: '1m' },
    { value: 300, label: '5m' },
    { value: 900, label: '15m' }
];

export default function DashboardPage() {
    const { user, isSuperAdmin } = useAuth();
    const [stats, setStats] = useState(null);
    const [brands, setBrands] = useState([]);
    const [brandDomainCounts, setBrandDomainCounts] = useState([]);
    const [selectedBrand, setSelectedBrand] = useState('all');
    const [loading, setLoading] = useState(true);
    const [seeding, setSeeding] = useState(false);
    const [monitoringStats, setMonitoringStats] = useState(null);
    const [recentAlerts, setRecentAlerts] = useState([]);
    
    // Auto-refresh state
    const [refreshInterval, setRefreshInterval] = useState(0);
    const [lastRefresh, setLastRefresh] = useState(null);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const refreshTimerRef = useRef(null);

    // Load refresh interval setting
    useEffect(() => {
        const loadRefreshSetting = async () => {
            try {
                const { data } = await dashboardSettingsAPI.getRefreshInterval();
                setRefreshInterval(data.refresh_interval || 0);
            } catch (err) {
                // Use localStorage fallback
                const saved = localStorage.getItem('dashboard_refresh_interval');
                if (saved) setRefreshInterval(parseInt(saved, 10));
            }
        };
        loadRefreshSetting();
    }, []);

    // Lightweight stats refresh (no heavy re-renders)
    const refreshStatsOnly = useCallback(async () => {
        if (isRefreshing) return;
        setIsRefreshing(true);
        try {
            const { data } = await dashboardSettingsAPI.getStats();
            setStats(prev => ({
                ...prev,
                total_domains: data.total_domains,
                total_networks: data.total_networks,
                monitored: data.monitored_count,
                indexed: data.indexed_count,
                noindex: data.noindex_count,
                ping_up: data.ping_up,
                ping_down: data.ping_down,
                critical_alerts: data.critical_alerts,
                critical_alert_details: data.critical_alert_details,
                active_alerts: data.active_alerts
            }));
            setLastRefresh(new Date());
        } catch (err) {
            console.error('Stats refresh failed:', err);
        } finally {
            setIsRefreshing(false);
        }
    }, [isRefreshing]);

    // Setup auto-refresh timer
    useEffect(() => {
        if (refreshTimerRef.current) {
            clearInterval(refreshTimerRef.current);
            refreshTimerRef.current = null;
        }
        
        if (refreshInterval > 0) {
            refreshTimerRef.current = setInterval(refreshStatsOnly, refreshInterval * 1000);
        }
        
        return () => {
            if (refreshTimerRef.current) {
                clearInterval(refreshTimerRef.current);
            }
        };
    }, [refreshInterval, refreshStatsOnly]);

    // Handle refresh interval change
    const handleRefreshIntervalChange = async (value) => {
        const interval = parseInt(value, 10);
        setRefreshInterval(interval);
        localStorage.setItem('dashboard_refresh_interval', interval.toString());
        
        try {
            await dashboardSettingsAPI.setRefreshInterval(interval);
        } catch (err) {
            console.error('Failed to save refresh setting:', err);
        }
    };

    useEffect(() => {
        loadData();
    }, [selectedBrand]);

    const loadData = async () => {
        try {
            const brandId = selectedBrand === 'all' ? undefined : selectedBrand;
            
            const [statsRes, brandsRes, monitorRes, alertsRes, brandDomainsRes] = await Promise.all([
                reportsAPI.getDashboardStats(),
                brandsAPI.getAll(),
                monitoringAPI.getStats(),
                alertsAPI.getAll({ acknowledged: false, limit: 5 }),
                v3ReportsAPI.getDomainsByBrand()
            ]);

            setStats(statsRes.data);
            setBrands(brandsRes.data);
            setMonitoringStats(monitorRes.data);
            setRecentAlerts(alertsRes.data);
            setBrandDomainCounts(brandDomainsRes.data.data || []);
        } catch (err) {
            console.error('Failed to load dashboard data:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleSeedData = async () => {
        setSeeding(true);
        try {
            await seedAPI.seedData();
            toast.success('Demo data seeded successfully!');
            loadData();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to seed data');
        } finally {
            setSeeding(false);
        }
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

    const monitoringPieData = monitoringStats ? [
        { name: 'Up', value: monitoringStats.up_count, fill: MONITORING_COLORS[0] },
        { name: 'Down', value: monitoringStats.down_count, fill: MONITORING_COLORS[1] },
        { name: 'Unknown', value: monitoringStats.unknown_count, fill: MONITORING_COLORS[2] }
    ].filter(d => d.value > 0) : [];

    return (
        <Layout>
            <div data-testid="dashboard-page">
                {/* Header */}
                <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="page-title flex items-center gap-2">
                            <Zap className="h-7 w-7 text-blue-500" />
                            SEO-NOC Dashboard
                        </h1>
                        <p className="page-subtitle">
                            Welcome back, {user?.name}
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        {/* Auto-refresh controls */}
                        <div className="flex items-center gap-2 bg-card border border-border rounded-lg px-3 py-1.5">
                            <RefreshCw 
                                className={`h-4 w-4 text-zinc-400 ${isRefreshing ? 'animate-spin' : ''}`}
                            />
                            <Select 
                                value={refreshInterval.toString()} 
                                onValueChange={handleRefreshIntervalChange}
                            >
                                <SelectTrigger className="w-[80px] border-0 bg-transparent h-7 px-1" data-testid="refresh-interval">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {REFRESH_OPTIONS.map(opt => (
                                        <SelectItem key={opt.value} value={opt.value.toString()}>
                                            {opt.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={refreshStatsOnly}
                                disabled={isRefreshing}
                                data-testid="manual-refresh"
                            >
                                <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
                            </Button>
                        </div>
                        
                        <Select value={selectedBrand} onValueChange={setSelectedBrand}>
                            <SelectTrigger className="w-[180px] bg-card border-border" data-testid="brand-filter">
                                <SelectValue placeholder="All Brands" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Brands</SelectItem>
                                {brands.map(brand => (
                                    <SelectItem key={brand.id} value={brand.id}>
                                        {brand.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {isSuperAdmin() && stats?.total_domains === 0 && (
                            <Button 
                                onClick={handleSeedData}
                                disabled={seeding}
                                className="bg-blue-600 hover:bg-blue-700"
                                data-testid="seed-data-btn"
                            >
                                {seeding ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Database className="h-4 w-4 mr-2" />}
                                Seed Demo Data
                            </Button>
                        )}
                    </div>
                </div>

                {/* Critical Alerts Banner */}
                {stats?.critical_alerts > 0 && (
                    <div className="mb-6 p-3 bg-red-950/30 border border-red-900/50 rounded-lg">
                        <div className="flex items-center justify-between gap-4">
                            <div className="flex items-center gap-3 min-w-0 flex-1">
                                <AlertCircle className="h-5 w-5 text-red-500 animate-pulse flex-shrink-0" />
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <p className="font-semibold text-red-400 text-sm">
                                            {stats.critical_alerts} Critical Alert{stats.critical_alerts > 1 ? 's' : ''}
                                        </p>
                                        {stats.critical_alert_details && stats.critical_alert_details.length > 0 && (
                                            <div className="flex items-center gap-1 flex-wrap">
                                                <span className="text-red-400/50 text-xs">|</span>
                                                {stats.critical_alert_details.slice(0, 3).map((alert, idx) => (
                                                    <code key={idx} className="bg-red-950/50 px-1.5 py-0.5 rounded text-xs text-red-300 truncate max-w-[120px]">
                                                        {alert.domain_name}
                                                    </code>
                                                ))}
                                                {stats.critical_alerts > 3 && (
                                                    <span className="text-xs text-red-400/60">
                                                        +{stats.critical_alerts - 3} more
                                                    </span>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                            <Link to="/settings/monitoring" className="flex-shrink-0">
                                <Button size="sm" className="bg-red-600 hover:bg-red-700 text-xs px-3">
                                    View Alerts
                                </Button>
                            </Link>
                        </div>
                    </div>
                )}

                {/* Stats Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6" data-testid="stats-grid">
                    <div className="stat-card card-hover">
                        <div className="flex items-center gap-2 mb-2">
                            <Globe className="h-4 w-4 text-blue-500" />
                            <span className="stat-label mb-0 text-xs">Domains</span>
                        </div>
                        <div className="stat-value text-2xl" data-testid="total-domains">{stats?.total_domains || 0}</div>
                    </div>

                    <div className="stat-card card-hover">
                        <div className="flex items-center gap-2 mb-2">
                            <Network className="h-4 w-4 text-purple-500" />
                            <span className="stat-label mb-0 text-xs">Networks</span>
                        </div>
                        <div className="stat-value text-2xl" data-testid="total-groups">{stats?.total_groups || 0}</div>
                    </div>

                    <div className="stat-card card-hover">
                        <div className="flex items-center gap-2 mb-2">
                            <Activity className="h-4 w-4 text-emerald-500" />
                            <span className="stat-label mb-0 text-xs">Monitored</span>
                        </div>
                        <div className="stat-value text-2xl text-emerald-500">{stats?.monitored_count || 0}</div>
                        <div className="text-xs text-zinc-500 mt-1">
                            <span className="text-emerald-400">{stats?.up_count || 0}</span> up / 
                            <span className="text-red-400 ml-1">{stats?.down_count || 0}</span> down
                        </div>
                    </div>

                    <div className="stat-card card-hover">
                        <div className="flex items-center gap-2 mb-2">
                            <TrendingUp className="h-4 w-4 text-emerald-500" />
                            <span className="stat-label mb-0 text-xs">Index Rate</span>
                        </div>
                        <div className="stat-value text-2xl">{stats?.index_rate || 0}%</div>
                    </div>

                    <div className={`stat-card card-hover ${stats?.active_alerts > 0 ? 'border-amber-900/50' : ''}`}>
                        <div className="flex items-center gap-2 mb-2">
                            <Bell className={`h-4 w-4 ${stats?.active_alerts > 0 ? 'text-amber-500' : 'text-zinc-500'}`} />
                            <span className="stat-label mb-0 text-xs">Active Alerts</span>
                        </div>
                        <div className={`stat-value text-2xl ${stats?.active_alerts > 0 ? 'text-amber-500' : ''}`}>
                            {stats?.active_alerts || 0}
                        </div>
                    </div>

                    <div className="stat-card card-hover">
                        <div className="flex items-center gap-2 mb-2">
                            <Building2 className="h-4 w-4 text-cyan-500" />
                            <span className="stat-label mb-0 text-xs">Brands</span>
                        </div>
                        <div className="stat-value text-2xl text-cyan-500">
                            {brandDomainCounts.length || 0}
                        </div>
                    </div>
                </div>

                {/* Charts Row - Domains by Brand & Monitoring */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                    {/* Domains by Brand - Simple list */}
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-2">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <Building2 className="h-4 w-4 text-blue-500" />
                                    Domains by Brand
                                </CardTitle>
                                <span className="text-xs text-zinc-500">{brandDomainCounts.length} brands</span>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {brandDomainCounts.length > 0 ? (
                                <div className="space-y-2">
                                    <div className="max-h-[160px] overflow-y-auto space-y-1 pr-1">
                                        {brandDomainCounts.map((brand, idx) => (
                                            <div key={brand.brand_id} className="flex items-center justify-between py-1 px-2 rounded hover:bg-zinc-800/50">
                                                <span className="text-sm truncate" title={brand.brand_name}>
                                                    {brand.brand_name}
                                                </span>
                                                <span className="text-sm font-mono text-zinc-400 ml-2">
                                                    {brand.domain_count}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="pt-2 border-t border-zinc-800 flex justify-between text-sm">
                                        <span className="text-zinc-500">Total</span>
                                        <span className="font-semibold">{brandDomainCounts.reduce((sum, b) => sum + b.domain_count, 0)} domains</span>
                                    </div>
                                </div>
                            ) : (
                                <div className="h-[160px] flex items-center justify-center text-zinc-500 text-sm">
                                    No brand data available
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Monitoring Status */}
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base flex items-center gap-2">
                                <Activity className="h-4 w-4 text-emerald-500" />
                                Monitoring Status
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {monitoringPieData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={200}>
                                    <PieChart>
                                        <Pie
                                            data={monitoringPieData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={50}
                                            outerRadius={75}
                                            paddingAngle={3}
                                            dataKey="value"
                                            label={({ name, value }) => `${name}: ${value}`}
                                            labelLine={{ stroke: '#52525B' }}
                                        >
                                            {monitoringPieData.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={entry.fill} />
                                            ))}
                                        </Pie>
                                        <Tooltip contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #27272A', borderRadius: '6px' }} />
                                    </PieChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-[200px] flex items-center justify-center text-zinc-500 text-sm">
                                    No monitored domains
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Recent Alerts */}
                <div className="grid grid-cols-1 gap-6 mb-6">
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-2">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <Bell className="h-4 w-4 text-amber-500" />
                                    Recent Alerts
                                </CardTitle>
                                <Link to="/alerts">
                                    <Button variant="ghost" size="sm" className="text-xs">
                                        View All <ArrowRight className="h-3 w-3 ml-1" />
                                    </Button>
                                </Link>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {recentAlerts.length > 0 ? (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                    {recentAlerts.slice(0, 6).map(alert => (
                                        <div key={alert.id} className="p-3 bg-black/50 rounded-lg border border-border">
                                            <div className="flex items-start justify-between gap-2">
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 mb-1">
                                                        <Badge variant="outline" className={`text-[10px] ${getSeverityBadgeClass(alert.severity)}`}>
                                                            {SEVERITY_LABELS[alert.severity]}
                                                        </Badge>
                                                        <span className="text-xs text-zinc-500">{alert.alert_type}</span>
                                                    </div>
                                                    <p className="font-mono text-sm truncate">{alert.domain_name}</p>
                                                    <p className="text-xs text-zinc-500 mt-1">{alert.title}</p>
                                                </div>
                                                <span className="text-[10px] text-zinc-600 whitespace-nowrap">
                                                    {formatDateTime(alert.created_at)}
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center py-8">
                                    <CheckCircle className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
                                    <p className="text-sm text-zinc-400">No active alerts</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Quick Actions */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <Link to="/domains" data-testid="quick-link-domains">
                        <Card className="bg-card border-border hover:border-blue-500/50 cursor-pointer transition-colors">
                            <CardContent className="p-4 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <Globe className="h-5 w-5 text-blue-500" />
                                    <span className="font-medium">Asset Domains</span>
                                </div>
                                <ArrowRight className="h-4 w-4 text-zinc-500" />
                            </CardContent>
                        </Card>
                    </Link>

                    <Link to="/groups" data-testid="quick-link-groups">
                        <Card className="bg-card border-border hover:border-purple-500/50 cursor-pointer transition-colors">
                            <CardContent className="p-4 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <Network className="h-5 w-5 text-purple-500" />
                                    <span className="font-medium">SEO Networks</span>
                                </div>
                                <ArrowRight className="h-4 w-4 text-zinc-500" />
                            </CardContent>
                        </Card>
                    </Link>

                    <Link to="/alerts" data-testid="quick-link-alerts">
                        <Card className="bg-card border-border hover:border-amber-500/50 cursor-pointer transition-colors">
                            <CardContent className="p-4 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <Bell className="h-5 w-5 text-amber-500" />
                                    <span className="font-medium">Alert Center</span>
                                </div>
                                <ArrowRight className="h-4 w-4 text-zinc-500" />
                            </CardContent>
                        </Card>
                    </Link>

                    <Link to="/reports" data-testid="quick-link-reports">
                        <Card className="bg-card border-border hover:border-emerald-500/50 cursor-pointer transition-colors">
                            <CardContent className="p-4 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <BarChart3 className="h-5 w-5 text-emerald-500" />
                                    <span className="font-medium">Reports</span>
                                </div>
                                <ArrowRight className="h-4 w-4 text-zinc-500" />
                            </CardContent>
                        </Card>
                    </Link>
                </div>
            </div>
        </Layout>
    );
}
