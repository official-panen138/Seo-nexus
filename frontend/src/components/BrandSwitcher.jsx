import { useBrand } from '../contexts/BrandContext';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Badge } from './ui/badge';
import { Building2 } from 'lucide-react';

export default function BrandSwitcher({ className = '' }) {
    const { 
        selectedBrandId, 
        selectBrand, 
        availableBrands, 
        canSelectAllBrands,
        loading 
    } = useBrand();

    if (loading) {
        return (
            <div className={`flex items-center gap-2 px-3 py-2 text-sm text-zinc-500 ${className}`}>
                <Building2 className="h-4 w-4 animate-pulse" />
                <span>Loading...</span>
            </div>
        );
    }

    // If only one brand available and not super admin, just show the brand name
    if (availableBrands.length === 1 && !canSelectAllBrands) {
        return (
            <div className={`flex items-center gap-2 px-3 py-2 ${className}`}>
                <Building2 className="h-4 w-4 text-emerald-500" />
                <span className="text-sm font-medium text-white">{availableBrands[0].name}</span>
            </div>
        );
    }

    // No brands available
    if (availableBrands.length === 0 && !canSelectAllBrands) {
        return (
            <div className={`flex items-center gap-2 px-3 py-2 ${className}`}>
                <Building2 className="h-4 w-4 text-red-500" />
                <span className="text-sm text-red-400">No brands assigned</span>
            </div>
        );
    }

    const currentValue = selectedBrandId || 'all';
    const currentBrand = availableBrands.find(b => b.id === selectedBrandId);

    return (
        <div className={`flex items-center gap-2 ${className}`}>
            <Building2 className="h-4 w-4 text-zinc-500" />
            <Select value={currentValue} onValueChange={selectBrand}>
                <SelectTrigger 
                    className="w-[180px] bg-zinc-900 border-zinc-800 text-white"
                    data-testid="brand-switcher"
                >
                    <SelectValue>
                        {currentValue === 'all' ? (
                            <span className="flex items-center gap-2">
                                All Brands
                                <Badge variant="secondary" className="text-xs">Super Admin</Badge>
                            </span>
                        ) : (
                            currentBrand?.name || 'Select Brand'
                        )}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {canSelectAllBrands && (
                        <SelectItem value="all">
                            <span className="flex items-center gap-2">
                                All Brands
                                <Badge variant="secondary" className="text-xs">Super Admin</Badge>
                            </span>
                        </SelectItem>
                    )}
                    {availableBrands.map((brand) => (
                        <SelectItem key={brand.id} value={brand.id}>
                            <span className="flex items-center gap-2">
                                {brand.name}
                                {brand.status === 'archived' && (
                                    <Badge variant="outline" className="text-xs text-zinc-500">Archived</Badge>
                                )}
                            </span>
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    );
}
