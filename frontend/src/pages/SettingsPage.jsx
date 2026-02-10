import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../lib/auth';
import { settingsAPI, domainMonitoringTelegramAPI, emailAlertsAPI, weeklyDigestAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Loader2, Settings, Send, MessageCircle, CheckCircle, AlertCircle, Network, Bell, Palette, Clock, Upload, Image, Globe, Shield, Mail, Plus, X, Calendar, Eye, FileText } from 'lucide-react';
import NotificationTemplatesTab from '../components/NotificationTemplatesTab';


// Timezone options
const TIMEZONE_OPTIONS = [
    { value: "Asia/Jakarta", label: "GMT+7 (Asia/Jakarta)" },
    { value: "Asia/Singapore", label: "GMT+8 (Asia/Singapore)" },
    { value: "Asia/Tokyo", label: "GMT+9 (Asia/Tokyo)" },
    { value: "Asia/Bangkok", label: "GMT+7 (Asia/Bangkok)" },
    { value: "Asia/Kolkata", label: "GMT+5:30 (Asia/Kolkata)" },
    { value: "Europe/London", label: "GMT+0 (Europe/London)" },
    { value: "Europe/Paris", label: "GMT+1 (Europe/Paris)" },
    { value: "America/New_York", label: "GMT-5 (America/New_York)" },
    { value: "America/Los_Angeles", label: "GMT-8 (America/Los_Angeles)" },
    { value: "UTC", label: "UTC" },
];

