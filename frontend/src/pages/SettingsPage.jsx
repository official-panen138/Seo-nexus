import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { settingsAPI } from '../lib/api';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import { Loader2, Settings, Send, MessageCircle, CheckCircle, AlertCircle, Network, Bell } from 'lucide-react';

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
    
    // SEO Telegram state
    const [seoTelegramConfig, setSeoTelegramConfig] = useState({
        bot_token: '',
        chat_id: '',
        enabled: true
    });
    const [newSeoToken, setNewSeoToken] = useState('');
    const [newSeoChatId, setNewSeoChatId] = useState('');
    const [savingSeo, setSavingSeo] = useState(false);
    const [testingSeo, setTestingSeo] = useState(false);

    useEffect(() => {
        loadSettings();
    }, []);

    const loadSettings = async () => {
        try {
            const [mainRes, seoRes] = await Promise.all([
                settingsAPI.getTelegram(),
                settingsAPI.getSeoTelegram()
            ]);
            setTelegramConfig(mainRes.data);
            setSeoTelegramConfig(seoRes.data);
        } catch (err) {
            console.error('Failed to load settings:', err);
        } finally {
            setLoading(false);
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
            const data = { enabled: seoTelegramConfig.enabled };
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
            // Revert on error
            setSeoTelegramConfig(prev => ({ ...prev, enabled: !enabled }));
            toast.error('Gagal mengubah pengaturan');
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
                            <p className="page-subtitle">
                                Configure system settings and integrations
                            </p>
                        </div>
                    </div>
                </div>

                <div className="max-w-2xl space-y-6">
                    {/* Telegram Configuration */}
                    <Card className="bg-card border-border">
                        <CardHeader>
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-lg bg-blue-500/10">
                                    <MessageCircle className="h-5 w-5 text-blue-500" />
                                </div>
                                <div>
                                    <CardTitle className="text-lg">Telegram Alerts</CardTitle>
                                    <CardDescription>
                                        Configure Telegram bot for real-time alerts
                                    </CardDescription>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {/* Current Status */}
                            <div className="p-3 rounded-lg bg-black/50 border border-border">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-sm text-zinc-400">Current Status</span>
                                    {telegramConfig.bot_token && telegramConfig.chat_id ? (
                                        <span className="flex items-center gap-1 text-xs text-emerald-500">
                                            <CheckCircle className="h-3 w-3" />
                                            Configured
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1 text-xs text-amber-500">
                                            <AlertCircle className="h-3 w-3" />
                                            Not configured
                                        </span>
                                    )}
                                </div>
                                {telegramConfig.bot_token && (
                                    <div className="text-xs text-zinc-500">
                                        Token: <code className="text-zinc-400">{telegramConfig.bot_token}</code>
                                    </div>
                                )}
                                {telegramConfig.chat_id && (
                                    <div className="text-xs text-zinc-500">
                                        Chat ID: <code className="text-zinc-400">{telegramConfig.chat_id}</code>
                                    </div>
                                )}
                            </div>

                            {/* Update Token */}
                            <div className="space-y-2">
                                <Label className="text-zinc-400">Bot Token</Label>
                                <Input
                                    value={newToken}
                                    onChange={(e) => setNewToken(e.target.value)}
                                    placeholder="Enter new bot token to update"
                                    className="bg-black border-border font-mono text-sm"
                                    data-testid="telegram-token-input"
                                />
                                <p className="text-xs text-zinc-600">
                                    Get a bot token from @BotFather on Telegram
                                </p>
                            </div>

                            {/* Update Chat ID */}
                            <div className="space-y-2">
                                <Label className="text-zinc-400">Chat ID</Label>
                                <Input
                                    value={newChatId}
                                    onChange={(e) => setNewChatId(e.target.value)}
                                    placeholder="Enter chat ID or group ID"
                                    className="bg-black border-border font-mono text-sm"
                                    data-testid="telegram-chatid-input"
                                />
                                <p className="text-xs text-zinc-600">
                                    Use @userinfobot to get your chat ID, or add -100 prefix for group chats
                                </p>
                            </div>

                            {/* Actions */}
                            <div className="flex items-center gap-3 pt-2">
                                <Button
                                    onClick={handleSave}
                                    disabled={saving || (!newToken && !newChatId)}
                                    className="bg-white text-black hover:bg-zinc-200"
                                    data-testid="save-telegram-btn"
                                >
                                    {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                    Save Changes
                                </Button>
                                <Button
                                    variant="outline"
                                    onClick={handleTest}
                                    disabled={testing || !telegramConfig.bot_token || !telegramConfig.chat_id}
                                    data-testid="test-telegram-btn"
                                >
                                    {testing ? (
                                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    ) : (
                                        <Send className="h-4 w-4 mr-2" />
                                    )}
                                    Send Test
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Alert Format Reference */}
                    <Card className="bg-card border-border">
                        <CardHeader>
                            <CardTitle className="text-base">Alert Format Reference</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-3">
                                <div>
                                    <h4 className="text-sm font-medium text-zinc-300 mb-1">Monitoring Alert</h4>
                                    <pre className="text-xs bg-black/50 p-3 rounded-lg overflow-x-auto text-zinc-400">
{`⚠️ DOMAIN ALERT

Domain        : example.com
Brand         : BrandName
Category      : Money Site
SEO Structure : Tier 1 (canonical → moneysite.com)

Issue         : HTTP 5xx
Last Status   : up → DOWN
Checked At    : 2024-01-15 10:30 UTC
Severity      : CRITICAL`}
                                    </pre>
                                </div>
                                
                                <div>
                                    <h4 className="text-sm font-medium text-zinc-300 mb-1">Expiration Alert</h4>
                                    <pre className="text-xs bg-black/50 p-3 rounded-lg overflow-x-auto text-zinc-400">
{`⏰ DOMAIN EXPIRATION ALERT

Domain     : example.com
Brand      : BrandName
Category   : Money Site
Registrar  : Namecheap

Expires In : 7 days
Expire On  : 2024-01-22
Severity   : WARNING`}
                                    </pre>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </Layout>
    );
}
