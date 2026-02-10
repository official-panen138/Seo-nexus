import { useState, useEffect, useCallback } from 'react';
import { presenceAPI } from '../lib/api';
import { useAuth } from '../lib/auth';
import { ScrollArea } from './ui/scroll-area';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from './ui/popover';
import { Users, Circle, Clock } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

export function OnlineUsers() {
    const { user } = useAuth();
    const [onlineUsers, setOnlineUsers] = useState([]);
    const [recentlyActive, setRecentlyActive] = useState([]);
    const [onlineCount, setOnlineCount] = useState(0);
    const [open, setOpen] = useState(false);

    useEffect(() => {
        if (!user) return;
        presenceAPI.sendHeartbeat().catch(console.error);
        const heartbeatInterval = setInterval(() => {
            presenceAPI.sendHeartbeat().catch(console.error);
        }, 30000);
        return () => clearInterval(heartbeatInterval);
    }, [user]);

    const fetchOnlineUsers = useCallback(async () => {
        try {
            const res = await presenceAPI.getOnlineUsers();
            setOnlineUsers(res.data.online || []);
            setRecentlyActive(res.data.recently_active || []);
            setOnlineCount(res.data.online_count || 0);
        } catch (err) {
            console.error('Failed to fetch online users:', err);
        }
    }, []);

    useEffect(() => {
        if (!user) return;
        fetchOnlineUsers();
        const interval = setInterval(fetchOnlineUsers, 30000);
        return () => clearInterval(interval);
    }, [user, fetchOnlineUsers]);

    useEffect(() => {
        if (open) fetchOnlineUsers();
    }, [open, fetchOnlineUsers]);

    const formatLastSeen = (dateStr) => {
        if (!dateStr) return 'Unknown';
        try {
            return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
        } catch {
            return dateStr;
        }
    };

    const getInitial = (name) => (name || '?').charAt(0).toUpperCase();

    const getRoleColor = (role) => {
        switch (role) {
            case 'super_admin': return 'bg-red-600';
            case 'admin': return 'bg-orange-600';
            case 'manager': return 'bg-blue-600';
            default: return 'bg-zinc-600';
        }
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/5 cursor-pointer" data-testid="online-users-trigger">
                    <div className="relative">
                        <Users className="h-4 w-4 text-zinc-400" />
                        <span className="absolute -top-1 -right-1 h-2 w-2 bg-emerald-500 rounded-full animate-pulse" />
                    </div>
                    <span className="text-xs text-zinc-400">{onlineCount} online</span>
                </div>
            </PopoverTrigger>
            <PopoverContent className="w-72 p-0 bg-zinc-900 border-border" align="start" side="right">
                <div className="p-3 border-b border-border">
                    <h4 className="font-semibold text-white flex items-center gap-2">
                        <Users className="h-4 w-4" />Online Users
                    </h4>
                    <p className="text-xs text-zinc-500 mt-1">{onlineCount} user{onlineCount !== 1 ? 's' : ''} online</p>
                </div>
                <ScrollArea className="max-h-[300px]">
                    {onlineUsers.length > 0 && (
                        <div className="p-2">
                            <p className="text-xs text-zinc-500 px-2 mb-2 flex items-center gap-1">
                                <Circle className="h-2 w-2 fill-emerald-500 text-emerald-500" />Online Now
                            </p>
                            {onlineUsers.map((u) => (
                                <div key={u.user_id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-zinc-800">
                                    <div className="relative">
                                        <div className={`w-8 h-8 rounded-full ${getRoleColor(u.user_role)} flex items-center justify-center text-white text-sm font-medium`}>
                                            {getInitial(u.user_name)}
                                        </div>
                                        <span className="absolute bottom-0 right-0 h-2.5 w-2.5 bg-emerald-500 rounded-full border-2 border-zinc-900" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-white truncate">
                                            {u.user_name}{u.user_id === user?.id && <span className="text-zinc-500 text-xs ml-1">(you)</span>}
                                        </p>
                                        <p className="text-xs text-zinc-500 capitalize">{u.user_role?.replace('_', ' ')}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                    {recentlyActive.length > 0 && (
                        <div className="p-2 border-t border-border">
                            <p className="text-xs text-zinc-500 px-2 mb-2 flex items-center gap-1"><Clock className="h-3 w-3" />Recently Active</p>
                            {recentlyActive.map((u) => (
                                <div key={u.user_id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-zinc-800">
                                    <div className="relative">
                                        <div className={`w-8 h-8 rounded-full ${getRoleColor(u.user_role)} opacity-60 flex items-center justify-center text-white text-sm font-medium`}>
                                            {getInitial(u.user_name)}
                                        </div>
                                        <span className="absolute bottom-0 right-0 h-2.5 w-2.5 bg-zinc-500 rounded-full border-2 border-zinc-900" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-zinc-400 truncate">{u.user_name}</p>
                                        <p className="text-xs text-zinc-600">{formatLastSeen(u.last_seen)}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                    {onlineUsers.length === 0 && recentlyActive.length === 0 && (
                        <div className="p-4 text-center text-zinc-500">
                            <Users className="h-8 w-8 mx-auto mb-2 opacity-50" /><p>No users online</p>
                        </div>
                    )}
                </ScrollArea>
            </PopoverContent>
        </Popover>
    );
}
