import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Loader2, Eye, EyeOff } from 'lucide-react';

export default function RegisterPage() {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [telegramUsername, setTelegramUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();
    const { register } = useAuth();

    const [pendingApproval, setPendingApproval] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        if (!name || !email || !password || !confirmPassword) {
            toast.error('Please fill in all fields');
            return;
        }

        if (password !== confirmPassword) {
            toast.error('Passwords do not match');
            return;
        }

        if (password.length < 6) {
            toast.error('Password must be at least 6 characters');
            return;
        }

        setLoading(true);
        try {
            const result = await register({ 
                name, 
                email, 
                password, 
                role: 'viewer',
                telegram_username: telegramUsername || null
            });
            
            // Check if user is pending approval
            if (result?.pending) {
                setPendingApproval(true);
                toast.success('Registration successful!');
                return;
            }
            
            // User is active (first user = Super Admin)
            if (result.role === 'super_admin') {
                toast.success('Account created! You are the first user, so you have Super Admin privileges.');
            } else {
                toast.success('Account created successfully!');
            }
            navigate('/dashboard');
        } catch (err) {
            toast.error(err.message || 'Registration failed');
        } finally {
            setLoading(false);
        }
    };

    // Show pending approval message
    if (pendingApproval) {
        return (
            <div className="login-page" data-testid="pending-approval-page">
                <div className="login-card animate-fade-in">
                    <div className="login-logo">
                        SEO<span className="text-blue-500">//</span>NEXUS
                    </div>
                    <div className="text-center py-8">
                        <div className="w-16 h-16 rounded-full bg-amber-500/20 flex items-center justify-center mx-auto mb-4">
                            <svg className="w-8 h-8 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <h2 className="text-xl font-semibold text-white mb-2">Awaiting Approval</h2>
                        <p className="text-zinc-400 mb-6">
                            Your account has been registered and is pending Super Admin approval.
                            You will be able to log in once your account is approved.
                        </p>
                        <Link to="/login">
                            <Button variant="outline" className="w-full">
                                Back to Login
                            </Button>
                        </Link>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="login-page" data-testid="register-page">
            <div className="login-card animate-fade-in">
                <div className="login-logo">
                    SEO<span className="text-blue-500">//</span>NEXUS
                </div>
                <p className="login-tagline">
                    Create your account
                </p>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="name" className="text-zinc-400 text-sm">
                            Full Name
                        </Label>
                        <Input
                            id="name"
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="John Doe"
                            className="bg-black border-zinc-800 focus:border-blue-500 h-11"
                            data-testid="register-name-input"
                            disabled={loading}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="email" className="text-zinc-400 text-sm">
                            Email Address
                        </Label>
                        <Input
                            id="email"
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="you@example.com"
                            className="bg-black border-zinc-800 focus:border-blue-500 h-11"
                            data-testid="register-email-input"
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
                                data-testid="register-password-input"
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

                    <div className="space-y-2">
                        <Label htmlFor="confirmPassword" className="text-zinc-400 text-sm">
                            Confirm Password
                        </Label>
                        <Input
                            id="confirmPassword"
                            type={showPassword ? 'text' : 'password'}
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            placeholder="••••••••"
                            className="bg-black border-zinc-800 focus:border-blue-500 h-11"
                            data-testid="register-confirm-password-input"
                            disabled={loading}
                        />
                    </div>

                    <Button
                        type="submit"
                        className="w-full h-11 bg-white text-black hover:bg-zinc-200 font-medium mt-2"
                        disabled={loading}
                        data-testid="register-submit-btn"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Creating account...
                            </>
                        ) : (
                            'Create Account'
                        )}
                    </Button>
                </form>

                <div className="mt-6 text-center">
                    <p className="text-sm text-zinc-500">
                        Already have an account?{' '}
                        <Link 
                            to="/login" 
                            className="text-blue-500 hover:text-blue-400 font-medium"
                            data-testid="login-link"
                        >
                            Sign In
                        </Link>
                    </p>
                </div>

                <p className="mt-4 text-xs text-zinc-600 text-center">
                    First user automatically becomes Super Admin
                </p>
            </div>
        </div>
    );
}
