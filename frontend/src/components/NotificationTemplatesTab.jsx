import { useState, useEffect, useCallback } from 'react';
import { notificationTemplatesAPI } from '../lib/api';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from './ui/collapsible';
import { toast } from 'sonner';
import { 
    Loader2, 
    FileText, 
    Eye, 
    RotateCcw, 
    Save, 
    CheckCircle, 
    AlertCircle,
    ChevronDown,
    ChevronRight,
    Copy,
    Info
} from 'lucide-react';

// Event type labels for display
const EVENT_TYPE_LABELS = {
    'seo_change': 'SEO Structure Change',
    'seo_network_created': 'New Network Created',
    'seo_optimization': 'Optimization Activity',
    'seo_optimization_status': 'Optimization Status Update',
    'seo_complaint': 'Optimization Complaint',
    'seo_project_complaint': 'Project-Level Complaint',
    'seo_reminder': 'Optimization Reminder',
    'domain_expiration': 'Domain Expiration Alert',
    'domain_down': 'Domain Down Alert',
    'seo_node_deleted': 'Node Deleted',
    'test': 'Test Notification',
};

// Channel labels
const CHANNEL_LABELS = {
    'telegram': 'Telegram',
    'email': 'Email',
};

export default function NotificationTemplatesTab() {
    const [loading, setLoading] = useState(true);
    const [templates, setTemplates] = useState([]);
    const [variables, setVariables] = useState({});
    const [events, setEvents] = useState([]);
    
    // Edit state
    const [selectedTemplate, setSelectedTemplate] = useState(null);
    const [editedBody, setEditedBody] = useState('');
    const [editedTitle, setEditedTitle] = useState('');
    const [editedEnabled, setEditedEnabled] = useState(true);
    const [hasChanges, setHasChanges] = useState(false);
    
    // Preview state
    const [preview, setPreview] = useState('');
    const [loadingPreview, setLoadingPreview] = useState(false);
    
    // Actions state
    const [saving, setSaving] = useState(false);
    const [resetting, setResetting] = useState(false);
    const [validating, setValidating] = useState(false);
    const [validationResult, setValidationResult] = useState(null);
    
    // Variables panel
    const [variablesOpen, setVariablesOpen] = useState(false);
    
    // Load initial data
    useEffect(() => {
        loadData();
    }, []);
    
    const loadData = async () => {
        setLoading(true);
        try {
            const [templatesRes, variablesRes, eventsRes] = await Promise.all([
                notificationTemplatesAPI.list(),
                notificationTemplatesAPI.getVariables(),
                notificationTemplatesAPI.getEvents(),
            ]);
            
            setTemplates(templatesRes.data.templates || []);
            setVariables(variablesRes.data.variables || {});
            setEvents(eventsRes.data.events || []);
        } catch (err) {
            console.error('Failed to load templates:', err);
            toast.error('Failed to load notification templates');
        } finally {
            setLoading(false);
        }
    };
    
    // Select a template for editing
    const handleSelectTemplate = useCallback(async (template) => {
        setSelectedTemplate(template);
        setEditedBody(template.template_body || '');
        setEditedTitle(template.title || '');
        setEditedEnabled(template.enabled !== false);
        setHasChanges(false);
        setPreview('');
        setValidationResult(null);
        
        // Load preview
        loadPreview(template.channel, template.event_type);
    }, []);
    
    // Load preview for a template
    const loadPreview = async (channel, eventType, body = null) => {
        setLoadingPreview(true);
        try {
            const res = await notificationTemplatesAPI.preview(channel, eventType, body);
            setPreview(res.data.preview || '');
        } catch (err) {
            console.error('Failed to load preview:', err);
            setPreview('Error loading preview');
        } finally {
            setLoadingPreview(false);
        }
    };
    
    // Handle body change
    const handleBodyChange = (value) => {
        setEditedBody(value);
        setHasChanges(true);
        setValidationResult(null);
    };
    
    // Handle title change
    const handleTitleChange = (value) => {
        setEditedTitle(value);
        setHasChanges(true);
    };
    
    // Handle enabled change
    const handleEnabledChange = (value) => {
        setEditedEnabled(value);
        setHasChanges(true);
    };
    
    // Validate template
    const handleValidate = async () => {
        setValidating(true);
        try {
            const res = await notificationTemplatesAPI.validate(editedBody);
            setValidationResult(res.data);
            
            if (res.data.valid) {
                toast.success('Template is valid');
            } else {
                toast.error(`Invalid variables: ${res.data.invalid_variables.join(', ')}`);
            }
        } catch (err) {
            toast.error('Validation failed');
        } finally {
            setValidating(false);
        }
    };
    
    // Update preview with current edits
    const handleRefreshPreview = async () => {
        if (!selectedTemplate) return;
        await loadPreview(selectedTemplate.channel, selectedTemplate.event_type, editedBody);
    };
    
    // Save template
    const handleSave = async () => {
        if (!selectedTemplate) return;
        
        setSaving(true);
        try {
            await notificationTemplatesAPI.update(
                selectedTemplate.channel,
                selectedTemplate.event_type,
                {
                    title: editedTitle,
                    template_body: editedBody,
                    enabled: editedEnabled,
                }
            );
            
            toast.success('Template saved successfully');
            setHasChanges(false);
            
            // Reload templates
            await loadData();
            
            // Update selected template
            const updatedTemplate = {
                ...selectedTemplate,
                title: editedTitle,
                template_body: editedBody,
                enabled: editedEnabled,
            };
            setSelectedTemplate(updatedTemplate);
            
        } catch (err) {
            console.error('Failed to save template:', err);
            const errorMsg = err.response?.data?.detail || 'Failed to save template';
            toast.error(errorMsg);
        } finally {
            setSaving(false);
        }
    };
    
    // Reset template to default
    const handleReset = async () => {
        if (!selectedTemplate) return;
        
        if (!confirm('Are you sure you want to reset this template to its default? This cannot be undone.')) {
            return;
        }
        
        setResetting(true);
        try {
            const res = await notificationTemplatesAPI.reset(
                selectedTemplate.channel,
                selectedTemplate.event_type
            );
            
            toast.success('Template reset to default');
            
            // Update state
            setEditedBody(res.data.template_body || '');
            setEditedTitle(res.data.title || '');
            setEditedEnabled(true);
            setHasChanges(false);
            
            // Reload preview
            await loadPreview(selectedTemplate.channel, selectedTemplate.event_type);
            
            // Reload templates list
            await loadData();
            
        } catch (err) {
            console.error('Failed to reset template:', err);
            toast.error('Failed to reset template');
        } finally {
            setResetting(false);
        }
    };
    
    // Copy variable to clipboard
    const copyVariable = (varName) => {
        navigator.clipboard.writeText(`{{${varName}}}`);
        toast.success(`Copied {{${varName}}} to clipboard`);
    };
    
    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }
    
    // Group templates by channel
    const templatesByChannel = templates.reduce((acc, t) => {
        const ch = t.channel || 'telegram';
        if (!acc[ch]) acc[ch] = [];
        acc[ch].push(t);
        return acc;
    }, {});
    
    return (
        <div className="space-y-6">
            {/* Info Card */}
            <Card className="bg-blue-500/5 border-blue-500/20">
                <CardContent className="py-4">
                    <div className="flex items-start gap-3">
                        <Info className="h-5 w-5 text-blue-500 mt-0.5" />
                        <div className="text-sm text-muted-foreground">
                            <p className="font-medium text-foreground mb-1">Notification Template Editor</p>
                            <p>Customize the messages sent via Telegram and Email for various events. Use <code className="bg-muted px-1 rounded">{'{{variable}}'}</code> syntax to insert dynamic values.</p>
                        </div>
                    </div>
                </CardContent>
            </Card>
            
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Template List */}
                <div className="lg:col-span-1 space-y-4">
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base">Templates</CardTitle>
                            <CardDescription>Select a template to edit</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {Object.entries(templatesByChannel).map(([channel, channelTemplates]) => (
                                <div key={channel} className="space-y-2">
                                    <div className="flex items-center gap-2">
                                        <Badge variant="outline" className="text-xs">
                                            {CHANNEL_LABELS[channel] || channel}
                                        </Badge>
                                    </div>
                                    <div className="space-y-1">
                                        {channelTemplates.map((template) => {
                                            const isSelected = selectedTemplate?.channel === template.channel && 
                                                              selectedTemplate?.event_type === template.event_type;
                                            return (
                                                <button
                                                    key={`${template.channel}-${template.event_type}`}
                                                    onClick={() => handleSelectTemplate(template)}
                                                    className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                                                        isSelected 
                                                            ? 'bg-primary/10 text-primary border border-primary/20' 
                                                            : 'hover:bg-muted'
                                                    }`}
                                                    data-testid={`template-item-${template.event_type}`}
                                                >
                                                    <div className="flex items-center justify-between">
                                                        <span className="font-medium">
                                                            {EVENT_TYPE_LABELS[template.event_type] || template.event_type}
                                                        </span>
                                                        {template.enabled === false && (
                                                            <Badge variant="secondary" className="text-xs">Disabled</Badge>
                                                        )}
                                                    </div>
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                            ))}
                        </CardContent>
                    </Card>
                    
                    {/* Variables Reference */}
                    <Collapsible open={variablesOpen} onOpenChange={setVariablesOpen}>
                        <Card className="bg-card border-border">
                            <CollapsibleTrigger asChild>
                                <CardHeader className="pb-3 cursor-pointer hover:bg-muted/50">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <CardTitle className="text-base">Variables Reference</CardTitle>
                                            <CardDescription>Click to expand</CardDescription>
                                        </div>
                                        {variablesOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                                    </div>
                                </CardHeader>
                            </CollapsibleTrigger>
                            <CollapsibleContent>
                                <CardContent className="pt-0 space-y-3 max-h-[400px] overflow-y-auto">
                                    {Object.entries(variables).map(([category, vars]) => (
                                        <div key={category}>
                                            <p className="text-xs font-semibold text-muted-foreground uppercase mb-1">
                                                {category}
                                            </p>
                                            <div className="flex flex-wrap gap-1">
                                                {vars.map((v) => (
                                                    <button
                                                        key={v}
                                                        onClick={() => copyVariable(v)}
                                                        className="text-xs bg-muted px-2 py-1 rounded hover:bg-primary/10 hover:text-primary transition-colors"
                                                        title={`Click to copy {{${v}}}`}
                                                    >
                                                        {v}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </CardContent>
                            </CollapsibleContent>
                        </Card>
                    </Collapsible>
                </div>
                
                {/* Editor */}
                <div className="lg:col-span-2 space-y-4">
                    {selectedTemplate ? (
                        <>
                            {/* Editor Card */}
                            <Card className="bg-card border-border">
                                <CardHeader className="pb-3">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <CardTitle className="text-base flex items-center gap-2">
                                                <FileText className="h-4 w-4" />
                                                {EVENT_TYPE_LABELS[selectedTemplate.event_type] || selectedTemplate.event_type}
                                            </CardTitle>
                                            <CardDescription>
                                                Channel: {CHANNEL_LABELS[selectedTemplate.channel] || selectedTemplate.channel}
                                            </CardDescription>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Label htmlFor="template-enabled" className="text-sm">Enabled</Label>
                                            <Switch
                                                id="template-enabled"
                                                checked={editedEnabled}
                                                onCheckedChange={handleEnabledChange}
                                                data-testid="template-enabled-switch"
                                            />
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {/* Title */}
                                    <div className="space-y-2">
                                        <Label htmlFor="template-title">Title</Label>
                                        <input
                                            id="template-title"
                                            type="text"
                                            value={editedTitle}
                                            onChange={(e) => handleTitleChange(e.target.value)}
                                            className="w-full px-3 py-2 text-sm rounded-md border border-input bg-background"
                                            placeholder="Template title..."
                                            data-testid="template-title-input"
                                        />
                                    </div>
                                    
                                    {/* Template Body */}
                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between">
                                            <Label htmlFor="template-body">Template Body</Label>
                                            <div className="flex items-center gap-2">
                                                {validationResult && (
                                                    <Badge variant={validationResult.valid ? 'default' : 'destructive'} className="text-xs">
                                                        {validationResult.valid ? (
                                                            <><CheckCircle className="h-3 w-3 mr-1" /> Valid</>
                                                        ) : (
                                                            <><AlertCircle className="h-3 w-3 mr-1" /> Invalid</>
                                                        )}
                                                    </Badge>
                                                )}
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={handleValidate}
                                                    disabled={validating}
                                                    data-testid="validate-template-btn"
                                                >
                                                    {validating ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Validate'}
                                                </Button>
                                            </div>
                                        </div>
                                        <Textarea
                                            id="template-body"
                                            value={editedBody}
                                            onChange={(e) => handleBodyChange(e.target.value)}
                                            className="min-h-[300px] font-mono text-sm"
                                            placeholder="Template content..."
                                            data-testid="template-body-textarea"
                                        />
                                        <p className="text-xs text-muted-foreground">
                                            Use {'{{variable}}'} syntax for dynamic values. Click variables in the reference panel to copy.
                                        </p>
                                    </div>
                                    
                                    {/* Actions */}
                                    <div className="flex items-center justify-between pt-2 border-t">
                                        <Button
                                            variant="outline"
                                            onClick={handleReset}
                                            disabled={resetting}
                                            data-testid="reset-template-btn"
                                        >
                                            {resetting ? (
                                                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                            ) : (
                                                <RotateCcw className="h-4 w-4 mr-2" />
                                            )}
                                            Reset to Default
                                        </Button>
                                        <div className="flex items-center gap-2">
                                            <Button
                                                variant="outline"
                                                onClick={handleRefreshPreview}
                                                disabled={loadingPreview}
                                                data-testid="refresh-preview-btn"
                                            >
                                                {loadingPreview ? (
                                                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                                ) : (
                                                    <Eye className="h-4 w-4 mr-2" />
                                                )}
                                                Preview
                                            </Button>
                                            <Button
                                                onClick={handleSave}
                                                disabled={saving || !hasChanges}
                                                data-testid="save-template-btn"
                                            >
                                                {saving ? (
                                                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                                ) : (
                                                    <Save className="h-4 w-4 mr-2" />
                                                )}
                                                Save Changes
                                            </Button>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                            
                            {/* Preview Card */}
                            <Card className="bg-card border-border">
                                <CardHeader className="pb-3">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <CardTitle className="text-base flex items-center gap-2">
                                                <Eye className="h-4 w-4" />
                                                Live Preview
                                            </CardTitle>
                                            <CardDescription>How the notification will appear with sample data</CardDescription>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => {
                                                navigator.clipboard.writeText(preview);
                                                toast.success('Preview copied to clipboard');
                                            }}
                                        >
                                            <Copy className="h-4 w-4" />
                                        </Button>
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    {loadingPreview ? (
                                        <div className="flex items-center justify-center py-8">
                                            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : (
                                        <div 
                                            className="bg-muted/50 rounded-lg p-4 text-sm font-mono whitespace-pre-wrap max-h-[400px] overflow-y-auto"
                                            data-testid="template-preview"
                                            dangerouslySetInnerHTML={{ 
                                                __html: preview
                                                    .replace(/</g, '&lt;')
                                                    .replace(/>/g, '&gt;')
                                                    .replace(/&lt;b&gt;/g, '<b>')
                                                    .replace(/&lt;\/b&gt;/g, '</b>')
                                                    .replace(/&lt;i&gt;/g, '<i>')
                                                    .replace(/&lt;\/i&gt;/g, '</i>')
                                                    .replace(/&lt;code&gt;/g, '<code>')
                                                    .replace(/&lt;\/code&gt;/g, '</code>')
                                            }}
                                        />
                                    )}
                                </CardContent>
                            </Card>
                        </>
                    ) : (
                        <Card className="bg-card border-border">
                            <CardContent className="py-12">
                                <div className="text-center text-muted-foreground">
                                    <FileText className="h-12 w-12 mx-auto mb-4 opacity-20" />
                                    <p className="text-lg font-medium">Select a template to edit</p>
                                    <p className="text-sm">Choose a template from the list on the left</p>
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>
        </div>
    );
}
