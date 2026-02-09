import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { optimizationsAPI } from '../lib/api';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../components/ui/sheet';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../components/ui/collapsible';
import { Skeleton } from '../components/ui/skeleton';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import { 
    X, 
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
    Maximize2,
    Loader2,
    AlertCircle,
    Tag,
    TrendingUp,
    Globe,
    Flag
} from 'lucide-react';
import ComplaintTimeline from './ComplaintTimeline';

const STATUS_CONFIG = {
    planned: { label: 'Planned', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
    in_progress: { label: 'In Progress', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
    completed: { label: 'Completed', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
    reverted: { label: 'Reverted', color: 'bg-red-500/20 text-red-400 border-red-500/30' }
};

const COMPLAINT_STATUS_CONFIG = {
    none: { label: 'No Complaints', color: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30', icon: CheckCircle },
    complained: { label: 'Complained', color: 'bg-red-500/20 text-red-400 border-red-500/30', icon: AlertTriangle },
    under_review: { label: 'Under Review', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', icon: Clock },
    resolved: { label: 'Resolved', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', icon: CheckCircle }
};

const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', { 
        year: 'numeric', month: 'short', day: 'numeric', 
        hour: '2-digit', minute: '2-digit' 
    });
};

export default function OptimizationDetailDrawer({ 
    optimizationId, 
    isOpen, 
    onClose, 
    onUpdate,
    networkId 
}) {
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
        if (isOpen && optimizationId) {
            loadDetail();
        }
    }, [isOpen, optimizationId]);

    const loadDetail = async () => {
        setLoading(true);
        try {
            const response = await optimizationsAPI.getDetail(optimizationId);
            setDetail(response.data);
            // Auto-expand the active complaint
            if (response.data.active_complaint) {
                setExpandedComplaints({ [response.data.active_complaint.id]: true });
            }
        } catch (err) {
            console.error('Failed to load optimization detail:', err);
            toast.error('Failed to load optimization details');
        } finally {
            setLoading(false);
        }
    };

    const handleCopyLink = () => {
        const url = `${window.location.origin}/groups/${networkId}?optimization_id=${optimizationId}`;
        navigator.clipboard.writeText(url);
        toast.success('Link copied to clipboard');
    };

    const handleOpenFullView = () => {
        window.open(`/optimizations/${optimizationId}`, '_blank');
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
            if (onUpdate) onUpdate();
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
            if (onUpdate) onUpdate();
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
            if (onUpdate) onUpdate();
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

    if (!isOpen) return null;

    return (
        <Sheet open={isOpen} onOpenChange={onClose}>
            <SheetContent 
                side="right" 
                className="w-full sm:w-[600px] lg:w-[700px] overflow-y-auto bg-black border-l border-border"
                data-testid="optimization-detail-drawer"
            >
                {loading ? (
                    <div className="space-y-4 pt-6">
                        <Skeleton className="h-8 w-3/4" />
                        <Skeleton className="h-4 w-1/2" />
                        <Skeleton className="h-32 w-full" />
                        <Skeleton className="h-24 w-full" />
                        <Skeleton className="h-48 w-full" />
                    </div>
                ) : detail ? (
                    <div className="space-y-6 pb-8">
                        {/* Header */}
                        <SheetHeader className="space-y-3">
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex-1 min-w-0">
                                    <SheetTitle className="text-xl text-white pr-8 line-clamp-2">
                                        {detail.title}
                                    </SheetTitle>
                                    <SheetDescription className="mt-1">
                                        {detail.network_name} • {detail.brand_name}
                                    </SheetDescription>
                                </div>
                            </div>
                            
                            {/* Action Buttons */}
                            <div className="flex gap-2 flex-wrap">
                                <Button 
                                    variant="outline" 
                                    size="sm" 
                                    onClick={handleCopyLink}
                                    className="gap-2"
                                    data-testid="copy-link-btn"
                                >
                                    <Copy className="h-4 w-4" />
                                    Copy Link
                                </Button>
                                <Button 
                                    variant="outline" 
                                    size="sm" 
                                    onClick={handleOpenFullView}
                                    className="gap-2"
                                    data-testid="open-full-view-btn"
                                >
                                    <Maximize2 className="h-4 w-4" />
                                    Full View
                                </Button>
                            </div>
                            
                            {/* Status Badges */}
                            <div className="flex flex-wrap gap-2">
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
                        </SheetHeader>

                        <Separator />

                        {/* Section A: Summary */}
                        <Card className="bg-zinc-900/50 border-border">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                                    <FileText className="h-4 w-4" />
                                    Summary
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div>
                                        <p className="text-zinc-500">Activity Type</p>
                                        <p className="text-white">{detail.activity_type_name || detail.activity_type}</p>
                                    </div>
                                    <div>
                                        <p className="text-zinc-500">Status</p>
                                        <p className="text-white">{STATUS_CONFIG[detail.status]?.label}</p>
                                    </div>
                                    <div>
                                        <p className="text-zinc-500">Created By</p>
                                        <p className="text-white">{detail.created_by?.display_name}</p>
                                    </div>
                                    <div>
                                        <p className="text-zinc-500">Created</p>
                                        <p className="text-white">{formatDate(detail.created_at)}</p>
                                    </div>
                                    {detail.closed_at && (
                                        <>
                                            <div>
                                                <p className="text-zinc-500">Closed By</p>
                                                <p className="text-white">{detail.closed_by?.display_name}</p>
                                            </div>
                                            <div>
                                                <p className="text-zinc-500">Closed</p>
                                                <p className="text-white">{formatDate(detail.closed_at)}</p>
                                            </div>
                                        </>
                                    )}
                                </div>
                                <div>
                                    <p className="text-zinc-500 text-sm mb-1">Description</p>
                                    <p className="text-zinc-300 text-sm whitespace-pre-wrap">{detail.description}</p>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Section B: Reason & Intent */}
                        {detail.reason_note && (
                            <Card className="bg-amber-950/20 border-amber-900/30">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm text-amber-400 flex items-center gap-2">
                                        <FileText className="h-4 w-4" />
                                        Reason for Optimization
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <p className="text-zinc-300 text-sm whitespace-pre-wrap">{detail.reason_note}</p>
                                </CardContent>
                            </Card>
                        )}

                        {/* Section C: Scope & Targets */}
                        <Card className="bg-zinc-900/50 border-border">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                                    <Target className="h-4 w-4" />
                                    Scope & Targets
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div>
                                        <p className="text-zinc-500">Affected Scope</p>
                                        <p className="text-white capitalize">{detail.affected_scope?.replace('_', ' ')}</p>
                                    </div>
                                    {detail.observed_impact && (
                                        <div>
                                            <p className="text-zinc-500">Observed Impact</p>
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
                                        <p className="text-zinc-500 text-sm mb-1">Target Domains/Paths</p>
                                        <div className="flex flex-wrap gap-1">
                                            {detail.target_domains.map((d, i) => (
                                                <Badge key={i} variant="secondary" className="text-xs">
                                                    <Globe className="h-3 w-3 mr-1" />
                                                    {d}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                
                                {detail.keywords?.length > 0 && (
                                    <div>
                                        <p className="text-zinc-500 text-sm mb-1">Keywords</p>
                                        <div className="flex flex-wrap gap-1">
                                            {detail.keywords.map((k, i) => (
                                                <Badge key={i} variant="outline" className="text-xs">
                                                    <Tag className="h-3 w-3 mr-1" />
                                                    {k}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                
                                {detail.expected_impact?.length > 0 && (
                                    <div>
                                        <p className="text-zinc-500 text-sm mb-1">Expected Impact</p>
                                        <div className="flex flex-wrap gap-1">
                                            {detail.expected_impact.map((impact, i) => (
                                                <Badge key={i} className="bg-blue-500/20 text-blue-400 text-xs">
                                                    <TrendingUp className="h-3 w-3 mr-1" />
                                                    {impact}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Section D: Reports & Timeline */}
                        {detail.report_urls?.length > 0 && (
                            <Card className="bg-zinc-900/50 border-border">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                                        <Link2 className="h-4 w-4" />
                                        Reports & Timeline
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-2">
                                        {detail.report_urls.map((report, i) => {
                                            const url = typeof report === 'string' ? report : report.url;
                                            const startDate = typeof report === 'object' ? report.start_date : null;
                                            const endDate = typeof report === 'object' ? report.end_date : null;
                                            
                                            return (
                                                <div key={i} className="flex items-center justify-between p-2 rounded bg-zinc-800/50">
                                                    <a 
                                                        href={url} 
                                                        target="_blank" 
                                                        rel="noopener noreferrer"
                                                        className="text-blue-400 hover:text-blue-300 text-sm truncate flex-1 flex items-center gap-2"
                                                    >
                                                        <ExternalLink className="h-4 w-4 flex-shrink-0" />
                                                        {url.length > 50 ? url.slice(0, 50) + '...' : url}
                                                    </a>
                                                    {startDate && (
                                                        <span className="text-xs text-zinc-500 ml-2">
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

                        {/* Section E: Complaint Timeline (Visual) */}
                        {(detail.complaints?.length > 0 || detail.responses?.length > 0) && (
                            <ComplaintTimeline 
                                complaints={detail.complaints || []}
                                responses={detail.responses || []}
                            />
                        )}

                        {/* Section F: Complaint Thread (Detailed) */}
                        {detail.complaints?.length > 0 && (
                            <Card className="bg-red-950/20 border-red-900/30">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm text-red-400 flex items-center gap-2">
                                        <AlertTriangle className="h-4 w-4" />
                                        Complaint Thread ({detail.complaints.length})
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-3">
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
                                                    <CollapsibleTrigger className="w-full p-3 flex items-center justify-between hover:bg-zinc-800/30">
                                                        <div className="flex items-center gap-2">
                                                            <Badge className={isActive ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'}>
                                                                Complaint #{complaintNum}
                                                            </Badge>
                                                            <Badge variant="outline" className="text-xs">
                                                                {complaint.status}
                                                            </Badge>
                                                            {isActive && index === 0 && (
                                                                <Badge className="bg-amber-500/20 text-amber-400 text-xs">
                                                                    Active
                                                                </Badge>
                                                            )}
                                                        </div>
                                                        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                                                    </CollapsibleTrigger>
                                                    
                                                    <CollapsibleContent>
                                                        <div className="px-3 pb-3 space-y-3">
                                                            <Separator />
                                                            
                                                            <div className="text-sm">
                                                                <p className="text-zinc-500">
                                                                    By {complaint.created_by?.display_name} • {formatDate(complaint.created_at)}
                                                                </p>
                                                                <p className="text-zinc-300 mt-2 whitespace-pre-wrap">{complaint.reason}</p>
                                                            </div>
                                                            
                                                            {complaint.responsible_users?.length > 0 && (
                                                                <div>
                                                                    <p className="text-zinc-500 text-xs mb-1">Responsible Users:</p>
                                                                    <div className="flex flex-wrap gap-1">
                                                                        {complaint.responsible_users.map(u => (
                                                                            <Badge key={u.id} variant="secondary" className="text-xs">
                                                                                @{u.name || u.email}
                                                                            </Badge>
                                                                        ))}
                                                                    </div>
                                                                </div>
                                                            )}
                                                            
                                                            {complaint.resolved_at && (
                                                                <div className="p-2 rounded bg-emerald-950/30 border border-emerald-900/30">
                                                                    <p className="text-xs text-emerald-400">
                                                                        Resolved by {complaint.resolved_by?.display_name} • {formatDate(complaint.resolved_at)}
                                                                    </p>
                                                                    {complaint.resolution_note && (
                                                                        <p className="text-sm text-zinc-300 mt-1">{complaint.resolution_note}</p>
                                                                    )}
                                                                    {complaint.time_to_resolution_hours && (
                                                                        <p className="text-xs text-zinc-500 mt-1">
                                                                            Resolution time: {complaint.time_to_resolution_hours.toFixed(1)} hours
                                                                        </p>
                                                                    )}
                                                                </div>
                                                            )}
                                                            
                                                            {/* Resolve Form (Super Admin only, active complaints only) */}
                                                            {isSuperAdmin && isActive && (
                                                                <div className="mt-3 p-3 rounded bg-zinc-900 border border-zinc-700">
                                                                    <Label className="text-sm text-zinc-300 mb-2 block">Resolve Complaint</Label>
                                                                    <Textarea
                                                                        value={resolutionNote}
                                                                        onChange={(e) => setResolutionNote(e.target.value)}
                                                                        placeholder="Resolution note (min 10 chars)..."
                                                                        className="bg-black border-border min-h-[80px] mb-2"
                                                                    />
                                                                    <div className="flex items-center gap-2 mb-2">
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
                                                                        size="sm" 
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

                        {/* Section F: Team Responses */}
                        <Card className="bg-zinc-900/50 border-border">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                                    <MessageSquare className="h-4 w-4" />
                                    Team Responses ({detail.responses?.length || 0})
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {/* Existing Responses */}
                                {detail.responses?.length > 0 ? (
                                    <div className="space-y-2">
                                        {detail.responses.map((response) => (
                                            <div key={response.id} className="p-3 rounded bg-zinc-800/50 border border-zinc-700">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <User className="h-4 w-4 text-zinc-500" />
                                                    <span className="text-sm text-zinc-300">{response.created_by?.display_name}</span>
                                                    <span className="text-xs text-zinc-500">{formatDate(response.created_at)}</span>
                                                </div>
                                                <p className="text-sm text-zinc-300 whitespace-pre-wrap">{response.note}</p>
                                                {response.report_urls?.length > 0 && (
                                                    <div className="mt-2 flex flex-wrap gap-1">
                                                        {response.report_urls.map((url, i) => (
                                                            <a 
                                                                key={i}
                                                                href={url}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                                                            >
                                                                <ExternalLink className="h-3 w-3" />
                                                                Report
                                                            </a>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-zinc-500 italic">No responses yet</p>
                                )}
                                
                                {/* Add Response Form (Admin/Super Admin only) */}
                                {isAdmin && detail.complaint_status !== 'none' && detail.status !== 'completed' && (
                                    <div className="mt-4 p-3 rounded border border-blue-500/30 bg-blue-950/20">
                                        <Label className="text-sm text-blue-300 mb-2 block flex items-center gap-2">
                                            <Send className="h-4 w-4" />
                                            Add Team Response
                                        </Label>
                                        <div className="space-y-3">
                                            <div>
                                                <div className="flex justify-between mb-1">
                                                    <span className="text-xs text-zinc-500">Response Note</span>
                                                    <span className={`text-xs ${responseNote.length >= 20 && responseNote.length <= 2000 ? 'text-green-400' : 'text-amber-400'}`}>
                                                        {responseNote.length}/2000
                                                    </span>
                                                </div>
                                                <Textarea
                                                    value={responseNote}
                                                    onChange={(e) => setResponseNote(e.target.value)}
                                                    placeholder="Explain what was done to address the complaint (min 20 chars, max 2000 chars)..."
                                                    className="bg-black border-border min-h-[100px]"
                                                />
                                            </div>
                                            
                                            <div>
                                                <Label className="text-xs text-zinc-500 mb-1 block">Evidence URLs (optional)</Label>
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
                                                                {url.slice(0, 30)}...
                                                                <button onClick={() => removeResponseUrl(url)} className="ml-1 hover:text-red-400">×</button>
                                                            </Badge>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                            
                                            <Button 
                                                onClick={handleSubmitResponse}
                                                disabled={submittingResponse || responseNote.trim().length < 20 || responseNote.trim().length > 2000}
                                                className="gap-2"
                                            >
                                                {submittingResponse && <Loader2 className="h-4 w-4 animate-spin" />}
                                                <Send className="h-4 w-4" />
                                                Submit Response
                                            </Button>
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Section G: Final Closure (Super Admin only) */}
                        {isSuperAdmin && detail.status !== 'completed' && (
                            <Card className={`border ${detail.is_blocked ? 'bg-red-950/20 border-red-900/30' : 'bg-emerald-950/20 border-emerald-900/30'}`}>
                                <CardHeader className="pb-2">
                                    <CardTitle className={`text-sm flex items-center gap-2 ${detail.is_blocked ? 'text-red-400' : 'text-emerald-400'}`}>
                                        {detail.is_blocked ? <AlertCircle className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
                                        Final Closure
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    {detail.is_blocked ? (
                                        <div className="text-sm text-red-300">
                                            <p className="font-medium">{detail.blocked_reason}</p>
                                            <p className="text-zinc-500 mt-2">Resolve all complaints before closing this optimization.</p>
                                        </div>
                                    ) : (
                                        <div className="space-y-3">
                                            <Textarea
                                                value={finalNote}
                                                onChange={(e) => setFinalNote(e.target.value)}
                                                placeholder="Final note (optional)..."
                                                className="bg-black border-border min-h-[60px]"
                                            />
                                            <Button 
                                                onClick={handleCloseOptimization}
                                                disabled={closing}
                                                className="gap-2 bg-emerald-600 hover:bg-emerald-700"
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
                    </div>
                ) : (
                    <div className="flex items-center justify-center h-64 text-zinc-500">
                        <p>Optimization not found</p>
                    </div>
                )}
            </SheetContent>
        </Sheet>
    );
}
