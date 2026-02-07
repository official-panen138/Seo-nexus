import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { TIER_COLORS, TIER_LABELS } from '../lib/utils';

const TIER_HIERARCHY = {
    'tier_5': 5,
    'tier_4': 4,
    'tier_3': 3,
    'tier_2': 2,
    'tier_1': 1,
    'lp_money_site': 0
};

export const NetworkGraph = ({ domains, onNodeClick, selectedNodeId }) => {
    const svgRef = useRef(null);
    const containerRef = useRef(null);
    const [tooltip, setTooltip] = useState(null);
    const simulationRef = useRef(null);

    const getNodeColor = useCallback((d) => {
        if (d.index_status === 'noindex') return '#52525B';
        if (d.hasError) return '#EF4444';
        return TIER_COLORS[d.tier_level] || '#3B82F6';
    }, []);

    const getNodeRadius = useCallback((d) => {
        const baseSize = {
            'lp_money_site': 28,
            'tier_1': 22,
            'tier_2': 18,
            'tier_3': 15,
            'tier_4': 12,
            'tier_5': 10
        };
        return baseSize[d.tier_level] || 12;
    }, []);

    useEffect(() => {
        if (!domains || domains.length === 0 || !containerRef.current) return;

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

        // Build links from parent-child relationships
        const links = [];
        const nodeMap = new Map(domains.map(d => [d.id, d]));

        domains.forEach(domain => {
            if (domain.parent_domain_id && nodeMap.has(domain.parent_domain_id)) {
                links.push({
                    source: domain.parent_domain_id,
                    target: domain.id
                });
            }
        });

        // Mark orphan domains (in group but no parent and not LP)
        const nodes = domains.map(d => ({
            ...d,
            hasError: d.tier_level !== 'lp_money_site' && !d.parent_domain_id && d.group_id
        }));

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
                    const tier = TIER_HIERARCHY[d.tier_level] || 0;
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
            .attr('stroke-width', 1.5);

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
            .text(d => d.domain_name.length > 15 ? d.domain_name.substring(0, 15) + '...' : d.domain_name)
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
    }, [domains, selectedNodeId, onNodeClick, getNodeColor, getNodeRadius]);

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
                        {tooltip.data.domain_name}
                    </div>
                    <div className="space-y-1 text-xs">
                        <div className="flex justify-between gap-4">
                            <span className="text-zinc-500">Tier</span>
                            <span className="font-mono" style={{ color: TIER_COLORS[tooltip.data.tier_level] }}>
                                {TIER_LABELS[tooltip.data.tier_level]}
                            </span>
                        </div>
                        <div className="flex justify-between gap-4">
                            <span className="text-zinc-500">Index</span>
                            <span className={tooltip.data.index_status === 'index' ? 'text-emerald-400' : 'text-zinc-400'}>
                                {tooltip.data.index_status.toUpperCase()}
                            </span>
                        </div>
                        <div className="flex justify-between gap-4">
                            <span className="text-zinc-500">Status</span>
                            <span className="text-white">{tooltip.data.domain_status}</span>
                        </div>
                        {tooltip.data.hasError && (
                            <div className="mt-2 pt-2 border-t border-zinc-800 text-red-400">
                                Orphan domain - no parent
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Legend */}
            <div className="absolute bottom-4 left-4 p-3 glass rounded-md text-xs space-y-2">
                <div className="text-zinc-400 font-medium mb-2">Tier Legend</div>
                {Object.entries(TIER_LABELS).reverse().map(([key, label]) => (
                    <div key={key} className="flex items-center gap-2">
                        <div 
                            className="w-3 h-3 rounded-full" 
                            style={{ backgroundColor: TIER_COLORS[key] }}
                        />
                        <span className="text-zinc-300">{label}</span>
                    </div>
                ))}
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
