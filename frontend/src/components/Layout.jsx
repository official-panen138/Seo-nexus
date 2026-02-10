import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { useMenuPermissions } from '../lib/menuPermissions';
import { cn } from '../lib/utils';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import BrandSwitcher from './BrandSwitcher';
import { NotificationBell } from './NotificationBell';
import { OnlineUsers } from './OnlineUsers';
import { 
    LayoutDashboard, 
    Globe, 
    Network, 
    FileText, 
    Users, 
    Tag, 
    Settings, 
    LogOut,
    ChevronLeft,
    ChevronRight,
    Menu,
    X,
    Shield,
    Activity,
    Bell,
    Folder,
    Zap,
    History,
    Building,
    Radio,
    Clock,
    BarChart3
} from 'lucide-react';

// Nav items with menuKey for permission checking
const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, menuKey: 'dashboard' },
    { path: '/domains', label: 'Asset Domains', icon: Globe, menuKey: 'asset_domains' },
    { path: '/groups', label: 'SEO Networks', icon: Network, menuKey: 'seo_networks' },
    { path: '/alerts', label: 'Alert Center', icon: Bell, menuKey: 'alert_center' },
    { path: '/reports', label: 'Reports', icon: FileText, menuKey: 'reports' },
    { path: '/reports/team-evaluation', label: 'Team Evaluation', icon: Users, menuKey: 'team_evaluation' },
    { type: 'divider', menuKey: '_divider_admin' },
    { path: '/brands', label: 'Brands', icon: Tag, menuKey: 'brands' },
    { path: '/categories', label: 'Categories', icon: Folder, menuKey: 'categories' },
    { path: '/registrars', label: 'Registrars', icon: Building, menuKey: 'registrars' },
    { path: '/users', label: 'Users', icon: Users, menuKey: 'users' },
    { path: '/audit-logs', label: 'Audit Logs', icon: Activity, menuKey: 'audit_logs' },
    { path: '/metrics', label: 'Metrics', icon: BarChart3, menuKey: 'metrics' },
    { path: '/activity-logs', label: 'V3 Activity', icon: History, menuKey: 'v3_activity' },
    { path: '/settings/monitoring', label: 'Monitoring', icon: Radio, menuKey: 'monitoring' },
    { path: '/settings/activity-types', label: 'Activity Types', icon: Zap, menuKey: 'activity_types' },
    { path: '/settings/scheduler', label: 'Scheduler', icon: Clock, menuKey: 'scheduler' },
    { path: '/settings', label: 'Settings', icon: Settings, menuKey: 'settings' },
];

export const Layout = ({ children }) => {
    const [collapsed, setCollapsed] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);
    const location = useLocation();
    const navigate = useNavigate();
    const { user, logout } = useAuth();
    const { canAccessMenu, isSuperAdmin, loading: permLoading } = useMenuPermissions();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    // Filter nav items based on menu permissions
    const filteredNavItems = navItems.filter(item => {
        if (item.type === 'divider') {
            // Show divider only if super admin or has access to admin menus
            return isSuperAdmin || canAccessMenu('brands') || canAccessMenu('users');
        }
        return canAccessMenu(item.menuKey);
    });

    return (
        <div className="app-layout">
            {/* Mobile overlay */}
            {mobileOpen && (
                <div 
                    className="fixed inset-0 bg-black/60 z-30 lg:hidden"
                    onClick={() => setMobileOpen(false)}
                />
            )}

            {/* Sidebar */}
            <aside className={cn(
                "sidebar noise-overlay",
                collapsed && "collapsed",
                mobileOpen && "open"
            )}>
                {/* Header */}
                <div className="sidebar-header">
                    <div className="flex items-center justify-between">
                        {!collapsed && (
                            <Link to="/dashboard" className="flex items-center gap-2">
                                <Zap className="h-5 w-5 text-blue-500" />
                                <span className="font-mono text-lg font-bold text-white tracking-tighter">
                                    SEO<span className="text-blue-500">//</span>NOC
                                </span>
                            </Link>
                        )}
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setCollapsed(!collapsed)}
                            className="hidden lg:flex hover:bg-white/5"
                        >
                            {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setMobileOpen(false)}
                            className="lg:hidden hover:bg-white/5"
                        >
                            <X size={18} />
                        </Button>
                    </div>
                </div>

                {/* Brand Switcher */}
                {!collapsed && (
                    <div className="px-3 mb-3 border-t border-zinc-800 pt-3">
                        <BrandSwitcher />
                    </div>
                )}

                {/* Online Users */}
                {!collapsed && (
                    <div className="px-3 mb-3">
                        <OnlineUsers />
                    </div>
                )}

                {/* Navigation */}
                <ScrollArea className="sidebar-nav">
                    <nav className="px-3 space-y-1">
                        {filteredNavItems.map((item, idx) => {
                            if (item.type === 'divider') {
                                return (
                                    <div key={`divider-${idx}`} className="my-3 border-t border-zinc-800" />
                                );
                            }
                            
                            const Icon = item.icon;
                            const isActive = location.pathname === item.path || 
                                (item.path !== '/dashboard' && location.pathname.startsWith(item.path));
                            
                            return (
                                <Link
                                    key={item.path}
                                    to={item.path}
                                    onClick={() => setMobileOpen(false)}
                                    className={cn(
                                        "sidebar-item flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium",
                                        isActive 
                                            ? "bg-white/10 text-white border-l-2 border-blue-500" 
                                            : "text-zinc-400 hover:text-white hover:bg-white/5"
                                    )}
                                >
                                    <Icon size={18} className={isActive ? "text-blue-500" : ""} />
                                    {!collapsed && <span>{item.label}</span>}
                                </Link>
                            );
                        })}
                    </nav>
                </ScrollArea>

                {/* Footer */}
                <div className="sidebar-footer">
                    {!collapsed && user && (
                        <div className="mb-3 px-3">
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-medium text-sm">
                                    {user.name?.charAt(0).toUpperCase()}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="text-sm font-medium text-white truncate">
                                        {user.name}
                                    </div>
                                    <div className="flex items-center gap-1 text-xs text-zinc-500">
                                        <Shield size={10} />
                                        <span className="capitalize">{user.role?.replace('_', ' ')}</span>
                                    </div>
                                </div>
                                <NotificationBell />
                            </div>
                        </div>
                    )}
                    <Button
                        variant="ghost"
                        onClick={handleLogout}
                        className={cn(
                            "w-full justify-start gap-3 text-zinc-400 hover:text-white hover:bg-white/5",
                            collapsed && "justify-center px-0"
                        )}
                    >
                        <LogOut size={18} />
                        {!collapsed && <span>Logout</span>}
                    </Button>
                </div>
            </aside>

            {/* Main content */}
            <main className="main-content">
                {/* Mobile header */}
                <div className="lg:hidden sticky top-0 z-20 glass border-b border-zinc-800 px-4 py-3">
                    <div className="flex items-center justify-between">
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setMobileOpen(true)}
                            className="hover:bg-white/5"
                        >
                            <Menu size={20} />
                        </Button>
                        <span className="font-mono text-lg font-bold text-white tracking-tighter flex items-center gap-2">
                            <Zap className="h-5 w-5 text-blue-500" />
                            SEO<span className="text-blue-500">//</span>NOC
                        </span>
                        <NotificationBell />
                    </div>
                </div>
                
                <div className="page-container">
                    {children}
                </div>
            </main>
        </div>
    );
};

export default Layout;
