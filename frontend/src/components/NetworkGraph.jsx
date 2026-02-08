import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { TIER_COLORS, TIER_LABELS } from '../lib/utils';

// V3 tier mapping (derived tiers are numeric 0-5)
const TIER_HIERARCHY = {
    'tier_5': 5,
    'tier_4': 4,
    'tier_3': 3,
    'tier_2': 2,
    'tier_1': 1,
    'lp_money_site': 0
};

// V3 tier colors by numeric tier
const V3_TIER_COLORS = {
    0: '#F97316', // LP/Money Site - orange
    1: '#EAB308', // Tier 1 - yellow
    2: '#22C55E', // Tier 2 - green
    3: '#3B82F6', // Tier 3 - blue
    4: '#8B5CF6', // Tier 4 - purple
    5: '#6B7280'  // Tier 5+ - gray
};

const V3_TIER_LABELS = {
    0: 'LP/Money Site',
    1: 'Tier 1',
    2: 'Tier 2',
    3: 'Tier 3',
    4: 'Tier 4',
    5: 'Tier 5+'
};

export const NetworkGraph = ({ domains, entries, onNodeClick, selectedNodeId, useV3 = false }) => {
    const svgRef = useRef(null);
    const containerRef = useRef(null);
    const [tooltip, setTooltip] = useState(null);
    const simulationRef = useRef(null);

    // Get tier from domain - supports both V2 (tier_level) and V3 (calculated_tier)
    const getTier = useCallback((d) => {
        if (useV3 && d.calculated_tier !== undefined) {
            return d.calculated_tier;
        }
        return TIER_HIERARCHY[d.tier_level] ?? 5;
    }, [useV3]);

    const getNodeColor = useCallback((d) => {
        if (d.index_status === 'noindex') return '#52525B';
        if (d.hasError) return '#EF4444';
        
        if (useV3 && d.calculated_tier !== undefined) {
            return V3_TIER_COLORS[d.calculated_tier] || '#3B82F6';
        }
        return TIER_COLORS[d.tier_level] || '#3B82F6';
    }, [useV3]);

    const getNodeRadius = useCallback((d) => {
        const tier = getTier(d);
        const sizeByTier = {
            0: 28, // LP/Money Site
            1: 22, // Tier 1
            2: 18, // Tier 2
            3: 15, // Tier 3
            4: 12, // Tier 4
            5: 10  // Tier 5+
        };
        return sizeByTier[tier] || 12;
    }, [getTier]);

    const getTierLabel = useCallback((d) => {
        if (useV3 && d.tier_label) {
            return d.tier_label;
        }
        if (useV3 && d.calculated_tier !== undefined) {
            return V3_TIER_LABELS[d.calculated_tier] || `Tier ${d.calculated_tier}`;
        }
        return TIER_LABELS[d.tier_level] || 'Unknown';
    }, [useV3]);

    useEffect(() => {
        // Use entries for V3, domains for V2
        const data = useV3 ? entries : domains;
        if (!data || data.length === 0 || !containerRef.current) return;

        const container = containerRef.current;
        const width = container.clientWidth;
        const height = container.clientHeight || 600;

        // Clear previous
        d3.select(svgRef.current).selectAll('*').remove();

        const svg = d3.select(svgRef.current)
            .attr('width', width)
            .attr('height', height)
            .attr('viewBox', [0, 0, width, height]);

        // Create zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.2, 4])
            .on('zoom', (event) => {
                g.attr('transform', event.transform);
            });

        svg.call(zoom);

        const g = svg.append('g');

        // Build links from relationships
        const links = [];
        
        if (useV3) {
            // V3: Use entry.id as node identifier and target_entry_id for relationships
            // A node is a unique combination of domain + path, represented by entry.id
            const nodeMap = new Map(data.map(d => [d.id, d]));
            
            data.forEach(entry => {
                // Use target_entry_id (node-to-node relationship)
                if (entry.target_entry_id && nodeMap.has(entry.target_entry_id)) {
                    links.push({
                        source: entry.id,
                        target: entry.target_entry_id
                    });
                }
            });
        } else {
            // V2: Use parent_domain_id for relationships
            const nodeMap = new Map(data.map(d => [d.id, d]));
            
            data.forEach(domain => {
                if (domain.parent_domain_id && nodeMap.has(domain.parent_domain_id)) {
                    links.push({
                        source: domain.parent_domain_id,
                        target: domain.id
                    });
                }
            });
        }

        // Build nodes with error detection
        const nodes = data.map(d => {
            const tier = getTier(d);
            const isMain = useV3 ? d.domain_role === 'main' : d.tier_level === 'lp_money_site';
            // V3: Use target_entry_id (node-to-node), V2: use parent_domain_id
            const hasTarget = useV3 ? !!d.target_entry_id : !!d.parent_domain_id;
            const hasError = !isMain && !hasTarget;
            
            return {
                ...d,
                // V3: Use entry.id (not asset_domain_id) as the node identifier
                id: useV3 ? d.id : d.id,
                hasError
            };
        });

        // Create force simulation
        const simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(links)
                .id(d => d.id)
                .distance(80)
                .strength(0.8))
            .force('charge', d3.forceManyBody()
                .strength(-200)
                .distanceMax(300))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(d => getNodeRadius(d) + 10))
            .force('y', d3.forceY()
                .y(d => {
                    const tier = getTier(d);
                    return height * 0.15 + tier * (height * 0.14);
                })
                .strength(0.3));

        simulationRef.current = simulation;

        // Draw links
        const link = g.append('g')
            .attr('class', 'links')
            .selectAll('line')
            .data(links)
            .join('line')
            .attr('class', 'graph-link')
            .attr('stroke', '#6b7280')
            .attr('stroke-width', 2);

        // Draw nodes
        const node = g.append('g')
            .attr('class', 'nodes')
            .selectAll('g')
            .data(nodes)
            .join('g')
            .attr('class', 'graph-node')
            .call(d3.drag()
                .on('start', (event, d) => {
                    if (!event.active) simulation.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                })
                .on('drag', (event, d) => {
                    d.fx = event.x;
                    d.fy = event.y;
                })
                .on('end', (event, d) => {
                    if (!event.active) simulation.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                }));

        // Node circles
        node.append('circle')
            .attr('r', d => getNodeRadius(d))
            .attr('fill', d => getNodeColor(d))
            .attr('stroke', d => d.id === selectedNodeId ? '#fff' : 'rgba(255,255,255,0.3)')
            .attr('stroke-width', d => d.id === selectedNodeId ? 3 : 1.5)
            .style('filter', d => d.hasError ? 'drop-shadow(0 0 8px #EF4444)' : 'none')
            .on('click', (event, d) => {
                event.stopPropagation();
                if (onNodeClick) onNodeClick(d);
            })
            .on('mouseenter', (event, d) => {
                const rect = container.getBoundingClientRect();
                setTooltip({
                    x: event.clientX - rect.left + 10,
                    y: event.clientY - rect.top - 10,
                    data: d
                });
                
                // Highlight connected links
                link.attr('stroke', l => 
                    l.source.id === d.id || l.target.id === d.id ? '#fff' : 'hsl(240 4% 16%)'
                ).attr('stroke-width', l => 
                    l.source.id === d.id || l.target.id === d.id ? 2.5 : 1.5
                );
            })
            .on('mouseleave', () => {
                setTooltip(null);
                link.attr('stroke', 'hsl(240 4% 16%)').attr('stroke-width', 1.5);
            });

        // Node labels (only for larger nodes)
        node.filter(d => getNodeRadius(d) >= 15)
            .append('text')
            .attr('dy', d => getNodeRadius(d) + 14)
            .attr('text-anchor', 'middle')
            .attr('fill', '#A1A1AA')
            .attr('font-size', '10px')
            .attr('font-family', 'JetBrains Mono, monospace')
            .text(d => {
                // V3: Use node_label (domain + path), V2: use domain_name
                const name = (useV3 && d.node_label) ? d.node_label : (d.domain_name || '');
                return name.length > 20 ? name.substring(0, 20) + '...' : name;
            })
            .style('pointer-events', 'none');

        // Simulation tick
        simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });

        // Cleanup
        return () => {
            simulation.stop();
        };
    }, [domains, entries, selectedNodeId, onNodeClick, getNodeColor, getNodeRadius, getTier, useV3]);

    // Handle resize
    useEffect(() => {
        const handleResize = () => {
            if (simulationRef.current && containerRef.current) {
                const width = containerRef.current.clientWidth;
                const height = containerRef.current.clientHeight || 600;
                simulationRef.current.force('center', d3.forceCenter(width / 2, height / 2));
                simulationRef.current.alpha(0.3).restart();
            }
        };

        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    // Determine which tier system to use for legend
    const tierLabels = useV3 ? V3_TIER_LABELS : TIER_LABELS;
    const tierColors = useV3 ? V3_TIER_COLORS : TIER_COLORS;

    return (
        <div ref={containerRef} className="relative w-full h-full min-h-[500px]">
            <svg ref={svgRef} className="w-full h-full" />
            
            {/* Tooltip */}
            {tooltip && (
                <div 
                    className="graph-tooltip animate-fade-in"
                    style={{ left: tooltip.x, top: tooltip.y }}
                >
                    <div className="font-mono text-sm text-white font-semibold mb-2">
                        {/* V3: show node_label (domain + path), V2: show domain_name */}
                        {(useV3 && tooltip.data.node_label) ? tooltip.data.node_label : tooltip.data.domain_name}
                    </div>
                    {/* Show path separately if exists */}
                    {useV3 && tooltip.data.optimized_path && (
                        <div className="text-xs text-blue-400 mb-2 font-mono">
                            Path: {tooltip.data.optimized_path}
                        </div>
                    )}
                    <div className="space-y-1 text-xs">
                        <div className="flex justify-between gap-4">
                            <span className="text-zinc-500">Tier</span>
                            <span className="font-mono" style={{ color: getNodeColor(tooltip.data) }}>
                                {getTierLabel(tooltip.data)}
                            </span>
                        </div>
                        <div className="flex justify-between gap-4">
                            <span className="text-zinc-500">Index</span>
                            <span className={tooltip.data.index_status === 'index' ? 'text-emerald-400' : 'text-zinc-400'}>
                                {(tooltip.data.index_status || '').toUpperCase()}
                            </span>
                        </div>
                        <div className="flex justify-between gap-4">
                            <span className="text-zinc-500">Status</span>
                            <span className="text-white">{tooltip.data.domain_status}</span>
                        </div>
                        {useV3 && tooltip.data.domain_role && (
                            <div className="flex justify-between gap-4">
                                <span className="text-zinc-500">Role</span>
                                <span className="text-white capitalize">{tooltip.data.domain_role}</span>
                            </div>
                        )}
                        {/* Show target node for V3 */}
                        {useV3 && tooltip.data.target_domain_name && (
                            <div className="flex justify-between gap-4">
                                <span className="text-zinc-500">Target</span>
                                <span className="text-blue-400 font-mono text-xs truncate max-w-[150px]">
                                    {tooltip.data.target_domain_name}{tooltip.data.target_entry_path || ''}
                                </span>
                            </div>
                        )}
                        {tooltip.data.hasError && (
                            <div className="mt-2 pt-2 border-t border-zinc-800 text-red-400">
                                Orphan node - no target
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Legend */}
            <div className="absolute bottom-4 left-4 p-3 glass rounded-md text-xs space-y-2">
                <div className="text-zinc-400 font-medium mb-2">
                    {useV3 ? 'Derived Tiers' : 'Tier Legend'}
                </div>
                {useV3 ? (
                    // V3 legend (numeric tiers)
                    Object.entries(V3_TIER_LABELS).map(([tier, label]) => (
                        <div key={tier} className="flex items-center gap-2">
                            <div 
                                className="w-3 h-3 rounded-full" 
                                style={{ backgroundColor: V3_TIER_COLORS[tier] }}
                            />
                            <span className="text-zinc-300">{label}</span>
                        </div>
                    ))
                ) : (
                    // V2 legend
                    Object.entries(TIER_LABELS).reverse().map(([key, label]) => (
                        <div key={key} className="flex items-center gap-2">
                            <div 
                                className="w-3 h-3 rounded-full" 
                                style={{ backgroundColor: TIER_COLORS[key] }}
                            />
                            <span className="text-zinc-300">{label}</span>
                        </div>
                    ))
                )}
                <div className="pt-2 border-t border-zinc-700 mt-2">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-zinc-500" />
                        <span className="text-zinc-300">Noindex</span>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                        <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse" />
                        <span className="text-zinc-300">Error/Orphan</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default NetworkGraph;
