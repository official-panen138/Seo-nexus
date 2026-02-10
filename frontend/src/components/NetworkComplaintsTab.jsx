import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../lib/auth';
import { projectComplaintsAPI, optimizationsAPI } from '../lib/api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Badge } from './ui/badge';
import { Skeleton } from './ui/skeleton';
import { ScrollArea } from './ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from './ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { toast } from 'sonner';
import {
    AlertCircle,
    MessageSquare,
    Plus,
    Loader2,
    User,
    Clock,
    CheckCircle,
    XCircle,
    AlertTriangle,
    FileText,
    ExternalLink,
    ChevronDown,
    ChevronUp,
    Send,
    Search
} from 'lucide-react';
import axios from 'axios';

// Create API instance for user search
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

const PRIORITY_OPTIONS = [
    { value: 'low', label: 'Low', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
    { value: 'medium', label: 'Medium', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
    { value: 'high', label: 'High', color: 'bg-red-500/20 text-red-400 border-red-500/30' }
];

const CATEGORY_OPTIONS = [
    { value: 'communication', label: 'Communication' },
    { value: 'deadline', label: 'Deadline' },
    { value: 'quality', label: 'Quality' },
    { value: 'process', label: 'Process' },
    { value: 'other', label: 'Other' }
];

const STATUS_BADGES = {
    open: { label: 'Open', className: 'bg-red-500/20 text-red-400 border-red-500/30' },
    under_review: { label: 'Under Review', className: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
    resolved: { label: 'Resolved', className: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
    dismissed: { label: 'Dismissed', className: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30' }
};

export function NetworkComplaintsTab({ networkId, brandId }) {
    const { user } = useAuth();
    const [activeSubTab, setActiveSubTab] = useState('project');
    const [loading, setLoading] = useState(true);
    const [projectComplaints, setProjectComplaints] = useState([]);
    const [optimizationComplaints, setOptimizationComplaints] = useState([]);
    
    // Create dialog state
    const [createDialogOpen, setCreateDialogOpen] = useState(false);
    const [creating, setCreating] = useState(false);
    const [form, setForm] = useState({
        reason: '',
        priority: 'medium',
        category: '',
        report_urls: '',
        responsible_user_ids: []
    });
    
    // User search state
    const [userSearchQuery, setUserSearchQuery] = useState('');
    const [userSearchResults, setUserSearchResults] = useState([]);
    const [selectedUsers, setSelectedUsers] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    
    // Response dialog state
    const [respondDialogOpen, setRespondDialogOpen] = useState(false);
    const [selectedComplaint, setSelectedComplaint] = useState(null);
    const [responseNote, setResponseNote] = useState('');
    const [responding, setResponding] = useState(false);
    
    // Resolve dialog state
    const [resolveDialogOpen, setResolveDialogOpen] = useState(false);
    const [resolutionNote, setResolutionNote] = useState('');
    const [resolving, setResolving] = useState(false);
    
    // Expanded complaint state
    const [expandedComplaintId, setExpandedComplaintId] = useState(null);

    const isSuperAdmin = user?.role === 'super_admin';

    useEffect(() => {
        if (networkId) {
            loadComplaints();
        }
    }, [networkId]);

    const loadComplaints = async () => {
        setLoading(true);
        try {
            // Load project-level complaints
            const projectRes = await projectComplaintsAPI.getAll(networkId);
            setProjectComplaints(projectRes.data || []);
        } catch (err) {
            console.error('Failed to load project complaints:', err);
        }
        
        try {
            // Load optimization complaints (from optimizations with complaints)
            const optRes = await optimizationsAPI.getAll(networkId, { limit: 100 });
            const complainedOpts = (optRes.data?.data || []).filter(o => 
                o.complaint_status && o.complaint_status !== 'none'
            );
            setOptimizationComplaints(complainedOpts);
        } catch (err) {
            console.error('Failed to load optimization complaints:', err);
        }
        
        setLoading(false);
    };

    // Debounced user search
    const searchUsers = useCallback(async (query) => {
        if (query.length < 2) {
            setUserSearchResults([]);
            return;
        }
        setIsSearching(true);
        try {
            const res = await apiV3.get('/users/search', { params: { q: query, network_id: networkId } });
            setUserSearchResults(res.data.results || []);
        } catch (err) {
            console.error('User search failed:', err);
        } finally {
            setIsSearching(false);
        }
    }, [networkId]);

    const handleUserSearchChange = (e) => {
        const value = e.target.value;
        setUserSearchQuery(value);
        if (value.length >= 2) {
            searchUsers(value);
        } else {
            setUserSearchResults([]);
        }
    };

    const addUser = (userToAdd) => {
        if (!selectedUsers.find(u => u.id === userToAdd.id)) {
            setSelectedUsers([...selectedUsers, userToAdd]);
            setForm(prev => ({
                ...prev,
                responsible_user_ids: [...prev.responsible_user_ids, userToAdd.id]
            }));
        }
        setUserSearchQuery('');
        setUserSearchResults([]);
    };

    const removeUser = (userId) => {
        setSelectedUsers(selectedUsers.filter(u => u.id !== userId));
        setForm(prev => ({
            ...prev,
            responsible_user_ids: prev.responsible_user_ids.filter(id => id !== userId)
        }));
    };

    const handleCreateComplaint = async () => {
        if (form.reason.trim().length < 10) {
            toast.error('Complaint reason must be at least 10 characters');
            return;
        }

        setCreating(true);
        try {
            const payload = {
                reason: form.reason.trim(),
                priority: form.priority,
                category: form.category || null,
                report_urls: form.report_urls.split('\n').filter(url => url.trim()),
                responsible_user_ids: form.responsible_user_ids
            };
            
            await projectComplaintsAPI.create(networkId, payload);
            toast.success('Project complaint created');
            setCreateDialogOpen(false);
            resetForm();
            loadComplaints();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to create complaint');
        } finally {
            setCreating(false);
        }
    };

    const resetForm = () => {
        setForm({
            reason: '',
            priority: 'medium',
            category: '',
            report_urls: '',
            responsible_user_ids: []
        });
        setSelectedUsers([]);
        setUserSearchQuery('');
    };

    const handleRespond = async () => {
        if (responseNote.trim().length < 20) {
            toast.error('Response must be at least 20 characters');
            return;
        }

        setResponding(true);
        try {
            await projectComplaintsAPI.respond(networkId, selectedComplaint.id, {
                note: responseNote.trim()
            });
            toast.success('Response added');
            setRespondDialogOpen(false);
            setResponseNote('');
            setSelectedComplaint(null);
            loadComplaints();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to add response');
        } finally {
            setResponding(false);
        }
    };

    const handleResolve = async () => {
        if (resolutionNote.trim().length < 10) {
            toast.error('Resolution note must be at least 10 characters');
            return;
        }

        setResolving(true);
        try {
            await projectComplaintsAPI.resolve(networkId, selectedComplaint.id, {
                resolution_note: resolutionNote.trim()
            });
            toast.success('Complaint resolved');
            setResolveDialogOpen(false);
            setResolutionNote('');
            setSelectedComplaint(null);
            loadComplaints();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to resolve complaint');
        } finally {
            setResolving(false);
        }
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const openRespond = (complaint) => {
        setSelectedComplaint(complaint);
        setResponseNote('');
        setRespondDialogOpen(true);
    };

    const openResolve = (complaint) => {
        setSelectedComplaint(complaint);
        setResolutionNote('');
        setResolveDialogOpen(true);
    };

    if (loading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-32 w-full" />
                <Skeleton className="h-32 w-full" />
            </div>
        );
    }

    const openCount = projectComplaints.filter(c => c.status === 'open' || c.status === 'under_review').length;
    const optOpenCount = optimizationComplaints.filter(o => 
        o.complaint_status === 'complained' || o.complaint_status === 'under_review'
    ).length;

    return (
        <div className="space-y-6" data-testid="network-complaints-tab">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                        <AlertCircle className="h-5 w-5 text-red-400" />
                        Network Complaints
                    </h3>
                    <p className="text-sm text-zinc-500 mt-1">
                        View and manage complaints for this SEO network
                    </p>
                </div>
                {isSuperAdmin && (
                    <Button
                        onClick={() => setCreateDialogOpen(true)}
                        className="bg-red-600 hover:bg-red-700"
                        data-testid="create-project-complaint-btn"
                    >
                        <Plus className="h-4 w-4 mr-2" />
                        New Project Complaint
                    </Button>
                )}
            </div>

            {/* Sub-tabs */}
            <Tabs value={activeSubTab} onValueChange={setActiveSubTab}>
                <TabsList className="bg-card border border-border">
                    <TabsTrigger value="project" className="relative" data-testid="project-complaints-tab">
                        <FileText className="h-4 w-4 mr-2" />
                        Project-Level
                        {openCount > 0 && (
                            <Badge className="ml-2 h-5 min-w-[20px] bg-red-500/20 text-red-400 border-red-500/30">
                                {openCount}
                            </Badge>
                        )}
                    </TabsTrigger>
                    <TabsTrigger value="optimization" className="relative" data-testid="optimization-complaints-tab">
                        <MessageSquare className="h-4 w-4 mr-2" />
                        Optimization
                        {optOpenCount > 0 && (
                            <Badge className="ml-2 h-5 min-w-[20px] bg-amber-500/20 text-amber-400 border-amber-500/30">
                                {optOpenCount}
                            </Badge>
                        )}
                    </TabsTrigger>
                </TabsList>

                {/* Project-Level Complaints */}
                <TabsContent value="project" className="mt-4">
                    {projectComplaints.length === 0 ? (
                        <Card className="bg-card border-border">
                            <CardContent className="py-12 text-center">
                                <CheckCircle className="h-12 w-12 text-emerald-500 mx-auto mb-3" />
                                <p className="text-zinc-400">No project-level complaints</p>
                                <p className="text-sm text-zinc-600 mt-1">
                                    Project complaints are network-wide issues not tied to specific optimizations
                                </p>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-4">
                            {projectComplaints.map((complaint) => {
                                const statusBadge = STATUS_BADGES[complaint.status] || STATUS_BADGES.open;
                                const priorityOpt = PRIORITY_OPTIONS.find(p => p.value === complaint.priority);
                                const isExpanded = expandedComplaintId === complaint.id;
                                
                                return (
                                    <Card 
                                        key={complaint.id} 
                                        className={`bg-card border-border ${complaint.status === 'open' ? 'border-red-500/30' : ''}`}
                                        data-testid={`project-complaint-${complaint.id}`}
                                    >
                                        <CardContent className="pt-4">
                                            {/* Header */}
                                            <div className="flex items-start justify-between mb-3">
                                                <div className="flex items-center gap-3">
                                                    <AlertCircle className={`h-5 w-5 ${
                                                        complaint.status === 'resolved' ? 'text-emerald-400' : 'text-red-400'
                                                    }`} />
                                                    <div>
                                                        <div className="flex items-center gap-2">
                                                            <Badge className={statusBadge.className}>
                                                                {statusBadge.label}
                                                            </Badge>
                                                            {priorityOpt && (
                                                                <Badge className={priorityOpt.color}>
                                                                    {priorityOpt.label}
                                                                </Badge>
                                                            )}
                                                            {complaint.category && (
                                                                <Badge variant="outline" className="text-zinc-400">
                                                                    {complaint.category}
                                                                </Badge>
                                                            )}
                                                        </div>
                                                        <p className="text-xs text-zinc-500 mt-1 flex items-center gap-2">
                                                            <User className="h-3 w-3" />
                                                            {complaint.created_by?.display_name || complaint.created_by?.email}
                                                            <Clock className="h-3 w-3 ml-2" />
                                                            {formatDate(complaint.created_at)}
                                                        </p>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    {complaint.status !== 'resolved' && (
                                                        <>
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() => openRespond(complaint)}
                                                                data-testid={`respond-btn-${complaint.id}`}
                                                            >
                                                                <Send className="h-3 w-3 mr-1" />
                                                                Respond
                                                            </Button>
                                                            {isSuperAdmin && (
                                                                <Button
                                                                    variant="outline"
                                                                    size="sm"
                                                                    className="text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10"
                                                                    onClick={() => openResolve(complaint)}
                                                                    data-testid={`resolve-btn-${complaint.id}`}
                                                                >
                                                                    <CheckCircle className="h-3 w-3 mr-1" />
                                                                    Resolve
                                                                </Button>
                                                            )}
                                                        </>
                                                    )}
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => setExpandedComplaintId(isExpanded ? null : complaint.id)}
                                                    >
                                                        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                                                    </Button>
                                                </div>
                                            </div>

                                            {/* Reason */}
                                            <div className="p-3 rounded-lg bg-red-950/20 border border-red-900/30 mb-3">
                                                <p className="text-sm text-red-200">{complaint.reason}</p>
                                            </div>

                                            {/* Tagged Users */}
                                            {complaint.responsible_users?.length > 0 && (
                                                <div className="flex flex-wrap gap-2 mb-3">
                                                    <span className="text-xs text-zinc-500">Tagged:</span>
                                                    {complaint.responsible_users.map((u, idx) => (
                                                        <Badge key={idx} variant="outline" className="text-xs">
                                                            {u.telegram_username ? `@${u.telegram_username}` : (u.name || u.email)}
                                                        </Badge>
                                                    ))}
                                                </div>
                                            )}

                                            {/* Expanded Content */}
                                            {isExpanded && (
                                                <div className="mt-4 pt-4 border-t border-border space-y-4">
                                                    {/* Report URLs */}
                                                    {complaint.report_urls?.length > 0 && (
                                                        <div>
                                                            <Label className="text-xs text-zinc-500">Related Reports</Label>
                                                            <div className="mt-1 space-y-1">
                                                                {complaint.report_urls.map((url, idx) => (
                                                                    <a
                                                                        key={idx}
                                                                        href={url}
                                                                        target="_blank"
                                                                        rel="noopener noreferrer"
                                                                        className="text-xs text-blue-400 hover:underline flex items-center gap-1"
                                                                    >
                                                                        <ExternalLink className="h-3 w-3" />
                                                                        {url}
                                                                    </a>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* Responses */}
                                                    {complaint.responses?.length > 0 && (
                                                        <div>
                                                            <Label className="text-xs text-zinc-500 mb-2 block">
                                                                Responses ({complaint.responses.length})
                                                            </Label>
                                                            <div className="space-y-2">
                                                                {complaint.responses.map((resp, idx) => (
                                                                    <div key={idx} className="p-3 rounded-lg bg-zinc-900/50 border border-border">
                                                                        <div className="flex items-center gap-2 mb-2">
                                                                            <User className="h-3 w-3 text-zinc-500" />
                                                                            <span className="text-xs text-zinc-400">
                                                                                {resp.created_by?.display_name || resp.created_by?.email}
                                                                            </span>
                                                                            <Clock className="h-3 w-3 text-zinc-600 ml-2" />
                                                                            <span className="text-xs text-zinc-600">
                                                                                {formatDate(resp.created_at)}
                                                                            </span>
                                                                        </div>
                                                                        <p className="text-sm text-zinc-300">{resp.note}</p>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* Resolution Note */}
                                                    {complaint.status === 'resolved' && complaint.resolution_note && (
                                                        <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-900/30">
                                                            <div className="flex items-center gap-2 mb-2">
                                                                <CheckCircle className="h-4 w-4 text-emerald-400" />
                                                                <span className="text-xs text-emerald-400">
                                                                    Resolved by {complaint.resolved_by?.display_name || complaint.resolved_by?.email}
                                                                </span>
                                                                <span className="text-xs text-zinc-600">
                                                                    {formatDate(complaint.resolved_at)}
                                                                </span>
                                                            </div>
                                                            <p className="text-sm text-emerald-200">{complaint.resolution_note}</p>
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>
                                );
                            })}
                        </div>
                    )}
                </TabsContent>

                {/* Optimization Complaints */}
                <TabsContent value="optimization" className="mt-4">
                    {optimizationComplaints.length === 0 ? (
                        <Card className="bg-card border-border">
                            <CardContent className="py-12 text-center">
                                <CheckCircle className="h-12 w-12 text-emerald-500 mx-auto mb-3" />
                                <p className="text-zinc-400">No optimization complaints</p>
                                <p className="text-sm text-zinc-600 mt-1">
                                    Complaints on specific optimizations will appear here
                                </p>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-3">
                            {optimizationComplaints.map((opt) => {
                                const statusBadge = STATUS_BADGES[opt.complaint_status] || STATUS_BADGES.open;
                                return (
                                    <Card 
                                        key={opt.id} 
                                        className="bg-card border-border"
                                        data-testid={`optimization-complaint-${opt.id}`}
                                    >
                                        <CardContent className="pt-4">
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <MessageSquare className="h-4 w-4 text-amber-400" />
                                                        <span className="font-medium text-white">{opt.title}</span>
                                                        <Badge className={statusBadge.className}>
                                                            {statusBadge.label}
                                                        </Badge>
                                                    </div>
                                                    <p className="text-xs text-zinc-500 mt-1">
                                                        {opt.activity_type?.replace('_', ' ')} · {opt.complaints_count || 0} complaint(s)
                                                    </p>
                                                </div>
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => window.location.href = `/groups/${networkId}?optimization_id=${opt.id}`}
                                                >
                                                    View Details
                                                </Button>
                                            </div>
                                        </CardContent>
                                    </Card>
                                );
                            })}
                        </div>
                    )}
                </TabsContent>
            </Tabs>

            {/* Create Project Complaint Dialog */}
            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                <DialogContent className="bg-card border-border max-w-lg">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <AlertCircle className="h-5 w-5 text-red-400" />
                            Create Project Complaint
                        </DialogTitle>
                        <DialogDescription>
                            Create a complaint that applies to the entire network, not a specific optimization.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4">
                        {/* Reason */}
                        <div>
                            <Label>Complaint Reason *</Label>
                            <Textarea
                                value={form.reason}
                                onChange={(e) => setForm({ ...form, reason: e.target.value })}
                                placeholder="Describe the issue in detail (min 10 characters)..."
                                className="bg-black border-border mt-1"
                                rows={4}
                                data-testid="complaint-reason-input"
                            />
                            <p className={`text-xs mt-1 ${form.reason.length >= 10 ? 'text-emerald-400' : 'text-zinc-500'}`}>
                                {form.reason.length} / 10 min characters
                            </p>
                        </div>

                        {/* Priority & Category */}
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <Label>Priority</Label>
                                <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                                    <SelectTrigger className="bg-black border-border mt-1" data-testid="priority-select">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {PRIORITY_OPTIONS.map(opt => (
                                            <SelectItem key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div>
                                <Label>Category</Label>
                                <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                                    <SelectTrigger className="bg-black border-border mt-1" data-testid="category-select">
                                        <SelectValue placeholder="Select..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {CATEGORY_OPTIONS.map(opt => (
                                            <SelectItem key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        {/* Tag Users */}
                        <div>
                            <Label>Tag Responsible Users</Label>
                            <div className="relative mt-1">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                                <Input
                                    value={userSearchQuery}
                                    onChange={handleUserSearchChange}
                                    placeholder="Search users by name or email..."
                                    className="pl-10 bg-black border-border"
                                    data-testid="user-search-input"
                                />
                                {isSearching && (
                                    <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-zinc-500" />
                                )}
                            </div>
                            
                            {/* Search Results */}
                            {userSearchResults.length > 0 && (
                                <div className="mt-2 p-2 border border-border rounded-lg bg-zinc-900 max-h-32 overflow-y-auto">
                                    {userSearchResults.map(u => (
                                        <div
                                            key={u.id}
                                            onClick={() => addUser(u)}
                                            className="flex items-center justify-between p-2 rounded hover:bg-zinc-800 cursor-pointer"
                                        >
                                            <span className="text-sm text-white">{u.name || u.email}</span>
                                            <Plus className="h-4 w-4 text-emerald-400" />
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Selected Users */}
                            {selectedUsers.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-2">
                                    {selectedUsers.map(u => (
                                        <Badge
                                            key={u.id}
                                            variant="outline"
                                            className="text-xs cursor-pointer hover:bg-red-500/10"
                                            onClick={() => removeUser(u.id)}
                                        >
                                            {u.name || u.email}
                                            <XCircle className="h-3 w-3 ml-1" />
                                        </Badge>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Report URLs */}
                        <div>
                            <Label>Report URLs (one per line)</Label>
                            <Textarea
                                value={form.report_urls}
                                onChange={(e) => setForm({ ...form, report_urls: e.target.value })}
                                placeholder="https://..."
                                className="bg-black border-border mt-1 font-mono text-sm"
                                rows={2}
                                data-testid="report-urls-input"
                            />
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => { setCreateDialogOpen(false); resetForm(); }}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleCreateComplaint}
                            disabled={creating || form.reason.trim().length < 10}
                            className="bg-red-600 hover:bg-red-700"
                            data-testid="submit-complaint-btn"
                        >
                            {creating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Create Complaint
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Respond Dialog */}
            <Dialog open={respondDialogOpen} onOpenChange={setRespondDialogOpen}>
                <DialogContent className="bg-card border-border max-w-md">
                    <DialogHeader>
                        <DialogTitle>Add Response</DialogTitle>
                        <DialogDescription>
                            Provide a response to this complaint
                        </DialogDescription>
                    </DialogHeader>
                    <div>
                        <Textarea
                            value={responseNote}
                            onChange={(e) => setResponseNote(e.target.value)}
                            placeholder="Your response (min 20 characters)..."
                            className="bg-black border-border"
                            rows={4}
                            data-testid="response-note-input"
                        />
                        <p className={`text-xs mt-1 ${responseNote.length >= 20 ? 'text-emerald-400' : 'text-zinc-500'}`}>
                            {responseNote.length} / 20 min characters
                        </p>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setRespondDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleRespond}
                            disabled={responding || responseNote.trim().length < 20}
                            data-testid="submit-response-btn"
                        >
                            {responding && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            <Send className="h-4 w-4 mr-2" />
                            Send Response
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Resolve Dialog */}
            <Dialog open={resolveDialogOpen} onOpenChange={setResolveDialogOpen}>
                <DialogContent className="bg-card border-border max-w-md">
                    <DialogHeader>
                        <DialogTitle>Resolve Complaint</DialogTitle>
                        <DialogDescription>
                            Mark this complaint as resolved
                        </DialogDescription>
                    </DialogHeader>
                    <div>
                        <Textarea
                            value={resolutionNote}
                            onChange={(e) => setResolutionNote(e.target.value)}
                            placeholder="Resolution note (min 10 characters)..."
                            className="bg-black border-border"
                            rows={3}
                            data-testid="resolution-note-input"
                        />
                        <p className={`text-xs mt-1 ${resolutionNote.length >= 10 ? 'text-emerald-400' : 'text-zinc-500'}`}>
                            {resolutionNote.length} / 10 min characters
                        </p>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setResolveDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleResolve}
                            disabled={resolving || resolutionNote.trim().length < 10}
                            className="bg-emerald-600 hover:bg-emerald-700"
                            data-testid="submit-resolution-btn"
                        >
                            {resolving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            <CheckCircle className="h-4 w-4 mr-2" />
                            Resolve Complaint
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
