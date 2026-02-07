import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { groupsAPI, domainsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { NetworkGraph } from '../components/NetworkGraph';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../components/ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { toast } from 'sonner';
import { 
    ArrowLeft, 
    Loader2, 
    ZoomIn, 
    ZoomOut, 
    Maximize2,
    Globe,
    ExternalLink,
    Network,
    AlertTriangle
} from 'lucide-react';
import { 
    TIER_LABELS, 
    STATUS_LABELS, 
    INDEX_STATUS_LABELS, 
    getTierBadgeClass, 
    TIER_COLORS,
    formatDate 
} from '../lib/utils';

export default function GroupDetailPage() {
    const { groupId } = useParams();
    const navigate = useNavigate();
    const [group, setGroup] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedDomain, setSelectedDomain] = useState(null);
    const [sheetOpen, setSheetOpen] = useState(false);

    useEffect(() => {
        loadGroup();
    }, [groupId]);

    const loadGroup = async () => {
        try {
            const res = await groupsAPI.getOne(groupId);
            setGroup(res.data);
        } catch (err) {
            toast.error('Failed to load network');
            navigate('/groups');
        } finally {
            setLoading(false);
        }
    };

    const handleNodeClick = (node) => {
        setSelectedDomain(node);
        setSheetOpen(true);
    };

    // Calculate stats
    const stats = group?.domains ? {
        total: group.domains.length,
        indexed: group.domains.filter(d => d.index_status === 'index').length,
        orphans: group.domains.filter(d => d.tier_level !== 'lp_money_site' && !d.parent_domain_id).length,
        tierCounts: group.domains.reduce((acc, d) => {
            acc[d.tier_level] = (acc[d.tier_level] || 0) + 1;
            return acc;
        }, {})
    } : null;

    if (loading) {
        return (
            <Layout>
                <div className="flex items-center justify-center h-96">
                    <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
                </div>
            </Layout>
        );
    }

    if (!group) {
        return (
            <Layout>
                <div className="text-center py-16">
                    <p className="text-zinc-400">Network not found</p>
                </div>
            </Layout>
        );
    }

    return (
        <Layout>
            <div data-testid="group-detail-page">
                {/* Header */}
                <div className="page-header">
                    <Button
                        variant="ghost"
                        onClick={() => navigate('/groups')}
                        className="mb-4 text-zinc-400 hover:text-white"
                        data-testid="back-btn"
                    >
                        <ArrowLeft className="h-4 w-4 mr-2" />
                        Back to Networks
                    </Button>
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div>
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-md bg-purple-500/10">
                                    <Network className="h-6 w-6 text-purple-500" />
                                </div>
                                <h1 className="page-title">{group.name}</h1>
                            </div>
                            {group.description && (
                                <p className="page-subtitle mt-2">{group.description}</p>
                            )}
                        </div>
                    </div>
                </div>

                {/* Stats */}
                {stats && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <Card className="bg-card border-border">
                            <CardContent className="pt-4">
                                <div className="text-sm text-zinc-500 mb-1">Total Domains</div>
                                <div className="text-2xl font-bold font-mono">{stats.total}</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-card border-border">
                            <CardContent className="pt-4">
                                <div className="text-sm text-zinc-500 mb-1">Indexed</div>
                                <div className="text-2xl font-bold font-mono text-emerald-500">
                                    {stats.indexed}
                                    <span className="text-sm font-normal text-zinc-500 ml-1">
                                        ({stats.total > 0 ? Math.round(stats.indexed / stats.total * 100) : 0}%)
                                    </span>
                                </div>
                            </CardContent>
                        </Card>
                        <Card className="bg-card border-border">
                            <CardContent className="pt-4">
                                <div className="text-sm text-zinc-500 mb-1">Noindex</div>
                                <div className="text-2xl font-bold font-mono text-zinc-400">
                                    {stats.total - stats.indexed}
                                </div>
                            </CardContent>
                        </Card>
                        <Card className={`border-border ${stats.orphans > 0 ? 'bg-red-950/20 border-red-900/50' : 'bg-card'}`}>
                            <CardContent className="pt-4">
                                <div className="text-sm text-zinc-500 mb-1 flex items-center gap-1">
                                    {stats.orphans > 0 && <AlertTriangle className="h-3 w-3 text-red-500" />}
                                    Orphan Domains
                                </div>
                                <div className={`text-2xl font-bold font-mono ${stats.orphans > 0 ? 'text-red-500' : 'text-zinc-400'}`}>
                                    {stats.orphans}
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                )}

                {/* Tabs */}
                <Tabs defaultValue="graph" className="space-y-4">
                    <TabsList className="bg-card border border-border">
                        <TabsTrigger value="graph" data-testid="graph-tab">Visual Graph</TabsTrigger>
                        <TabsTrigger value="list" data-testid="list-tab">Domain List</TabsTrigger>
                    </TabsList>

                    {/* Graph View */}
                    <TabsContent value="graph">
                        <div className="network-graph-container h-[600px]" data-testid="network-graph">
                            {group.domains && group.domains.length > 0 ? (
                                <NetworkGraph 
                                    domains={group.domains}
                                    onNodeClick={handleNodeClick}
                                    selectedNodeId={selectedDomain?.id}
                                />
                            ) : (
                                <div className="flex items-center justify-center h-full">
                                    <div className="text-center">
                                        <Globe className="h-12 w-12 text-zinc-700 mx-auto mb-3" />
                                        <p className="text-zinc-500">No domains in this network</p>
                                        <p className="text-sm text-zinc-600 mt-1">
                                            Add domains and assign them to this network
                                        </p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </TabsContent>

                    {/* List View */}
                    <TabsContent value="list">
                        <div className="data-table-container" data-testid="domains-list">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Domain</TableHead>
                                        <TableHead>Tier</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Index</TableHead>
                                        <TableHead>Parent</TableHead>
                                        <TableHead>Brand</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {group.domains?.length === 0 ? (
                                        <TableRow>
                                            <TableCell colSpan={6} className="h-32 text-center text-zinc-500">
                                                No domains in this network
                                            </TableCell>
                                        </TableRow>
                                    ) : (
                                        group.domains?.map((domain) => {
                                            const parent = group.domains.find(d => d.id === domain.parent_domain_id);
                                            const isOrphan = domain.tier_level !== 'lp_money_site' && !domain.parent_domain_id;
                                            
                                            return (
                                                <TableRow 
                                                    key={domain.id} 
                                                    className={`table-row-hover cursor-pointer ${isOrphan ? 'bg-red-950/10' : ''}`}
                                                    onClick={() => handleNodeClick(domain)}
                                                    data-testid={`domain-list-row-${domain.id}`}
                                                >
                                                    <TableCell>
                                                        <div className="flex items-center gap-2">
                                                            {isOrphan && <AlertTriangle className="h-4 w-4 text-red-500" />}
                                                            <span className="font-mono text-sm">{domain.domain_name}</span>
                                                            <a 
                                                                href={`https://${domain.domain_name}`}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                onClick={(e) => e.stopPropagation()}
                                                                className="text-zinc-500 hover:text-blue-500"
                                                            >
                                                                <ExternalLink className="h-3 w-3" />
                                                            </a>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <span className={`badge-tier ${getTierBadgeClass(domain.tier_level)}`}>
                                                            {TIER_LABELS[domain.tier_level]}
                                                        </span>
                                                    </TableCell>
                                                    <TableCell className="text-zinc-400 text-sm">
                                                        {STATUS_LABELS[domain.domain_status]}
                                                    </TableCell>
                                                    <TableCell>
                                                        <span className={`text-xs px-2 py-1 rounded-full font-mono uppercase ${
                                                            domain.index_status === 'index' ? 'status-indexed' : 'status-noindex'
                                                        }`}>
                                                            {domain.index_status}
                                                        </span>
                                                    </TableCell>
                                                    <TableCell className="text-zinc-400 text-sm font-mono">
                                                        {parent?.domain_name || '-'}
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge variant="outline" className="font-normal">
                                                            {domain.brand_name || '-'}
                                                        </Badge>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })
                                    )}
                                </TableBody>
                            </Table>
                        </div>
                    </TabsContent>
                </Tabs>

                {/* Domain Detail Sheet */}
                <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
                    <SheetContent className="bg-card border-border w-full sm:max-w-md">
                        <SheetHeader>
                            <SheetTitle className="font-mono text-lg">
                                {selectedDomain?.domain_name}
                            </SheetTitle>
                        </SheetHeader>
                        
                        {selectedDomain && (
                            <div className="mt-6 space-y-6">
                                {/* Quick Info */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Tier</span>
                                        <span 
                                            className="font-mono font-medium"
                                            style={{ color: TIER_COLORS[selectedDomain.tier_level] }}
                                        >
                                            {TIER_LABELS[selectedDomain.tier_level]}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Index Status</span>
                                        <span className={`text-xs px-2 py-1 rounded-full font-mono uppercase ${
                                            selectedDomain.index_status === 'index' ? 'status-indexed' : 'status-noindex'
                                        }`}>
                                            {selectedDomain.index_status}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Domain Status</span>
                                        <span className="text-sm text-white">
                                            {STATUS_LABELS[selectedDomain.domain_status]}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-zinc-500">Brand</span>
                                        <Badge variant="outline">{selectedDomain.brand_name || '-'}</Badge>
                                    </div>
                                </div>

                                {/* Parent Domain */}
                                {selectedDomain.parent_domain_id && (
                                    <div className="pt-4 border-t border-border">
                                        <span className="text-sm text-zinc-500 block mb-2">Parent Domain</span>
                                        <div className="bg-black rounded-md p-3">
                                            <span className="font-mono text-sm text-blue-400">
                                                {group.domains?.find(d => d.id === selectedDomain.parent_domain_id)?.domain_name || 'Unknown'}
                                            </span>
                                        </div>
                                    </div>
                                )}

                                {/* Child Domains */}
                                {group.domains?.filter(d => d.parent_domain_id === selectedDomain.id).length > 0 && (
                                    <div className="pt-4 border-t border-border">
                                        <span className="text-sm text-zinc-500 block mb-2">Child Domains</span>
                                        <div className="space-y-2">
                                            {group.domains
                                                .filter(d => d.parent_domain_id === selectedDomain.id)
                                                .map(child => (
                                                    <div key={child.id} className="bg-black rounded-md p-3 flex items-center justify-between">
                                                        <span className="font-mono text-sm">{child.domain_name}</span>
                                                        <span className={`badge-tier ${getTierBadgeClass(child.tier_level)}`}>
                                                            {TIER_LABELS[child.tier_level]}
                                                        </span>
                                                    </div>
                                                ))
                                            }
                                        </div>
                                    </div>
                                )}

                                {/* Notes */}
                                {selectedDomain.notes && (
                                    <div className="pt-4 border-t border-border">
                                        <span className="text-sm text-zinc-500 block mb-2">Notes</span>
                                        <p className="text-sm text-zinc-300">{selectedDomain.notes}</p>
                                    </div>
                                )}

                                {/* Timestamps */}
                                <div className="pt-4 border-t border-border text-xs text-zinc-600">
                                    <p>Created: {formatDate(selectedDomain.created_at)}</p>
                                    <p>Updated: {formatDate(selectedDomain.updated_at)}</p>
                                </div>

                                {/* Actions */}
                                <div className="pt-4">
                                    <a 
                                        href={`https://${selectedDomain.domain_name}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="w-full"
                                    >
                                        <Button variant="outline" className="w-full">
                                            <ExternalLink className="h-4 w-4 mr-2" />
                                            Open Domain
                                        </Button>
                                    </a>
                                </div>
                            </div>
                        )}
                    </SheetContent>
                </Sheet>
            </div>
        </Layout>
    );
}
