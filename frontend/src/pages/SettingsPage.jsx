import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../lib/auth';
import { settingsAPI, domainMonitoringTelegramAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import { Loader2, Settings, Send, MessageCircle, CheckCircle, AlertCircle, Network, Bell, Palette, Clock, Upload, Image, Globe, Shield } from 'lucide-react';


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
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(false);
    const [telegramConfig, setTelegramConfig] = useState({
        bot_token: '',
        chat_id: ''
    });
    const [newToken, setNewToken] = useState('');
    const [newChatId, setNewChatId] = useState('');
    
    // SEO Telegram state with topic routing support
    const [seoTelegramConfig, setSeoTelegramConfig] = useState({
        bot_token: '',
        chat_id: '',
        enabled: true,
        enable_topic_routing: false,
        seo_change_topic_id: '',
        seo_optimization_topic_id: '',
        seo_complaint_topic_id: '',
        seo_reminder_topic_id: ''
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

    useEffect(() => {
        loadSettings();
    }, []);

    const loadSettings = async () => {
        try {
            const [mainRes, seoRes, brandingRes, timezoneRes, domainMonitoringRes] = await Promise.all([
                settingsAPI.getTelegram(),
                settingsAPI.getSeoTelegram().catch(() => ({ data: { bot_token: '', chat_id: '', enabled: true } })),
                settingsAPI.getBranding().catch(() => ({ data: { site_title: 'SEO//NOC', site_description: '', logo_url: '' } })),
                settingsAPI.getTimezone().catch(() => ({ data: { default_timezone: 'Asia/Jakarta', timezone_label: 'GMT+7' } })),
                domainMonitoringTelegramAPI.getSettings().catch(() => ({ data: { bot_token: '', chat_id: '', enabled: true } }))
            ]);
            setTelegramConfig(mainRes.data);
            setSeoTelegramConfig(seoRes.data);
            setBrandingConfig(brandingRes.data);
            setTimezoneConfig(timezoneRes.data);
            setDomainMonitoringConfig(domainMonitoringRes.data);
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

    const handleSave = async () => {
        setSaving(true);
        try {
            const data = {};
            if (newToken) data.bot_token = newToken;
            if (newChatId) data.chat_id = newChatId;
            
            await settingsAPI.updateTelegram(data);
            toast.success('Telegram settings updated');
            setNewToken('');
            setNewChatId('');
            loadSettings();
        } catch (err) {
            toast.error('Failed to save settings');
        } finally {
            setSaving(false);
        }
    };

    const handleTest = async () => {
        setTesting(true);
        try {
            await settingsAPI.testTelegram();
            toast.success('Test message sent! Check your Telegram.');
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to send test message');
        } finally {
            setTesting(false);
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
                seo_reminder_topic_id: seoTelegramConfig.seo_reminder_topic_id || null
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
                            <TabsTrigger value="monitoring" className="flex items-center gap-2">
                                <Bell className="h-4 w-4" />
                                Monitoring Alerts
                            </TabsTrigger>
                            <TabsTrigger value="seo" className="flex items-center gap-2" data-testid="seo-notifications-tab">
                                <Network className="h-4 w-4" />
                                SEO Notifications
                            </TabsTrigger>
                            <TabsTrigger value="domain-monitoring" className="flex items-center gap-2" data-testid="domain-monitoring-tab">
                                <Globe className="h-4 w-4" />
                                Domain Monitoring
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
                        
                        {/* Monitoring Alerts Tab */}
                        <TabsContent value="monitoring" className="space-y-6">
                            <Card className="bg-card border-border">
                                <CardHeader>
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-blue-500/10">
                                            <MessageCircle className="h-5 w-5 text-blue-500" />
                                        </div>
                                        <div>
                                            <CardTitle className="text-lg">Telegram Alerts (Monitoring)</CardTitle>
                                            <CardDescription>Configure Telegram for domain monitoring (ping/expiration)</CardDescription>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="p-3 rounded-lg bg-black/50 border border-border">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="text-sm text-zinc-400">Current Status</span>
                                            {telegramConfig.bot_token && telegramConfig.chat_id ? (
                                                <span className="flex items-center gap-1 text-xs text-emerald-500">
                                                    <CheckCircle className="h-3 w-3" />Configured
                                                </span>
                                            ) : (
                                                <span className="flex items-center gap-1 text-xs text-amber-500">
                                                    <AlertCircle className="h-3 w-3" />Not configured
                                                </span>
                                            )}
                                        </div>
                                        {telegramConfig.bot_token && <div className="text-xs text-zinc-500">Token: <code className="text-zinc-400">{telegramConfig.bot_token}</code></div>}
                                        {telegramConfig.chat_id && <div className="text-xs text-zinc-500">Chat ID: <code className="text-zinc-400">{telegramConfig.chat_id}</code></div>}
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-zinc-400">Bot Token</Label>
                                        <Input value={newToken} onChange={(e) => setNewToken(e.target.value)} placeholder="Enter new bot token to update" className="bg-black border-border font-mono text-sm" data-testid="telegram-token-input" />
                                        <p className="text-xs text-zinc-600">Get a bot token from @BotFather on Telegram</p>
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-zinc-400">Chat ID</Label>
                                        <Input value={newChatId} onChange={(e) => setNewChatId(e.target.value)} placeholder="Enter chat ID or group ID" className="bg-black border-border font-mono text-sm" data-testid="telegram-chatid-input" />
                                        <p className="text-xs text-zinc-600">Use @userinfobot to get your chat ID</p>
                                    </div>

                                    <div className="flex items-center gap-3 pt-2">
                                        <Button onClick={handleSave} disabled={saving || (!newToken && !newChatId)} className="bg-white text-black hover:bg-zinc-200" data-testid="save-telegram-btn">
                                            {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Save Changes
                                        </Button>
                                        <Button variant="outline" onClick={handleTest} disabled={testing || !telegramConfig.bot_token || !telegramConfig.chat_id} data-testid="test-telegram-btn">
                                            {testing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Send className="h-4 w-4 mr-2" />}Send Test
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
                    </Tabs>
                </div>
            </div>
        </Layout>
    );
}
