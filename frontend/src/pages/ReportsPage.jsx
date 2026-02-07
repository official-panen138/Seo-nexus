import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { reportsAPI, brandsAPI, groupsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { 
    Download, 
    Loader2, 
    BarChart3,
    AlertTriangle,
    CheckCircle,
    TrendingUp,
    FileJson,
    FileText
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
import { TIER_LABELS, TIER_COLORS, downloadFile } from '../lib/utils';

const HEALTH_COLORS = ['#22C55E', '#F59E0B', '#EF4444'];

export default function ReportsPage() {
    const [loading, setLoading] = useState(true);
    const [brands, setBrands] = useState([]);
    const [groups, setGroups] = useState([]);
    const [selectedBrand, setSelectedBrand] = useState('all');
    const [selectedGroup, setSelectedGroup] = useState('all');
    
    // Report data
    const [tierData, setTierData] = useState([]);
    const [indexData, setIndexData] = useState([]);
    const [brandHealth, setBrandHealth] = useState([]);
    const [orphanDomains, setOrphanDomains] = useState([]);
    const [exporting, setExporting] = useState(false);

    useEffect(() => {
        loadInitialData();
    }, []);

    useEffect(() => {
        loadReports();
    }, [selectedBrand]);

    const loadInitialData = async () => {
        try {
            const [brandsRes, groupsRes] = await Promise.all([
                brandsAPI.getAll(),
                groupsAPI.getAll()
            ]);
            setBrands(brandsRes.data);
            setGroups(groupsRes.data);
        } catch (err) {
            console.error('Failed to load initial data:', err);
        }
    };

    const loadReports = async () => {
        setLoading(true);
        try {
            const brandId = selectedBrand === 'all' ? undefined : selectedBrand;
            
            const [tierRes, indexRes, healthRes, orphanRes] = await Promise.all([
                reportsAPI.getTierDistribution(brandId),
                reportsAPI.getIndexStatus(brandId),
                reportsAPI.getBrandHealth(),
                reportsAPI.getOrphanDomains()
            ]);

            setTierData(tierRes.data.map(t => ({
                name: TIER_LABELS[t.tier] || t.tier,
                value: t.count,
                fill: TIER_COLORS[t.tier] || '#3B82F6'
            })));

            setIndexData(indexRes.data.map(s => ({
                name: s.status === 'index' ? 'Indexed' : 'Noindex',
                value: s.count,
                fill: s.status === 'index' ? '#22C55E' : '#52525B'
            })));

            setBrandHealth(healthRes.data);
            setOrphanDomains(orphanRes.data);
        } catch (err) {
            toast.error('Failed to load reports');
        } finally {
            setLoading(false);
        }
    };

    const handleExport = async (format) => {
        setExporting(true);
        try {
            const brandId = selectedBrand === 'all' ? undefined : selectedBrand;
            const groupId = selectedGroup === 'all' ? undefined : selectedGroup;
            
            const res = await reportsAPI.exportDomains(format, brandId, groupId);
            
            if (format === 'csv') {
                downloadFile(res.data.data, 'domains_export.csv', 'text/csv');
            } else {
                downloadFile(JSON.stringify(res.data.data, null, 2), 'domains_export.json', 'application/json');
            }
            
            toast.success(`Exported as ${format.toUpperCase()}`);
        } catch (err) {
            toast.error('Export failed');
        } finally {
            setExporting(false);
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
            <div data-testid="reports-page">
                {/* Header */}
                <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="page-title">Reports</h1>
                        <p className="page-subtitle">
                            Domain analytics and health reports
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <Select value={selectedBrand} onValueChange={setSelectedBrand}>
                            <SelectTrigger className="w-[180px] bg-card border-border" data-testid="report-brand-filter">
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
                    </div>
                </div>

                {/* Export Section */}
                <Card className="bg-card border-border mb-6">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Download className="h-4 w-4 text-blue-500" />
                            Export Data
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex flex-wrap items-center gap-4">
                            <Select value={selectedGroup} onValueChange={setSelectedGroup}>
                                <SelectTrigger className="w-[180px] bg-black border-border" data-testid="export-group-filter">
                                    <SelectValue placeholder="All Networks" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All Networks</SelectItem>
                                    {groups.map(group => (
                                        <SelectItem key={group.id} value={group.id}>
                                            {group.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            
                            <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    onClick={() => handleExport('json')}
                                    disabled={exporting}
                                    data-testid="export-json-btn"
                                >
                                    {exporting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <FileJson className="h-4 w-4 mr-2" />}
                                    Export JSON
                                </Button>
                                <Button
                                    variant="outline"
                                    onClick={() => handleExport('csv')}
                                    disabled={exporting}
                                    data-testid="export-csv-btn"
                                >
                                    {exporting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <FileText className="h-4 w-4 mr-2" />}
                                    Export CSV
                                </Button>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Charts Grid */}
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
                                <ResponsiveContainer width="100%" height={300}>
                                    <BarChart data={tierData} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                                        <XAxis type="number" tick={{ fill: '#A1A1AA', fontSize: 12 }} />
                                        <YAxis 
                                            type="category" 
                                            dataKey="name" 
                                            tick={{ fill: '#A1A1AA', fontSize: 11 }} 
                                            width={110}
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
                                <div className="h-[300px] flex items-center justify-center text-zinc-500">
                                    No data available
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
                                <ResponsiveContainer width="100%" height={300}>
                                    <PieChart>
                                        <Pie
                                            data={indexData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={70}
                                            outerRadius={100}
                                            paddingAngle={3}
                                            dataKey="value"
                                        >
                                            {indexData.map((entry, index) => (
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
                                            formatter={(value) => <span className="text-zinc-300">{value}</span>}
                                        />
                                    </PieChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-[300px] flex items-center justify-center text-zinc-500">
                                    No data available
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Brand Health */}
                <Card className="bg-card border-border mb-6">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-lg flex items-center gap-2">
                            <TrendingUp className="h-5 w-5 text-emerald-500" />
                            Brand Health Overview
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {brandHealth.length > 0 ? (
                            <div className="overflow-x-auto">
                                <Table data-testid="brand-health-table">
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Brand</TableHead>
                                            <TableHead className="text-right">Total</TableHead>
                                            <TableHead className="text-right">Indexed</TableHead>
                                            <TableHead className="text-right">Noindex</TableHead>
                                            <TableHead className="text-right">Health Score</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {brandHealth.map((brand) => (
                                            <TableRow key={brand.brand_id} className="table-row-hover">
                                                <TableCell className="font-medium">{brand.brand_name}</TableCell>
                                                <TableCell className="text-right font-mono">{brand.total}</TableCell>
                                                <TableCell className="text-right">
                                                    <span className="text-emerald-500 font-mono">{brand.indexed}</span>
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    <span className="text-zinc-500 font-mono">{brand.noindex}</span>
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    <Badge 
                                                        variant="outline"
                                                        className={`font-mono ${
                                                            brand.health_score >= 70 
                                                                ? 'border-emerald-500 text-emerald-500' 
                                                                : brand.health_score >= 40 
                                                                    ? 'border-amber-500 text-amber-500'
                                                                    : 'border-red-500 text-red-500'
                                                        }`}
                                                    >
                                                        {brand.health_score}%
                                                    </Badge>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        ) : (
                            <div className="text-center py-8 text-zinc-500">
                                No brand data available
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Orphan Domains */}
                <Card className={`border-border ${orphanDomains.length > 0 ? 'bg-red-950/10 border-red-900/50' : 'bg-card'}`}>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-lg flex items-center gap-2">
                            <AlertTriangle className={`h-5 w-5 ${orphanDomains.length > 0 ? 'text-red-500' : 'text-zinc-500'}`} />
                            Orphan Domains
                            {orphanDomains.length > 0 && (
                                <Badge variant="destructive" className="ml-2">
                                    {orphanDomains.length} found
                                </Badge>
                            )}
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {orphanDomains.length > 0 ? (
                            <div className="overflow-x-auto">
                                <Table data-testid="orphan-domains-table">
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Domain</TableHead>
                                            <TableHead>Tier</TableHead>
                                            <TableHead>Brand</TableHead>
                                            <TableHead>Issue</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {orphanDomains.map((domain) => (
                                            <TableRow key={domain.id} className="table-row-hover">
                                                <TableCell className="font-mono text-sm">{domain.domain_name}</TableCell>
                                                <TableCell>{TIER_LABELS[domain.tier_level]}</TableCell>
                                                <TableCell>{domain.brand_name}</TableCell>
                                                <TableCell className="text-red-400 text-sm">
                                                    No parent domain assigned
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        ) : (
                            <div className="text-center py-8">
                                <CheckCircle className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
                                <p className="text-zinc-400">No orphan domains found</p>
                                <p className="text-sm text-zinc-600">All domains have proper parent relationships</p>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </Layout>
    );
}
