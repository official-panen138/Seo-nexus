import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { v3ReportsAPI, conflictsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent } from '../components/ui/card';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { 
    AlertTriangle,
    CheckCircle, 
    Loader2, 
    Network,
    ExternalLink,
    RefreshCw,
    Link2,
    ClipboardList
} from 'lucide-react';

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
    const [conflicts, setConflicts] = useState([]);
    const [storedConflicts, setStoredConflicts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [processing, setProcessing] = useState(false);

    useEffect(() => {
        loadConflicts();
    }, []);

    const loadConflicts = async () => {
        setLoading(true);
        try {
            // Load both detected and stored conflicts
            const [detectedRes, storedRes] = await Promise.all([
                v3ReportsAPI.getConflicts(),
                conflictsAPI.getStored()
            ]);
            
            setConflicts(detectedRes.data?.conflicts || []);
            setStoredConflicts(storedRes.data?.conflicts || []);
        } catch (err) {
            console.error('Failed to load conflicts:', err);
            toast.error('Failed to load SEO conflicts');
        } finally {
            setLoading(false);
        }
    };

    const handleProcessConflicts = async () => {
        setProcessing(true);
        try {
            const res = await conflictsAPI.process();
            const data = res.data;
            
            if (data.success) {
                toast.success(
                    `Processed ${data.conflicts_processed} conflicts. Created ${data.optimizations_created} optimization tasks.`
                );
                loadConflicts(); // Reload to show updated data
            }
        } catch (err) {
            console.error('Failed to process conflicts:', err);
            toast.error('Failed to process conflicts');
        } finally {
            setProcessing(false);
        }
    };

    // Create a map of stored conflicts by their key for quick lookup
    const storedConflictMap = storedConflicts.reduce((acc, c) => {
        const key = `${c.network_id}|${c.conflict_type}|${c.node_a_id}|${c.node_b_id || ''}`;
        acc[key] = c;
        return acc;
    }, {});

    // Enhance detected conflicts with stored info (linked optimization)
    const enhancedConflicts = conflicts.map(c => {
        const key = `${c.network_id}|${c.conflict_type}|${c.node_a_id}|${c.node_b_id || ''}`;
        const stored = storedConflictMap[key];
        return {
            ...c,
            stored_conflict: stored,
            linked_optimization: stored?.linked_optimization
        };
    });

    // Conflict stats
    const conflictStats = {
        total: enhancedConflicts.length,
        critical: enhancedConflicts.filter(c => c.severity === 'critical').length,
        high: enhancedConflicts.filter(c => c.severity === 'high').length,
        linked: enhancedConflicts.filter(c => c.linked_optimization).length,
        byType: enhancedConflicts.reduce((acc, c) => {
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
                        <AlertTriangle className="h-7 w-7 text-amber-500" />
                        <div>
                            <h1 className="page-title">SEO Conflicts</h1>
                            <p className="page-subtitle">
                                Detect and resolve SEO configuration issues across networks
                            </p>
                        </div>
                    </div>
                </div>

                {/* Stats Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <Card className="bg-card border-border">
                        <CardContent className="pt-4">
                            <div className="text-sm text-zinc-500 mb-1">Total Conflicts</div>
                            <div className="text-2xl font-bold font-mono">{conflictStats.total}</div>
                        </CardContent>
                    </Card>
                    <Card className={`bg-card border-border ${conflictStats.critical > 0 ? 'border-red-900/50' : ''}`}>
                        <CardContent className="pt-4">
                            <div className="text-sm text-zinc-500 mb-1">Critical</div>
                            <div className={`text-2xl font-bold font-mono ${conflictStats.critical > 0 ? 'text-red-500' : 'text-zinc-400'}`}>
                                {conflictStats.critical}
                            </div>
                        </CardContent>
                    </Card>
                    <Card className={`bg-card border-border ${conflictStats.high > 0 ? 'border-amber-900/50' : ''}`}>
                        <CardContent className="pt-4">
                            <div className="text-sm text-zinc-500 mb-1">High Priority</div>
                            <div className={`text-2xl font-bold font-mono ${conflictStats.high > 0 ? 'text-amber-500' : 'text-zinc-400'}`}>
                                {conflictStats.high}
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="bg-card border-border">
                        <CardContent className="pt-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <div className="text-sm text-zinc-500 mb-1">Refresh</div>
                                    <Button 
                                        variant="outline" 
                                        size="sm" 
                                        onClick={loadConflicts}
                                        disabled={loading}
                                        data-testid="refresh-conflicts-btn"
                                    >
                                        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                                    </Button>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Conflicts List */}
                {conflicts.length === 0 ? (
                    <Card className="bg-card border-border">
                        <CardContent className="py-12 text-center">
                            <CheckCircle className="h-12 w-12 text-emerald-500 mx-auto mb-3" />
                            <p className="text-lg font-medium text-white">No Conflicts Detected</p>
                            <p className="text-sm text-zinc-500 mt-1">
                                Your SEO networks are configured correctly
                            </p>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="space-y-4" data-testid="conflicts-list">
                        {conflicts.map((conflict, idx) => {
                            const severityClass = CONFLICT_SEVERITY_CLASSES[conflict.severity] || CONFLICT_SEVERITY_CLASSES.medium;
                            const typeLabel = CONFLICT_TYPE_LABELS[conflict.conflict_type] || conflict.conflict_type;
                            
                            return (
                                <Card 
                                    key={idx} 
                                    className={`bg-card border-border ${conflict.severity === 'critical' ? 'border-red-500/30' : conflict.severity === 'high' ? 'border-amber-500/30' : ''}`}
                                    data-testid={`conflict-${idx}`}
                                >
                                    <CardContent className="pt-4">
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-start gap-3">
                                                <AlertTriangle className={`h-5 w-5 flex-shrink-0 ${
                                                    conflict.severity === 'critical' ? 'text-red-400' :
                                                    conflict.severity === 'high' ? 'text-amber-400' : 'text-yellow-400'
                                                }`} />
                                                <div>
                                                    <div className="flex items-center gap-2 mb-1">
                                                        <Badge className={severityClass}>
                                                            {(conflict.severity || 'medium').toUpperCase()}
                                                        </Badge>
                                                        <Badge variant="outline" className="text-xs">
                                                            {typeLabel}
                                                        </Badge>
                                                    </div>
                                                    <p className="text-sm text-white font-medium">
                                                        {conflict.description || conflict.message || 'SEO structure conflict detected'}
                                                    </p>
                                                    {conflict.network_name && (
                                                        <p className="text-xs text-zinc-500 mt-1">
                                                            Network: {conflict.network_name}
                                                        </p>
                                                    )}
                                                    {conflict.affected_nodes && conflict.affected_nodes.length > 0 && (
                                                        <div className="mt-2 space-y-1">
                                                            <p className="text-xs text-zinc-500">Affected Nodes:</p>
                                                            {conflict.affected_nodes.slice(0, 3).map((node, nIdx) => (
                                                                <div key={nIdx} className="flex items-center gap-2">
                                                                    <Network className="h-3 w-3 text-zinc-600" />
                                                                    <code className="text-xs text-zinc-400 bg-zinc-900 px-1 rounded">
                                                                        {node.domain}{node.path || ''}
                                                                    </code>
                                                                </div>
                                                            ))}
                                                            {conflict.affected_nodes.length > 3 && (
                                                                <p className="text-xs text-zinc-600">
                                                                    +{conflict.affected_nodes.length - 3} more nodes
                                                                </p>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                            {conflict.network_id && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => window.location.href = `/groups/${conflict.network_id}`}
                                                    className="text-xs"
                                                >
                                                    <ExternalLink className="h-3 w-3 mr-1" />
                                                    View Network
                                                </Button>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                )}
            </div>
        </Layout>
    );
}
