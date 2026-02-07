import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { reportsAPI, seedAPI, brandsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { 
    Globe, 
    Network, 
    Tag, 
    TrendingUp, 
    AlertTriangle, 
    CheckCircle,
    ArrowRight,
    Loader2,
    Database,
    BarChart3
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
    Cell
} from 'recharts';
import { TIER_LABELS, TIER_COLORS } from '../lib/utils';

const PIE_COLORS = ['#22C55E', '#52525B'];

export default function DashboardPage() {
    const { user, isSuperAdmin } = useAuth();
    const [stats, setStats] = useState(null);
    const [tierData, setTierData] = useState([]);
    const [indexData, setIndexData] = useState([]);
    const [brands, setBrands] = useState([]);
    const [selectedBrand, setSelectedBrand] = useState('all');
    const [loading, setLoading] = useState(true);
    const [seeding, setSeeding] = useState(false);

    useEffect(() => {
        loadData();
    }, [selectedBrand]);

    const loadData = async () => {
        try {
            const brandId = selectedBrand === 'all' ? undefined : selectedBrand;
            
            const [statsRes, tierRes, indexRes, brandsRes] = await Promise.all([
                reportsAPI.getDashboardStats(),
                reportsAPI.getTierDistribution(brandId),
                reportsAPI.getIndexStatus(brandId),
                brandsAPI.getAll()
            ]);

            setStats(statsRes.data);
            setTierData(tierRes.data.map(t => ({
                name: TIER_LABELS[t.tier] || t.tier,
                value: t.count,
                fill: TIER_COLORS[t.tier] || '#3B82F6'
            })));
            setIndexData(indexRes.data.map(s => ({
                name: s.status === 'index' ? 'Indexed' : 'Noindex',
                value: s.count
            })));
            setBrands(brandsRes.data);
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

    return (
        <Layout>
            <div data-testid="dashboard-page">
                {/* Header */}
                <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="page-title">Dashboard</h1>
                        <p className="page-subtitle">
                            Welcome back, {user?.name}
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
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

                {/* Stats Grid */}
                <div className="stats-grid" data-testid="stats-grid">
                    <div className="stat-card card-hover">
                        <div className="flex items-center gap-3 mb-3">
                            <div className="p-2 rounded-md bg-blue-500/10">
                                <Globe className="h-5 w-5 text-blue-500" />
                            </div>
                            <span className="stat-label mb-0">Total Domains</span>
                        </div>
                        <div className="stat-value" data-testid="total-domains">{stats?.total_domains || 0}</div>
                    </div>

                    <div className="stat-card card-hover">
                        <div className="flex items-center gap-3 mb-3">
                            <div className="p-2 rounded-md bg-purple-500/10">
                                <Network className="h-5 w-5 text-purple-500" />
                            </div>
                            <span className="stat-label mb-0">Networks</span>
                        </div>
                        <div className="stat-value" data-testid="total-groups">{stats?.total_groups || 0}</div>
                    </div>

                    <div className="stat-card card-hover">
                        <div className="flex items-center gap-3 mb-3">
                            <div className="p-2 rounded-md bg-amber-500/10">
                                <Tag className="h-5 w-5 text-amber-500" />
                            </div>
                            <span className="stat-label mb-0">Brands</span>
                        </div>
                        <div className="stat-value" data-testid="total-brands">{stats?.total_brands || 0}</div>
                    </div>

                    <div className="stat-card card-hover">
                        <div className="flex items-center gap-3 mb-3">
                            <div className="p-2 rounded-md bg-emerald-500/10">
                                <TrendingUp className="h-5 w-5 text-emerald-500" />
                            </div>
                            <span className="stat-label mb-0">Index Rate</span>
                        </div>
                        <div className="stat-value" data-testid="index-rate">{stats?.index_rate || 0}%</div>
                        <div className={`stat-change ${stats?.index_rate >= 70 ? 'positive' : 'negative'}`}>
                            {stats?.indexed_count || 0} indexed / {stats?.noindex_count || 0} noindex
                        </div>
                    </div>
                </div>

                {/* Charts */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                    {/* Tier Distribution */}
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-lg flex items-center gap-2">
                                <BarChart3 className="h-5 w-5 text-blue-500" />
                                Tier Distribution
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {tierData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={280}>
                                    <BarChart data={tierData} layout="vertical">
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
                                        <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                                            {tierData.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={entry.fill} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-[280px] flex items-center justify-center text-zinc-500">
                                    No domain data available
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Index Status */}
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-lg flex items-center gap-2">
                                <CheckCircle className="h-5 w-5 text-emerald-500" />
                                Index Status
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {indexData.length > 0 ? (
                                <div className="flex items-center justify-center">
                                    <ResponsiveContainer width="100%" height={280}>
                                        <PieChart>
                                            <Pie
                                                data={indexData}
                                                cx="50%"
                                                cy="50%"
                                                innerRadius={70}
                                                outerRadius={100}
                                                paddingAngle={3}
                                                dataKey="value"
                                                label={({ name, value }) => `${name}: ${value}`}
                                                labelLine={{ stroke: '#52525B' }}
                                            >
                                                {indexData.map((entry, index) => (
                                                    <Cell key={`cell-${index}`} fill={PIE_COLORS[index]} />
                                                ))}
                                            </Pie>
                                            <Tooltip 
                                                contentStyle={{ 
                                                    backgroundColor: '#0A0A0A', 
                                                    border: '1px solid #27272A',
                                                    borderRadius: '6px'
                                                }}
                                            />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : (
                                <div className="h-[280px] flex items-center justify-center text-zinc-500">
                                    No index data available
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Quick Actions */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <Link to="/domains" data-testid="quick-link-domains">
                        <Card className="bg-card border-border hover:border-blue-500/50 cursor-pointer transition-colors">
                            <CardContent className="p-4 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <Globe className="h-5 w-5 text-blue-500" />
                                    <span className="font-medium">Manage Domains</span>
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
                                    <span className="font-medium">View Networks</span>
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
                                    <span className="font-medium">View Reports</span>
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
