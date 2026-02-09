import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { optimizationsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../components/ui/collapsible';
import { Skeleton } from '../components/ui/skeleton';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import { 
    ArrowLeft,
    ExternalLink, 
    Calendar, 
    User, 
    AlertTriangle, 
    CheckCircle,
    Clock,
    Target,
    FileText,
    MessageSquare,
    Send,
    ChevronDown,
    ChevronUp,
    Link2,
    Copy,
    Loader2,
    AlertCircle,
    Tag,
    TrendingUp,
    Globe,
    Printer,
    Share2
} from 'lucide-react';

const STATUS_CONFIG = {
    planned: { label: 'Planned', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
    in_progress: { label: 'In Progress', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
    completed: { label: 'Completed', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
    reverted: { label: 'Reverted', color: 'bg-red-500/20 text-red-400 border-red-500/30' }
};

const COMPLAINT_STATUS_CONFIG = {
    none: { label: 'No Complaints', color: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30' },
    complained: { label: 'Complained', color: 'bg-red-500/20 text-red-400 border-red-500/30' },
    under_review: { label: 'Under Review', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
    resolved: { label: 'Resolved', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' }
};

const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', { 
        year: 'numeric', month: 'short', day: 'numeric', 
        hour: '2-digit', minute: '2-digit' 
    });
};

export default function OptimizationDetailPage() {
    const { optimizationId } = useParams();
    const navigate = useNavigate();
    const { user } = useAuth();
    const [loading, setLoading] = useState(true);
    const [detail, setDetail] = useState(null);
    const [expandedComplaints, setExpandedComplaints] = useState({});
    
    // Response form state
    const [responseNote, setResponseNote] = useState('');
    const [responseUrls, setResponseUrls] = useState([]);
    const [responseUrlInput, setResponseUrlInput] = useState('');
    const [submittingResponse, setSubmittingResponse] = useState(false);
    
    // Resolve form state
    const [resolutionNote, setResolutionNote] = useState('');
    const [markComplete, setMarkComplete] = useState(false);
    const [resolving, setResolving] = useState(false);
    
    // Close form state
    const [finalNote, setFinalNote] = useState('');
    const [closing, setClosing] = useState(false);

    const isSuperAdmin = user?.role === 'super_admin';
    const isAdmin = user?.role === 'admin' || isSuperAdmin;

    useEffect(() => {
        if (optimizationId) {
            loadDetail();
        }
    }, [optimizationId]);

    const loadDetail = async () => {
        setLoading(true);
        try {
            const response = await optimizationsAPI.getDetail(optimizationId);
            setDetail(response.data);
            // Auto-expand all complaints for full view
            const expanded = {};
            response.data.complaints?.forEach(c => { expanded[c.id] = true; });
            setExpandedComplaints(expanded);
        } catch (err) {
            console.error('Failed to load optimization detail:', err);
            toast.error('Failed to load optimization details');
        } finally {
            setLoading(false);
        }
    };

    const handleCopyLink = () => {
        navigator.clipboard.writeText(window.location.href);
        toast.success('Link copied to clipboard');
    };

    const handlePrint = () => {
        window.print();
    };

    const addResponseUrl = () => {
        if (responseUrlInput.trim() && !responseUrls.includes(responseUrlInput.trim())) {
            setResponseUrls([...responseUrls, responseUrlInput.trim()]);
            setResponseUrlInput('');
        }
    };

    const removeResponseUrl = (url) => {
        setResponseUrls(responseUrls.filter(u => u !== url));
    };

    const handleSubmitResponse = async () => {
        if (responseNote.trim().length < 20) {
            toast.error('Response must be at least 20 characters');
            return;
        }
        if (responseNote.trim().length > 2000) {
            toast.error('Response cannot exceed 2000 characters');
            return;
        }

        setSubmittingResponse(true);
        try {
            await optimizationsAPI.addResponse(optimizationId, {
                note: responseNote.trim(),
                report_urls: responseUrls
            });
            toast.success('Response submitted successfully');
            setResponseNote('');
            setResponseUrls([]);
            loadDetail();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to submit response');
        } finally {
            setSubmittingResponse(false);
        }
    };

    const handleResolveComplaint = async (complaintId) => {
        if (resolutionNote.trim().length < 10) {
            toast.error('Resolution note must be at least 10 characters');
            return;
        }

        setResolving(true);
        try {
            await optimizationsAPI.resolveComplaint(optimizationId, complaintId, {
                resolution_note: resolutionNote.trim(),
                mark_optimization_complete: markComplete
            });
            toast.success('Complaint resolved successfully');
            setResolutionNote('');
            setMarkComplete(false);
            loadDetail();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to resolve complaint');
        } finally {
            setResolving(false);
        }
    };

    const handleCloseOptimization = async () => {
        setClosing(true);
        try {
            await optimizationsAPI.closeOptimization(optimizationId, {
                final_note: finalNote.trim() || null
            });
            toast.success('Optimization closed successfully');
            setFinalNote('');
            loadDetail();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to close optimization');
        } finally {
            setClosing(false);
        }
    };

    const toggleComplaint = (complaintId) => {
        setExpandedComplaints(prev => ({
            ...prev,
            [complaintId]: !prev[complaintId]
        }));
    };

    if (loading) {
        return (
            <Layout>
                <div className="space-y-6" data-testid="optimization-detail-page">
                    <Skeleton className="h-8 w-96" />
                    <Skeleton className="h-4 w-64" />
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div className="lg:col-span-2 space-y-6">
                            <Skeleton className="h-48" />
                            <Skeleton className="h-32" />
                            <Skeleton className="h-64" />
                        </div>
                        <div className="space-y-6">
                            <Skeleton className="h-48" />
                            <Skeleton className="h-32" />
                        </div>
                    </div>
                </div>
            </Layout>
        );
    }

    if (!detail) {
        return (
            <Layout>
                <div className="flex flex-col items-center justify-center h-64 text-zinc-500">
                    <AlertCircle className="h-12 w-12 mb-4" />
                    <p className="text-lg">Optimization not found</p>
                    <Button variant="outline" onClick={() => navigate(-1)} className="mt-4">
                        <ArrowLeft className="h-4 w-4 mr-2" />
                        Go Back
                    </Button>
                </div>
            </Layout>
        );
    }

    return (
        <Layout>
            <div className="space-y-6 print:space-y-4" data-testid="optimization-detail-page">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                    <div>
                        <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => navigate(-1)}
                            className="mb-2 -ml-2 print:hidden"
                        >
                            <ArrowLeft className="h-4 w-4 mr-2" />
                            Back
                        </Button>
                        <h1 className="text-2xl font-bold text-white">{detail.title}</h1>
                        <p className="text-zinc-400 mt-1">
                            {detail.network_name} • {detail.brand_name}
                        </p>
                        
                        {/* Status Badges */}
                        <div className="flex flex-wrap gap-2 mt-3">
                            <Badge className={STATUS_CONFIG[detail.status]?.color || 'bg-zinc-500/20'}>
                                {STATUS_CONFIG[detail.status]?.label || detail.status}
                            </Badge>
                            {detail.complaint_status !== 'none' && (
                                <Badge className={COMPLAINT_STATUS_CONFIG[detail.complaint_status]?.color}>
                                    {COMPLAINT_STATUS_CONFIG[detail.complaint_status]?.label}
                                </Badge>
                            )}
                            {detail.is_blocked && (
                                <Badge variant="destructive" className="gap-1">
                                    <AlertCircle className="h-3 w-3" />
                                    Blocked
                                </Badge>
                            )}
                        </div>
                    </div>
                    
                    {/* Action Buttons */}
                    <div className="flex gap-2 print:hidden">
                        <Button variant="outline" size="sm" onClick={handleCopyLink} className="gap-2">
                            <Copy className="h-4 w-4" />
                            Copy Link
                        </Button>
                        <Button variant="outline" size="sm" onClick={handlePrint} className="gap-2">
                            <Printer className="h-4 w-4" />
                            Print
                        </Button>
                    </div>
                </div>

                <Separator />

                {/* Main Content Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left Column - Main Content */}
                    <div className="lg:col-span-2 space-y-6">
                        {/* Summary Section */}
                        <Card className="bg-card border-border">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <FileText className="h-5 w-5 text-blue-500" />
                                    Summary
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    <div>
                                        <p className="text-xs text-zinc-500 uppercase">Activity Type</p>
                                        <p className="text-white font-medium">{detail.activity_type_name || detail.activity_type}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-zinc-500 uppercase">Status</p>
                                        <p className="text-white font-medium">{STATUS_CONFIG[detail.status]?.label}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-zinc-500 uppercase">Created By</p>
                                        <p className="text-white font-medium">{detail.created_by?.display_name}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-zinc-500 uppercase">Created</p>
                                        <p className="text-white font-medium">{formatDate(detail.created_at)}</p>
                                    </div>
                                </div>
                                
                                {detail.closed_at && (
                                    <div className="grid grid-cols-2 gap-4 pt-2 border-t border-border">
                                        <div>
                                            <p className="text-xs text-zinc-500 uppercase">Closed By</p>
                                            <p className="text-emerald-400 font-medium">{detail.closed_by?.display_name}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-zinc-500 uppercase">Closed</p>
                                            <p className="text-emerald-400 font-medium">{formatDate(detail.closed_at)}</p>
                                        </div>
                                    </div>
                                )}
                                
                                <div className="pt-2 border-t border-border">
                                    <p className="text-xs text-zinc-500 uppercase mb-2">Description</p>
                                    <p className="text-zinc-300 whitespace-pre-wrap">{detail.description}</p>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Reason for Optimization */}
                        {detail.reason_note && (
                            <Card className="bg-amber-950/20 border-amber-900/30">
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2 text-amber-400">
                                        <FileText className="h-5 w-5" />
                                        Reason for Optimization
                                    </CardTitle>
                                    <CardDescription className="text-amber-300/70">
                                        Why this optimization was initiated
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <p className="text-zinc-300 whitespace-pre-wrap">{detail.reason_note}</p>
                                </CardContent>
                            </Card>
                        )}

                        {/* Scope & Targets */}
                        <Card className="bg-card border-border">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <Target className="h-5 w-5 text-emerald-500" />
                                    Scope & Targets
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <p className="text-xs text-zinc-500 uppercase">Affected Scope</p>
                                        <p className="text-white font-medium capitalize">{detail.affected_scope?.replace('_', ' ')}</p>
                                    </div>
                                    {detail.observed_impact && (
                                        <div>
                                            <p className="text-xs text-zinc-500 uppercase">Observed Impact</p>
                                            <Badge className={
                                                detail.observed_impact === 'positive' ? 'bg-emerald-500/20 text-emerald-400' :
                                                detail.observed_impact === 'negative' ? 'bg-red-500/20 text-red-400' :
                                                'bg-zinc-500/20 text-zinc-400'
                                            }>
                                                {detail.observed_impact}
                                            </Badge>
                                        </div>
                                    )}
                                </div>
                                
                                {detail.target_domains?.length > 0 && (
                                    <div>
                                        <p className="text-xs text-zinc-500 uppercase mb-2">Target Domains/Paths</p>
                                        <div className="flex flex-wrap gap-2">
                                            {detail.target_domains.map((d, i) => (
                                                <Badge key={i} variant="secondary">
                                                    <Globe className="h-3 w-3 mr-1" />
                                                    {d}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                
                                {detail.keywords?.length > 0 && (
                                    <div>
                                        <p className="text-xs text-zinc-500 uppercase mb-2">Keywords</p>
                                        <div className="flex flex-wrap gap-2">
                                            {detail.keywords.map((k, i) => (
                                                <Badge key={i} variant="outline">
                                                    <Tag className="h-3 w-3 mr-1" />
                                                    {k}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                
                                {detail.expected_impact?.length > 0 && (
                                    <div>
                                        <p className="text-xs text-zinc-500 uppercase mb-2">Expected Impact</p>
                                        <div className="flex flex-wrap gap-2">
                                            {detail.expected_impact.map((impact, i) => (
                                                <Badge key={i} className="bg-blue-500/20 text-blue-400">
                                                    <TrendingUp className="h-3 w-3 mr-1" />
                                                    {impact}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Reports & Timeline */}
                        {detail.report_urls?.length > 0 && (
                            <Card className="bg-card border-border">
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <Link2 className="h-5 w-5 text-blue-500" />
                                        Reports & Timeline
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-3">
                                        {detail.report_urls.map((report, i) => {
                                            const url = typeof report === 'string' ? report : report.url;
                                            const startDate = typeof report === 'object' ? report.start_date : null;
                                            const endDate = typeof report === 'object' ? report.end_date : null;
                                            
                                            return (
                                                <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/50 border border-border">
                                                    <a 
                                                        href={url} 
                                                        target="_blank" 
                                                        rel="noopener noreferrer"
                                                        className="text-blue-400 hover:text-blue-300 flex items-center gap-2 truncate flex-1"
                                                    >
                                                        <ExternalLink className="h-4 w-4 flex-shrink-0" />
                                                        {url}
                                                    </a>
                                                    {startDate && (
                                                        <span className="text-sm text-zinc-500 ml-4 flex-shrink-0">
                                                            {startDate} {endDate ? `→ ${endDate}` : ''}
                                                        </span>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Complaint Thread */}
                        {detail.complaints?.length > 0 && (
                            <Card className="bg-red-950/20 border-red-900/30">
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2 text-red-400">
                                        <AlertTriangle className="h-5 w-5" />
                                        Complaint Thread ({detail.complaints.length})
                                    </CardTitle>
                                    <CardDescription className="text-red-300/70">
                                        Issues raised against this optimization
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {detail.complaints.map((complaint, index) => {
                                        const isActive = complaint.status !== 'resolved';
                                        const isExpanded = expandedComplaints[complaint.id];
                                        const complaintNum = detail.complaints.length - index;
                                        
                                        return (
                                            <Collapsible 
                                                key={complaint.id} 
                                                open={isExpanded}
                                                onOpenChange={() => toggleComplaint(complaint.id)}
                                            >
                                                <div className={`rounded-lg border ${isActive ? 'border-red-500/50 bg-red-950/30' : 'border-zinc-700 bg-zinc-900/30'}`}>
                                                    <CollapsibleTrigger className="w-full p-4 flex items-center justify-between hover:bg-zinc-800/30">
                                                        <div className="flex items-center gap-3">
                                                            <Badge className={isActive ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'}>
                                                                Complaint #{complaintNum}
                                                            </Badge>
                                                            <Badge variant="outline">
                                                                {complaint.status}
                                                            </Badge>
                                                            {isActive && index === 0 && (
                                                                <Badge className="bg-amber-500/20 text-amber-400">
                                                                    Active
                                                                </Badge>
                                                            )}
                                                        </div>
                                                        {isExpanded ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                                                    </CollapsibleTrigger>
                                                    
                                                    <CollapsibleContent>
                                                        <div className="px-4 pb-4 space-y-4">
                                                            <Separator />
                                                            
                                                            <div>
                                                                <p className="text-sm text-zinc-500 mb-2">
                                                                    Submitted by <span className="text-white">{complaint.created_by?.display_name}</span> on {formatDate(complaint.created_at)}
                                                                </p>
                                                                <p className="text-zinc-300 whitespace-pre-wrap bg-black/30 p-3 rounded">{complaint.reason}</p>
                                                            </div>
                                                            
                                                            {complaint.responsible_users?.length > 0 && (
                                                                <div>
                                                                    <p className="text-xs text-zinc-500 uppercase mb-2">Responsible Users</p>
                                                                    <div className="flex flex-wrap gap-2">
                                                                        {complaint.responsible_users.map(u => (
                                                                            <Badge key={u.id} variant="secondary">
                                                                                <User className="h-3 w-3 mr-1" />
                                                                                {u.name || u.email}
                                                                            </Badge>
                                                                        ))}
                                                                    </div>
                                                                </div>
                                                            )}
                                                            
                                                            {complaint.resolved_at && (
                                                                <div className="p-4 rounded-lg bg-emerald-950/30 border border-emerald-900/30">
                                                                    <div className="flex items-center gap-2 mb-2">
                                                                        <CheckCircle className="h-4 w-4 text-emerald-400" />
                                                                        <span className="text-emerald-400 font-medium">Resolved</span>
                                                                    </div>
                                                                    <p className="text-sm text-zinc-400">
                                                                        By {complaint.resolved_by?.display_name} on {formatDate(complaint.resolved_at)}
                                                                    </p>
                                                                    {complaint.resolution_note && (
                                                                        <p className="text-zinc-300 mt-2 whitespace-pre-wrap">{complaint.resolution_note}</p>
                                                                    )}
                                                                    {complaint.time_to_resolution_hours && (
                                                                        <p className="text-xs text-zinc-500 mt-2">
                                                                            Resolution time: {complaint.time_to_resolution_hours.toFixed(1)} hours
                                                                        </p>
                                                                    )}
                                                                </div>
                                                            )}
                                                            
                                                            {/* Resolve Form (Super Admin only, active complaints only) */}
                                                            {isSuperAdmin && isActive && (
                                                                <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-700 print:hidden">
                                                                    <Label className="text-sm text-zinc-300 mb-3 block font-medium">Resolve Complaint</Label>
                                                                    <Textarea
                                                                        value={resolutionNote}
                                                                        onChange={(e) => setResolutionNote(e.target.value)}
                                                                        placeholder="Resolution note (min 10 chars)..."
                                                                        className="bg-black border-border min-h-[100px] mb-3"
                                                                    />
                                                                    <div className="flex items-center gap-2 mb-3">
                                                                        <input 
                                                                            type="checkbox" 
                                                                            id={`mark-complete-${complaint.id}`}
                                                                            checked={markComplete}
                                                                            onChange={(e) => setMarkComplete(e.target.checked)}
                                                                            className="rounded"
                                                                        />
                                                                        <Label htmlFor={`mark-complete-${complaint.id}`} className="text-sm text-zinc-400">
                                                                            Also mark optimization as Completed
                                                                        </Label>
                                                                    </div>
                                                                    <Button 
                                                                        onClick={() => handleResolveComplaint(complaint.id)}
                                                                        disabled={resolving || resolutionNote.trim().length < 10}
                                                                        className="gap-2"
                                                                    >
                                                                        {resolving && <Loader2 className="h-4 w-4 animate-spin" />}
                                                                        <CheckCircle className="h-4 w-4" />
                                                                        Resolve Complaint
                                                                    </Button>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </CollapsibleContent>
                                                </div>
                                            </Collapsible>
                                        );
                                    })}
                                </CardContent>
                            </Card>
                        )}
                    </div>

                    {/* Right Column - Sidebar */}
                    <div className="space-y-6">
                        {/* Team Responses */}
                        <Card className="bg-card border-border">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <MessageSquare className="h-5 w-5 text-blue-500" />
                                    Team Responses ({detail.responses?.length || 0})
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {detail.responses?.length > 0 ? (
                                    <div className="space-y-3 max-h-[400px] overflow-y-auto">
                                        {detail.responses.map((response) => (
                                            <div key={response.id} className="p-3 rounded-lg bg-zinc-900/50 border border-border">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <User className="h-4 w-4 text-zinc-500" />
                                                    <span className="text-sm text-zinc-300 font-medium">{response.created_by?.display_name}</span>
                                                </div>
                                                <p className="text-xs text-zinc-500 mb-2">{formatDate(response.created_at)}</p>
                                                <p className="text-sm text-zinc-300 whitespace-pre-wrap">{response.note}</p>
                                                {response.report_urls?.length > 0 && (
                                                    <div className="mt-2 flex flex-wrap gap-2">
                                                        {response.report_urls.map((url, i) => (
                                                            <a 
                                                                key={i}
                                                                href={url}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                                                            >
                                                                <ExternalLink className="h-3 w-3" />
                                                                Evidence
                                                            </a>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-zinc-500 italic text-center py-4">No responses yet</p>
                                )}
                                
                                {/* Add Response Form */}
                                {isAdmin && detail.complaint_status !== 'none' && detail.status !== 'completed' && (
                                    <div className="pt-4 border-t border-border print:hidden">
                                        <Label className="text-sm text-blue-300 mb-2 block flex items-center gap-2">
                                            <Send className="h-4 w-4" />
                                            Add Response
                                        </Label>
                                        <div className="space-y-3">
                                            <div>
                                                <div className="flex justify-between mb-1">
                                                    <span className="text-xs text-zinc-500">Note</span>
                                                    <span className={`text-xs ${responseNote.length >= 20 && responseNote.length <= 2000 ? 'text-green-400' : 'text-amber-400'}`}>
                                                        {responseNote.length}/2000
                                                    </span>
                                                </div>
                                                <Textarea
                                                    value={responseNote}
                                                    onChange={(e) => setResponseNote(e.target.value)}
                                                    placeholder="Explain what was done (min 20 chars)..."
                                                    className="bg-black border-border min-h-[100px]"
                                                />
                                            </div>
                                            
                                            <div>
                                                <Label className="text-xs text-zinc-500 mb-1 block">Evidence URLs</Label>
                                                <div className="flex gap-2">
                                                    <Input
                                                        value={responseUrlInput}
                                                        onChange={(e) => setResponseUrlInput(e.target.value)}
                                                        onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addResponseUrl())}
                                                        placeholder="https://..."
                                                        className="bg-black border-border text-sm"
                                                    />
                                                    <Button variant="outline" size="sm" onClick={addResponseUrl}>Add</Button>
                                                </div>
                                                {responseUrls.length > 0 && (
                                                    <div className="flex flex-wrap gap-1 mt-2">
                                                        {responseUrls.map((url, i) => (
                                                            <Badge key={i} variant="secondary" className="text-xs pr-1">
                                                                {url.slice(0, 25)}...
                                                                <button onClick={() => removeResponseUrl(url)} className="ml-1 hover:text-red-400">×</button>
                                                            </Badge>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                            
                                            <Button 
                                                onClick={handleSubmitResponse}
                                                disabled={submittingResponse || responseNote.trim().length < 20 || responseNote.trim().length > 2000}
                                                className="w-full gap-2"
                                            >
                                                {submittingResponse && <Loader2 className="h-4 w-4 animate-spin" />}
                                                <Send className="h-4 w-4" />
                                                Submit
                                            </Button>
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Final Closure (Super Admin only) */}
                        {isSuperAdmin && detail.status !== 'completed' && (
                            <Card className={`border print:hidden ${detail.is_blocked ? 'bg-red-950/20 border-red-900/30' : 'bg-emerald-950/20 border-emerald-900/30'}`}>
                                <CardHeader>
                                    <CardTitle className={`flex items-center gap-2 ${detail.is_blocked ? 'text-red-400' : 'text-emerald-400'}`}>
                                        {detail.is_blocked ? <AlertCircle className="h-5 w-5" /> : <CheckCircle className="h-5 w-5" />}
                                        Final Closure
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    {detail.is_blocked ? (
                                        <div className="text-sm">
                                            <p className="text-red-300 font-medium">{detail.blocked_reason}</p>
                                            <p className="text-zinc-500 mt-2">Resolve all complaints before closing.</p>
                                        </div>
                                    ) : (
                                        <div className="space-y-3">
                                            <Textarea
                                                value={finalNote}
                                                onChange={(e) => setFinalNote(e.target.value)}
                                                placeholder="Final note (optional)..."
                                                className="bg-black border-border min-h-[80px]"
                                            />
                                            <Button 
                                                onClick={handleCloseOptimization}
                                                disabled={closing}
                                                className="w-full gap-2 bg-emerald-600 hover:bg-emerald-700"
                                            >
                                                {closing && <Loader2 className="h-4 w-4 animate-spin" />}
                                                <CheckCircle className="h-4 w-4" />
                                                Mark as Completed
                                            </Button>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        )}

                        {/* Completed Badge */}
                        {detail.status === 'completed' && (
                            <Card className="bg-emerald-950/20 border-emerald-900/30">
                                <CardContent className="p-6 text-center">
                                    <CheckCircle className="h-12 w-12 text-emerald-500 mx-auto mb-3" />
                                    <p className="text-emerald-400 font-medium text-lg">Optimization Completed</p>
                                    {detail.closed_by && (
                                        <p className="text-zinc-400 text-sm mt-1">
                                            by {detail.closed_by.display_name}
                                        </p>
                                    )}
                                    {detail.closed_at && (
                                        <p className="text-zinc-500 text-xs mt-1">
                                            {formatDate(detail.closed_at)}
                                        </p>
                                    )}
                                </CardContent>
                            </Card>
                        )}
                    </div>
                </div>
            </div>
        </Layout>
    );
}
