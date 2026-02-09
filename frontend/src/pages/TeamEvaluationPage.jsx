import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { teamEvaluationAPI, brandsAPI, networksAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Progress } from '../components/ui/progress';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { 
    Users,
    Trophy,
    AlertTriangle,
    TrendingUp,
    TrendingDown,
    CheckCircle,
    XCircle,
    Clock,
    Target,
    Star,
    Activity,
    BarChart3,
    Calendar,
    RefreshCw,
    User,
    Download
} from 'lucide-react';
import { 
    BarChart, 
    Bar, 
    XAxis, 
    YAxis, 
    CartesianGrid, 
    Tooltip, 
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
    Legend
} from 'recharts';

const SCORE_COLORS = {
    excellent: '#22C55E',  // 4.5-5.0
    good: '#84CC16',       // 3.5-4.4
    average: '#F59E0B',    // 2.5-3.4
    poor: '#EF4444'        // 0-2.4
};

const IMPACT_COLORS = {
    positive: '#22C55E',
    neutral: '#6B7280',
    no_impact: '#F59E0B',
    negative: '#EF4444'
};

const STATUS_COLORS = {
    planned: '#F59E0B',
    in_progress: '#3B82F6',
    completed: '#22C55E',
    reverted: '#EF4444'
};

function getScoreColor(score) {
    if (score >= 4.5) return SCORE_COLORS.excellent;
    if (score >= 3.5) return SCORE_COLORS.good;
    if (score >= 2.5) return SCORE_COLORS.average;
    return SCORE_COLORS.poor;
}

function getScoreLabel(score) {
    if (score >= 4.5) return 'Excellent';
    if (score >= 3.5) return 'Good';
    if (score >= 2.5) return 'Average';
    return 'Needs Improvement';
}

