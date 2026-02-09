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

// Quick templates for common SEO actions (Bahasa Indonesia)
const CHANGE_NOTE_TEMPLATES = [
    {
        category: 'Strategi Linking',
        templates: [
            { label: 'Relink ke Main', text: 'Domain diarahkan langsung ke domain utama untuk konsolidasi link juice dan transfer authority.' },
            { label: 'Halaman Support Baru', text: 'Menambahkan halaman support baru untuk memperkuat topical relevance ke target utama.' },
            { label: 'Penyesuaian Struktur Tier', text: 'Menyesuaikan struktur tier untuk memperbaiki aliran internal linking dan efisiensi crawl.' },
            { label: 'Penguatan Authority', text: 'Support halaman promo utama menjelang update Google, untuk meningkatkan authority domain.' }
        ]
    },
    {
        category: 'Perbaikan Cannibalization',
        templates: [
            { label: 'Keyword Cannibalization', text: 'Perbaikan keyword cannibalization antar path. Halaman ini bersaing dengan target utama untuk keyword yang sama.' },
            { label: 'Konsolidasi Konten', text: 'Konsolidasi konten duplikat/serupa untuk menghindari kebingungan search engine dan meningkatkan potensi ranking.' }
        ]
    },
    {
        category: 'Optimisasi',
        templates: [
            { label: 'Optimisasi Path', text: 'Optimisasi struktur URL path untuk sinyal SEO yang lebih baik dan arsitektur site yang lebih jelas.' },
            { label: 'Upgrade Role', text: 'Mempromosikan halaman ini menjadi target utama berdasarkan metrik performa dan prioritas strategis.' },
            { label: 'Perubahan Status Index', text: 'Mengubah status index untuk mencegah thin content dari menurunkan kualitas site.' },
            { label: 'Penguatan LP', text: 'Penguatan internal authority ke LP untuk meningkatkan ranking target keyword utama.' }
        ]
    },
    {
        category: 'Maintenance',
        templates: [
            { label: 'Domain Expired', text: 'Menghapus domain expired dari network. Tidak ada rencana perpanjangan.' },
            { label: 'Migrasi Site', text: 'Bagian dari proyek migrasi site. Memperbarui struktur untuk mencerminkan arsitektur domain baru.' },
            { label: 'Cleanup', text: 'Pembersihan network - menghapus halaman support yang tidak terpakai/abandoned.' }
        ]
    }
];

export function ChangeNoteInput({ 
    value, 
    onChange, 
    placeholder = "Jelaskan alasan perubahan ini... (contoh: Support halaman promo utama)",
    minHeight = "140px",
    recommendedChars = 50,
    minChars = 10,
    maxChars = 2000,
    label = "Catatan Perubahan",
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
    const isMinMet = charCount >= minChars;
    
    return (
        <div className={`space-y-3 p-4 ${getBackgroundClass()} border ${getBorderClass().split(' ')[0]} rounded-lg`}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <Label className={`${getLabelColor()} flex items-center gap-2`}>
                    <FileText className="h-4 w-4" />
                    <span>{label}</span>
                    {required && <span className="text-xs opacity-70">(Wajib)</span>}
                </Label>
                
                {/* Quick Templates Dropdown */}
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="h-7 text-xs text-zinc-400 hover:text-white">
                            <Lightbulb className="h-3 w-3 mr-1" />
                            Template
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
                            Minimal {minChars} karakter
                        </Badge>
                    )}
                    {isMinMet && !isRecommendedMet && (
                        <Badge variant="outline" className="text-amber-400 border-amber-400/30">
                            Disarankan: {recommendedChars}+ karakter
                        </Badge>
                    )}
                    {isRecommendedMet && (
                        <Badge variant="outline" className="text-emerald-400 border-emerald-400/30">
                            Detail yang baik
                        </Badge>
                    )}
                </div>
                <span className={`${charCount > maxChars * 0.9 ? 'text-red-400' : 'text-zinc-500'}`}>
                    {charCount} / {maxChars}
                </span>
            </div>
            
            {/* Guidance text */}
            <p className="text-xs text-zinc-500">
                Catatan detail membantu tim memahami keputusan SEO. Sertakan: apa yang berubah, mengapa, dan dampak yang diharapkan.
            </p>
        </div>
    );
}
