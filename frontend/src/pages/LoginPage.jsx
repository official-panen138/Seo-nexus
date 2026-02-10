import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { useBranding } from '../lib/BrandingContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Loader2, Eye, EyeOff } from 'lucide-react';

export default function LoginPage() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();
    const { login } = useAuth();
    const { branding } = useBranding();

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!email || !password) {
            toast.error('Please fill in all fields');
            return;
        }

        setLoading(true);
        try {
            await login(email, password);
            toast.success('Welcome back!');
            navigate('/dashboard');
        } catch (err) {
            toast.error(err.message || 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    // Parse site_title to handle SEO//NOC format for styling
    const renderBrandLogo = () => {
        const title = branding.site_title || 'SEO//NOC';
        // Check if it contains // for special styling
        if (title.includes('//')) {
            const parts = title.split('//');
            return (
                <>
                    {parts[0]}<span className="text-blue-500">//</span>{parts[1]}
                </>
            );
        }
        return title;
    };

    return (
        <div className="login-page" data-testid="login-page">
            <div className="login-card animate-fade-in">
                <div className="login-logo" data-testid="login-logo">
                    {renderBrandLogo()}
                </div>
                <p className="login-tagline">
                    {branding.tagline || 'Domain Network Management System'}
                </p>

                <form onSubmit={handleSubmit} className="space-y-5">
                    <div className="space-y-2">
                        <Label htmlFor="email" className="text-zinc-400 text-sm">
                            Email Address
                        </Label>
                        <Input
                            id="email"
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="admin@example.com"
                            className="bg-black border-zinc-800 focus:border-blue-500 h-11"
                            data-testid="login-email-input"
                            disabled={loading}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="password" className="text-zinc-400 text-sm">
                            Password
                        </Label>
                        <div className="relative">
                            <Input
                                id="password"
                                type={showPassword ? 'text' : 'password'}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                className="bg-black border-zinc-800 focus:border-blue-500 h-11 pr-10"
                                data-testid="login-password-input"
                                disabled={loading}
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white"
                                tabIndex={-1}
                            >
                                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>
                    </div>

                    <Button
                        type="submit"
                        className="w-full h-11 bg-white text-black hover:bg-zinc-200 font-medium"
                        disabled={loading}
                        data-testid="login-submit-btn"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Signing in...
                            </>
                        ) : (
                            'Sign In'
                        )}
                    </Button>
                </form>

                <div className="mt-6 text-center">
                    <p className="text-sm text-zinc-500">
                        Don't have an account?{' '}
                        <Link 
                            to="/register" 
                            className="text-blue-500 hover:text-blue-400 font-medium"
                            data-testid="register-link"
                        >
                            Create Account
                        </Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
