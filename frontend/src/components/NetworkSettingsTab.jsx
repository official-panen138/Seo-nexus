import { useState, useEffect } from 'react';
import { useAuth } from '../lib/auth';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Skeleton } from './ui/skeleton';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import {
    Bell,
    Clock,
    Loader2,
    Save,
    RotateCcw,
    AlertCircle,
    CheckCircle,
    Info
} from 'lucide-react';
import axios from 'axios';

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

export function NetworkSettingsTab({ networkId, networkName }) {
    const { user } = useAuth();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    
    // Reminder config state
    const [reminderConfig, setReminderConfig] = useState({
        enabled: true,
        interval_days: null,  // null = use global default
        use_global: true,
        global_interval_days: 2
    });
    
    const [localInterval, setLocalInterval] = useState('');
    
    const isSuperAdmin = user?.role === 'super_admin';
    const isManager = isSuperAdmin; // TODO: Check if user is network manager

    useEffect(() => {
        if (networkId) {
            loadSettings();
        }
    }, [networkId]);

    const loadSettings = async () => {
        setLoading(true);
        try {
            const res = await apiV3.get(`/networks/${networkId}/reminder-config`);
            const data = res.data;
            
            // API returns: { global_default: {...}, network_override: {...}, effective_interval_days: N }
            const globalConfig = data.global_default || {};
            const networkOverride = data.network_override || {};
            const hasNetworkOverride = networkOverride && Object.keys(networkOverride).length > 0 && networkOverride.interval_days;
            
            setReminderConfig({
                enabled: globalConfig.enabled !== false,
                interval_days: networkOverride.interval_days || null,
                use_global: !hasNetworkOverride,  // Use global if no network override
                global_interval_days: globalConfig.interval_days || 2
            });
            
            setLocalInterval(networkOverride.interval_days ? String(networkOverride.interval_days) : '');
        } catch (err) {
            console.error('Failed to load network settings:', err);
            toast.error('Failed to load settings');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            const payload = {
                enabled: reminderConfig.enabled,
                use_global: reminderConfig.use_global
            };
            
            if (!reminderConfig.use_global && localInterval) {
                const days = parseInt(localInterval, 10);
                if (days < 1 || days > 30) {
                    toast.error('Interval must be between 1 and 30 days');
                    setSaving(false);
                    return;
                }
                payload.interval_days = days;
            }
            
            await apiV3.put(`/networks/${networkId}/reminder-config`, payload);
            toast.success('Reminder settings saved');
            loadSettings();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to save settings');
        } finally {
            setSaving(false);
        }
    };

    const handleReset = async () => {
        setSaving(true);
        try {
            await apiV3.put(`/networks/${networkId}/reminder-config`, {
                use_global: true
            });
            toast.success('Reset to global defaults');
            loadSettings();
        } catch (err) {
            toast.error('Failed to reset settings');
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-32 w-full" />
            </div>
        );
    }

    const effectiveInterval = reminderConfig.use_global 
        ? reminderConfig.global_interval_days 
        : (reminderConfig.interval_days || reminderConfig.global_interval_days);

    return (
        <div className="space-y-6" data-testid="network-settings-tab">
            {/* Header */}
            <div>
                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                    <Bell className="h-5 w-5 text-amber-400" />
                    Network Settings
                </h3>
                <p className="text-sm text-zinc-500 mt-1">
                    Configure behavior settings for this SEO network
                </p>
            </div>

            {/* Reminder Settings */}
            <Card className="bg-card border-border">
                <CardHeader>
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-amber-500/10">
                            <Clock className="h-5 w-5 text-amber-400" />
                        </div>
                        <div className="flex-1">
                            <CardTitle className="text-base">Optimization Reminders</CardTitle>
                            <CardDescription>
                                Send reminders for "In Progress" optimizations that haven't been updated
                            </CardDescription>
                        </div>
                        <Switch
                            checked={reminderConfig.enabled}
                            onCheckedChange={(checked) => setReminderConfig({...reminderConfig, enabled: checked})}
                            disabled={!isManager}
                            data-testid="reminder-enabled-toggle"
                        />
                    </div>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Current Status */}
                    <div className="p-3 rounded-lg bg-zinc-900/50 border border-border">
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-zinc-400">Current Status</span>
                            {reminderConfig.enabled ? (
                                <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                                    <CheckCircle className="h-3 w-3 mr-1" />
                                    Enabled
                                </Badge>
                            ) : (
                                <Badge className="bg-zinc-500/20 text-zinc-400 border-zinc-500/30">
                                    Disabled
                                </Badge>
                            )}
                        </div>
                        <div className="flex items-center justify-between mt-2">
                            <span className="text-sm text-zinc-400">Reminder Interval</span>
                            <span className="text-sm text-white font-medium">
                                Every {effectiveInterval} day{effectiveInterval !== 1 ? 's' : ''}
                                {reminderConfig.use_global && (
                                    <span className="text-zinc-500 ml-1">(global)</span>
                                )}
                            </span>
                        </div>
                    </div>

                    {/* Interval Configuration */}
                    {reminderConfig.enabled && (
                        <div className="space-y-4 pt-2">
                            {/* Use Global Toggle */}
                            <div className="flex items-center justify-between p-3 rounded-lg bg-blue-500/5 border border-blue-500/20">
                                <div>
                                    <Label className="text-sm font-medium">Use Global Default</Label>
                                    <p className="text-xs text-zinc-500 mt-0.5">
                                        Global default: {reminderConfig.global_interval_days} days
                                    </p>
                                </div>
                                <Switch
                                    checked={reminderConfig.use_global}
                                    onCheckedChange={(checked) => {
                                        setReminderConfig({...reminderConfig, use_global: checked});
                                        if (checked) {
                                            setLocalInterval('');
                                        }
                                    }}
                                    disabled={!isManager}
                                    data-testid="use-global-toggle"
                                />
                            </div>

                            {/* Custom Interval */}
                            {!reminderConfig.use_global && (
                                <div className="space-y-2">
                                    <Label className="text-sm text-zinc-400">Custom Interval (Days)</Label>
                                    <div className="flex items-center gap-3">
                                        <Input
                                            type="number"
                                            min="1"
                                            max="30"
                                            value={localInterval}
                                            onChange={(e) => setLocalInterval(e.target.value)}
                                            placeholder={String(reminderConfig.global_interval_days)}
                                            className="bg-black border-border w-32"
                                            disabled={!isManager}
                                            data-testid="interval-days-input"
                                        />
                                        <span className="text-sm text-zinc-500">days between reminders</span>
                                    </div>
                                    <p className="text-xs text-zinc-600">
                                        <Info className="h-3 w-3 inline mr-1" />
                                        Valid range: 1-30 days. Leave empty to use global default.
                                    </p>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Reminder Info */}
                    <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                        <div className="flex items-start gap-2">
                            <AlertCircle className="h-4 w-4 text-amber-400 mt-0.5 flex-shrink-0" />
                            <div className="text-xs text-zinc-400">
                                <p className="font-medium text-amber-400 mb-1">How Reminders Work</p>
                                <ul className="space-y-1">
                                    <li>• Reminders are sent for optimizations with status "In Progress"</li>
                                    <li>• Triggered when no activity for {effectiveInterval}+ days</li>
                                    <li>• Sent via Telegram to tagged managers</li>
                                    <li>• Stops automatically when status changes to Completed/Reverted</li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    {/* Actions */}
                    {isManager && (
                        <div className="flex items-center gap-3 pt-2">
                            <Button
                                onClick={handleSave}
                                disabled={saving}
                                className="bg-amber-500 text-black hover:bg-amber-400"
                                data-testid="save-reminder-settings-btn"
                            >
                                {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                                Save Settings
                            </Button>
                            {!reminderConfig.use_global && (
                                <Button
                                    variant="outline"
                                    onClick={handleReset}
                                    disabled={saving}
                                    data-testid="reset-reminder-settings-btn"
                                >
                                    <RotateCcw className="h-4 w-4 mr-2" />
                                    Reset to Global
                                </Button>
                            )}
                        </div>
                    )}

                    {!isManager && (
                        <p className="text-xs text-zinc-600 pt-2">
                            Only network managers and Super Admins can modify these settings.
                        </p>
                    )}
                </CardContent>
            </Card>

            {/* Future Settings Placeholder */}
            <Card className="bg-card border-border border-dashed opacity-60">
                <CardContent className="py-8 text-center">
                    <p className="text-sm text-zinc-500">
                        Additional settings (risk level, notification rules) coming soon
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}
