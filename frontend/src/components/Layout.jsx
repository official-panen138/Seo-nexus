import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { cn } from '../lib/utils';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import BrandSwitcher from './BrandSwitcher';
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
    Clock
} from 'lucide-react';

const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['super_admin', 'admin', 'viewer'] },
    { path: '/domains', label: 'Asset Domains', icon: Globe, roles: ['super_admin', 'admin', 'viewer'] },
    { path: '/groups', label: 'SEO Networks', icon: Network, roles: ['super_admin', 'admin', 'viewer'] },
    { path: '/alerts', label: 'Alert Center', icon: Bell, roles: ['super_admin', 'admin', 'viewer'] },
    { path: '/reports', label: 'Reports', icon: FileText, roles: ['super_admin', 'admin', 'viewer'] },
    { path: '/reports/team-evaluation', label: 'Team Evaluation', icon: Users, roles: ['super_admin', 'admin'] },
    { type: 'divider', roles: ['super_admin'] },
    { path: '/brands', label: 'Brands', icon: Tag, roles: ['super_admin'] },
    { path: '/categories', label: 'Categories', icon: Folder, roles: ['super_admin'] },
    { path: '/registrars', label: 'Registrars', icon: Building, roles: ['super_admin'] },
    { path: '/users', label: 'Users', icon: Users, roles: ['super_admin'] },
    { path: '/audit-logs', label: 'Audit Logs', icon: Activity, roles: ['super_admin'] },
    { path: '/activity-logs', label: 'V3 Activity', icon: History, roles: ['super_admin', 'admin'] },
    { path: '/settings/monitoring', label: 'Monitoring', icon: Radio, roles: ['super_admin', 'admin'] },
    { path: '/settings/activity-types', label: 'Activity Types', icon: Zap, roles: ['super_admin'] },
    { path: '/settings/scheduler', label: 'Scheduler', icon: Clock, roles: ['super_admin'] },
    { path: '/settings', label: 'Settings', icon: Settings, roles: ['super_admin'] },
];

export const Layout = ({ children }) => {
    const [collapsed, setCollapsed] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);
    const location = useLocation();
    const navigate = useNavigate();
    const { user, logout, hasRole } = useAuth();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const filteredNavItems = navItems.filter(item => 
        item.roles.some(role => hasRole(role))
    );

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
                        <div className="w-9" />
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
