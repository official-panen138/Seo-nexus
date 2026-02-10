import { useLocation, Link } from 'react-router-dom';
import { ShieldX, ArrowLeft, Home } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';

export default function AccessDeniedPage() {
    const location = useLocation();
    const { from, menuKey } = location.state || {};

    return (
        <div className="min-h-screen bg-background flex items-center justify-center p-4">
            <Card className="max-w-md w-full bg-card border-red-900/50">
                <CardContent className="pt-8 pb-6 text-center">
                    <div className="w-16 h-16 mx-auto mb-4 bg-red-950/30 rounded-full flex items-center justify-center">
                        <ShieldX className="h-8 w-8 text-red-500" />
                    </div>
                    
                    <h1 className="text-2xl font-bold mb-2">Access Denied</h1>
                    
                    <p className="text-zinc-400 mb-6">
                        You don't have permission to access this page.
                        {menuKey && (
                            <span className="block mt-1 text-sm">
                                Menu: <code className="bg-zinc-800 px-2 py-0.5 rounded">{menuKey}</code>
                            </span>
                        )}
                    </p>
                    
                    <p className="text-sm text-zinc-500 mb-6">
                        Please contact your Super Admin if you need access to this feature.
                    </p>
                    
                    <div className="flex gap-3 justify-center">
                        <Button variant="outline" onClick={() => window.history.back()}>
                            <ArrowLeft className="h-4 w-4 mr-2" />
                            Go Back
                        </Button>
                        <Link to="/dashboard">
                            <Button>
                                <Home className="h-4 w-4 mr-2" />
                                Dashboard
                            </Button>
                        </Link>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
