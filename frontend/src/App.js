import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import { BrandProvider } from "./contexts/BrandContext";
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
import SettingsPage from "./pages/SettingsPage";
import ActivityLogsPage from "./pages/ActivityLogsPage";
import RegistrarsPage from "./pages/RegistrarsPage";
import MonitoringSettingsPage from "./pages/MonitoringSettingsPage";

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
            
            {/* Protected routes */}
            <Route path="/dashboard" element={
                <ProtectedRoute>
                    <DashboardPage />
                </ProtectedRoute>
            } />
            <Route path="/domains" element={
                <ProtectedRoute>
                    <DomainsPage />
                </ProtectedRoute>
            } />
            <Route path="/groups" element={
                <ProtectedRoute>
                    <GroupsPage />
                </ProtectedRoute>
            } />
            <Route path="/groups/:groupId" element={
                <ProtectedRoute>
                    <GroupDetailPage />
                </ProtectedRoute>
            } />
            <Route path="/optimizations/:optimizationId" element={
                <ProtectedRoute>
                    <OptimizationDetailPage />
                </ProtectedRoute>
            } />
            <Route path="/alerts" element={
                <ProtectedRoute>
                    <AlertsPage />
                </ProtectedRoute>
            } />
            <Route path="/reports" element={
                <ProtectedRoute>
                    <ReportsPage />
                </ProtectedRoute>
            } />
            <Route path="/reports/team-evaluation" element={
                <ProtectedRoute>
                    <TeamEvaluationPage />
                </ProtectedRoute>
            } />
            <Route path="/brands" element={
                <ProtectedRoute>
                    <BrandsPage />
                </ProtectedRoute>
            } />
            <Route path="/categories" element={
                <ProtectedRoute>
                    <CategoriesPage />
                </ProtectedRoute>
            } />
            <Route path="/users" element={
                <ProtectedRoute>
                    <UsersPage />
                </ProtectedRoute>
            } />
            <Route path="/audit-logs" element={
                <ProtectedRoute>
                    <AuditLogsPage />
                </ProtectedRoute>
            } />
            <Route path="/activity-logs" element={
                <ProtectedRoute>
                    <ActivityLogsPage />
                </ProtectedRoute>
            } />
            <Route path="/settings" element={
                <ProtectedRoute>
                    <SettingsPage />
                </ProtectedRoute>
            } />
            <Route path="/registrars" element={
                <ProtectedRoute>
                    <RegistrarsPage />
                </ProtectedRoute>
            } />
            <Route path="/settings/monitoring" element={
                <ProtectedRoute>
                    <MonitoringSettingsPage />
                </ProtectedRoute>
            } />
            <Route path="/settings/activity-types" element={
                <ProtectedRoute>
                    <ActivityTypesPage />
                </ProtectedRoute>
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
            </AuthProvider>
        </BrowserRouter>
    );
}

export default App;
