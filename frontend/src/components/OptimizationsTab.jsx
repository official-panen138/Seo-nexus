import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { useSearchParams } from 'react-router-dom';
import { optimizationsAPI } from '../lib/api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from './ui/dialog';
import { Skeleton } from './ui/skeleton';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { toast } from 'sonner';
import { formatDate } from '../lib/utils';
import OptimizationDetailDrawer from './OptimizationDetailDrawer';
import { 
    Plus, 
    Loader2, 
    Link2, 
    FileText, 
    Code, 
    Settings2, 
    Beaker, 
    MoreHorizontal,
    ExternalLink,
    User,
    Calendar,
    Tag,
    Target,
    TrendingUp,
    ChevronLeft,
    ChevronRight,
    Edit,
    Trash2,
    LinkIcon,
    AlertTriangle,
    MessageSquare,
    Eye,
    AlertCircle,
    Download
} from 'lucide-react';

// Activity type configuration
const ACTIVITY_TYPES = {
    backlink: { label: 'Backlink Campaign', icon: Link2, color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
    onpage: { label: 'On-Page Optimization', icon: FileText, color: 'bg-green-500/20 text-green-400 border-green-500/30' },
    content: { label: 'Content Update', icon: FileText, color: 'bg-purple-500/20 text-purple-400 border-purple-500/30' },
    technical: { label: 'Technical SEO', icon: Code, color: 'bg-orange-500/20 text-orange-400 border-orange-500/30' },
    schema: { label: 'Schema Markup', icon: Settings2, color: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30' },
    'internal-link': { label: 'Internal Linking', icon: LinkIcon, color: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' },
    experiment: { label: 'SEO Experiment', icon: Beaker, color: 'bg-pink-500/20 text-pink-400 border-pink-500/30' },
    other: { label: 'Other', icon: MoreHorizontal, color: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30' }
};

const STATUS_CONFIG = {
    planned: { label: 'Planned', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
    in_progress: { label: 'In Progress', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
    completed: { label: 'Completed', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
    reverted: { label: 'Reverted', color: 'bg-red-500/20 text-red-400 border-red-500/30' }
};

const SCOPE_OPTIONS = [
    { value: 'money_site', label: 'Money Site' },
    { value: 'domain', label: 'Specific Domain' },
    { value: 'path', label: 'Specific Path' },
    { value: 'whole_network', label: 'Whole Network' }
];

const IMPACT_OPTIONS = [
    { value: 'ranking', label: 'Ranking' },
    { value: 'authority', label: 'Authority' },
    { value: 'crawl', label: 'Crawl' },
    { value: 'conversion', label: 'Conversion' }
];

const INITIAL_FORM = {
    activity_type: 'backlink',
    title: '',
    description: '',
    reason_note: '',  // MANDATORY - min 20 chars
    affected_scope: 'specific_domain',
    target_domains: [],  // renamed from affected_targets
    keywords: [],
    report_urls: [],  // Now supports { url, start_date, end_date }
    expected_impact: [],
    status: 'completed'
};

export function OptimizationsTab({ networkId, networkName, brandName }) {
    const { hasRole, isSuperAdmin } = useAuth();
    const [searchParams, setSearchParams] = useSearchParams();
    const [optimizations, setOptimizations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [complaintDialogOpen, setComplaintDialogOpen] = useState(false);
    const [selectedOptimization, setSelectedOptimization] = useState(null);
    const [form, setForm] = useState(INITIAL_FORM);
    const [complaintForm, setComplaintForm] = useState({ reason: '', priority: 'medium', report_urls: [] });
    const [complaintUrlInput, setComplaintUrlInput] = useState('');
    
    // Detail drawer state
    const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);
    const [selectedOptimizationId, setSelectedOptimizationId] = useState(null);
    
    // Pagination
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize] = useState(20);
    const [totalItems, setTotalItems] = useState(0);
    const [totalPages, setTotalPages] = useState(1);
    
    // Filter
    const [filterType, setFilterType] = useState('all');
    const [filterStatus, setFilterStatus] = useState('all');
    
    // Tag inputs
    const [targetInput, setTargetInput] = useState('');
    const [keywordInput, setKeywordInput] = useState('');
    const [reportUrlInput, setReportUrlInput] = useState('');
    const [reportUrlDate, setReportUrlDate] = useState(new Date().toISOString().split('T')[0]);

    // Check for deep-link on mount
    useEffect(() => {
        const optimizationId = searchParams.get('optimization_id');
        if (optimizationId) {
            setSelectedOptimizationId(optimizationId);
            setDetailDrawerOpen(true);
        }
    }, [searchParams]);

    useEffect(() => {
        loadOptimizations();
    }, [networkId, currentPage, filterType, filterStatus]);

    const loadOptimizations = async () => {
        setLoading(true);
        try {
            const params = { page: currentPage, limit: pageSize };
            if (filterType !== 'all') params.activity_type = filterType;
            if (filterStatus !== 'all') params.status = filterStatus;
            
            const response = await optimizationsAPI.getAll(networkId, params);
            
            if (response.data?.data && response.data?.meta) {
                setOptimizations(response.data.data);
                setTotalItems(response.data.meta.total);
                setTotalPages(response.data.meta.total_pages);
            } else {
                setOptimizations(Array.isArray(response.data) ? response.data : []);
            }
        } catch (err) {
            console.error('Failed to load optimizations:', err);
            toast.error('Failed to load optimizations');
        } finally {
            setLoading(false);
        }
    };

    const openDetailDrawer = (opt) => {
        setSelectedOptimizationId(opt.id);
        setDetailDrawerOpen(true);
        // Update URL with optimization_id for deep-linking
        setSearchParams({ optimization_id: opt.id });
    };

    const closeDetailDrawer = () => {
        setDetailDrawerOpen(false);
        setSelectedOptimizationId(null);
        // Remove optimization_id from URL
        searchParams.delete('optimization_id');
        setSearchParams(searchParams);
    };

    const openCreateDialog = () => {
        setSelectedOptimization(null);
        setForm(INITIAL_FORM);
        setTargetInput('');
        setKeywordInput('');
        setReportUrlInput('');
        setDialogOpen(true);
    };

    const openEditDialog = (opt) => {
        setSelectedOptimization(opt);
        setForm({
            activity_type: opt.activity_type,
            title: opt.title,
            description: opt.description,
            reason_note: opt.reason_note || '',
            affected_scope: opt.affected_scope,
            target_domains: opt.target_domains || opt.affected_targets || [],
            keywords: opt.keywords || [],
            report_urls: opt.report_urls || [],
            expected_impact: opt.expected_impact || [],
            status: opt.status
        });
        setTargetInput('');
        setKeywordInput('');
        setReportUrlInput('');
        setDialogOpen(true);
    };

    const handleSave = async () => {
        if (!form.title.trim()) {
            toast.error('Title is required');
            return;
        }
        if (!form.description.trim()) {
            toast.error('Description is required');
            return;
        }
        // MANDATORY: reason_note must be at least 20 characters
        if (!selectedOptimization && (!form.reason_note || form.reason_note.trim().length < 20)) {
            toast.error('Reason note is required (minimum 20 characters). Please explain why this optimization is being done.');
            return;
        }

        setSaving(true);
        try {
            // Prepare data for API - map target_domains to the right field
            const submitData = {
                ...form,
                target_domains: form.target_domains || [],
                // Convert report_urls to proper format if they're plain strings
                report_urls: (form.report_urls || []).map(r => {
                    if (typeof r === 'string') {
                        return { url: r, start_date: new Date().toISOString().split('T')[0] };
                    }
                    return r;
                })
            };
            
            if (selectedOptimization) {
                await optimizationsAPI.update(selectedOptimization.id, submitData);
                toast.success('Optimization updated');
            } else {
                await optimizationsAPI.create(networkId, submitData);
                toast.success('Optimization created and notification sent');
            }
            setDialogOpen(false);
            loadOptimizations();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to save optimization');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!selectedOptimization) return;
        
        // Double-check Super Admin permission
        if (!isSuperAdmin()) {
            toast.error('Only Super Admin can delete optimization records');
            setDeleteDialogOpen(false);
            return;
        }
        
        setSaving(true);
        try {
            await optimizationsAPI.delete(selectedOptimization.id);
            toast.success('Optimization deleted');
            setDeleteDialogOpen(false);
            setSelectedOptimization(null);
            loadOptimizations();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to delete optimization');
        } finally {
            setSaving(false);
        }
    };

    const openComplaintDialog = (opt) => {
        setSelectedOptimization(opt);
        setComplaintForm({ reason: '', priority: 'medium', report_urls: [] });
        setComplaintUrlInput('');
        setComplaintDialogOpen(true);
    };

    const handleCreateComplaint = async () => {
        if (!selectedOptimization) return;
        if (!complaintForm.reason.trim()) {
            toast.error('Complaint reason is required');
            return;
        }
        
        setSaving(true);
        try {
            const API_URL = process.env.REACT_APP_BACKEND_URL;
            const token = localStorage.getItem('seo_nexus_token');
            
            const response = await fetch(`${API_URL}/api/v3/optimizations/${selectedOptimization.id}/complaints`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    reason: complaintForm.reason.trim(),
                    priority: complaintForm.priority,
                    report_urls: complaintForm.report_urls,
                    responsible_user_ids: []  // TODO: Add user selection
                })
            });
            
            if (response.ok) {
                toast.success('Complaint submitted and notification sent');
                setComplaintDialogOpen(false);
                setSelectedOptimization(null);
                loadOptimizations();
            } else {
                const error = await response.json();
                toast.error(error.detail || 'Failed to create complaint');
            }
        } catch (err) {
            toast.error('Failed to create complaint');
        } finally {
            setSaving(false);
        }
    };

    const addComplaintUrl = () => {
        if (complaintUrlInput.trim() && !complaintForm.report_urls.includes(complaintUrlInput.trim())) {
            setComplaintForm(prev => ({ ...prev, report_urls: [...prev.report_urls, complaintUrlInput.trim()] }));
            setComplaintUrlInput('');
        }
    };

    const removeComplaintUrl = (url) => {
        setComplaintForm(prev => ({ ...prev, report_urls: prev.report_urls.filter(u => u !== url) }));
    };

    // Tag input handlers - updated to use target_domains
    const addTarget = () => {
        if (targetInput.trim() && !form.target_domains.includes(targetInput.trim())) {
            setForm(prev => ({ ...prev, target_domains: [...prev.target_domains, targetInput.trim()] }));
            setTargetInput('');
        }
    };

    const removeTarget = (target) => {
        setForm(prev => ({ ...prev, target_domains: prev.target_domains.filter(t => t !== target) }));
    };

    const addKeyword = () => {
        if (keywordInput.trim() && !form.keywords.includes(keywordInput.trim())) {
            setForm(prev => ({ ...prev, keywords: [...prev.keywords, keywordInput.trim()] }));
            setKeywordInput('');
        }
    };

    const removeKeyword = (kw) => {
        setForm(prev => ({ ...prev, keywords: prev.keywords.filter(k => k !== kw) }));
    };

    const addReportUrl = () => {
        if (reportUrlInput.trim()) {
            const urlExists = form.report_urls.some(r => 
                (typeof r === 'string' ? r : r.url) === reportUrlInput.trim()
            );
            if (!urlExists) {
                // Add with current date as start_date
                setForm(prev => ({ 
                    ...prev, 
                    report_urls: [...prev.report_urls, { 
                        url: reportUrlInput.trim(), 
                        start_date: new Date().toISOString().split('T')[0] 
                    }] 
                }));
                setReportUrlInput('');
            }
        }
    };

    const removeReportUrl = (urlToRemove) => {
        setForm(prev => ({ 
            ...prev, 
            report_urls: prev.report_urls.filter(r => 
                (typeof r === 'string' ? r : r.url) !== (typeof urlToRemove === 'string' ? urlToRemove : urlToRemove.url)
            ) 
        }));
    };

    const toggleImpact = (impact) => {
        setForm(prev => ({
            ...prev,
            expected_impact: prev.expected_impact.includes(impact)
                ? prev.expected_impact.filter(i => i !== impact)
                : [...prev.expected_impact, impact]
        }));
    };

    // Export to CSV
    const [exporting, setExporting] = useState(false);
    const handleExportCSV = async () => {
        setExporting(true);
        try {
            const params = {};
            if (filterType !== 'all') params.activity_type = filterType;
            if (filterStatus !== 'all') params.status = filterStatus;
            
            const response = await optimizationsAPI.exportCSV(networkId, params);
            
            const blob = new Blob([response.data], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `optimizations_${networkId.slice(0, 8)}_${new Date().toISOString().slice(0, 10)}.csv`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
            
            toast.success('Optimizations exported successfully');
        } catch (err) {
            toast.error('Failed to export optimizations');
        } finally {
            setExporting(false);
        }
    };

    // Loading skeleton
    if (loading && optimizations.length === 0) {
        return (
            <div className="space-y-4">
                <div className="flex justify-between items-center">
                    <Skeleton className="h-8 w-48" />
                    <Skeleton className="h-10 w-32" />
                </div>
                {[1, 2, 3].map(i => (
                    <Skeleton key={i} className="h-40 w-full" />
                ))}
            </div>
        );
    }

    return (
        <div className="space-y-6" data-testid="optimizations-tab">
            {/* Header */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h3 className="text-lg font-semibold">SEO Optimizations</h3>
                    <p className="text-sm text-zinc-400">
                        Track SEO activities that don't change the network structure
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button 
                        variant="outline" 
                        onClick={handleExportCSV} 
                        disabled={exporting || optimizations.length === 0}
                        className="gap-2"
                        data-testid="export-optimizations-btn"
                    >
                        <Download className={`h-4 w-4 ${exporting ? 'animate-bounce' : ''}`} />
                        {exporting ? 'Exporting...' : 'Export CSV'}
                    </Button>
                    <Button onClick={openCreateDialog} className="gap-2" data-testid="add-optimization-btn">
                        <Plus className="h-4 w-4" />
                        Add Optimization
                    </Button>
                </div>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-3">
                <Select value={filterType} onValueChange={(v) => { setFilterType(v); setCurrentPage(1); }}>
                    <SelectTrigger className="w-44 bg-black border-border">
                        <SelectValue placeholder="Filter by type" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Types</SelectItem>
                        {Object.entries(ACTIVITY_TYPES).map(([key, config]) => (
                            <SelectItem key={key} value={key}>{config.label}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                
                <Select value={filterStatus} onValueChange={(v) => { setFilterStatus(v); setCurrentPage(1); }}>
                    <SelectTrigger className="w-40 bg-black border-border">
                        <SelectValue placeholder="Filter by status" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Status</SelectItem>
                        {Object.entries(STATUS_CONFIG).map(([key, config]) => (
                            <SelectItem key={key} value={key}>{config.label}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                
                <div className="text-sm text-zinc-400 flex items-center">
                    {totalItems} optimization{totalItems !== 1 ? 's' : ''}
                </div>
            </div>

            {/* Optimizations List */}
            {optimizations.length === 0 ? (
                <div className="text-center py-16 border border-dashed border-zinc-700 rounded-lg">
                    <FileText className="h-12 w-12 mx-auto text-zinc-600 mb-4" />
                    <p className="text-zinc-400">No optimizations recorded yet</p>
                    <p className="text-sm text-zinc-500 mt-1">Start tracking your SEO activities</p>
                    <Button onClick={openCreateDialog} variant="outline" className="mt-4">
                        <Plus className="h-4 w-4 mr-2" />
                        Add First Optimization
                    </Button>
                </div>
            ) : (
                <div className="space-y-4">
                    {optimizations.map((opt) => {
                        const typeConfig = ACTIVITY_TYPES[opt.activity_type] || ACTIVITY_TYPES.other;
                        const statusConfig = STATUS_CONFIG[opt.status] || STATUS_CONFIG.planned;
                        const TypeIcon = typeConfig.icon;
                        
                        return (
                            <Card key={opt.id} className="bg-card border-border hover:border-zinc-600 transition-colors" data-testid={`optimization-${opt.id}`}>
                                <CardContent className="p-4">
                                    <div className="flex flex-col lg:flex-row lg:items-start gap-4">
                                        {/* Icon & Type */}
                                        <div className="flex items-center gap-3 lg:w-48 flex-shrink-0">
                                            <div className={`p-2 rounded-lg ${typeConfig.color.split(' ')[0]}`}>
                                                <TypeIcon className={`h-5 w-5 ${typeConfig.color.split(' ')[1]}`} />
                                            </div>
                                            <div>
                                                <Badge variant="outline" className={typeConfig.color}>
                                                    {typeConfig.label}
                                                </Badge>
                                                <Badge variant="outline" className={`${statusConfig.color} ml-2`}>
                                                    {statusConfig.label}
                                                </Badge>
                                                {/* Complaint Status Badge */}
                                                {opt.complaint_status && opt.complaint_status !== 'none' && (
                                                    <Badge 
                                                        variant="outline" 
                                                        className={`ml-2 ${
                                                            opt.complaint_status === 'complained' ? 'bg-red-500/20 text-red-400 border-red-500/30' :
                                                            opt.complaint_status === 'under_review' ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' :
                                                            'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                                                        }`}
                                                    >
                                                        {opt.complaint_status === 'complained' && <AlertCircle className="h-3 w-3 mr-1" />}
                                                        {opt.complaint_status === 'under_review' && '🟡 '}
                                                        {opt.complaint_status === 'resolved' && '✓ '}
                                                        {opt.complaint_status.replace('_', ' ')}
                                                    </Badge>
                                                )}
                                            </div>
                                        </div>
                                        
                                        {/* Content */}
                                        <div className="flex-1 min-w-0">
                                            <h4 className="font-medium text-white mb-1">{opt.title}</h4>
                                            <p className="text-sm text-zinc-400 line-clamp-2 mb-2">{opt.description}</p>
                                            
                                            {/* Show reason note if exists */}
                                            {opt.reason_note && (
                                                <p className="text-xs text-amber-400/80 italic mb-2 line-clamp-1">
                                                    Alasan: {opt.reason_note}
                                                </p>
                                            )}
                                            
                                            <div className="flex flex-wrap gap-3 text-xs text-zinc-500">
                                                <span className="flex items-center gap-1">
                                                    <User className="h-3 w-3" />
                                                    {opt.created_by?.display_name || 'Unknown'}
                                                </span>
                                                <span className="flex items-center gap-1">
                                                    <Calendar className="h-3 w-3" />
                                                    {formatDate(opt.created_at)}
                                                </span>
                                                {opt.keywords?.length > 0 && (
                                                    <span className="flex items-center gap-1">
                                                        <Tag className="h-3 w-3" />
                                                        {opt.keywords.slice(0, 3).join(', ')}
                                                        {opt.keywords.length > 3 && ` +${opt.keywords.length - 3}`}
                                                    </span>
                                                )}
                                                {(opt.target_domains?.length > 0 || opt.affected_targets?.length > 0) && (
                                                    <span className="flex items-center gap-1">
                                                        <Target className="h-3 w-3" />
                                                        {(opt.target_domains || opt.affected_targets).length} target{(opt.target_domains || opt.affected_targets).length !== 1 ? 's' : ''}
                                                    </span>
                                                )}
                                                {opt.report_urls?.length > 0 && (
                                                    <a 
                                                        href={typeof opt.report_urls[0] === 'string' ? opt.report_urls[0] : opt.report_urls[0]?.url} 
                                                        target="_blank" 
                                                        rel="noopener noreferrer"
                                                        className="flex items-center gap-1 text-blue-400 hover:text-blue-300"
                                                    >
                                                        <ExternalLink className="h-3 w-3" />
                                                        Report
                                                    </a>
                                                )}
                                            </div>
                                        </div>
                                        
                                        {/* Actions */}
                                        <div className="flex items-center gap-1 lg:ml-4">
                                            {/* View button - Opens detail drawer */}
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button 
                                                            variant="ghost" 
                                                            size="icon"
                                                            onClick={() => openDetailDrawer(opt)}
                                                            className="h-8 w-8 hover:bg-emerald-500/10 hover:text-emerald-400"
                                                            data-testid={`view-opt-${opt.id}`}
                                                        >
                                                            <Eye className="h-4 w-4" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>View Details</TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                            
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button 
                                                            variant="ghost" 
                                                            size="icon"
                                                            onClick={() => openEditDialog(opt)}
                                                            className="h-8 w-8 hover:bg-blue-500/10 hover:text-blue-400"
                                                        >
                                                            <Edit className="h-4 w-4" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>Edit</TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                            
                                            {/* Complaint button - Super Admin only */}
                                            {isSuperAdmin() && (
                                                <TooltipProvider>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button 
                                                                variant="ghost" 
                                                                size="icon"
                                                                onClick={() => openComplaintDialog(opt)}
                                                                className="h-8 w-8 hover:bg-amber-500/10 hover:text-amber-400"
                                                            >
                                                                <AlertTriangle className="h-4 w-4" />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent>Submit Complaint</TooltipContent>
                                                    </Tooltip>
                                                </TooltipProvider>
                                            )}
                                            
                                            {/* Delete button - Super Admin only */}
                                            {isSuperAdmin() && (
                                                <TooltipProvider>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button 
                                                                variant="ghost" 
                                                                size="icon"
                                                                onClick={() => { setSelectedOptimization(opt); setDeleteDialogOpen(true); }}
                                                                className="h-8 w-8 hover:bg-red-500/10 hover:text-red-400"
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent>Delete (Super Admin)</TooltipContent>
                                                    </Tooltip>
                                                </TooltipProvider>
                                            )}
                                            
                                            {/* Complaints indicator */}
                                            {opt.complaints_count > 0 && (
                                                <Badge variant="outline" className="text-amber-400 border-amber-500/30 text-xs">
                                                    <MessageSquare className="h-3 w-3 mr-1" />
                                                    {opt.complaints_count}
                                                </Badge>
                                            )}
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between py-4 border-t border-border">
                    <div className="text-sm text-zinc-400">
                        Showing {((currentPage - 1) * pageSize) + 1} - {Math.min(currentPage * pageSize, totalItems)} of {totalItems}
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                            disabled={currentPage === 1 || loading}
                        >
                            <ChevronLeft className="h-4 w-4 mr-1" />
                            Prev
                        </Button>
                        <span className="text-sm text-zinc-400 px-2">
                            Page {currentPage} of {totalPages}
                        </span>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                            disabled={currentPage >= totalPages || loading}
                        >
                            Next
                            <ChevronRight className="h-4 w-4 ml-1" />
                        </Button>
                    </div>
                </div>
            )}

            {/* Add/Edit Dialog */}
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogContent className="bg-card border-border max-w-2xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>
                            {selectedOptimization ? 'Edit Optimization' : 'Add SEO Optimization'}
                        </DialogTitle>
                        <DialogDescription>
                            Record an SEO activity. This does NOT modify the network structure.
                        </DialogDescription>
                    </DialogHeader>
                    
                    <div className="space-y-4 py-4">
                        {/* Activity Type */}
                        <div>
                            <Label>Activity Type *</Label>
                            <Select value={form.activity_type} onValueChange={(v) => setForm(prev => ({ ...prev, activity_type: v }))}>
                                <SelectTrigger className="mt-1 bg-black border-border">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {Object.entries(ACTIVITY_TYPES).map(([key, config]) => (
                                        <SelectItem key={key} value={key}>{config.label}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        
                        {/* Title */}
                        <div>
                            <Label>Title *</Label>
                            <Input
                                value={form.title}
                                onChange={(e) => setForm(prev => ({ ...prev, title: e.target.value }))}
                                placeholder="e.g., Tier 1 Backlink Purchase for Main Site"
                                className="mt-1 bg-black border-border"
                            />
                        </div>
                        
                        {/* Description */}
                        <div>
                            <Label>Description *</Label>
                            <Textarea
                                value={form.description}
                                onChange={(e) => setForm(prev => ({ ...prev, description: e.target.value }))}
                                placeholder="Describe the optimization activity in detail..."
                                className="mt-1 bg-black border-border min-h-[100px]"
                                rows={4}
                            />
                        </div>
                        
                        {/* Reason Note - MANDATORY for new entries */}
                        {!selectedOptimization && (
                            <div className="border border-amber-500/30 rounded-lg p-4 bg-amber-500/5">
                                <div className="flex items-center justify-between mb-2">
                                    <Label className="text-amber-400 flex items-center gap-2">
                                        <AlertTriangle className="h-4 w-4" />
                                        Reason Note (Alasan Optimasi) *
                                    </Label>
                                    <span className={`text-xs ${form.reason_note.length >= 20 ? 'text-green-400' : 'text-amber-400'}`}>
                                        {form.reason_note.length} / 20+ chars
                                    </span>
                                </div>
                                <Textarea
                                    value={form.reason_note}
                                    onChange={(e) => setForm(prev => ({ ...prev, reason_note: e.target.value }))}
                                    placeholder="Jelaskan mengapa optimasi ini dilakukan. Contoh: 'Meningkatkan authority domain utama untuk keyword kompetitif...'"
                                    className="bg-black border-amber-500/50 min-h-[80px] focus:border-amber-500"
                                    rows={3}
                                />
                                <p className="text-xs text-amber-400/70 mt-2">
                                    ⚠️ Catatan ini wajib dan akan dikirim ke tim SEO via Telegram
                                </p>
                            </div>
                        )}
                        
                        {/* Affected Scope */}
                        <div>
                            <Label>Affected Scope</Label>
                            <Select value={form.affected_scope} onValueChange={(v) => setForm(prev => ({ ...prev, affected_scope: v }))}>
                                <SelectTrigger className="mt-1 bg-black border-border">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {SCOPE_OPTIONS.map(opt => (
                                        <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        
                        {/* Target Domains/Paths */}
                        <div>
                            <Label>Target Domains/Paths</Label>
                            <div className="flex gap-2 mt-1">
                                <Input
                                    value={targetInput}
                                    onChange={(e) => setTargetInput(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTarget())}
                                    placeholder="e.g., moneysite.com or /blog/article"
                                    className="bg-black border-border"
                                />
                                <Button type="button" variant="outline" onClick={addTarget}>Add</Button>
                            </div>
                            {form.target_domains.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-2">
                                    {form.target_domains.map((target, i) => (
                                        <Badge key={i} variant="secondary" className="pr-1">
                                            {target}
                                            <button onClick={() => removeTarget(target)} className="ml-1 hover:text-red-400">×</button>
                                        </Badge>
                                    ))}
                                </div>
                            )}
                        </div>
                        
                        {/* Keywords */}
                        <div>
                            <Label>Keywords</Label>
                            <div className="flex gap-2 mt-1">
                                <Input
                                    value={keywordInput}
                                    onChange={(e) => setKeywordInput(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addKeyword())}
                                    placeholder="Add keyword"
                                    className="bg-black border-border"
                                />
                                <Button type="button" variant="outline" onClick={addKeyword}>Add</Button>
                            </div>
                            {form.keywords.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-2">
                                    {form.keywords.map((kw, i) => (
                                        <Badge key={i} variant="secondary" className="pr-1">
                                            {kw}
                                            <button onClick={() => removeKeyword(kw)} className="ml-1 hover:text-red-400">×</button>
                                        </Badge>
                                    ))}
                                </div>
                            )}
                        </div>
                        
                        {/* Report URLs */}
                        <div>
                            <Label>Report URLs</Label>
                            <div className="flex gap-2 mt-1">
                                <Input
                                    value={reportUrlInput}
                                    onChange={(e) => setReportUrlInput(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addReportUrl())}
                                    placeholder="https://docs.google.com/..."
                                    className="bg-black border-border"
                                />
                                <Button type="button" variant="outline" onClick={addReportUrl}>Add</Button>
                            </div>
                            {form.report_urls.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-2">
                                    {form.report_urls.map((urlItem, i) => {
                                        const url = typeof urlItem === 'string' ? urlItem : urlItem.url;
                                        const displayUrl = url.length > 40 ? url.slice(0, 40) + '...' : url;
                                        return (
                                            <Badge key={i} variant="secondary" className="pr-1">
                                                <a href={url} target="_blank" rel="noopener noreferrer" className="hover:text-blue-400">
                                                    {displayUrl}
                                                </a>
                                                <button onClick={() => removeReportUrl(urlItem)} className="ml-1 hover:text-red-400">×</button>
                                            </Badge>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                        
                        {/* Expected Impact */}
                        <div>
                            <Label>Expected Impact</Label>
                            <div className="flex flex-wrap gap-2 mt-2">
                                {IMPACT_OPTIONS.map(opt => (
                                    <Button
                                        key={opt.value}
                                        type="button"
                                        variant={form.expected_impact.includes(opt.value) ? 'default' : 'outline'}
                                        size="sm"
                                        onClick={() => toggleImpact(opt.value)}
                                        className={form.expected_impact.includes(opt.value) ? 'bg-emerald-600' : ''}
                                    >
                                        <TrendingUp className="h-3 w-3 mr-1" />
                                        {opt.label}
                                    </Button>
                                ))}
                            </div>
                        </div>
                        
                        {/* Status */}
                        <div>
                            <Label>Status</Label>
                            <Select value={form.status} onValueChange={(v) => setForm(prev => ({ ...prev, status: v }))}>
                                <SelectTrigger className="mt-1 bg-black border-border">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {Object.entries(STATUS_CONFIG).map(([key, config]) => (
                                        <SelectItem key={key} value={key}>{config.label}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                        <Button 
                            onClick={handleSave} 
                            disabled={saving || !form.title.trim() || !form.description.trim() || (!selectedOptimization && form.reason_note.trim().length < 20)}
                        >
                            {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            {selectedOptimization ? 'Update' : 'Create & Notify'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Dialog */}
            <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <DialogContent className="bg-card border-border max-w-md">
                    <DialogHeader>
                        <DialogTitle>Delete Optimization</DialogTitle>
                    </DialogHeader>
                    <p className="text-zinc-400">
                        Are you sure you want to delete "<span className="text-white font-medium">{selectedOptimization?.title}</span>"?
                    </p>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleDelete} disabled={saving} className="bg-red-600 hover:bg-red-700">
                            {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Delete
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Complaint Dialog - Super Admin only */}
            <Dialog open={complaintDialogOpen} onOpenChange={setComplaintDialogOpen}>
                <DialogContent className="bg-card border-border max-w-lg">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <AlertTriangle className="h-5 w-5 text-amber-500" />
                            Submit Complaint
                        </DialogTitle>
                        <DialogDescription>
                            Submit a complaint on "{selectedOptimization?.title}". Tagged users will be notified via Telegram.
                        </DialogDescription>
                    </DialogHeader>
                    
                    <div className="space-y-4 py-4">
                        {/* Complaint Reason */}
                        <div>
                            <Label>Complaint Reason *</Label>
                            <Textarea
                                value={complaintForm.reason}
                                onChange={(e) => setComplaintForm(prev => ({ ...prev, reason: e.target.value }))}
                                placeholder="Describe the issue with this optimization..."
                                className="mt-1 bg-black border-border min-h-[100px]"
                                rows={4}
                            />
                        </div>
                        
                        {/* Priority */}
                        <div>
                            <Label>Priority</Label>
                            <Select value={complaintForm.priority} onValueChange={(v) => setComplaintForm(prev => ({ ...prev, priority: v }))}>
                                <SelectTrigger className="mt-1 bg-black border-border">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="low">🔵 Low</SelectItem>
                                    <SelectItem value="medium">🟡 Medium</SelectItem>
                                    <SelectItem value="high">🔴 High</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        
                        {/* Report URLs */}
                        <div>
                            <Label>Related Reports</Label>
                            <div className="flex gap-2 mt-1">
                                <Input
                                    value={complaintUrlInput}
                                    onChange={(e) => setComplaintUrlInput(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addComplaintUrl())}
                                    placeholder="https://..."
                                    className="bg-black border-border"
                                />
                                <Button type="button" variant="outline" onClick={addComplaintUrl}>Add</Button>
                            </div>
                            {complaintForm.report_urls.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-2">
                                    {complaintForm.report_urls.map((url, i) => (
                                        <Badge key={i} variant="secondary" className="pr-1">
                                            {url.length > 30 ? url.slice(0, 30) + '...' : url}
                                            <button onClick={() => removeComplaintUrl(url)} className="ml-1 hover:text-red-400">×</button>
                                        </Badge>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                    
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setComplaintDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleCreateComplaint} disabled={saving || !complaintForm.reason.trim()} className="bg-amber-600 hover:bg-amber-700">
                            {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Submit Complaint
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
            
            {/* Optimization Detail Drawer */}
            <OptimizationDetailDrawer
                optimizationId={selectedOptimizationId}
                isOpen={detailDrawerOpen}
                onClose={closeDetailDrawer}
                onUpdate={loadOptimizations}
                networkId={networkId}
            />
        </div>
    );
}