export default function TeamEvaluationPage() {
    const { user } = useAuth();
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [summary, setSummary] = useState(null);
    const [brands, setBrands] = useState([]);
    const [networks, setNetworks] = useState([]);
    
    // Filters
    const [selectedBrand, setSelectedBrand] = useState('all');
    const [selectedNetwork, setSelectedNetwork] = useState('all');
    const [dateRange, setDateRange] = useState('30'); // days

    useEffect(() => {
        loadInitialData();
    }, []);

    useEffect(() => {
        loadSummary();
    }, [selectedBrand, selectedNetwork, dateRange]);

    const loadInitialData = async () => {
        try {
            const [brandsRes, networksRes] = await Promise.all([
                brandsAPI.getAll(),
                networksAPI.getAll()
            ]);
            setBrands(brandsRes.data);
            setNetworks(networksRes.data);
        } catch (err) {
            console.error('Failed to load initial data:', err);
        }
    };

    const loadSummary = async () => {
        setLoading(true);
        try {
            const params = {};
            if (selectedBrand !== 'all') params.brand_id = selectedBrand;
            if (selectedNetwork !== 'all') params.network_id = selectedNetwork;
            
            // Calculate date range
            const endDate = new Date().toISOString();
            const startDate = new Date(Date.now() - parseInt(dateRange) * 24 * 60 * 60 * 1000).toISOString();
            params.start_date = startDate;
            params.end_date = endDate;
            
            const response = await teamEvaluationAPI.getSummary(params);
            setSummary(response.data);
        } catch (err) {
            console.error('Failed to load team evaluation:', err);
            toast.error('Failed to load team evaluation data');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    const handleRefresh = () => {
        setRefreshing(true);
        loadSummary();
    };

    const [exporting, setExporting] = useState(false);
    
    const handleExportCSV = async () => {
        setExporting(true);
        try {
            const params = {};
            if (selectedBrand !== 'all') params.brand_id = selectedBrand;
            if (selectedNetwork !== 'all') params.network_id = selectedNetwork;
            
            // Calculate date range
            const endDate = new Date().toISOString();
            const startDate = new Date(Date.now() - parseInt(dateRange) * 24 * 60 * 60 * 1000).toISOString();
            params.start_date = startDate;
            params.end_date = endDate;
            
            const response = await teamEvaluationAPI.exportCSV(params);
            
            // Create download link
            const blob = new Blob([response.data], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            
            // Generate filename
            const startShort = startDate.slice(0, 10);
            const endShort = endDate.slice(0, 10);
            link.download = `seo_team_evaluation_${startShort}_to_${endShort}.csv`;
            
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
            
            toast.success('CSV exported successfully');
        } catch (err) {
            console.error('Failed to export CSV:', err);
            toast.error('Failed to export CSV');
        } finally {
            setExporting(false);
        }
    };

    // Prepare chart data
    const statusChartData = summary ? Object.entries(summary.by_status || {}).map(([status, count]) => ({
        name: status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' '),
        value: count,
        fill: STATUS_COLORS[status] || '#6B7280'
    })) : [];

    const impactChartData = summary ? Object.entries(summary.by_observed_impact || {}).map(([impact, count]) => ({
        name: impact.charAt(0).toUpperCase() + impact.slice(1).replace('_', ' '),
        value: count,
        fill: IMPACT_COLORS[impact] || '#6B7280'
    })).filter(d => d.value > 0) : [];

    const activityTypeData = summary ? Object.entries(summary.by_activity_type || {}).map(([type, count]) => ({
        name: type.charAt(0).toUpperCase() + type.slice(1).replace('_', ' '),
        count: count
    })).sort((a, b) => b.count - a.count) : [];

    if (loading && !summary) {
        return (
            <Layout>
                <div className="space-y-6" data-testid="team-evaluation-page">
                    <div className="page-header">
                        <Skeleton className="h-8 w-64" />
                        <Skeleton className="h-4 w-96 mt-2" />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        {[1, 2, 3, 4].map(i => (
                            <Skeleton key={i} className="h-32" />
                        ))}
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <Skeleton className="h-80" />
                        <Skeleton className="h-80" />
                    </div>
                </div>
            </Layout>
        );
    }

    return (
        <Layout>
            <div className="space-y-6" data-testid="team-evaluation-page">
                {/* Header */}
                <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="page-title flex items-center gap-3">
                            <Users className="h-7 w-7 text-emerald-500" />
                            SEO Team Evaluation
                        </h1>
                        <p className="page-subtitle">
                            Performance metrics and scoring for the SEO optimization team
                        </p>
                    </div>
                    <div className="flex items-center gap-3 flex-wrap">
                        <Select value={dateRange} onValueChange={setDateRange}>
                            <SelectTrigger className="w-[140px] bg-card border-border" data-testid="date-range-filter">
                                <Calendar className="h-4 w-4 mr-2 text-zinc-500" />
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="7">Last 7 days</SelectItem>
                                <SelectItem value="30">Last 30 days</SelectItem>
                                <SelectItem value="90">Last 90 days</SelectItem>
                                <SelectItem value="365">Last year</SelectItem>
                            </SelectContent>
                        </Select>
                        
                        <Select value={selectedBrand} onValueChange={setSelectedBrand}>
                            <SelectTrigger className="w-[160px] bg-card border-border" data-testid="brand-filter">
                                <SelectValue placeholder="All Brands" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Brands</SelectItem>
                                {brands.map(brand => (
                                    <SelectItem key={brand.id} value={brand.id}>{brand.name}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        
                        <Button 
                            variant="outline" 
                            size="icon" 
                            onClick={handleRefresh}
                            disabled={refreshing}
                            data-testid="refresh-btn"
                        >
                            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
                        </Button>
                    </div>
                </div>

                {/* Summary Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card className="bg-card border-border">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-xs text-zinc-500 uppercase tracking-wide">Total Optimizations</p>
                                    <p className="text-2xl font-bold text-white mt-1">{summary?.total_optimizations || 0}</p>
                                </div>
                                <div className="p-3 rounded-lg bg-emerald-500/10">
                                    <Activity className="h-5 w-5 text-emerald-500" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    
                    <Card className="bg-card border-border">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-xs text-zinc-500 uppercase tracking-wide">Completed</p>
                                    <p className="text-2xl font-bold text-emerald-400 mt-1">{summary?.by_status?.completed || 0}</p>
                                </div>
                                <div className="p-3 rounded-lg bg-emerald-500/10">
                                    <CheckCircle className="h-5 w-5 text-emerald-500" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    
                    <Card className="bg-card border-border">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-xs text-zinc-500 uppercase tracking-wide">Total Complaints</p>
                                    <p className="text-2xl font-bold text-amber-400 mt-1">{summary?.total_complaints || 0}</p>
                                </div>
                                <div className="p-3 rounded-lg bg-amber-500/10">
                                    <AlertTriangle className="h-5 w-5 text-amber-500" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    
                    <Card className="bg-card border-border">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-xs text-zinc-500 uppercase tracking-wide">Reverted</p>
                                    <p className="text-2xl font-bold text-red-400 mt-1">{summary?.by_status?.reverted || 0}</p>
                                </div>
                                <div className="p-3 rounded-lg bg-red-500/10">
                                    <XCircle className="h-5 w-5 text-red-500" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Top Contributors */}
                <Card className="bg-card border-border">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-lg flex items-center gap-2">
                            <Trophy className="h-5 w-5 text-amber-500" />
                            Top Contributors
                        </CardTitle>
                        <CardDescription>
                            Team members with the highest performance scores
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {summary?.top_contributors?.length > 0 ? (
                            <div className="overflow-x-auto">
                                <Table data-testid="top-contributors-table">
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Rank</TableHead>
                                            <TableHead>Team Member</TableHead>
                                            <TableHead className="text-center">Total</TableHead>
                                            <TableHead className="text-center">Completed</TableHead>
                                            <TableHead className="text-center">Reverted</TableHead>
                                            <TableHead className="text-center">Complaints</TableHead>
                                            <TableHead className="text-center">Score</TableHead>
                                            <TableHead>Status</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {summary.top_contributors.map((user, index) => (
                                            <TableRow key={user.user_id} className="table-row-hover">
                                                <TableCell>
                                                    {index === 0 ? (
                                                        <span className="flex items-center gap-1 text-amber-500">
                                                            <Trophy className="h-4 w-4" /> 1st
                                                        </span>
                                                    ) : index === 1 ? (
                                                        <span className="text-zinc-400">2nd</span>
                                                    ) : index === 2 ? (
                                                        <span className="text-amber-700">3rd</span>
                                                    ) : (
                                                        <span className="text-zinc-500">{index + 1}th</span>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-2">
                                                        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-500 to-blue-500 flex items-center justify-center text-white text-sm font-medium">
                                                            {user.user_name?.charAt(0)?.toUpperCase() || 'U'}
                                                        </div>
                                                        <div>
                                                            <p className="font-medium text-white">{user.user_name || 'Unknown'}</p>
                                                            <p className="text-xs text-zinc-500">{user.user_email}</p>
                                                        </div>
                                                    </div>
                                                </TableCell>
                                                <TableCell className="text-center font-mono">{user.total_optimizations}</TableCell>
                                                <TableCell className="text-center font-mono text-emerald-400">{user.completed_optimizations}</TableCell>
                                                <TableCell className="text-center font-mono text-red-400">{user.reverted_optimizations}</TableCell>
                                                <TableCell className="text-center font-mono text-amber-400">{user.complaint_count}</TableCell>
                                                <TableCell className="text-center">
                                                    <div className="flex items-center justify-center gap-2">
                                                        <span 
                                                            className="font-bold text-lg"
                                                            style={{ color: getScoreColor(user.score) }}
                                                        >
                                                            {user.score.toFixed(1)}
                                                        </span>
                                                        <Star className="h-4 w-4" style={{ color: getScoreColor(user.score) }} />
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge 
                                                        variant="outline" 
                                                        className="text-xs"
                                                        style={{ 
                                                            borderColor: getScoreColor(user.score),
                                                            color: getScoreColor(user.score)
                                                        }}
                                                    >
                                                        {getScoreLabel(user.score)}
                                                    </Badge>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        ) : (
                            <div className="text-center py-8 text-zinc-500">
                                <Users className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                <p>No optimization data available for this period</p>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Charts Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Status Distribution */}
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-lg flex items-center gap-2">
                                <BarChart3 className="h-5 w-5 text-blue-500" />
                                Status Distribution
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {statusChartData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={280}>
                                    <PieChart>
                                        <Pie
                                            data={statusChartData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={60}
                                            outerRadius={90}
                                            paddingAngle={3}
                                            dataKey="value"
                                            label={({ name, value }) => `${name}: ${value}`}
                                            labelLine={false}
                                        >
                                            {statusChartData.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={entry.fill} />
                                            ))}
                                        </Pie>
                                        <Tooltip 
                                            contentStyle={{ 
                                                backgroundColor: '#0A0A0A', 
                                                border: '1px solid #27272A',
                                                borderRadius: '6px'
                                            }}
                                        />
                                        <Legend 
                                            verticalAlign="bottom"
                                            formatter={(value) => <span className="text-zinc-300 text-sm">{value}</span>}
                                        />
                                    </PieChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-[280px] flex items-center justify-center text-zinc-500">
                                    No data available
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Activity Type Distribution */}
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-lg flex items-center gap-2">
                                <Target className="h-5 w-5 text-emerald-500" />
                                Activity Types
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {activityTypeData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={280}>
                                    <BarChart data={activityTypeData} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                                        <XAxis type="number" tick={{ fill: '#A1A1AA', fontSize: 12 }} />
                                        <YAxis 
                                            type="category" 
                                            dataKey="name" 
                                            tick={{ fill: '#A1A1AA', fontSize: 11 }} 
                                            width={100}
                                        />
                                        <Tooltip 
                                            contentStyle={{ 
                                                backgroundColor: '#0A0A0A', 
                                                border: '1px solid #27272A',
                                                borderRadius: '6px'
                                            }}
                                        />
                                        <Bar dataKey="count" fill="#22C55E" radius={[0, 4, 4, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-[280px] flex items-center justify-center text-zinc-500">
                                    No data available
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Most Complained Users (Alert Section) */}
                {summary?.most_complained_users?.some(u => u.complaint_count > 0) && (
                    <Card className="bg-red-950/20 border-red-900/50">
                        <CardHeader className="pb-3">
                            <CardTitle className="text-lg flex items-center gap-2 text-red-400">
                                <AlertTriangle className="h-5 w-5" />
                                Attention Required: Users with Complaints
                            </CardTitle>
                            <CardDescription className="text-red-300/70">
                                Team members with optimization complaints that may need review
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {summary.most_complained_users
                                    .filter(u => u.complaint_count > 0)
                                    .map(user => (
                                    <div 
                                        key={user.user_id}
                                        className="p-4 rounded-lg bg-black/30 border border-red-900/30"
                                    >
                                        <div className="flex items-center gap-3 mb-3">
                                            <div className="h-10 w-10 rounded-full bg-red-500/20 flex items-center justify-center text-red-400 font-medium">
                                                {user.user_name?.charAt(0)?.toUpperCase() || 'U'}
                                            </div>
                                            <div>
                                                <p className="font-medium text-white">{user.user_name}</p>
                                                <p className="text-xs text-zinc-500">{user.user_email}</p>
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-2 gap-2 text-sm">
                                            <div>
                                                <p className="text-zinc-500">Complaints</p>
                                                <p className="font-mono text-red-400">{user.complaint_count}</p>
                                            </div>
                                            <div>
                                                <p className="text-zinc-500">Resolved</p>
                                                <p className="font-mono text-emerald-400">{user.resolved_complaints}</p>
                                            </div>
                                        </div>
                                        {user.has_repeated_issues && (
                                            <Badge variant="destructive" className="mt-3 text-xs">
                                                Repeated Issues
                                            </Badge>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Observed Impact Overview */}
                {impactChartData.length > 0 && (
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-3">
                            <CardTitle className="text-lg flex items-center gap-2">
                                <TrendingUp className="h-5 w-5 text-emerald-500" />
                                Observed Impact Summary
                            </CardTitle>
                            <CardDescription>
                                Impact assessment of completed optimizations (filled 14-30 days after completion)
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                {Object.entries(summary?.by_observed_impact || {}).map(([impact, count]) => {
                                    const Icon = impact === 'positive' ? TrendingUp : 
                                               impact === 'negative' ? TrendingDown : 
                                               impact === 'no_impact' ? XCircle : Activity;
                                    const color = IMPACT_COLORS[impact] || '#6B7280';
                                    return (
                                        <div 
                                            key={impact}
                                            className="p-4 rounded-lg border"
                                            style={{ borderColor: `${color}40` }}
                                        >
                                            <div className="flex items-center gap-2 mb-2">
                                                <Icon className="h-4 w-4" style={{ color }} />
                                                <span className="text-xs uppercase text-zinc-500">
                                                    {impact.replace('_', ' ')}
                                                </span>
                                            </div>
                                            <p className="text-2xl font-bold" style={{ color }}>
                                                {count}
                                            </p>
                                        </div>
                                    );
                                })}
                            </div>
                        </CardContent>
                    </Card>
                )}
            </div>
        </Layout>
    );
}
