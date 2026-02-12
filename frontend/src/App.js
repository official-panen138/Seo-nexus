import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import { BrandProvider } from "./contexts/BrandContext";
import { BrandingProvider } from "./lib/BrandingContext";
import { MenuPermissionsProvider, useMenuPermissions } from "./lib/menuPermissions";
import { Toaster } from "./components/ui/sonner";

// Pages
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import DomainsPage from "./pages/DomainsPage";
import GroupsPage from "./pages/GroupsPage";
import GroupDetailPage from "./pages/GroupDetailPage";
import ReportsPage from "./pages/ReportsPage";
import TeamEvaluationPage from "./pages/TeamEvaluationPage";
import OptimizationDetailPage from "./pages/OptimizationDetailPage";
import ActivityTypesPage from "./pages/ActivityTypesPage";
import BrandsPage from "./pages/BrandsPage";
import CategoriesPage from "./pages/CategoriesPage";
import UsersPage from "./pages/UsersPage";
import AuditLogsPage from "./pages/AuditLogsPage";
import AlertsPage from "./pages/AlertsPage";
import ConflictDashboardPage from "./pages/ConflictDashboardPage";
import SettingsPage from "./pages/SettingsPage";
import ActivityLogsPage from "./pages/ActivityLogsPage";
import RegistrarsPage from "./pages/RegistrarsPage";
import MonitoringSettingsPage from "./pages/MonitoringSettingsPage";
import SchedulerDashboardPage from "./pages/SchedulerDashboardPage";
import MetricsDashboardPage from "./pages/MetricsDashboardPage";
import AccessDeniedPage from "./pages/AccessDeniedPage";
import QuarantineCategoriesPage from "./pages/QuarantineCategoriesPage";

// Protected Route wrapper
const ProtectedRoute = ({ children }) => {
    const { isAuthenticated, loading } = useAuth();
    
    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full"></div>
            </div>
        );
    }
    
    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }
    
    return children;
};

// Menu Protected Route - checks both auth and menu permissions
const MenuProtectedRoute = ({ children, menuKey }) => {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const { canAccessMenu, loading: permLoading, isSuperAdmin } = useMenuPermissions();
    const location = useLocation();
    
    if (authLoading || permLoading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full"></div>
            </div>
        );
    }
    
    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }
    
    // Check menu permission
    if (!isSuperAdmin && menuKey && !canAccessMenu(menuKey)) {
        return <Navigate to="/access-denied" state={{ from: location.pathname, menuKey }} replace />;
    }
    
    return children;
};

// Public Route wrapper (redirect to dashboard if already logged in)
const PublicRoute = ({ children }) => {
    const { isAuthenticated, loading } = useAuth();
    
    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full"></div>
            </div>
        );
    }
    
    if (isAuthenticated) {
        return <Navigate to="/dashboard" replace />;
    }
    
    return children;
};

