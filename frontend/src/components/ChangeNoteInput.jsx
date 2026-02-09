import { useState, useRef, useEffect } from 'react';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { 
    DropdownMenu, 
    DropdownMenuContent, 
    DropdownMenuItem, 
    DropdownMenuTrigger,
    DropdownMenuSeparator,
    DropdownMenuLabel
} from './ui/dropdown-menu';
import { ChevronDown, Lightbulb, FileText } from 'lucide-react';

// Quick templates for common SEO actions
const CHANGE_NOTE_TEMPLATES = [
    {
        category: 'Linking Strategy',
        templates: [
            { label: 'Relink to Main', text: 'Relink support page to main target for consolidated link juice and authority transfer.' },
            { label: 'New Support Page', text: 'Added new supporting page to strengthen topical relevance for main target.' },
            { label: 'Tier Structure Adjustment', text: 'Adjusted tier structure to improve internal linking flow and crawl efficiency.' }
        ]
    },
    {
        category: 'Cannibalization Fix',
        templates: [
            { label: 'Keyword Cannibalization', text: 'Fixed keyword cannibalization issue. This page was competing with main target for the same keywords. Redirecting to consolidate rankings.' },
            { label: 'Content Consolidation', text: 'Consolidating duplicate/similar content to prevent search engine confusion and improve ranking potential.' }
        ]
    },
    {
        category: 'Optimization',
        templates: [
            { label: 'Path Optimization', text: 'Optimized URL path structure for better SEO signal and clearer site architecture.' },
            { label: 'Role Upgrade', text: 'Promoting this page to main target based on performance metrics and strategic priority.' },
            { label: 'Index Status Change', text: 'Changed index status to prevent thin content from diluting site quality.' }
        ]
    },
    {
        category: 'Maintenance',
        templates: [
            { label: 'Domain Expired', text: 'Removing expired domain from network. No renewal planned.' },
            { label: 'Site Migration', text: 'Part of site migration project. Updating structure to reflect new domain architecture.' },
            { label: 'Cleanup', text: 'Network cleanup - removing unused/abandoned supporting pages.' }
        ]
    }
];

export function ChangeNoteInput({ 
    value, 
    onChange, 
    placeholder = "Explain the reason for this change...",
    minHeight = "140px",
    recommendedChars = 150,
    maxChars = 2000,
    label = "Change Note",
    required = true,
    variant = "default" // default, delete, or add
}) {
    const textareaRef = useRef(null);
    const [charCount, setCharCount] = useState(value?.length || 0);
    
    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = minHeight;
            textareaRef.current.style.height = `${Math.max(parseInt(minHeight), textareaRef.current.scrollHeight)}px`;
        }
    }, [value, minHeight]);
    
    const handleChange = (e) => {
        const newValue = e.target.value;
        if (newValue.length <= maxChars) {
            setCharCount(newValue.length);
            onChange(newValue);
        }
    };
    
    const handleTemplateSelect = (template) => {
        const newValue = template.text;
        setCharCount(newValue.length);
        onChange(newValue);
        // Focus textarea after template selection
        setTimeout(() => {
            if (textareaRef.current) {
                textareaRef.current.focus();
                textareaRef.current.setSelectionRange(newValue.length, newValue.length);
            }
        }, 100);
    };
    
    // Determine border color based on variant
    const getBorderClass = () => {
        switch (variant) {
            case 'delete':
                return 'border-red-400/30 focus-visible:ring-red-400/50';
            case 'add':
                return 'border-emerald-400/30 focus-visible:ring-emerald-400/50';
            default:
                return 'border-amber-400/30 focus-visible:ring-amber-400/50';
        }
    };
    
    const getBackgroundClass = () => {
        switch (variant) {
            case 'delete':
                return 'bg-red-500/5';
            case 'add':
                return 'bg-emerald-500/5';
            default:
                return 'bg-amber-500/5';
        }
    };
    
    const getLabelColor = () => {
        switch (variant) {
            case 'delete':
                return 'text-red-400';
            case 'add':
                return 'text-emerald-400';
            default:
                return 'text-amber-400';
        }
    };
    
    const isRecommendedMet = charCount >= recommendedChars;
    const isMinMet = charCount >= 3;
    
    return (
        <div className={`space-y-3 p-4 ${getBackgroundClass()} border ${getBorderClass().split(' ')[0]} rounded-lg`}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <Label className={`${getLabelColor()} flex items-center gap-2`}>
                    <FileText className="h-4 w-4" />
                    <span>{label}</span>
                    {required && <span className="text-xs opacity-70">(Required)</span>}
                </Label>
                
                {/* Quick Templates Dropdown */}
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="h-7 text-xs text-zinc-400 hover:text-white">
                            <Lightbulb className="h-3 w-3 mr-1" />
                            Templates
                            <ChevronDown className="h-3 w-3 ml-1" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-[350px] max-h-[400px] overflow-y-auto">
                        {CHANGE_NOTE_TEMPLATES.map((category, idx) => (
                            <div key={idx}>
                                {idx > 0 && <DropdownMenuSeparator />}
                                <DropdownMenuLabel className="text-xs text-zinc-500">
                                    {category.category}
                                </DropdownMenuLabel>
                                {category.templates.map((template, tIdx) => (
                                    <DropdownMenuItem 
                                        key={tIdx}
                                        onClick={() => handleTemplateSelect(template)}
                                        className="cursor-pointer"
                                    >
                                        <div className="flex flex-col gap-1">
                                            <span className="font-medium text-sm">{template.label}</span>
                                            <span className="text-xs text-zinc-500 line-clamp-2">{template.text}</span>
                                        </div>
                                    </DropdownMenuItem>
                                ))}
                            </div>
                        ))}
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
            
            {/* Textarea */}
            <Textarea
                ref={textareaRef}
                value={value}
                onChange={handleChange}
                placeholder={placeholder}
                className={`bg-black ${getBorderClass()} resize-none transition-all`}
                style={{ minHeight }}
                data-testid="change-note-input"
            />
            
            {/* Footer: Character counter and guidance */}
            <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                    {!isMinMet && (
                        <Badge variant="outline" className="text-red-400 border-red-400/30">
                            Min 3 characters required
                        </Badge>
                    )}
                    {isMinMet && !isRecommendedMet && (
                        <Badge variant="outline" className="text-amber-400 border-amber-400/30">
                            Recommended: {recommendedChars}+ chars for detailed reasoning
                        </Badge>
                    )}
                    {isRecommendedMet && (
                        <Badge variant="outline" className="text-emerald-400 border-emerald-400/30">
                            Good detail level
                        </Badge>
                    )}
                </div>
                <span className={`${charCount > maxChars * 0.9 ? 'text-red-400' : 'text-zinc-500'}`}>
                    {charCount} / {maxChars}
                </span>
            </div>
            
            {/* Guidance text */}
            <p className="text-xs text-zinc-500">
                Detailed notes help your team understand SEO decisions. Include: what changed, why, and expected impact.
            </p>
        </div>
    );
}