export default function SettingsPage() {
    const { isSuperAdmin } = useAuth();
    const [loading, setLoading] = useState(true);
    
    // SEO Telegram state with topic routing support
    const [seoTelegramConfig, setSeoTelegramConfig] = useState({
        bot_token: '',
        chat_id: '',
        enabled: true,
        enable_topic_routing: false,
        seo_change_topic_id: '',
        seo_optimization_topic_id: '',
        seo_complaint_topic_id: '',
        seo_reminder_topic_id: '',
        seo_leader_telegram_usernames: []  // Multiple Global SEO Leaders
    });
    const [newSeoToken, setNewSeoToken] = useState('');
    const [newSeoChatId, setNewSeoChatId] = useState('');
    const [savingSeo, setSavingSeo] = useState(false);
    const [testingSeo, setTestingSeo] = useState(false);
    
    // Domain Monitoring Telegram state (SEPARATE from SEO)
    const [domainMonitoringConfig, setDomainMonitoringConfig] = useState({
        bot_token: '',
        chat_id: '',
        enabled: true
    });
    const [newDomainMonitoringToken, setNewDomainMonitoringToken] = useState('');
    const [newDomainMonitoringChatId, setNewDomainMonitoringChatId] = useState('');
    const [savingDomainMonitoring, setSavingDomainMonitoring] = useState(false);
    const [testingDomainMonitoring, setTestingDomainMonitoring] = useState(false);
    
    // Branding state
    const [brandingConfig, setBrandingConfig] = useState({
        site_title: 'SEO//NOC',
        site_description: '',
        logo_url: ''
    });
    const [savingBranding, setSavingBranding] = useState(false);
    const [uploadingLogo, setUploadingLogo] = useState(false);
    const fileInputRef = useRef(null);
    
    // Timezone state
    const [timezoneConfig, setTimezoneConfig] = useState({
        default_timezone: 'Asia/Jakarta',
        timezone_label: 'GMT+7'
    });
    const [savingTimezone, setSavingTimezone] = useState(false);
    
    // Email Alerts state
    const [emailAlertsConfig, setEmailAlertsConfig] = useState({
        enabled: false,
        configured: false,
        global_admin_emails: [],
        severity_threshold: 'high',
        include_network_managers: true,
        sender_email: ''
    });
    const [newResendApiKey, setNewResendApiKey] = useState('');
    const [newAdminEmail, setNewAdminEmail] = useState('');
    const [testEmailAddress, setTestEmailAddress] = useState('');
    const [savingEmailAlerts, setSavingEmailAlerts] = useState(false);
    const [testingEmailAlerts, setTestingEmailAlerts] = useState(false);

    // Weekly Digest state
    const [digestConfig, setDigestConfig] = useState({
        enabled: false,
        schedule_day: 'monday',
        schedule_hour: 9,
        schedule_minute: 0,
        include_expiring_domains: true,
        include_down_domains: true,
        include_soft_blocked: true,
        expiring_days_threshold: 30,
        last_sent_at: null
    });
    const [digestPreview, setDigestPreview] = useState(null);
    const [savingDigest, setSavingDigest] = useState(false);
    const [sendingDigest, setSendingDigest] = useState(false);
    const [loadingPreview, setLoadingPreview] = useState(false);

    useEffect(() => {
        loadSettings();
    }, []);

    const loadSettings = async () => {
        try {
            const [seoRes, brandingRes, timezoneRes, domainMonitoringRes, emailAlertsRes, digestRes] = await Promise.all([
                settingsAPI.getSeoTelegram().catch(() => ({ data: { bot_token: '', chat_id: '', enabled: true } })),
                settingsAPI.getBranding().catch(() => ({ data: { site_title: 'SEO//NOC', site_description: '', logo_url: '' } })),
                settingsAPI.getTimezone().catch(() => ({ data: { default_timezone: 'Asia/Jakarta', timezone_label: 'GMT+7' } })),
                domainMonitoringTelegramAPI.getSettings().catch(() => ({ data: { bot_token: '', chat_id: '', enabled: true } })),
                emailAlertsAPI.getSettings().catch(() => ({ data: { enabled: false, configured: false, global_admin_emails: [], severity_threshold: 'high', include_network_managers: true } })),
                weeklyDigestAPI.getSettings().catch(() => ({ data: { enabled: false, schedule_day: 'monday', schedule_hour: 9 } }))
            ]);
            setSeoTelegramConfig(seoRes.data);
            setBrandingConfig(brandingRes.data);
            setTimezoneConfig(timezoneRes.data);
            setDomainMonitoringConfig(domainMonitoringRes.data);
            setEmailAlertsConfig(emailAlertsRes.data);
            setDigestConfig(digestRes.data);
        } catch (err) {
            console.error('Failed to load settings:', err);
        } finally {
            setLoading(false);
        }
    };

    // Domain Monitoring Telegram handlers (SEPARATE channel)
    const handleSaveDomainMonitoring = async () => {
        setSavingDomainMonitoring(true);
        try {
            const data = { enabled: domainMonitoringConfig.enabled };
            if (newDomainMonitoringToken) data.bot_token = newDomainMonitoringToken;
            if (newDomainMonitoringChatId) data.chat_id = newDomainMonitoringChatId;
            
            await domainMonitoringTelegramAPI.updateSettings(data);
            toast.success('Domain Monitoring Telegram settings saved');
            setNewDomainMonitoringToken('');
            setNewDomainMonitoringChatId('');
            loadSettings();
        } catch (err) {
            toast.error('Failed to save Domain Monitoring settings');
        } finally {
            setSavingDomainMonitoring(false);
        }
    };

    const handleTestDomainMonitoring = async () => {
        setTestingDomainMonitoring(true);
        try {
            await domainMonitoringTelegramAPI.testAlert();
            toast.success('Test message sent to Domain Monitoring channel');
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to send test message. Configure bot_token and chat_id first.');
        } finally {
            setTestingDomainMonitoring(false);
        }
    };
    
    // SEO Telegram handlers
    const handleSaveSeo = async () => {
        setSavingSeo(true);
        try {
            const data = { 
                enabled: seoTelegramConfig.enabled,
                enable_topic_routing: seoTelegramConfig.enable_topic_routing,
                seo_change_topic_id: seoTelegramConfig.seo_change_topic_id || null,
                seo_optimization_topic_id: seoTelegramConfig.seo_optimization_topic_id || null,
                seo_complaint_topic_id: seoTelegramConfig.seo_complaint_topic_id || null,
                seo_reminder_topic_id: seoTelegramConfig.seo_reminder_topic_id || null,
                seo_leader_telegram_usernames: seoTelegramConfig.seo_leader_telegram_usernames || []
            };
            if (newSeoToken) data.bot_token = newSeoToken;
            if (newSeoChatId) data.chat_id = newSeoChatId;
            
            await settingsAPI.updateSeoTelegram(data);
            toast.success('Pengaturan Telegram SEO berhasil disimpan');
            setNewSeoToken('');
            setNewSeoChatId('');
            loadSettings();
        } catch (err) {
            toast.error('Gagal menyimpan pengaturan');
        } finally {
            setSavingSeo(false);
        }
    };
    
    const handleTestSeo = async () => {
        setTestingSeo(true);
        try {
            await settingsAPI.testSeoTelegram();
            toast.success('Pesan test berhasil dikirim! Cek Telegram Anda.');
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Gagal mengirim pesan test');
        } finally {
            setTestingSeo(false);
        }
    };
    
    const handleToggleSeoEnabled = async (enabled) => {
        setSeoTelegramConfig(prev => ({ ...prev, enabled }));
        try {
            await settingsAPI.updateSeoTelegram({ enabled });
            toast.success(enabled ? 'Notifikasi SEO diaktifkan' : 'Notifikasi SEO dinonaktifkan');
        } catch (err) {
            setSeoTelegramConfig(prev => ({ ...prev, enabled: !enabled }));
            toast.error('Gagal mengubah pengaturan');
        }
    };
    
    // Branding handlers
    const handleSaveBranding = async () => {
        setSavingBranding(true);
        try {
            await settingsAPI.updateBranding(brandingConfig);
            toast.success('Branding settings saved');
            loadSettings();
        } catch (err) {
            toast.error('Failed to save branding settings');
        } finally {
            setSavingBranding(false);
        }
    };
    
    const handleLogoUpload = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        
        setUploadingLogo(true);
        try {
            const res = await settingsAPI.uploadLogo(file);
            setBrandingConfig(prev => ({ ...prev, logo_url: res.data.logo_url }));
            toast.success('Logo uploaded successfully');
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to upload logo');
        } finally {
            setUploadingLogo(false);
        }
    };
    
    // Timezone handlers
    const handleTimezoneChange = (value) => {
        const selected = TIMEZONE_OPTIONS.find(opt => opt.value === value);
        if (selected) {
            // Extract label (e.g., "GMT+7" from "GMT+7 (Asia/Jakarta)")
            const label = selected.label.split(' ')[0];
            setTimezoneConfig({
                default_timezone: value,
                timezone_label: label
            });
        }
    };
    
    const handleSaveTimezone = async () => {
        setSavingTimezone(true);
        try {
            await settingsAPI.updateTimezone(timezoneConfig);
            toast.success('Timezone settings saved');
            loadSettings();
        } catch (err) {
            toast.error('Failed to save timezone settings');
        } finally {
            setSavingTimezone(false);
        }
    };

    // ==================== EMAIL ALERTS HANDLERS ====================
    
    const handleSaveEmailAlerts = async () => {
        setSavingEmailAlerts(true);
        try {
            const data = {};
            
            // Only send API key if provided (new)
            if (newResendApiKey) {
                data.resend_api_key = newResendApiKey;
            }
            
            // Always send these settings
            data.enabled = emailAlertsConfig.enabled;
            data.severity_threshold = emailAlertsConfig.severity_threshold;
            data.include_network_managers = emailAlertsConfig.include_network_managers;
            data.global_admin_emails = emailAlertsConfig.global_admin_emails;
            
            if (emailAlertsConfig.sender_email) {
                data.sender_email = emailAlertsConfig.sender_email;
            }
            
            const res = await emailAlertsAPI.updateSettings(data);
            setEmailAlertsConfig(res.data);
            setNewResendApiKey('');
            toast.success('Email alert settings saved');
        } catch (err) {
            toast.error('Failed to save email alert settings');
        } finally {
            setSavingEmailAlerts(false);
        }
    };

    const handleTestEmailAlerts = async () => {
        if (!testEmailAddress) {
            toast.error('Please enter a test email address');
            return;
        }
        
        setTestingEmailAlerts(true);
        try {
            await emailAlertsAPI.testEmail(testEmailAddress);
            toast.success(`Test email sent to ${testEmailAddress}`);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to send test email');
        } finally {
            setTestingEmailAlerts(false);
        }
    };

    const handleAddAdminEmail = () => {
        if (!newAdminEmail || !newAdminEmail.includes('@')) {
            toast.error('Please enter a valid email address');
            return;
        }
        
        const emails = [...(emailAlertsConfig.global_admin_emails || [])];
        if (!emails.includes(newAdminEmail.toLowerCase())) {
            emails.push(newAdminEmail.toLowerCase());
            setEmailAlertsConfig({ ...emailAlertsConfig, global_admin_emails: emails });
            setNewAdminEmail('');
        } else {
            toast.error('Email already added');
        }
    };

    const handleRemoveAdminEmail = (email) => {
        const emails = (emailAlertsConfig.global_admin_emails || []).filter(e => e !== email);
        setEmailAlertsConfig({ ...emailAlertsConfig, global_admin_emails: emails });
    };

    // ==================== WEEKLY DIGEST HANDLERS ====================
    
    const handleSaveDigest = async () => {
        setSavingDigest(true);
        try {
            const data = {
                enabled: digestConfig.enabled,
                schedule_day: digestConfig.schedule_day,
                schedule_hour: digestConfig.schedule_hour,
                schedule_minute: digestConfig.schedule_minute,
                include_expiring_domains: digestConfig.include_expiring_domains,
                include_down_domains: digestConfig.include_down_domains,
                include_soft_blocked: digestConfig.include_soft_blocked,
                expiring_days_threshold: digestConfig.expiring_days_threshold
            };
            
            const res = await weeklyDigestAPI.updateSettings(data);
            setDigestConfig(res.data);
            toast.success('Weekly digest settings saved');
        } catch (err) {
            toast.error('Failed to save digest settings');
        } finally {
            setSavingDigest(false);
        }
    };

    const handleSendDigestNow = async () => {
        setSendingDigest(true);
        try {
            const res = await weeklyDigestAPI.sendNow();
            toast.success(`Digest sent to ${res.data.recipients?.length || 0} recipients`);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to send digest');
        } finally {
            setSendingDigest(false);
        }
    };

    const handlePreviewDigest = async () => {
        setLoadingPreview(true);
        try {
            const res = await weeklyDigestAPI.preview();
            setDigestPreview(res.data);
        } catch (err) {
            toast.error('Failed to load preview');
        } finally {
            setLoadingPreview(false);
        }
    };

    if (!isSuperAdmin()) {
        return (
            <Layout>
                <div className="text-center py-16">
                    <p className="text-zinc-400">Access denied. Super Admin only.</p>
                </div>
            </Layout>
        );
    }

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
            <div data-testid="settings-page">
                {/* Header */}
                <div className="page-header">
                    <div className="flex items-center gap-3">
                        <Settings className="h-7 w-7 text-zinc-400" />
                        <div>
                            <h1 className="page-title">Settings</h1>
                            <p className="page-subtitle">Configure system settings and integrations</p>
                        </div>
                    </div>
                </div>

                <div className="max-w-3xl">
                    <Tabs defaultValue="branding" className="w-full">
                        <TabsList className="mb-6 flex-wrap h-auto gap-1">
                            <TabsTrigger value="branding" className="flex items-center gap-2">
                                <Palette className="h-4 w-4" />
                                Branding
                            </TabsTrigger>
                            <TabsTrigger value="timezone" className="flex items-center gap-2">
                                <Clock className="h-4 w-4" />
                                Timezone
                            </TabsTrigger>
                            <TabsTrigger value="seo" className="flex items-center gap-2" data-testid="seo-notifications-tab">
                                <Network className="h-4 w-4" />
                                SEO Notifications
                            </TabsTrigger>
                            <TabsTrigger value="domain-monitoring" className="flex items-center gap-2" data-testid="domain-monitoring-tab">
                                <Globe className="h-4 w-4" />
                                Domain Monitoring
                            </TabsTrigger>
                            <TabsTrigger value="email-alerts" className="flex items-center gap-2" data-testid="email-alerts-tab">
                                <Mail className="h-4 w-4" />
                                Email Alerts
                            </TabsTrigger>
                            <TabsTrigger value="templates" className="flex items-center gap-2" data-testid="notification-templates-tab">
                                <FileText className="h-4 w-4" />
                                Templates
                            </TabsTrigger>
                        </TabsList>
                        
                        {/* Branding Tab */}
                        <TabsContent value="branding" className="space-y-6">
                            <Card className="bg-card border-border">
                                <CardHeader>
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-purple-500/10">
                                            <Palette className="h-5 w-5 text-purple-500" />
                                        </div>
                                        <div>
                                            <CardTitle className="text-lg">App Branding</CardTitle>
                                            <CardDescription>Customize site title, description, and logo</CardDescription>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div>
                                        <Label>Site Title</Label>
                                        <Input
                                            value={brandingConfig.site_title}
                                            onChange={(e) => setBrandingConfig(prev => ({ ...prev, site_title: e.target.value }))}
                                            placeholder="SEO//NOC"
                                            className="mt-1 bg-black border-border"
                                        />
                                        <p className="text-xs text-zinc-500 mt-1">Appears in browser tab and header</p>
                                    </div>
                                    
                                    <div>
                                        <Label>Site Description</Label>
                                        <Textarea
                                            value={brandingConfig.site_description}
                                            onChange={(e) => setBrandingConfig(prev => ({ ...prev, site_description: e.target.value }))}
                                            placeholder="SEO Network Operations Center - Manage your domain networks efficiently"
                                            className="mt-1 bg-black border-border"
                                            rows={2}
                                        />
                                        <p className="text-xs text-zinc-500 mt-1">Meta description for SEO</p>
                                    </div>
                                    
                                    <div>
                                        <Label>Logo</Label>
                                        <div className="flex items-center gap-4 mt-2">
                                            {brandingConfig.logo_url ? (
                                                <div className="w-16 h-16 rounded-lg bg-zinc-800 flex items-center justify-center overflow-hidden border border-border">
                                                    <img src={brandingConfig.logo_url} alt="Logo" className="max-w-full max-h-full object-contain" />
                                                </div>
                                            ) : (
                                                <div className="w-16 h-16 rounded-lg bg-zinc-800 flex items-center justify-center border border-dashed border-zinc-600">
                                                    <Image className="h-6 w-6 text-zinc-500" />
                                                </div>
                                            )}
                                            <div className="flex flex-col gap-2">
                                                <input
                                                    type="file"
                                                    ref={fileInputRef}
                                                    onChange={handleLogoUpload}
                                                    accept="image/png,image/jpeg,image/svg+xml,image/webp"
                                                    className="hidden"
                                                />
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => fileInputRef.current?.click()}
                                                    disabled={uploadingLogo}
                                                >
                                                    {uploadingLogo ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Upload className="h-4 w-4 mr-2" />}
                                                    Upload Logo
                                                </Button>
                                                <p className="text-xs text-zinc-500">PNG, JPEG, SVG, or WebP. Max 2MB.</p>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div className="flex justify-end pt-2">
                                        <Button onClick={handleSaveBranding} disabled={savingBranding}>
                                            {savingBranding && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                            Save Branding
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>
                        
                        {/* Timezone Tab */}
                        <TabsContent value="timezone" className="space-y-6">
                            <Card className="bg-card border-border">
                                <CardHeader>
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-cyan-500/10">
                                            <Clock className="h-5 w-5 text-cyan-500" />
                                        </div>
                                        <div>
                                            <CardTitle className="text-lg">Monitoring Timezone</CardTitle>
                                            <CardDescription>Set default timezone for all monitoring alerts and displays</CardDescription>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="p-4 bg-cyan-500/10 border border-cyan-500/30 rounded-lg">
                                        <p className="text-sm text-cyan-300">
                                            All monitoring timestamps (Domain Expiration, Availability/Ping alerts, Telegram messages) 
                                            will be displayed in the selected timezone. Internal storage remains in UTC.
                                        </p>
                                    </div>
                                    
                                    <div>
                                        <Label>Default Timezone</Label>
                                        <Select
                                            value={timezoneConfig.default_timezone}
                                            onValueChange={handleTimezoneChange}
                                        >
                                            <SelectTrigger className="mt-1 bg-black border-border">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {TIMEZONE_OPTIONS.map(opt => (
                                                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                        <p className="text-xs text-zinc-500 mt-1">
                                            Currently: {timezoneConfig.timezone_label} ({timezoneConfig.default_timezone})
                                        </p>
                                    </div>
                                    
                                    <div className="flex justify-end pt-2">
                                        <Button onClick={handleSaveTimezone} disabled={savingTimezone}>
                                            {savingTimezone && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                            Save Timezone
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>
                        
                        {/* SEO Notifications Tab */}
                        <TabsContent value="seo" className="space-y-6">
                            <Card className="bg-card border-border">
                                <CardHeader>
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-amber-500/10">
                                            <Network className="h-5 w-5 text-amber-500" />
                                        </div>
                                        <div>
                                            <CardTitle className="text-lg">Notifikasi Perubahan SEO</CardTitle>
                                            <CardDescription>Channel Telegram khusus untuk notifikasi perubahan SEO Network</CardDescription>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="flex items-center justify-between p-3 rounded-lg bg-black/50 border border-border">
                                        <div>
                                            <Label className="text-zinc-300">Aktifkan Notifikasi SEO</Label>
                                            <p className="text-xs text-zinc-500 mt-1">Kirim notifikasi ke Telegram setiap ada perubahan SEO</p>
                                        </div>
                                        <Switch checked={seoTelegramConfig.enabled} onCheckedChange={handleToggleSeoEnabled} data-testid="seo-notifications-toggle" />
                                    </div>
                                    
                                    <div className="p-3 rounded-lg bg-black/50 border border-border">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="text-sm text-zinc-400">Status Konfigurasi</span>
                                            {seoTelegramConfig.bot_token && seoTelegramConfig.chat_id ? (
                                                <span className="flex items-center gap-1 text-xs text-emerald-500"><CheckCircle className="h-3 w-3" />Terkonfigurasi</span>
                                            ) : (
                                                <span className="flex items-center gap-1 text-xs text-amber-500"><AlertCircle className="h-3 w-3" />Fallback ke monitoring</span>
                                            )}
                                        </div>
                                        {seoTelegramConfig.bot_token && <div className="text-xs text-zinc-500">Token: <code className="text-zinc-400">{seoTelegramConfig.bot_token}</code></div>}
                                        {seoTelegramConfig.chat_id && <div className="text-xs text-zinc-500">Chat ID: <code className="text-zinc-400">{seoTelegramConfig.chat_id}</code></div>}
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-zinc-400">Bot Token (Opsional)</Label>
                                        <Input value={newSeoToken} onChange={(e) => setNewSeoToken(e.target.value)} placeholder="Kosongkan untuk menggunakan token monitoring" className="bg-black border-border font-mono text-sm" data-testid="seo-telegram-token-input" />
                                        <p className="text-xs text-zinc-600">Jika tidak diisi, akan menggunakan bot token dari channel monitoring</p>
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-zinc-400">Chat ID (Wajib untuk channel terpisah)</Label>
                                        <Input value={newSeoChatId} onChange={(e) => setNewSeoChatId(e.target.value)} placeholder="ID grup/channel untuk notifikasi SEO" className="bg-black border-border font-mono text-sm" data-testid="seo-telegram-chatid-input" />
                                        <p className="text-xs text-zinc-600">Disarankan membuat grup/channel terpisah untuk tim SEO</p>
                                    </div>

                                    {/* Forum Topic Routing Section */}
                                    <div className="mt-6 p-4 rounded-lg border border-amber-500/20 bg-amber-500/5">
                                        <div className="flex items-center justify-between mb-4">
                                            <div>
                                                <Label className="text-amber-400 font-medium">Forum Topic Routing</Label>
                                                <p className="text-xs text-zinc-500 mt-1">Route different notification types to specific forum topics</p>
                                            </div>
                                            <Switch 
                                                checked={seoTelegramConfig.enable_topic_routing} 
                                                onCheckedChange={(checked) => setSeoTelegramConfig({...seoTelegramConfig, enable_topic_routing: checked})}
                                                data-testid="topic-routing-toggle" 
                                            />
                                        </div>
                                        
                                        {seoTelegramConfig.enable_topic_routing && (
                                            <div className="space-y-4 pt-2">
                                                <div className="grid grid-cols-2 gap-4">
                                                    <div className="space-y-1">
                                                        <Label className="text-xs text-zinc-500">SEO Change Topic ID</Label>
                                                        <Input 
                                                            value={seoTelegramConfig.seo_change_topic_id || ''} 
                                                            onChange={(e) => setSeoTelegramConfig({...seoTelegramConfig, seo_change_topic_id: e.target.value})}
                                                            placeholder="e.g., 123" 
                                                            className="bg-black border-border font-mono text-sm h-9" 
                                                            data-testid="seo-change-topic-input"
                                                        />
                                                    </div>
                                                    <div className="space-y-1">
                                                        <Label className="text-xs text-zinc-500">Optimization Topic ID</Label>
                                                        <Input 
                                                            value={seoTelegramConfig.seo_optimization_topic_id || ''} 
                                                            onChange={(e) => setSeoTelegramConfig({...seoTelegramConfig, seo_optimization_topic_id: e.target.value})}
                                                            placeholder="e.g., 124" 
                                                            className="bg-black border-border font-mono text-sm h-9" 
                                                            data-testid="seo-optimization-topic-input"
                                                        />
                                                    </div>
                                                    <div className="space-y-1">
                                                        <Label className="text-xs text-zinc-500">Complaint Topic ID</Label>
                                                        <Input 
                                                            value={seoTelegramConfig.seo_complaint_topic_id || ''} 
                                                            onChange={(e) => setSeoTelegramConfig({...seoTelegramConfig, seo_complaint_topic_id: e.target.value})}
                                                            placeholder="e.g., 125" 
                                                            className="bg-black border-border font-mono text-sm h-9" 
                                                            data-testid="seo-complaint-topic-input"
                                                        />
                                                    </div>
                                                    <div className="space-y-1">
                                                        <Label className="text-xs text-zinc-500">Reminder Topic ID</Label>
                                                        <Input 
                                                            value={seoTelegramConfig.seo_reminder_topic_id || ''} 
                                                            onChange={(e) => setSeoTelegramConfig({...seoTelegramConfig, seo_reminder_topic_id: e.target.value})}
                                                            placeholder="e.g., 126" 
                                                            className="bg-black border-border font-mono text-sm h-9" 
                                                            data-testid="seo-reminder-topic-input"
                                                        />
                                                    </div>
                                                </div>
                                                <p className="text-xs text-zinc-600">Get topic IDs from your Telegram forum group. If a topic ID is missing, messages will go to General.</p>
                                            </div>
                                        )}
                                    </div>

                                    {/* SEO Leader Tagging Section */}
                                    <div className="space-y-3 pt-4 border-t border-border">
                                        <div>
                                            <Label className="text-amber-400 font-medium">Global SEO Leaders</Label>
                                            <p className="text-xs text-zinc-500 mt-1">Telegram usernames untuk di-tag pada semua notifikasi SEO (untuk oversight). Bisa lebih dari satu leader.</p>
                                        </div>
                                        
                                        {/* Current Leaders List */}
                                        {seoTelegramConfig.seo_leader_telegram_usernames?.length > 0 && (
                                            <div className="flex flex-wrap gap-2">
                                                {seoTelegramConfig.seo_leader_telegram_usernames.map((leader, idx) => (
                                                    <Badge 
                                                        key={idx}
                                                        variant="outline"
                                                        className="text-xs bg-amber-500/10 text-amber-400 border-amber-500/30 cursor-pointer hover:bg-red-500/20"
                                                        onClick={() => {
                                                            const updated = seoTelegramConfig.seo_leader_telegram_usernames.filter((_, i) => i !== idx);
                                                            setSeoTelegramConfig({...seoTelegramConfig, seo_leader_telegram_usernames: updated});
                                                        }}
                                                    >
                                                        @{leader.replace('@', '')} ✕
                                                    </Badge>
                                                ))}
                                            </div>
                                        )}
                                        
                                        {/* Add New Leader */}
                                        <div className="flex gap-2">
                                            <Input 
                                                id="new-seo-leader"
                                                placeholder="username (tanpa @)" 
                                                className="bg-black border-border font-mono text-sm h-9 flex-1" 
                                                data-testid="seo-leader-username-input"
                                                onKeyDown={(e) => {
                                                    if (e.key === 'Enter') {
                                                        const input = e.target.value.trim().replace('@', '');
                                                        if (input && !seoTelegramConfig.seo_leader_telegram_usernames?.includes(input)) {
                                                            setSeoTelegramConfig({
                                                                ...seoTelegramConfig, 
                                                                seo_leader_telegram_usernames: [...(seoTelegramConfig.seo_leader_telegram_usernames || []), input]
                                                            });
                                                            e.target.value = '';
                                                        }
                                                    }
                                                }}
                                            />
                                            <Button 
                                                variant="outline" 
                                                size="sm"
                                                onClick={() => {
                                                    const input = document.getElementById('new-seo-leader');
                                                    const value = input.value.trim().replace('@', '');
                                                    if (value && !seoTelegramConfig.seo_leader_telegram_usernames?.includes(value)) {
                                                        setSeoTelegramConfig({
                                                            ...seoTelegramConfig, 
                                                            seo_leader_telegram_usernames: [...(seoTelegramConfig.seo_leader_telegram_usernames || []), value]
                                                        });
                                                        input.value = '';
                                                    }
                                                }}
                                            >
                                                Add Leader
                                            </Button>
                                        </div>
                                        <p className="text-xs text-zinc-600">
                                            SEO Leaders akan di-tag pada semua notifikasi SEO (change, optimization, node update). 
                                            Untuk notifikasi complaint, hanya Network Manager yang akan di-tag.
                                        </p>
                                    </div>

                                    <div className="flex items-center gap-3 pt-2">
                                        <Button onClick={handleSaveSeo} disabled={savingSeo || (!newSeoToken && !newSeoChatId && !seoTelegramConfig.enable_topic_routing)} className="bg-amber-500 text-black hover:bg-amber-400" data-testid="save-seo-telegram-btn">
                                            {savingSeo && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Simpan Pengaturan
                                        </Button>
                                        <Button variant="outline" onClick={handleTestSeo} disabled={testingSeo} data-testid="test-seo-telegram-btn">
                                            {testingSeo ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Send className="h-4 w-4 mr-2" />}Kirim Test
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>

                            <Card className="bg-card border-border">
                                <CardHeader>
                                    <CardTitle className="text-base">Contoh Format Notifikasi SEO</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <pre className="text-xs bg-black/50 p-4 rounded-lg overflow-x-auto text-zinc-400 whitespace-pre-wrap">{`👤 PEMBARUAN OPTIMASI SEO

Antoni telah melakukan perubahan optimasi bagan SEO
pada network 'Main SEO Network' untuk brand 'Panen138',
dengan detail sebagai berikut:

📌 Ringkasan Aksi
• Aksi            : Mengubah Target Node
• Dilakukan Oleh  : Antoni (admin@seonoc.com)
• Waktu           : 2026-02-09 18:21 UTC

📝 Alasan Perubahan:
"Domain diarahkan langsung ke domain utama karena
 memiliki power besar"

🔄 Perubahan yang Dilakukan:
• Node             : domaina.com/example
• Role             : Supporting
• Status           : Canonical
• Target Sebelumnya: tier1-site1.com
• Target Baru      : moneysite.com

🧭 STRUKTUR SEO TERKINI:
LP / Money Site:
  • moneysite.com

Tier 1:
  • domaina.com → moneysite.com
  • domaina.com/example → moneysite.com
  • tier1-site1.com → moneysite.com

Tier 2:
  • tier1-site2.com → domaina.com/example`}</pre>
                                </CardContent>
                            </Card>
                            
                            <Card className="bg-card border-border">
                                <CardHeader>
                                    <CardTitle className="text-base">Kapan Notifikasi Dikirim?</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-2 text-sm text-zinc-400">
                                        <p>Notifikasi dikirim untuk setiap perubahan SEO berikut:</p>
                                        <ul className="list-disc list-inside space-y-1 ml-2">
                                            <li>Membuat SEO Network baru</li>
                                            <li>Menambah/Mengubah/Menghapus node</li>
                                            <li>Mengubah target node (relink)</li>
                                            <li>Mengubah role (main ↔ supporting)</li>
                                            <li>Mengubah status domain (canonical/301/302)</li>
                                            <li>Mengubah status index</li>
                                            <li>Mengubah path yang dioptimasi</li>
                                        </ul>
                                        <p className="text-xs text-zinc-500 mt-3">Rate limit: 1 pesan per network per menit untuk mencegah spam</p>
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>

                        {/* Domain Monitoring Tab - SEPARATE from SEO */}
                        <TabsContent value="domain-monitoring" className="space-y-6">
                            <Card className="bg-card border-border">
                                <CardHeader>
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-blue-500/10">
                                            <Globe className="h-5 w-5 text-blue-400" />
                                        </div>
                                        <div>
                                            <CardTitle>Domain Monitoring Telegram</CardTitle>
                                            <CardDescription>
                                                Channel terpisah untuk alert domain (expiration & availability).
                                                <span className="block text-amber-400 mt-1">⚠️ BUKAN untuk SEO change notifications - gunakan tab SEO Notifications.</span>
                                            </CardDescription>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {/* Enable toggle */}
                                    <div className="flex items-center justify-between p-3 rounded-lg bg-blue-500/5 border border-blue-500/20">
                                        <div>
                                            <Label className="text-blue-400">Aktifkan Domain Monitoring Alerts</Label>
                                            <p className="text-xs text-zinc-500 mt-1">Kirim alert ke Telegram untuk expiration & availability</p>
                                        </div>
                                        <Switch 
                                            checked={domainMonitoringConfig.enabled} 
                                            onCheckedChange={(checked) => setDomainMonitoringConfig({...domainMonitoringConfig, enabled: checked})}
                                            data-testid="domain-monitoring-toggle"
                                        />
                                    </div>

                                    {/* Status */}
                                    <div className="flex items-center justify-between p-3 rounded-lg bg-card border border-border">
                                        <span className="text-zinc-400">Status Konfigurasi</span>
                                        {domainMonitoringConfig.configured ? (
                                            <span className="flex items-center gap-2 text-emerald-400">
                                                <CheckCircle className="h-4 w-4" /> Terkonfigurasi
                                            </span>
                                        ) : (
                                            <span className="flex items-center gap-2 text-amber-400">
                                                <AlertCircle className="h-4 w-4" /> Belum dikonfigurasi
                                            </span>
                                        )}
                                    </div>

                                    {/* Bot Token */}
                                    <div className="space-y-2">
                                        <Label className="text-zinc-400">Bot Token (Wajib untuk channel terpisah)</Label>
                                        <Input 
                                            value={newDomainMonitoringToken} 
                                            onChange={(e) => setNewDomainMonitoringToken(e.target.value)} 
                                            type="password"
                                            placeholder={domainMonitoringConfig.bot_token ? '••••••••••' : 'Masukkan bot token'} 
                                            className="bg-black border-border font-mono text-sm" 
                                            data-testid="domain-monitoring-token-input"
                                        />
                                        <p className="text-xs text-zinc-600">Buat bot baru di @BotFather untuk channel monitoring terpisah</p>
                                    </div>

                                    {/* Chat ID */}
                                    <div className="space-y-2">
                                        <Label className="text-zinc-400">Chat ID (Wajib)</Label>
                                        <Input 
                                            value={newDomainMonitoringChatId} 
                                            onChange={(e) => setNewDomainMonitoringChatId(e.target.value)} 
                                            placeholder={domainMonitoringConfig.chat_id || 'ID grup/channel untuk monitoring alerts'} 
                                            className="bg-black border-border font-mono text-sm" 
                                            data-testid="domain-monitoring-chatid-input"
                                        />
                                        <p className="text-xs text-zinc-600">Gunakan grup/channel BERBEDA dari SEO notifications</p>
                                    </div>

                                    {/* Actions */}
                                    <div className="flex items-center gap-3 pt-2">
                                        <Button 
                                            onClick={handleSaveDomainMonitoring} 
                                            disabled={savingDomainMonitoring || (!newDomainMonitoringToken && !newDomainMonitoringChatId)} 
                                            className="bg-blue-500 text-white hover:bg-blue-400" 
                                            data-testid="save-domain-monitoring-btn"
                                        >
                                            {savingDomainMonitoring && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                            Simpan Pengaturan
                                        </Button>
                                        <Button 
                                            variant="outline" 
                                            onClick={handleTestDomainMonitoring} 
                                            disabled={testingDomainMonitoring || !domainMonitoringConfig.configured} 
                                            data-testid="test-domain-monitoring-btn"
                                        >
                                            {testingDomainMonitoring ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Send className="h-4 w-4 mr-2" />}
                                            Kirim Test
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Alert Types Info */}
                            <Card className="bg-card border-border">
                                <CardHeader>
                                    <CardTitle className="text-base">Jenis Alert Domain Monitoring</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20">
                                            <div className="flex items-center gap-2 mb-2">
                                                <span className="text-red-400 font-medium">🔴 Domain Expiration</span>
                                            </div>
                                            <ul className="text-xs text-zinc-400 space-y-1">
                                                <li>• Alert di 30, 14, 7 hari sebelum expired</li>
                                                <li>• Daily reminder jika {"<"} 7 hari</li>
                                                <li>• Termasuk SEO impact jika domain ada di network</li>
                                            </ul>
                                        </div>
                                        <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                                            <div className="flex items-center gap-2 mb-2">
                                                <span className="text-amber-400 font-medium">🟠 Domain Availability</span>
                                            </div>
                                            <ul className="text-xs text-zinc-400 space-y-1">
                                                <li>• DOWN = CRITICAL (timeout, DNS error, 5xx)</li>
                                                <li>• SOFT BLOCK = WARNING (Cloudflare, captcha)</li>
                                                <li>• Recovery notification saat UP kembali</li>
                                            </ul>
                                        </div>
                                    </div>
                                    
                                    <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className="text-emerald-400 font-medium">🧩 SEO-Aware Alerts</span>
                                        </div>
                                        <p className="text-xs text-zinc-400">
                                            Setiap alert mencakup: SEO Context, Full Structure Chain ke Money Site, Downstream Impact, dan Impact Score untuk prioritas.
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>

                        {/* Email Alerts Tab */}
                        <TabsContent value="email-alerts" className="space-y-6" data-testid="email-alerts-content">
                            <Card className="bg-card border-border">
                                <CardHeader>
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-blue-500/10">
                                            <Mail className="h-5 w-5 text-blue-500" />
                                        </div>
                                        <div>
                                            <CardTitle>Email Alert Configuration</CardTitle>
                                            <CardDescription>
                                                Redundancy layer for HIGH/CRITICAL domain alerts via email
                                            </CardDescription>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-6">
                                    {/* Enable/Disable */}
                                    <div className="flex items-center justify-between p-4 rounded-lg bg-zinc-900/50 border border-border">
                                        <div>
                                            <p className="font-medium text-white">Enable Email Alerts</p>
                                            <p className="text-xs text-zinc-500">Send email notifications for critical domain issues</p>
                                        </div>
                                        <Switch
                                            checked={emailAlertsConfig.enabled}
                                            onCheckedChange={(checked) => setEmailAlertsConfig({...emailAlertsConfig, enabled: checked})}
                                            data-testid="email-alerts-enabled-switch"
                                        />
                                    </div>

                                    {/* Status Badge */}
                                    <div className={`flex items-center gap-2 p-3 rounded-lg ${emailAlertsConfig.configured ? 'bg-emerald-500/10 border border-emerald-500/30' : 'bg-amber-500/10 border border-amber-500/30'}`}>
                                        {emailAlertsConfig.configured ? (
                                            <>
                                                <CheckCircle className="h-4 w-4 text-emerald-500" />
                                                <span className="text-sm text-emerald-400">Resend API configured</span>
                                            </>
                                        ) : (
                                            <>
                                                <AlertCircle className="h-4 w-4 text-amber-500" />
                                                <span className="text-sm text-amber-400">Resend API key required</span>
                                            </>
                                        )}
                                    </div>

                                    {/* Resend API Key */}
                                    <div className="space-y-2">
                                        <Label>Resend API Key</Label>
                                        <Input 
                                            type="password"
                                            value={newResendApiKey} 
                                            onChange={(e) => setNewResendApiKey(e.target.value)} 
                                            placeholder={emailAlertsConfig.configured ? '••••••••••••••••' : 'Enter Resend API key'} 
                                            className="bg-black border-border font-mono text-sm" 
                                            data-testid="resend-api-key-input"
                                        />
                                        <p className="text-xs text-zinc-600">
                                            Get your API key from <a href="https://resend.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">resend.com/api-keys</a>
                                        </p>
                                    </div>

                                    {/* Sender Email (optional) */}
                                    <div className="space-y-2">
                                        <Label>Sender Email (Optional)</Label>
                                        <Input 
                                            value={emailAlertsConfig.sender_email || ''} 
                                            onChange={(e) => setEmailAlertsConfig({...emailAlertsConfig, sender_email: e.target.value})} 
                                            placeholder="alerts@yourdomain.com (default: onboarding@resend.dev)" 
                                            className="bg-black border-border font-mono text-sm" 
                                            data-testid="sender-email-input"
                                        />
                                        <p className="text-xs text-zinc-600">Must be a verified domain in Resend</p>
                                    </div>

                                    {/* Severity Threshold */}
                                    <div className="space-y-2">
                                        <Label>Severity Threshold</Label>
                                        <Select 
                                            value={emailAlertsConfig.severity_threshold || 'high'}
                                            onValueChange={(val) => setEmailAlertsConfig({...emailAlertsConfig, severity_threshold: val})}
                                        >
                                            <SelectTrigger className="bg-black border-border" data-testid="severity-threshold-select">
                                                <SelectValue placeholder="Select threshold" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="high">HIGH and above (includes soft blocks)</SelectItem>
                                                <SelectItem value="critical">CRITICAL only (domain down/expired)</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        <p className="text-xs text-zinc-600">Only alerts at or above this severity will be sent</p>
                                    </div>

                                    {/* Include Network Managers */}
                                    <div className="flex items-center justify-between p-4 rounded-lg bg-zinc-900/50 border border-border">
                                        <div>
                                            <p className="font-medium text-white">Include Network Managers</p>
                                            <p className="text-xs text-zinc-500">Send emails to managers of affected SEO networks</p>
                                        </div>
                                        <Switch
                                            checked={emailAlertsConfig.include_network_managers}
                                            onCheckedChange={(checked) => setEmailAlertsConfig({...emailAlertsConfig, include_network_managers: checked})}
                                            data-testid="include-managers-switch"
                                        />
                                    </div>

                                    {/* Global Admin Emails */}
                                    <div className="space-y-3">
                                        <Label>Global Admin Emails</Label>
                                        <div className="flex gap-2">
                                            <Input 
                                                type="email"
                                                value={newAdminEmail} 
                                                onChange={(e) => setNewAdminEmail(e.target.value)} 
                                                placeholder="admin@company.com" 
                                                className="bg-black border-border text-sm flex-1" 
                                                onKeyDown={(e) => e.key === 'Enter' && handleAddAdminEmail()}
                                                data-testid="add-admin-email-input"
                                            />
                                            <Button 
                                                variant="outline" 
                                                size="icon"
                                                onClick={handleAddAdminEmail}
                                                data-testid="add-admin-email-btn"
                                            >
                                                <Plus className="h-4 w-4" />
                                            </Button>
                                        </div>
                                        <p className="text-xs text-zinc-600">These emails receive ALL alerts regardless of network</p>
                                        
                                        {/* Email List */}
                                        {emailAlertsConfig.global_admin_emails?.length > 0 && (
                                            <div className="flex flex-wrap gap-2 pt-2">
                                                {emailAlertsConfig.global_admin_emails.map((email, idx) => (
                                                    <div 
                                                        key={idx} 
                                                        className="flex items-center gap-1 px-2 py-1 rounded bg-zinc-800 border border-zinc-700 text-sm"
                                                    >
                                                        <span className="text-zinc-300">{email}</span>
                                                        <button 
                                                            onClick={() => handleRemoveAdminEmail(email)}
                                                            className="text-zinc-500 hover:text-red-400 ml-1"
                                                            data-testid={`remove-email-${idx}`}
                                                        >
                                                            <X className="h-3 w-3" />
                                                        </button>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>

                                    {/* Save Button */}
                                    <div className="flex items-center gap-3 pt-2">
                                        <Button 
                                            onClick={handleSaveEmailAlerts} 
                                            disabled={savingEmailAlerts} 
                                            className="bg-blue-500 text-white hover:bg-blue-400" 
                                            data-testid="save-email-alerts-btn"
                                        >
                                            {savingEmailAlerts && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                            Save Settings
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Test Email Section */}
                            <Card className="bg-card border-border">
                                <CardHeader>
                                    <CardTitle className="text-base">Test Email Configuration</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="flex gap-2">
                                        <Input 
                                            type="email"
                                            value={testEmailAddress} 
                                            onChange={(e) => setTestEmailAddress(e.target.value)} 
                                            placeholder="your@email.com" 
                                            className="bg-black border-border text-sm flex-1" 
                                            data-testid="test-email-address-input"
                                        />
                                        <Button 
                                            variant="outline" 
                                            onClick={handleTestEmailAlerts} 
                                            disabled={testingEmailAlerts || !emailAlertsConfig.configured}
                                            data-testid="test-email-btn"
                                        >
                                            {testingEmailAlerts ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Send className="h-4 w-4 mr-2" />}
                                            Send Test
                                        </Button>
                                    </div>
                                    {!emailAlertsConfig.configured && (
                                        <p className="text-xs text-amber-400">Save your Resend API key first to enable testing</p>
                                    )}
                                </CardContent>
                            </Card>

                            {/* Info Card */}
                            <Card className="bg-card border-border">
                                <CardHeader>
                                    <CardTitle className="text-base">How Email Alerts Work</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20">
                                            <div className="flex items-center gap-2 mb-2">
                                                <span className="text-red-400 font-medium">CRITICAL Alerts</span>
                                            </div>
                                            <ul className="text-xs text-zinc-400 space-y-1">
                                                <li>• Domain DOWN (timeout, DNS error, 5xx)</li>
                                                <li>• Domain expired or expiring in ≤3 days</li>
                                                <li>• Always sent via email + Telegram</li>
                                            </ul>
                                        </div>
                                        <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                                            <div className="flex items-center gap-2 mb-2">
                                                <span className="text-amber-400 font-medium">HIGH Alerts</span>
                                            </div>
                                            <ul className="text-xs text-zinc-400 space-y-1">
                                                <li>• Soft blocked (Cloudflare, captcha)</li>
                                                <li>• Domain expiring in 4-7 days</li>
                                                <li>• Sent if threshold = HIGH</li>
                                            </ul>
                                        </div>
                                    </div>
                                    
                                    <div className="p-3 rounded-lg bg-blue-500/5 border border-blue-500/20">
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className="text-blue-400 font-medium">Recipient Logic</span>
                                        </div>
                                        <p className="text-xs text-zinc-400">
                                            <strong>Global Admins</strong> receive ALL alerts. <strong>Network Managers</strong> receive alerts for domains in their networks. 
                                            Email acts as a <strong>redundancy layer</strong> alongside Telegram (primary channel).
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Weekly Digest Section */}
                            <Card className="bg-card border-border" data-testid="weekly-digest-card">
                                <CardHeader>
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-purple-500/10">
                                            <Calendar className="h-5 w-5 text-purple-500" />
                                        </div>
                                        <div>
                                            <CardTitle>Weekly Digest Email</CardTitle>
                                            <CardDescription>
                                                Scheduled summary of domain health for management visibility
                                            </CardDescription>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-6">
                                    {/* Enable/Disable */}
                                    <div className="flex items-center justify-between p-4 rounded-lg bg-zinc-900/50 border border-border">
                                        <div>
                                            <p className="font-medium text-white">Enable Weekly Digest</p>
                                            <p className="text-xs text-zinc-500">Send weekly summary to global admins</p>
                                        </div>
                                        <Switch
                                            checked={digestConfig.enabled}
                                            onCheckedChange={(checked) => setDigestConfig({...digestConfig, enabled: checked})}
                                            data-testid="digest-enabled-switch"
                                        />
                                    </div>

                                    {/* Schedule */}
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                        <div className="space-y-2">
                                            <Label>Day of Week</Label>
                                            <Select 
                                                value={digestConfig.schedule_day}
                                                onValueChange={(val) => setDigestConfig({...digestConfig, schedule_day: val})}
                                            >
                                                <SelectTrigger className="bg-black border-border" data-testid="digest-day-select">
                                                    <SelectValue placeholder="Select day" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="monday">Monday</SelectItem>
                                                    <SelectItem value="tuesday">Tuesday</SelectItem>
                                                    <SelectItem value="wednesday">Wednesday</SelectItem>
                                                    <SelectItem value="thursday">Thursday</SelectItem>
                                                    <SelectItem value="friday">Friday</SelectItem>
                                                    <SelectItem value="saturday">Saturday</SelectItem>
                                                    <SelectItem value="sunday">Sunday</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Hour (24h)</Label>
                                            <Select 
                                                value={String(digestConfig.schedule_hour)}
                                                onValueChange={(val) => setDigestConfig({...digestConfig, schedule_hour: parseInt(val)})}
                                            >
                                                <SelectTrigger className="bg-black border-border" data-testid="digest-hour-select">
                                                    <SelectValue placeholder="Hour" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {Array.from({length: 24}, (_, i) => (
                                                        <SelectItem key={i} value={String(i)}>{String(i).padStart(2, '0')}:00</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Expiring Threshold</Label>
                                            <Select 
                                                value={String(digestConfig.expiring_days_threshold)}
                                                onValueChange={(val) => setDigestConfig({...digestConfig, expiring_days_threshold: parseInt(val)})}
                                            >
                                                <SelectTrigger className="bg-black border-border" data-testid="digest-threshold-select">
                                                    <SelectValue placeholder="Days" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="7">7 days</SelectItem>
                                                    <SelectItem value="14">14 days</SelectItem>
                                                    <SelectItem value="30">30 days</SelectItem>
                                                    <SelectItem value="60">60 days</SelectItem>
                                                    <SelectItem value="90">90 days</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>

                                    {/* Content Options */}
                                    <div className="space-y-3">
                                        <Label>Include in Digest</Label>
                                        <div className="space-y-2">
                                            <div className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/30 border border-border/50">
                                                <span className="text-sm text-zinc-300">Expiring Domains</span>
                                                <Switch
                                                    checked={digestConfig.include_expiring_domains}
                                                    onCheckedChange={(checked) => setDigestConfig({...digestConfig, include_expiring_domains: checked})}
                                                    data-testid="digest-include-expiring"
                                                />
                                            </div>
                                            <div className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/30 border border-border/50">
                                                <span className="text-sm text-zinc-300">Down Domains</span>
                                                <Switch
                                                    checked={digestConfig.include_down_domains}
                                                    onCheckedChange={(checked) => setDigestConfig({...digestConfig, include_down_domains: checked})}
                                                    data-testid="digest-include-down"
                                                />
                                            </div>
                                            <div className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/30 border border-border/50">
                                                <span className="text-sm text-zinc-300">Soft Blocked Domains</span>
                                                <Switch
                                                    checked={digestConfig.include_soft_blocked}
                                                    onCheckedChange={(checked) => setDigestConfig({...digestConfig, include_soft_blocked: checked})}
                                                    data-testid="digest-include-blocked"
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    {/* Last Sent Info */}
                                    {digestConfig.last_sent_at && (
                                        <div className="p-3 rounded-lg bg-zinc-900/30 border border-border/50">
                                            <p className="text-xs text-zinc-500">
                                                Last sent: {new Date(digestConfig.last_sent_at).toLocaleString()}
                                            </p>
                                        </div>
                                    )}

                                    {/* Actions */}
                                    <div className="flex items-center gap-3 pt-2">
                                        <Button 
                                            onClick={handleSaveDigest} 
                                            disabled={savingDigest} 
                                            className="bg-purple-500 text-white hover:bg-purple-400" 
                                            data-testid="save-digest-btn"
                                        >
                                            {savingDigest && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                            Save Settings
                                        </Button>
                                        <Button 
                                            variant="outline" 
                                            onClick={handlePreviewDigest}
                                            disabled={loadingPreview}
                                            data-testid="preview-digest-btn"
                                        >
                                            {loadingPreview ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Eye className="h-4 w-4 mr-2" />}
                                            Preview
                                        </Button>
                                        <Button 
                                            variant="outline" 
                                            onClick={handleSendDigestNow}
                                            disabled={sendingDigest || !emailAlertsConfig.configured}
                                            data-testid="send-digest-btn"
                                        >
                                            {sendingDigest ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Send className="h-4 w-4 mr-2" />}
                                            Send Now
                                        </Button>
                                    </div>
                                    {!emailAlertsConfig.configured && (
                                        <p className="text-xs text-amber-400">Configure Resend API key above to enable sending</p>
                                    )}

                                    {/* Preview Panel */}
                                    {digestPreview && (
                                        <div className="p-4 rounded-lg bg-zinc-900/50 border border-border space-y-3" data-testid="digest-preview-panel">
                                            <div className="flex items-center justify-between">
                                                <h4 className="font-medium text-white">Preview: {digestPreview.subject}</h4>
                                                <button onClick={() => setDigestPreview(null)} className="text-zinc-500 hover:text-white">
                                                    <X className="h-4 w-4" />
                                                </button>
                                            </div>
                                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                                <div className="p-3 rounded bg-zinc-800 text-center">
                                                    <div className="text-xl font-bold text-white">{digestPreview.total_issues}</div>
                                                    <div className="text-xs text-zinc-500">Total Issues</div>
                                                </div>
                                                <div className="p-3 rounded bg-zinc-800 text-center">
                                                    <div className="text-xl font-bold text-red-400">{digestPreview.expiring_domains?.critical?.length || 0}</div>
                                                    <div className="text-xs text-zinc-500">Critical Expiring</div>
                                                </div>
                                                <div className="p-3 rounded bg-zinc-800 text-center">
                                                    <div className="text-xl font-bold text-red-400">{digestPreview.down_domains_count}</div>
                                                    <div className="text-xs text-zinc-500">Down</div>
                                                </div>
                                                <div className="p-3 rounded bg-zinc-800 text-center">
                                                    <div className="text-xl font-bold text-amber-400">{digestPreview.soft_blocked_count}</div>
                                                    <div className="text-xs text-zinc-500">Soft Blocked</div>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </TabsContent>
                        
                        {/* Notification Templates Tab */}
                        <TabsContent value="templates" className="space-y-6" data-testid="notification-templates-content">
                            <NotificationTemplatesTab />
                        </TabsContent>
                    </Tabs>
                </div>
            </div>
        </Layout>
    );
}
