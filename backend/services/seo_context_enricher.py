"""
SEO Context Enrichment Helper for Domain Monitoring
====================================================

Provides:
- SEO context lookup for domains
- Full upstream chain traversal (BFS with loop detection)
- Downstream impact calculation
- Impact score calculation

Used by the Domain Monitoring service to create SEO-aware alerts.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class SeoContextEnricher:
    """
    Enriches domain alerts with SEO context information.

    Provides:
    - Full SEO network context for a domain
    - Upstream chain traversal to Money Site
    - Downstream impact (direct children)
    - Impact score calculation
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def enrich_domain_with_seo_context(
        self, domain_name: str, domain_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich a domain with full SEO context.

        Returns dict with:
        - seo_context: List of networks/nodes where domain is used
        - upstream_chain: Full chain to Money Site
        - downstream_impact: Direct children nodes
        - impact_score: Severity score and metrics
        """
        result = {
            "domain_name": domain_name,
            "used_in_seo": False,
            "seo_context": [],
            "upstream_chain": [],
            "downstream_impact": [],
            "impact_score": {
                "severity": "LOW",
                "networks_affected": 0,
                "downstream_nodes_count": 0,
                "reaches_money_site": False,
                "highest_tier_impacted": None,
                "node_role": None,
                "index_status": None,
            },
        }

        # Find all SEO structure entries for this domain
        query = {"domain": domain_name}
        if domain_id:
            query = {"$or": [{"domain": domain_name}, {"asset_domain_id": domain_id}]}

        entries = await self.db.seo_structure_entries.find(query, {"_id": 0}).to_list(
            100
        )

        if not entries:
            return result

        result["used_in_seo"] = True

        # Process each entry (domain may be in multiple networks)
        networks_processed = set()
        all_downstream = []
        reaches_money_site = False
        highest_tier = 99

        for entry in entries[:3]:  # Max 3 networks in detail
            network_id = entry.get("network_id")
            if network_id in networks_processed:
                continue
            networks_processed.add(network_id)

            # Get network info
            network = await self.db.seo_networks.find_one(
                {"id": network_id}, {"_id": 0, "name": 1, "brand_id": 1}
            )

            if not network:
                continue

            # Get brand info
            brand = await self.db.brands.find_one(
                {"id": network.get("brand_id")}, {"_id": 0, "name": 1}
            )

            # Calculate tier
            tier, tier_label = await self._calculate_entry_tier(entry, network_id)
            if tier < highest_tier:
                highest_tier = tier

            # Build SEO context for this entry
            # Get the domain name from the input or look it up from asset_domain
            entry_domain = entry.get('domain') or domain_name
            entry_path = entry.get('optimized_path') or ''
            full_node = f"{entry_domain}{entry_path}"
            
            seo_ctx = {
                "network_id": network_id,
                "network_name": network.get("name", "Unknown"),
                "brand_name": brand.get("name", "Unknown") if brand else "Unknown",
                "entry_id": entry.get("id"),
                "node": full_node,
                "role": (
                    "LP / Money Site"
                    if entry.get("domain_role") == "main"
                    else "Supporting"
                ),
                "domain_role": entry.get("domain_role", "supporting"),
                "tier": tier,
                "tier_label": tier_label,
                "domain_status": entry.get("domain_status", "canonical"),
                "target_node": None,
                "index_status": entry.get("index_status", "unknown"),
            }

            # Get target node
            if entry.get("target_entry_id"):
                target_entry = await self.db.seo_structure_entries.find_one(
                    {"id": entry["target_entry_id"]},
                    {"_id": 0, "domain": 1, "optimized_path": 1, "asset_domain_id": 1},
                )
                if target_entry:
                    seo_ctx["target_node"] = (
                        f"{target_entry.get('domain', '')}{target_entry.get('optimized_path', '')}"
                    )

            result["seo_context"].append(seo_ctx)

            # Calculate upstream chain
            chain, chain_reaches_money = await self._build_upstream_chain(
                entry, network_id
            )
            if chain:
                result["upstream_chain"] = chain  # Use the first chain
            if chain_reaches_money:
                reaches_money_site = True

            # Get downstream impact
            downstream = await self._get_downstream_impact(entry, network_id)
            all_downstream.extend(downstream)

        # Count additional networks
        total_networks = len(entries)
        additional_networks = total_networks - len(networks_processed)

        # Deduplicate downstream
        seen_nodes = set()
        unique_downstream = []
        for d in all_downstream:
            node_key = d.get("node", "")
            if node_key not in seen_nodes:
                seen_nodes.add(node_key)
                unique_downstream.append(d)

        result["downstream_impact"] = unique_downstream[:10]  # Max 10
        if len(unique_downstream) > 10:
            result["downstream_impact_more"] = len(unique_downstream) - 10

        # Calculate impact score
        result["impact_score"] = self._calculate_impact_score(
            networks_affected=total_networks,
            downstream_count=len(unique_downstream),
            reaches_money_site=reaches_money_site,
            highest_tier=highest_tier if highest_tier < 99 else None,
            node_role=(
                result["seo_context"][0].get("domain_role")
                if result["seo_context"]
                else None
            ),
            index_status=(
                result["seo_context"][0].get("index_status")
                if result["seo_context"]
                else None
            ),
        )

        # Add additional networks count
        if additional_networks > 0:
            result["additional_networks_count"] = additional_networks

        # Add full network structure formatted (for first network only)
        if result["seo_context"]:
            first_network_id = result["seo_context"][0].get("network_id")
            if first_network_id:
                result["full_structure_lines"] = await self.get_full_network_structure_formatted(
                    first_network_id
                )

        return result

    async def _calculate_entry_tier(
        self, entry: Dict[str, Any], network_id: str
    ) -> Tuple[int, str]:
        """Calculate tier for an entry using BFS from main nodes"""
        if entry.get("domain_role") == "main":
            return 0, "LP / Money Site"

        # Get all entries for this network
        entries = await self.db.seo_structure_entries.find(
            {"network_id": network_id},
            {"_id": 0, "id": 1, "target_entry_id": 1, "domain_role": 1},
        ).to_list(1000)

        # Build reverse lookup
        target_to_sources = {}
        main_ids = set()

        for e in entries:
            if e.get("domain_role") == "main":
                main_ids.add(e["id"])
            if e.get("target_entry_id"):
                if e["target_entry_id"] not in target_to_sources:
                    target_to_sources[e["target_entry_id"]] = []
                target_to_sources[e["target_entry_id"]].append(e["id"])

        if not main_ids:
            return 99, "Orphan"

        # BFS from main nodes
        entry_id = entry.get("id")
        tiers = {mid: 0 for mid in main_ids}
        queue = list(main_ids)
        tier = 0

        while queue:
            next_queue = []
            tier += 1
            for current_id in queue:
                for source_id in target_to_sources.get(current_id, []):
                    if source_id not in tiers:
                        tiers[source_id] = tier
                        next_queue.append(source_id)
            queue = next_queue

        entry_tier = tiers.get(entry_id, 99)
        tier_label = f"Tier {entry_tier}" if entry_tier < 99 else "Orphan"

        return entry_tier, tier_label

    async def _build_upstream_chain(
        self, entry: Dict[str, Any], network_id: str
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Build upstream chain from entry to Money Site.
        Uses BFS with loop detection.

        Returns (chain, reaches_money_site)
        """
        chain = []
        visited = set()
        current = entry
        reaches_money = False
        max_hops = 20  # Safety limit

        for _ in range(max_hops):
            current_id = current.get("id")

            if current_id in visited:
                # Loop detected
                chain.append(
                    {
                        "node": f"{current.get('domain', '')}{current.get('optimized_path', '')}",
                        "relation": "LOOP DETECTED",
                        "target": None,
                        "is_end": True,
                        "end_reason": "Loop detected",
                    }
                )
                break

            visited.add(current_id)

            node = f"{current.get('domain', '')}{current.get('optimized_path', '')}"
            relation = self._get_relation_type(
                current.get("domain_status", "canonical")
            )

            # Check if this is a main node (Money Site)
            if current.get("domain_role") == "main":
                chain.append(
                    {
                        "node": node,
                        "relation": "MAIN",
                        "target": None,
                        "is_end": True,
                        "end_reason": "Money Site reached",
                    }
                )
                reaches_money = True
                break

            # Get target
            target_id = current.get("target_entry_id")
            if not target_id:
                chain.append(
                    {
                        "node": node,
                        "relation": relation,
                        "target": None,
                        "is_end": True,
                        "end_reason": "Orphan (no target)",
                    }
                )
                break

            # Get target entry
            target = await self.db.seo_structure_entries.find_one(
                {"id": target_id, "network_id": network_id}, {"_id": 0}
            )

            if not target:
                chain.append(
                    {
                        "node": node,
                        "relation": relation,
                        "target": None,
                        "is_end": True,
                        "end_reason": "Target not found",
                    }
                )
                break

            target_node = (
                f"{target.get('domain', '')}{target.get('optimized_path', '')}"
            )
            target_relation = self._get_relation_type(
                target.get("domain_status", "canonical")
            )

            chain.append(
                {
                    "node": node,
                    "relation": relation,
                    "target": target_node,
                    "target_relation": target_relation,
                    "is_end": False,
                }
            )

            current = target

        return chain, reaches_money

    def _get_relation_type(self, domain_status: str) -> str:
        """Convert domain_status to relation type"""
        relation_map = {
            "canonical": "Canonical",
            "301_redirect": "301 Redirect",
            "302_redirect": "302 Redirect",
            "restore": "Restore",
            "main": "MAIN",
        }
        return relation_map.get(domain_status, domain_status.replace("_", " ").title())

    async def _get_downstream_impact(
        self, entry: Dict[str, Any], network_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get direct children (nodes that point to this entry).
        """
        entry_id = entry.get("id")

        children = await self.db.seo_structure_entries.find(
            {"network_id": network_id, "target_entry_id": entry_id},
            {"_id": 0, "domain": 1, "optimized_path": 1, "domain_status": 1},
        ).to_list(50)

        result = []
        for child in children:
            result.append(
                {
                    "node": f"{child.get('domain', '')}{child.get('optimized_path', '')}",
                    "relation": self._get_relation_type(
                        child.get("domain_status", "canonical")
                    ),
                    "target": f"{entry.get('domain', '')}{entry.get('optimized_path', '')}",
                }
            )

        return result

    def _calculate_impact_score(
        self,
        networks_affected: int,
        downstream_count: int,
        reaches_money_site: bool,
        highest_tier: Optional[int],
        node_role: Optional[str],
        index_status: Optional[str],
    ) -> Dict[str, Any]:
        """
        Calculate impact score and severity.

        Severity levels:
        - LOW: No Money Site chain, low tier only
        - MEDIUM: Tier 2+, Money Site indirect
        - HIGH: Tier 1 OR many downstream nodes
        - CRITICAL: Money Site OR direct supporter of Money Site
        """
        score = {
            "severity": "LOW",
            "networks_affected": networks_affected,
            "downstream_nodes_count": downstream_count,
            "reaches_money_site": reaches_money_site,
            "highest_tier_impacted": highest_tier,
            "node_role": node_role,
            "index_status": index_status,
        }

        # Determine severity
        if node_role == "main":
            score["severity"] = "CRITICAL"
        elif highest_tier == 1 and reaches_money_site:
            score["severity"] = "CRITICAL"
        elif highest_tier == 1 or downstream_count >= 10:
            score["severity"] = "HIGH"
        elif highest_tier is not None and highest_tier <= 3 and reaches_money_site:
            score["severity"] = "HIGH"
        elif reaches_money_site or (highest_tier is not None and highest_tier <= 3):
            score["severity"] = "MEDIUM"

        return score

    async def get_full_network_structure_formatted(
        self, network_id: str
    ) -> List[str]:
        """
        Get the full network structure formatted by tiers.
        
        Returns formatted lines like:
        LP / Money Site:
        • moneysite.com [Primary]
        
        Tier 1:
        • tier1-site1.com [301 Redirect] → moneysite.com [Primary]
        """
        lines = []
        
        # Get all entries for this network
        entries = await self.db.seo_structure_entries.find(
            {"network_id": network_id},
            {"_id": 0, "id": 1, "domain": 1, "optimized_path": 1, "domain_status": 1, 
             "domain_role": 1, "target_entry_id": 1, "asset_domain_id": 1}
        ).to_list(200)
        
        if not entries:
            return ["<i>No structure data available</i>"]
        
        # Get domain names for all asset_domain_ids
        asset_domain_ids = list(set(e.get("asset_domain_id") for e in entries if e.get("asset_domain_id")))
        asset_domains = {}
        if asset_domain_ids:
            domains_cursor = await self.db.asset_domains.find(
                {"id": {"$in": asset_domain_ids}},
                {"_id": 0, "id": 1, "domain_name": 1}
            ).to_list(200)
            asset_domains = {d["id"]: d.get("domain_name", "") for d in domains_cursor}
        
        # Helper function to get node display name
        def get_node_name(entry):
            domain = entry.get("domain") or ""
            if not domain and entry.get("asset_domain_id"):
                domain = asset_domains.get(entry["asset_domain_id"], "")
            path = entry.get("optimized_path") or ""
            if domain and path:
                return f"{domain}{path}"
            return domain or path or "Unknown"
        
        # Build entry lookup
        entry_by_id = {e["id"]: e for e in entries}
        
        # Build target to sources lookup
        target_to_sources = {}
        main_entries = []
        
        for e in entries:
            if e.get("domain_role") == "main":
                main_entries.append(e)
            if e.get("target_entry_id"):
                if e["target_entry_id"] not in target_to_sources:
                    target_to_sources[e["target_entry_id"]] = []
                target_to_sources[e["target_entry_id"]].append(e)
        
        # Calculate tiers using BFS
        main_ids = {e["id"] for e in main_entries}
        entry_tiers = {mid: 0 for mid in main_ids}
        queue = list(main_ids)
        tier = 0
        
        while queue:
            next_queue = []
            tier += 1
            for current_id in queue:
                for source in target_to_sources.get(current_id, []):
                    source_id = source["id"]
                    if source_id not in entry_tiers:
                        entry_tiers[source_id] = tier
                        next_queue.append(source_id)
            queue = next_queue
        
        # Group entries by tier
        tiers_dict = {}
        for e in entries:
            t = entry_tiers.get(e["id"], 99)
            if t not in tiers_dict:
                tiers_dict[t] = []
            tiers_dict[t].append(e)
        
        # Format output
        for t in sorted(tiers_dict.keys()):
            tier_entries = tiers_dict[t]
            
            # Tier header
            if t == 0:
                lines.append("<b>LP / Money Site:</b>")
            elif t == 99:
                if tier_entries:
                    lines.append("")
                    lines.append("<b>Orphan:</b>")
            else:
                lines.append("")
                lines.append(f"<b>Tier {t}:</b>")
            
            # Entries in this tier
            for entry in tier_entries:
                node = get_node_name(entry)
                status = self._get_relation_type(entry.get("domain_status", "canonical"))
                
                if t == 0:
                    # Money site - just show the domain
                    lines.append(f"  • {node} [Primary]")
                else:
                    # Supporting tiers - show relationship to target
                    target_id = entry.get("target_entry_id")
                    if target_id and target_id in entry_by_id:
                        target = entry_by_id[target_id]
                        target_node = get_node_name(target)
                        target_status = self._get_relation_type(target.get("domain_status", "canonical"))
                        if target.get("domain_role") == "main":
                            target_status = "Primary"
                        lines.append(f"  • {node} [{status}] → {target_node} [{target_status}]")
                    else:
                        lines.append(f"  • {node} [{status}]")
        
        return lines


def init_seo_context_enricher(db: AsyncIOMotorDatabase) -> SeoContextEnricher:
    """Initialize SEO context enricher"""
    return SeoContextEnricher(db)