function AppRoutes() {
    return (
        <Routes>
            {/* Public routes */}
            <Route path="/login" element={
                <PublicRoute>
                    <LoginPage />
                </PublicRoute>
            } />
            <Route path="/register" element={
                <PublicRoute>
                    <RegisterPage />
                </PublicRoute>
            } />
            
            {/* Access Denied page */}
            <Route path="/access-denied" element={
                <ProtectedRoute>
                    <AccessDeniedPage />
                </ProtectedRoute>
            } />
            
            {/* Protected routes with menu permissions */}
            <Route path="/dashboard" element={
                <MenuProtectedRoute menuKey="dashboard">
                    <DashboardPage />
                </MenuProtectedRoute>
            } />
            <Route path="/domains" element={
                <MenuProtectedRoute menuKey="asset_domains">
                    <DomainsPage />
                </MenuProtectedRoute>
            } />
            <Route path="/groups" element={
                <MenuProtectedRoute menuKey="seo_networks">
                    <GroupsPage />
                </MenuProtectedRoute>
            } />
            <Route path="/groups/:groupId" element={
                <MenuProtectedRoute menuKey="seo_networks">
                    <GroupDetailPage />
                </MenuProtectedRoute>
            } />
            <Route path="/networks/:groupId" element={
                <MenuProtectedRoute menuKey="seo_networks">
                    <GroupDetailPage />
                </MenuProtectedRoute>
            } />
            <Route path="/networks" element={
                <MenuProtectedRoute menuKey="seo_networks">
                    <GroupsPage />
                </MenuProtectedRoute>
            } />
            <Route path="/optimizations/:optimizationId" element={
                <MenuProtectedRoute menuKey="reports">
                    <OptimizationDetailPage />
                </MenuProtectedRoute>
            } />
            <Route path="/alerts" element={
                <MenuProtectedRoute menuKey="alert_center">
                    <AlertsPage />
                </MenuProtectedRoute>
            } />
            <Route path="/conflicts/dashboard" element={
                <MenuProtectedRoute menuKey="alert_center">
                    <ConflictDashboardPage />
                </MenuProtectedRoute>
            } />
            <Route path="/reports" element={
                <MenuProtectedRoute menuKey="reports">
                    <ReportsPage />
                </MenuProtectedRoute>
            } />
            <Route path="/reports/team-evaluation" element={
                <MenuProtectedRoute menuKey="team_evaluation">
                    <TeamEvaluationPage />
                </MenuProtectedRoute>
            } />
            <Route path="/brands" element={
                <MenuProtectedRoute menuKey="brands">
                    <BrandsPage />
                </MenuProtectedRoute>
            } />
            <Route path="/categories" element={
                <MenuProtectedRoute menuKey="categories">
                    <CategoriesPage />
                </MenuProtectedRoute>
            } />
            <Route path="/users" element={
                <MenuProtectedRoute menuKey="users">
                    <UsersPage />
                </MenuProtectedRoute>
            } />
            <Route path="/audit-logs" element={
                <MenuProtectedRoute menuKey="audit_logs">
                    <AuditLogsPage />
                </MenuProtectedRoute>
            } />
            <Route path="/activity-logs" element={
                <MenuProtectedRoute menuKey="v3_activity">
                    <ActivityLogsPage />
                </MenuProtectedRoute>
            } />
            <Route path="/settings" element={
                <MenuProtectedRoute menuKey="settings">
                    <SettingsPage />
                </MenuProtectedRoute>
            } />
            <Route path="/registrars" element={
                <MenuProtectedRoute menuKey="registrars">
                    <RegistrarsPage />
                </MenuProtectedRoute>
            } />
            <Route path="/settings/monitoring" element={
                <MenuProtectedRoute menuKey="monitoring">
                    <MonitoringSettingsPage />
                </MenuProtectedRoute>
            } />
            <Route path="/settings/activity-types" element={
                <MenuProtectedRoute menuKey="activity_types">
                    <ActivityTypesPage />
                </MenuProtectedRoute>
            } />
            <Route path="/settings/scheduler" element={
                <MenuProtectedRoute menuKey="scheduler">
                    <SchedulerDashboardPage />
                </MenuProtectedRoute>
            } />
            <Route path="/settings/quarantine-categories" element={
                <MenuProtectedRoute menuKey="quarantine_categories">
                    <QuarantineCategoriesPage />
                </MenuProtectedRoute>
            } />
            <Route path="/metrics" element={
                <MenuProtectedRoute menuKey="metrics">
                    <MetricsDashboardPage />
                </MenuProtectedRoute>
            } />
            
            {/* Default redirect */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
    );
}

function App() {
    return (
        <BrowserRouter>
            <AuthProvider>
                <BrandingProvider>
                    <MenuPermissionsProvider>
                        <BrandProvider>
                            <AppRoutes />
                            <Toaster 
                                position="top-right"
                                toastOptions={{
                                    style: {
                                        background: '#0A0A0A',
                                        border: '1px solid #27272A',
                                        color: '#FAFAFA'
                                    }
                                }}
                            />
                        </BrandProvider>
                    </MenuPermissionsProvider>
                </BrandingProvider>
            </AuthProvider>
        </BrowserRouter>
    );
}

export default App;
