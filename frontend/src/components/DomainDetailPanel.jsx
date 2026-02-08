import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../lib/auth';
import { domainsAPI } from '../lib/api';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from './ui/sheet';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Separator } from './ui/separator';
import { ScrollArea } from './ui/scroll-area';
import { Alert, AlertDescription } from './ui/alert';
import { Switch } from './ui/switch';
import { 
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from './ui/alert-dialog';
import { toast } from 'sonner';
import { 
    ExternalLink, 
    Loader2, 
    Save, 
    X, 
    AlertTriangle,
    ArrowDown,
    Clock,
    User,
    Edit,
    Unlink,
    Archive,
    ChevronRight,
    Network,
    Globe,
    History,
    Activity,
    Calendar,
    RefreshCw,
    Zap,
    VolumeX,
    Volume2
} from 'lucide-react';
import { 
    TIER_LABELS, 
    STATUS_LABELS, 
    INDEX_STATUS_LABELS, 
    MONITORING_INTERVAL_LABELS,
    PING_STATUS_LABELS,
    REGISTRARS,
    getTierBadgeClass,
    TIER_COLORS,
    formatDate,
    formatDateTime,
    getDaysUntilExpiration,
    getExpirationBadgeClass
} from '../lib/utils';

const TIER_HIERARCHY = {
    'tier_5': 5, 'tier_4': 4, 'tier_3': 3, 'tier_2': 2, 'tier_1': 1, 'lp_money_site': 0
};

export const DomainDetailPanel = ({ 
    domain, 
    isOpen, 
    onClose, 
    onUpdate,
    allDomains = [],
    brands = [],
    groups = [],
    categories = []
}) => {
    const { canEdit } = useAuth();
    const [isEditing, setIsEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [checking, setChecking] = useState(false);
    const [muting, setMuting] = useState(false);
    const [form, setForm] = useState({});
    const [warnings, setWarnings] = useState([]);
    const [showRemoveDialog, setShowRemoveDialog] = useState(false);
    const [showArchiveDialog, setShowArchiveDialog] = useState(false);
    const [history, setHistory] = useState([]);

    // Initialize form when domain changes
    useEffect(() => {
        if (domain) {
            setForm({
                domain_status: domain.domain_status,
                index_status: domain.index_status,
                tier_level: domain.tier_level,
                group_id: domain.group_id || '',
                parent_domain_id: domain.parent_domain_id || '',
                category_id: domain.category_id || '',
                registrar: domain.registrar || '',
                expiration_date: domain.expiration_date ? domain.expiration_date.split('T')[0] : '',
                auto_renew: domain.auto_renew || false,
                monitoring_enabled: domain.monitoring_enabled || false,
                monitoring_interval: domain.monitoring_interval || '1hour',
                notes: domain.notes || ''
            });
            setIsEditing(false);
            setWarnings([]);
            loadDomainHistory();
        }
    }, [domain?.id]);

    // Load domain history
    const loadDomainHistory = async () => {
        if (!domain) return;
        try {
            const token = localStorage.getItem('seo_nexus_token');
            const API_BASE = process.env.REACT_APP_BACKEND_URL + '/api';
            const res = await fetch(`${API_BASE}/audit-logs?entity_type=domain&limit=20`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                const logs = await res.json();
                setHistory(logs.filter(l => l.entity_id === domain.id).slice(0, 5));
            }
        } catch (err) {
            console.log('Could not load history');
        }
    };

    // Validate form
    useEffect(() => {
        const newWarnings = [];
        
        if (form.tier_level === 'lp_money_site' && form.index_status === 'noindex') {
            newWarnings.push({ type: 'error', message: 'LP / Money Site cannot be set to NOINDEX' });
        }
        
        if (form.domain_status === 'canonical' && !form.group_id) {
            newWarnings.push({ type: 'warning', message: 'Canonical domains should belong to a Network' });
        }
        
        if (domain && form.tier_level !== domain.tier_level && domain.group_id) {
            newWarnings.push({ type: 'warning', message: 'Changing tier while in a network may affect hierarchy' });
        }
        
        if (form.parent_domain_id && form.tier_level) {
            const parent = allDomains.find(d => d.id === form.parent_domain_id);
            if (parent) {
                const parentTier = TIER_HIERARCHY[parent.tier_level];
                const currentTier = TIER_HIERARCHY[form.tier_level];
                if (currentTier <= parentTier) {
                    newWarnings.push({ type: 'error', message: `Invalid tier: must be higher than parent (${TIER_LABELS[parent.tier_level]})` });
                }
            }
        }
        
        setWarnings(newWarnings);
    }, [form, domain, allDomains]);

    const parentDomain = useMemo(() => {
        if (!domain?.parent_domain_id) return null;
        return allDomains.find(d => d.id === domain.parent_domain_id);
    }, [domain, allDomains]);

    const childDomains = useMemo(() => {
        if (!domain) return [];
        return allDomains.filter(d => d.parent_domain_id === domain.id);
    }, [domain, allDomains]);

    const availableParents = useMemo(() => {
        if (!form.group_id || !form.tier_level) return [];
        const currentTier = TIER_HIERARCHY[form.tier_level];
        return allDomains.filter(d => {
            if (d.id === domain?.id) return false;
            if (d.group_id !== form.group_id) return false;
            const dTier = TIER_HIERARCHY[d.tier_level];
            return dTier < currentTier;
        });
    }, [allDomains, form.group_id, form.tier_level, domain]);

    const hasErrors = warnings.some(w => w.type === 'error');
    const daysUntilExpiration = getDaysUntilExpiration(domain?.expiration_date);

    const handleSave = async () => {
        if (hasErrors) {
            toast.error('Please fix errors before saving');
            return;
        }

        setSaving(true);
        try {
            const payload = {
                domain_status: form.domain_status,
                index_status: form.index_status,
                tier_level: form.tier_level,
                group_id: form.group_id || null,
                parent_domain_id: form.parent_domain_id || null,
                category_id: form.category_id || null,
                registrar: form.registrar || null,
                expiration_date: form.expiration_date ? new Date(form.expiration_date).toISOString() : null,
                auto_renew: form.auto_renew,
                monitoring_enabled: form.monitoring_enabled,
                monitoring_interval: form.monitoring_interval,
                notes: form.notes
            };

            await domainsAPI.update(domain.id, payload);
            toast.success('Domain updated successfully');
            setIsEditing(false);
            if (onUpdate) onUpdate();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to update domain');
        } finally {
            setSaving(false);
        }
    };

    const handleCheckNow = async () => {
        setChecking(true);
        try {
            await domainsAPI.checkNow(domain.id);
            toast.success('Health check scheduled');
            setTimeout(() => {
                if (onUpdate) onUpdate();
            }, 2000);
        } catch (err) {
            toast.error('Failed to schedule check');
        } finally {
            setChecking(false);
        }
    };

    const handleMute = async (duration) => {
        setMuting(true);
        try {
            await domainsAPI.mute(domain.id, duration);
            toast.success(`Alerts muted for ${duration}`);
        } catch (err) {
            toast.error('Failed to mute alerts');
        } finally {
            setMuting(false);
        }
    };

    const handleUnmute = async () => {
        setMuting(true);
        try {
            await domainsAPI.unmute(domain.id);
            toast.success('Alerts unmuted');
        } catch (err) {
            toast.error('Failed to unmute alerts');
        } finally {
            setMuting(false);
        }
    };

    const handleRemoveFromNetwork = async () => {
        setSaving(true);
        try {
            await domainsAPI.update(domain.id, { group_id: null, parent_domain_id: null });
            toast.success('Domain removed from network');
            setShowRemoveDialog(false);
            if (onUpdate) onUpdate();
        } catch (err) {
            toast.error('Failed to remove from network');
        } finally {
            setSaving(false);
        }
    };

    const handleArchive = async () => {
        setSaving(true);
        try {
            await domainsAPI.delete(domain.id);
            toast.success('Domain archived');
            setShowArchiveDialog(false);
            onClose();
            if (onUpdate) onUpdate();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to archive domain');
        } finally {
            setSaving(false);
        }
    };

    if (!domain) return null;

    return (
        <>
            <Sheet open={isOpen} onOpenChange={onClose}>
                <SheetContent className="bg-card border-border w-full sm:max-w-xl p-0 flex flex-col" data-testid="domain-detail-panel">
                    <SheetHeader className="px-6 py-4 border-b border-border bg-card/95 backdrop-blur">
                        <div className="flex items-center justify-between">
                            <SheetTitle className="text-lg font-semibold">Domain Details</SheetTitle>
                            <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
                                <X className="h-4 w-4" />
                            </Button>
                        </div>
                    </SheetHeader>

                    <ScrollArea className="flex-1">
                        <div className="p-6 space-y-6">
                            {/* SECTION 1: DOMAIN OVERVIEW */}
                            <section data-testid="section-overview">
                                <div className="flex items-start justify-between gap-4 mb-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-2">
                                            <h2 className="text-xl font-bold font-mono truncate" style={{ color: TIER_COLORS[domain.tier_level] }}>
                                                {domain.domain_name}
                                            </h2>
                                            <a href={`https://${domain.domain_name}`} target="_blank" rel="noopener noreferrer" className="p-1 rounded hover:bg-white/10 text-zinc-400 hover:text-blue-400">
                                                <ExternalLink className="h-4 w-4" />
                                            </a>
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <Badge variant="outline" className="font-normal">{domain.brand_name || 'No Brand'}</Badge>
                                            {domain.category_name && (
                                                <Badge variant="outline" className="font-normal text-teal-400 border-teal-400/30">{domain.category_name}</Badge>
                                            )}
                                            {domain.group_name && (
                                                <Badge variant="outline" className="font-normal text-purple-400 border-purple-400/30">
                                                    <Network className="h-3 w-3 mr-1" />{domain.group_name}
                                                </Badge>
                                            )}
                                        </div>
                                    </div>
                                    <span className={`badge-tier ${getTierBadgeClass(domain.tier_level)} text-sm whitespace-nowrap ${domain.tier_level === 'lp_money_site' ? 'ring-2 ring-amber-500/30' : ''}`}>
                                        {TIER_LABELS[domain.tier_level]}
                                    </span>
                                </div>

                                <div className="flex flex-wrap gap-2">
                                    <Badge variant="outline" className={domain.domain_status === 'canonical' ? 'border-emerald-500/30 text-emerald-400' : 'border-amber-500/30 text-amber-400'}>
                                        {STATUS_LABELS[domain.domain_status]}
                                    </Badge>
                                    <span className={`text-xs px-3 py-1 rounded-full font-mono uppercase ${domain.index_status === 'index' ? 'status-indexed' : 'status-noindex opacity-60'}`}>
                                        {domain.index_status}
                                    </span>
                                </div>
                            </section>

                            <Separator className="bg-border" />

                            {/* SECTION 2: MONITORING STATUS */}
                            <section data-testid="section-monitoring">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                                        <Activity className="h-4 w-4 text-emerald-500" />
                                        Monitoring
                                    </h3>
                                    {canEdit() && domain.monitoring_enabled && (
                                        <Button variant="ghost" size="sm" onClick={handleCheckNow} disabled={checking} className="text-xs">
                                            {checking ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <RefreshCw className="h-3 w-3 mr-1" />}
                                            Check Now
                                        </Button>
                                    )}
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                    <div className="p-3 rounded-lg bg-black/50 border border-border">
                                        <div className="text-xs text-zinc-500 mb-1">Status</div>
                                        <div className={`text-sm font-medium ${domain.ping_status === 'up' ? 'text-emerald-400' : domain.ping_status === 'down' ? 'text-red-400' : 'text-zinc-400'}`}>
                                            {PING_STATUS_LABELS[domain.ping_status] || 'Unknown'}
                                        </div>
                                    </div>
                                    <div className="p-3 rounded-lg bg-black/50 border border-border">
                                        <div className="text-xs text-zinc-500 mb-1">HTTP</div>
                                        <div className="text-sm font-mono text-zinc-300">
                                            {domain.http_status_code || domain.http_status || '-'}
                                        </div>
                                    </div>
                                    <div className="p-3 rounded-lg bg-black/50 border border-border">
                                        <div className="text-xs text-zinc-500 mb-1">Interval</div>
                                        <div className="text-sm text-zinc-300">
                                            {MONITORING_INTERVAL_LABELS[domain.monitoring_interval] || '-'}
                                        </div>
                                    </div>
                                    <div className="p-3 rounded-lg bg-black/50 border border-border">
                                        <div className="text-xs text-zinc-500 mb-1">Last Check</div>
                                        <div className="text-xs text-zinc-400">
                                            {domain.last_check ? formatDateTime(domain.last_check) : 'Never'}
                                        </div>
                                    </div>
                                </div>

                                {canEdit() && (
                                    <div className="mt-3 flex gap-2">
                                        <Button variant="outline" size="sm" onClick={() => handleMute('1h')} disabled={muting} className="text-xs">
                                            <VolumeX className="h-3 w-3 mr-1" /> Mute 1h
                                        </Button>
                                        <Button variant="outline" size="sm" onClick={() => handleMute('24h')} disabled={muting} className="text-xs">
                                            Mute 24h
                                        </Button>
                                        <Button variant="ghost" size="sm" onClick={handleUnmute} disabled={muting} className="text-xs">
                                            <Volume2 className="h-3 w-3 mr-1" /> Unmute
                                        </Button>
                                    </div>
                                )}
                            </section>

                            <Separator className="bg-border" />

                            {/* SECTION 3: ASSET INFO */}
                            <section data-testid="section-asset">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                                        <Calendar className="h-4 w-4 text-blue-500" />
                                        Asset Information
                                    </h3>
                                    {canEdit() && !isEditing && (
                                        <Button variant="ghost" size="sm" onClick={() => setIsEditing(true)} className="text-blue-400 hover:text-blue-300 text-xs">
                                            <Edit className="h-3 w-3 mr-1" /> Edit
                                        </Button>
                                    )}
                                </div>

                                {warnings.length > 0 && (
                                    <div className="space-y-2 mb-4">
                                        {warnings.map((warning, idx) => (
                                            <Alert key={idx} variant={warning.type === 'error' ? 'destructive' : 'default'} className={warning.type === 'error' ? 'bg-red-950/30 border-red-900/50' : 'bg-amber-950/30 border-amber-900/50'}>
                                                <AlertTriangle className={`h-4 w-4 ${warning.type === 'error' ? 'text-red-400' : 'text-amber-400'}`} />
                                                <AlertDescription className={warning.type === 'error' ? 'text-red-300' : 'text-amber-300'}>{warning.message}</AlertDescription>
                                            </Alert>
                                        ))}
                                    </div>
                                )}

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label className="text-zinc-400 text-xs">Registrar</Label>
                                        {isEditing ? (
                                            <Select value={form.registrar || 'none'} onValueChange={(v) => setForm({...form, registrar: v === 'none' ? '' : v})}>
                                                <SelectTrigger className="bg-black border-border h-9"><SelectValue placeholder="Select" /></SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="none">Not set</SelectItem>
                                                    {REGISTRARS.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                                                </SelectContent>
                                            </Select>
                                        ) : (
                                            <div className="text-sm text-white py-2">{domain.registrar || '-'}</div>
                                        )}
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-zinc-400 text-xs">Expiration</Label>
                                        {isEditing ? (
                                            <Input type="date" value={form.expiration_date} onChange={(e) => setForm({...form, expiration_date: e.target.value})} className="bg-black border-border h-9" />
                                        ) : (
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm text-white">{domain.expiration_date ? formatDate(domain.expiration_date) : '-'}</span>
                                                {daysUntilExpiration !== null && (
                                                    <Badge variant="outline" className={`text-[10px] ${getExpirationBadgeClass(daysUntilExpiration)}`}>
                                                        {daysUntilExpiration <= 0 ? 'EXPIRED' : `${daysUntilExpiration}d`}
                                                    </Badge>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-zinc-400 text-xs">Category</Label>
                                        {isEditing ? (
                                            <Select value={form.category_id || 'none'} onValueChange={(v) => setForm({...form, category_id: v === 'none' ? '' : v})}>
                                                <SelectTrigger className="bg-black border-border h-9"><SelectValue placeholder="Select" /></SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="none">None</SelectItem>
                                                    {categories.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                                                </SelectContent>
                                            </Select>
                                        ) : (
                                            <div className="text-sm text-white py-2">{domain.category_name || '-'}</div>
                                        )}
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-zinc-400 text-xs">Auto-Renew</Label>
                                        {isEditing ? (
                                            <div className="flex items-center gap-2 py-2">
                                                <Switch checked={form.auto_renew} onCheckedChange={(v) => setForm({...form, auto_renew: v})} />
                                                <span className="text-sm text-zinc-400">{form.auto_renew ? 'Enabled' : 'Disabled'}</span>
                                            </div>
                                        ) : (
                                            <div className="text-sm text-white py-2">{domain.auto_renew ? 'Yes' : 'No'}</div>
                                        )}
                                    </div>
                                </div>

                                {isEditing && (
                                    <>
                                        <Separator className="my-4 bg-border" />
                                        <h4 className="text-xs font-semibold text-zinc-400 uppercase mb-3">Monitoring Settings</h4>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="space-y-2">
                                                <Label className="text-zinc-400 text-xs">Enable Monitoring</Label>
                                                <div className="flex items-center gap-2 py-2">
                                                    <Switch checked={form.monitoring_enabled} onCheckedChange={(v) => setForm({...form, monitoring_enabled: v})} />
                                                    <span className="text-sm text-zinc-400">{form.monitoring_enabled ? 'Active' : 'Inactive'}</span>
                                                </div>
                                            </div>
                                            <div className="space-y-2">
                                                <Label className="text-zinc-400 text-xs">Check Interval</Label>
                                                <Select value={form.monitoring_interval} onValueChange={(v) => setForm({...form, monitoring_interval: v})}>
                                                    <SelectTrigger className="bg-black border-border h-9"><SelectValue /></SelectTrigger>
                                                    <SelectContent>
                                                        {Object.entries(MONITORING_INTERVAL_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </div>

                                        <Separator className="my-4 bg-border" />
                                        <h4 className="text-xs font-semibold text-zinc-400 uppercase mb-3">SEO Configuration</h4>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="space-y-2">
                                                <Label className="text-zinc-400 text-xs">Domain Status</Label>
                                                <Select value={form.domain_status} onValueChange={(v) => setForm({...form, domain_status: v})}>
                                                    <SelectTrigger className="bg-black border-border h-9"><SelectValue /></SelectTrigger>
                                                    <SelectContent>
                                                        {Object.entries(STATUS_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="space-y-2">
                                                <Label className="text-zinc-400 text-xs">Index Status</Label>
                                                <Select value={form.index_status} onValueChange={(v) => setForm({...form, index_status: v})}>
                                                    <SelectTrigger className="bg-black border-border h-9"><SelectValue /></SelectTrigger>
                                                    <SelectContent>
                                                        {Object.entries(INDEX_STATUS_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="space-y-2">
                                                <Label className="text-zinc-400 text-xs">Tier Level</Label>
                                                <Select value={form.tier_level} onValueChange={(v) => setForm({...form, tier_level: v, parent_domain_id: ''})}>
                                                    <SelectTrigger className="bg-black border-border h-9"><SelectValue /></SelectTrigger>
                                                    <SelectContent>
                                                        {Object.entries(TIER_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="space-y-2">
                                                <Label className="text-zinc-400 text-xs">Network</Label>
                                                <Select value={form.group_id || 'none'} onValueChange={(v) => setForm({...form, group_id: v === 'none' ? '' : v, parent_domain_id: ''})}>
                                                    <SelectTrigger className="bg-black border-border h-9"><SelectValue placeholder="None" /></SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="none">None</SelectItem>
                                                        {groups.map(g => <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>)}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </div>
                                        {form.group_id && form.tier_level !== 'lp_money_site' && (
                                            <div className="mt-4 space-y-2">
                                                <Label className="text-zinc-400 text-xs">Parent Domain</Label>
                                                <Select value={form.parent_domain_id || 'none'} onValueChange={(v) => setForm({...form, parent_domain_id: v === 'none' ? '' : v})}>
                                                    <SelectTrigger className="bg-black border-border h-9"><SelectValue placeholder="None" /></SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="none">None (Root)</SelectItem>
                                                        {availableParents.map(d => <SelectItem key={d.id} value={d.id}>{d.domain_name} ({TIER_LABELS[d.tier_level]})</SelectItem>)}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        )}
                                    </>
                                )}
                            </section>

                            <Separator className="bg-border" />

                            {/* SECTION 4: NETWORK HIERARCHY */}
                            <section data-testid="section-hierarchy">
                                <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider mb-4">Network Hierarchy</h3>
                                {domain.group_id ? (
                                    <div className="bg-black/50 rounded-lg p-4 border border-border">
                                        {parentDomain && (
                                            <div className="mb-3">
                                                <div className="text-xs text-zinc-500 mb-1">Parent Domain</div>
                                                <div className="flex items-center gap-2 p-2 rounded bg-zinc-900/50">
                                                    <ArrowDown className="h-3 w-3 text-zinc-500" />
                                                    <span className="font-mono text-sm text-zinc-300">{parentDomain.domain_name}</span>
                                                    <span className={`badge-tier ${getTierBadgeClass(parentDomain.tier_level)} text-[10px]`}>{TIER_LABELS[parentDomain.tier_level]}</span>
                                                </div>
                                            </div>
                                        )}
                                        <div className="mb-3">
                                            <div className="text-xs text-zinc-500 mb-1">Current Domain</div>
                                            <div className="flex items-center gap-2 p-2 rounded bg-blue-500/10 border border-blue-500/30">
                                                <Globe className="h-3 w-3 text-blue-400" />
                                                <span className="font-mono text-sm text-white font-medium">{domain.domain_name}</span>
                                                <span className={`badge-tier ${getTierBadgeClass(domain.tier_level)} text-[10px]`}>{TIER_LABELS[domain.tier_level]}</span>
                                            </div>
                                        </div>
                                        {childDomains.length > 0 && (
                                            <div>
                                                <div className="text-xs text-zinc-500 mb-1">Child Domains ({childDomains.length})</div>
                                                <div className="space-y-1">
                                                    {childDomains.map(child => (
                                                        <div key={child.id} className="flex items-center gap-2 p-2 rounded bg-zinc-900/50">
                                                            <ChevronRight className="h-3 w-3 text-zinc-500" />
                                                            <span className="font-mono text-sm text-zinc-300">{child.domain_name}</span>
                                                            <span className={`badge-tier ${getTierBadgeClass(child.tier_level)} text-[10px]`}>{TIER_LABELS[child.tier_level]}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                        {!parentDomain && childDomains.length === 0 && domain.tier_level !== 'lp_money_site' && (
                                            <div className="flex items-center gap-2 text-amber-400 text-sm">
                                                <AlertTriangle className="h-4 w-4" />
                                                <span>Orphan domain - no connections</span>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div className="bg-black/50 rounded-lg p-4 border border-border text-center">
                                        <Network className="h-8 w-8 text-zinc-600 mx-auto mb-2" />
                                        <p className="text-zinc-500 text-sm">Not assigned to any network</p>
                                    </div>
                                )}
                            </section>

                            <Separator className="bg-border" />

                            {/* SECTION 5: NOTES */}
                            <section data-testid="section-notes">
                                <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider mb-4">Notes & SEO Context</h3>
                                {isEditing ? (
                                    <Textarea value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} placeholder="Record SEO decisions, tier rationale..." className="bg-black border-border resize-none min-h-[100px]" />
                                ) : (
                                    <div className="bg-black/50 rounded-lg p-4 border border-border">
                                        <p className="text-sm text-zinc-300 whitespace-pre-wrap">{domain.notes || <span className="text-zinc-600 italic">No notes recorded</span>}</p>
                                    </div>
                                )}
                            </section>

                            <Separator className="bg-border" />

                            {/* SECTION 6: HISTORY */}
                            <section data-testid="section-history">
                                <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider mb-4">Activity & History</h3>
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-zinc-500 flex items-center gap-2"><Clock className="h-4 w-4" />Created</span>
                                        <span className="text-zinc-300">{formatDateTime(domain.created_at)}</span>
                                    </div>
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-zinc-500 flex items-center gap-2"><Clock className="h-4 w-4" />Updated</span>
                                        <span className="text-zinc-300">{formatDateTime(domain.updated_at)}</span>
                                    </div>
                                    {history.length > 0 && (
                                        <div className="mt-4 pt-4 border-t border-border">
                                            <div className="text-xs text-zinc-500 mb-2 flex items-center gap-1"><History className="h-3 w-3" />Recent Changes</div>
                                            <div className="space-y-2">
                                                {history.map((log, idx) => (
                                                    <div key={log.id || idx} className="text-xs p-2 rounded bg-zinc-900/50">
                                                        <div className="flex items-center justify-between mb-1">
                                                            <Badge variant="outline" className="text-[10px] capitalize">{log.action}</Badge>
                                                            <span className="text-zinc-600">{formatDate(log.created_at)}</span>
                                                        </div>
                                                        <div className="text-zinc-400 flex items-center gap-1"><User className="h-3 w-3" />{log.user_email}</div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </section>

                            {/* DANGER ZONE */}
                            {canEdit() && !isEditing && (
                                <>
                                    <Separator className="bg-border" />
                                    <section data-testid="section-actions">
                                        <h3 className="text-sm font-semibold text-red-400/70 uppercase tracking-wider mb-4">Danger Zone</h3>
                                        <div className="space-y-2">
                                            {domain.group_id && (
                                                <Button variant="outline" className="w-full justify-start border-amber-900/50 text-amber-400 hover:bg-amber-950/30" onClick={() => setShowRemoveDialog(true)}>
                                                    <Unlink className="h-4 w-4 mr-2" />Remove from Network
                                                </Button>
                                            )}
                                            <Button variant="outline" className="w-full justify-start border-red-900/50 text-red-400 hover:bg-red-950/30" onClick={() => setShowArchiveDialog(true)}>
                                                <Archive className="h-4 w-4 mr-2" />Archive Domain
                                            </Button>
                                        </div>
                                    </section>
                                </>
                            )}
                        </div>
                    </ScrollArea>

                    {/* Footer - Editing */}
                    {isEditing && (
                        <div className="px-6 py-4 border-t border-border bg-card/95 backdrop-blur">
                            <div className="flex items-center justify-end gap-3">
                                <Button variant="outline" onClick={() => { setIsEditing(false); setForm({ domain_status: domain.domain_status, index_status: domain.index_status, tier_level: domain.tier_level, group_id: domain.group_id || '', parent_domain_id: domain.parent_domain_id || '', category_id: domain.category_id || '', registrar: domain.registrar || '', expiration_date: domain.expiration_date ? domain.expiration_date.split('T')[0] : '', auto_renew: domain.auto_renew || false, monitoring_enabled: domain.monitoring_enabled || false, monitoring_interval: domain.monitoring_interval || '1hour', notes: domain.notes || '' }); }}>
                                    Cancel
                                </Button>
                                <Button onClick={handleSave} disabled={saving || hasErrors} className="bg-white text-black hover:bg-zinc-200">
                                    {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                                    Save Changes
                                </Button>
                            </div>
                        </div>
                    )}
                </SheetContent>
            </Sheet>

            {/* Dialogs */}
            <AlertDialog open={showRemoveDialog} onOpenChange={setShowRemoveDialog}>
                <AlertDialogContent className="bg-card border-border">
                    <AlertDialogHeader>
                        <AlertDialogTitle>Remove from Network</AlertDialogTitle>
                        <AlertDialogDescription>Remove <span className="text-white font-mono">{domain?.domain_name}</span> from the network?</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleRemoveFromNetwork} className="bg-amber-600 hover:bg-amber-700">
                            {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Remove
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog open={showArchiveDialog} onOpenChange={setShowArchiveDialog}>
                <AlertDialogContent className="bg-card border-border">
                    <AlertDialogHeader>
                        <AlertDialogTitle>Archive Domain</AlertDialogTitle>
                        <AlertDialogDescription>Permanently delete <span className="text-white font-mono">{domain?.domain_name}</span>?</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleArchive} className="bg-red-600 hover:bg-red-700">
                            {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Archive
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
};

export default DomainDetailPanel;
