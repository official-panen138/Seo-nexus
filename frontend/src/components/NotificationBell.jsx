import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { notificationsAPI } from '../lib/api';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from './ui/popover';
import { Bell, Check, CheckCheck, AlertTriangle, MessageSquare, FileText, ExternalLink } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

export function NotificationBell() {
    const navigate = useNavigate();
    const [notifications, setNotifications] = useState([]);
    const [unreadCount, setUnreadCount] = useState(0);
    const [loading, setLoading] = useState(false);
    const [open, setOpen] = useState(false);

    const loadNotifications = useCallback(async () => {
        setLoading(true);
        try {
            const res = await notificationsAPI.getAll({ limit: 20 });
            setNotifications(res.data.notifications || []);
            setUnreadCount(res.data.unread_count || 0);
        } catch (err) {
            console.error('Failed to load notifications:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    // Load notifications on mount and when popover opens
    useEffect(() => {
        loadNotifications();
        
        // Poll for new notifications every 30 seconds
        const interval = setInterval(loadNotifications, 30000);
        return () => clearInterval(interval);
    }, [loadNotifications]);

    const handleMarkAsRead = async (notificationId) => {
        try {
            await notificationsAPI.markAsRead(notificationId);
            setNotifications(prev => 
                prev.map(n => n.id === notificationId ? { ...n, read: true } : n)
            );
            setUnreadCount(prev => Math.max(0, prev - 1));
        } catch (err) {
            console.error('Failed to mark notification as read:', err);
        }
    };

    const handleMarkAllAsRead = async () => {
        try {
            await notificationsAPI.markAllAsRead();
            setNotifications(prev => prev.map(n => ({ ...n, read: true })));
            setUnreadCount(0);
        } catch (err) {
            console.error('Failed to mark all as read:', err);
        }
    };

    const handleNotificationClick = async (notification) => {
        // Mark as read
        if (!notification.read) {
            await handleMarkAsRead(notification.id);
        }
        
        // Navigate to link if present
        if (notification.link) {
            setOpen(false);
            navigate(notification.link);
        }
    };

    const getNotificationIcon = (type) => {
        switch (type) {
            case 'complaint_tagged':
                return <AlertTriangle className="h-4 w-4 text-amber-400" />;
            case 'complaint_response':
                return <MessageSquare className="h-4 w-4 text-blue-400" />;
            case 'optimization':
                return <FileText className="h-4 w-4 text-emerald-400" />;
            default:
                return <Bell className="h-4 w-4 text-zinc-400" />;
        }
    };

    const formatTime = (dateStr) => {
        try {
            return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
        } catch {
            return dateStr;
        }
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="ghost"
                    size="icon"
                    className="relative"
                    data-testid="notification-bell"
                >
                    <Bell className="h-5 w-5" />
                    {unreadCount > 0 && (
                        <Badge 
                            className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 flex items-center justify-center bg-red-500 text-white text-xs"
                            data-testid="notification-badge"
                        >
                            {unreadCount > 9 ? '9+' : unreadCount}
                        </Badge>
                    )}
                </Button>
            </PopoverTrigger>
            <PopoverContent 
                className="w-80 p-0 bg-zinc-900 border-border"
                align="end"
            >
                <div className="flex items-center justify-between p-3 border-b border-border">
                    <h4 className="font-semibold text-white">Notifications</h4>
                    {unreadCount > 0 && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleMarkAllAsRead}
                            className="text-xs text-zinc-400 hover:text-white"
                        >
                            <CheckCheck className="h-3 w-3 mr-1" />
                            Mark all read
                        </Button>
                    )}
                </div>
                
                <ScrollArea className="h-[300px]">
                    {loading && notifications.length === 0 ? (
                        <div className="p-4 text-center text-zinc-500">
                            Loading...
                        </div>
                    ) : notifications.length === 0 ? (
                        <div className="p-4 text-center text-zinc-500">
                            <Bell className="h-8 w-8 mx-auto mb-2 opacity-50" />
                            <p>No notifications</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-border">
                            {notifications.map((notification) => (
                                <div
                                    key={notification.id}
                                    onClick={() => handleNotificationClick(notification)}
                                    className={`p-3 hover:bg-zinc-800 cursor-pointer transition-colors ${
                                        !notification.read ? 'bg-zinc-800/50' : ''
                                    }`}
                                    data-testid={`notification-item-${notification.id}`}
                                >
                                    <div className="flex items-start gap-3">
                                        <div className="mt-1">
                                            {getNotificationIcon(notification.type)}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <p className={`text-sm font-medium truncate ${
                                                    !notification.read ? 'text-white' : 'text-zinc-400'
                                                }`}>
                                                    {notification.title}
                                                </p>
                                                {!notification.read && (
                                                    <span className="h-2 w-2 rounded-full bg-blue-500 flex-shrink-0" />
                                                )}
                                            </div>
                                            <p className="text-xs text-zinc-500 line-clamp-2 mt-1">
                                                {notification.message}
                                            </p>
                                            <div className="flex items-center gap-2 mt-1">
                                                <span className="text-xs text-zinc-600">
                                                    {formatTime(notification.created_at)}
                                                </span>
                                                {notification.link && (
                                                    <ExternalLink className="h-3 w-3 text-zinc-600" />
                                                )}
                                            </div>
                                        </div>
                                        {!notification.read && (
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6 flex-shrink-0"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleMarkAsRead(notification.id);
                                                }}
                                            >
                                                <Check className="h-3 w-3" />
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </ScrollArea>
            </PopoverContent>
        </Popover>
    );
}
