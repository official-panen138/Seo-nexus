"""
Tier Calculation Service for SEO-NOC V3
=======================================
Calculates tiers dynamically based on graph distance from main domain.
Tiers are DERIVED, not stored in the database.

V3.1 Update: Now supports node-based (entry-to-entry) relationships.
A "node" is an SeoStructureEntry (domain + optional path).

Algorithm:
- Main domain (domain_role = "main") = Tier 0 (LP/Money Site)
- 1 hop away = Tier 1
- 2 hops away = Tier 2
- N hops away = Tier N (capped at Tier 5+)
"""

from typing import Dict, List, Optional, Tuple
from collections import deque
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

from models_v3 import DomainRole, get_tier_label

logger = logging.getLogger(__name__)


class TierCalculationService:
    """Service for calculating domain/node tiers based on graph distance"""
    
    MAX_TIER = 5  # Tiers beyond 5 are grouped as "Tier 5+"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def calculate_network_tiers(self, network_id: str) -> Dict[str, int]:
        """
        Calculate tiers for all nodes (entries) in a network.
        
        Uses BFS from main node(s) to calculate distance.
        Returns tiers mapped by ENTRY ID (node ID), not domain ID.
        
        Args:
            network_id: ID of the SEO network
        
        Returns:
            Dictionary mapping entry_id to calculated tier
        """
        # Get all structure entries for this network
        entries = await self.db.seo_structure_entries.find(
            {"network_id": network_id},
            {"_id": 0}
        ).to_list(10000)
        
        if not entries:
            return {}
        
        # Build adjacency list (reverse direction: target -> sources)
        # We track which nodes (entries) point TO a target node
        # Support both new (target_entry_id) and legacy (target_asset_domain_id)
        graph: Dict[str, List[str]] = {}  # target_entry_id -> [source_entry_ids]
        entry_map: Dict[str, dict] = {}  # entry_id -> entry
        domain_to_entry: Dict[str, str] = {}  # asset_domain_id -> entry_id (for legacy)
        
        for entry in entries:
            entry_id = entry["id"]
            entry_map[entry_id] = entry
            
            if entry_id not in graph:
                graph[entry_id] = []
            
            # Map domain to entry for legacy support
            if entry.get("asset_domain_id"):
                domain_to_entry[entry["asset_domain_id"]] = entry_id
        
        # Build edges
        for entry in entries:
            entry_id = entry["id"]
            
            # New node-to-node relationship
            target_entry_id = entry.get("target_entry_id")
            
            # Legacy domain-to-domain relationship (convert to entry)
            if not target_entry_id and entry.get("target_asset_domain_id"):
                target_entry_id = domain_to_entry.get(entry["target_asset_domain_id"])
            
            if target_entry_id and target_entry_id in entry_map:
                if target_entry_id not in graph:
                    graph[target_entry_id] = []
                graph[target_entry_id].append(entry_id)
        
        # Find main node(s) - these are Tier 0
        main_entries = [
            entry["id"] 
            for entry in entries 
            if entry.get("domain_role") == DomainRole.MAIN.value
        ]
        
        if not main_entries:
            # No main domain found - all entries are orphans
            logger.warning(f"Network {network_id} has no main domain")
            return {entry_id: self.MAX_TIER for entry_id in entry_map.keys()}
        
        # BFS from main node(s)
        tiers: Dict[str, int] = {}
        visited = set()
        queue = deque()
        
        # Initialize with main entries at tier 0
        for main_id in main_entries:
            queue.append((main_id, 0))
            visited.add(main_id)
            tiers[main_id] = 0
        
        while queue:
            current_id, current_tier = queue.popleft()
            
            # Get all entries that point to current entry
            for source_id in graph.get(current_id, []):
                if source_id not in visited:
                    visited.add(source_id)
                    new_tier = min(current_tier + 1, self.MAX_TIER)
                    tiers[source_id] = new_tier
                    queue.append((source_id, new_tier))
        
        # Mark any unvisited entries as max tier (orphans)
        for entry_id in entry_map.keys():
            if entry_id not in tiers:
                tiers[entry_id] = self.MAX_TIER
                logger.debug(f"Orphan entry {entry_id} assigned tier {self.MAX_TIER}")
        
        return tiers
    
    async def calculate_domain_tier(
        self, 
        network_id: str, 
        entry_id: str
    ) -> Tuple[int, str]:
        """
        Calculate tier for a single entry (node).
        
        Args:
            network_id: ID of the SEO network
            entry_id: ID of the structure entry (node)
        
        Returns:
            Tuple of (tier_number, tier_label)
        """
        tiers = await self.calculate_network_tiers(network_id)
        tier = tiers.get(entry_id, self.MAX_TIER)
        return tier, get_tier_label(tier)
    
    async def get_tier_by_asset_domain(
        self,
        network_id: str,
        asset_domain_id: str
    ) -> Tuple[int, str]:
        """
        Calculate tier for an asset domain (legacy support).
        Finds the entry for this domain and returns its tier.
        
        Args:
            network_id: ID of the SEO network
            asset_domain_id: ID of the asset domain
        
        Returns:
            Tuple of (tier_number, tier_label)
        """
        # Find entry for this domain
        entry = await self.db.seo_structure_entries.find_one({
            "network_id": network_id,
            "asset_domain_id": asset_domain_id
        }, {"_id": 0, "id": 1})
        
        if not entry:
            return self.MAX_TIER, get_tier_label(self.MAX_TIER)
        
        return await self.calculate_domain_tier(network_id, entry["id"])
    
    async def get_tier_distribution(self, network_id: str) -> Dict[str, int]:
        """
        Get distribution of nodes across tiers for a network.
        
        Args:
            network_id: ID of the SEO network
        
        Returns:
            Dictionary mapping tier labels to counts
        """
        tiers = await self.calculate_network_tiers(network_id)
        
        distribution: Dict[str, int] = {}
        for tier in tiers.values():
            label = get_tier_label(tier)
            distribution[label] = distribution.get(label, 0) + 1
        
        return distribution
    
    async def get_entries_at_tier(
        self, 
        network_id: str, 
        tier: int
    ) -> List[str]:
        """
        Get all entry IDs at a specific tier.
        
        Args:
            network_id: ID of the SEO network
            tier: Tier level (0-5)
        
        Returns:
            List of entry_ids at the specified tier
        """
        tiers = await self.calculate_network_tiers(network_id)
        return [
            entry_id 
            for entry_id, entry_tier in tiers.items() 
            if entry_tier == tier
        ]
    
    async def validate_hierarchy(self, network_id: str) -> Dict[str, List[str]]:
        """
        Validate the hierarchy for potential issues.
        
        Returns:
            Dictionary of issues found:
            - orphans: Entries not connected to main domain
            - cycles: Entries involved in circular references
            - multiple_mains: Multiple main entries (may be valid)
        """
        entries = await self.db.seo_structure_entries.find(
            {"network_id": network_id},
            {"_id": 0}
        ).to_list(10000)
        
        issues = {
            "orphans": [],
            "cycles": [],
            "multiple_mains": []
        }
        
        if not entries:
            return issues
        
        # Find main entries
        main_entries = [
            entry["id"]
            for entry in entries
            if entry.get("domain_role") == DomainRole.MAIN.value
        ]
        
        if len(main_entries) > 1:
            issues["multiple_mains"] = main_entries
        
        # Calculate tiers to find orphans
        tiers = await self.calculate_network_tiers(network_id)
        
        for entry in entries:
            entry_id = entry["id"]
            
            # Check for orphans (not main but not connected)
            if entry.get("domain_role") != DomainRole.MAIN.value:
                if tiers.get(entry_id, self.MAX_TIER) == self.MAX_TIER:
                    # Check if it has no target
                    if not entry.get("target_entry_id") and not entry.get("target_asset_domain_id"):
                        issues["orphans"].append(entry_id)
        
        return issues
    
    async def enrich_entries_with_tiers(
        self, 
        entries: List[dict],
        network_id: Optional[str] = None
    ) -> List[dict]:
        """
        Add calculated tier information to structure entries.
        
        Args:
            entries: List of structure entry dictionaries
            network_id: Optional network ID (if not in entries)
        
        Returns:
            Entries enriched with calculated_tier and tier_label
        """
        if not entries:
            return entries
        
        # Group entries by network
        networks: Dict[str, List[dict]] = {}
        for entry in entries:
            nid = entry.get("network_id") or network_id
            if nid:
                if nid not in networks:
                    networks[nid] = []
                networks[nid].append(entry)
        
        # Calculate tiers for each network (now by entry_id)
        network_tiers: Dict[str, Dict[str, int]] = {}
        for nid in networks.keys():
            network_tiers[nid] = await self.calculate_network_tiers(nid)
        
        # Enrich entries
        for entry in entries:
            nid = entry.get("network_id") or network_id
            entry_id = entry.get("id")
            
            if nid and entry_id:
                tier = network_tiers.get(nid, {}).get(entry_id, self.MAX_TIER)
                entry["calculated_tier"] = tier
                entry["tier_label"] = get_tier_label(tier)
            else:
                entry["calculated_tier"] = None
                entry["tier_label"] = None
        
        return entries


# Singleton instance
tier_service: Optional[TierCalculationService] = None


def get_tier_service() -> TierCalculationService:
    """Get the tier calculation service instance"""
    if tier_service is None:
        raise RuntimeError("TierCalculationService not initialized")
    return tier_service


def init_tier_service(db: AsyncIOMotorDatabase) -> TierCalculationService:
    """Initialize the tier calculation service"""
    global tier_service
    tier_service = TierCalculationService(db)
    return tier_service
