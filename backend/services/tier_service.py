"""
Tier Calculation Service for SEO-NOC V3
=======================================
Calculates tiers dynamically based on graph distance from main domain.
Tiers are DERIVED, not stored in the database.

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
    """Service for calculating domain tiers based on graph distance"""
    
    MAX_TIER = 5  # Tiers beyond 5 are grouped as "Tier 5+"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def calculate_network_tiers(self, network_id: str) -> Dict[str, int]:
        """
        Calculate tiers for all domains in a network.
        
        Uses BFS from main domain(s) to calculate distance.
        
        Args:
            network_id: ID of the SEO network
        
        Returns:
            Dictionary mapping asset_domain_id to calculated tier
        """
        # Get all structure entries for this network
        entries = await self.db.seo_structure_entries.find(
            {"network_id": network_id},
            {"_id": 0}
        ).to_list(10000)
        
        if not entries:
            return {}
        
        # Build adjacency list (reverse direction: target -> sources)
        # We track which domains point TO a target
        graph: Dict[str, List[str]] = {}  # target_id -> [source_ids]
        entry_map: Dict[str, dict] = {}  # asset_domain_id -> entry
        
        for entry in entries:
            asset_id = entry["asset_domain_id"]
            target_id = entry.get("target_asset_domain_id")
            entry_map[asset_id] = entry
            
            if asset_id not in graph:
                graph[asset_id] = []
            
            if target_id:
                if target_id not in graph:
                    graph[target_id] = []
                graph[target_id].append(asset_id)
        
        # Find main domain(s) - these are Tier 0
        main_domains = [
            entry["asset_domain_id"] 
            for entry in entries 
            if entry.get("domain_role") == DomainRole.MAIN.value
        ]
        
        if not main_domains:
            # No main domain found - all domains are orphans
            logger.warning(f"Network {network_id} has no main domain")
            return {asset_id: self.MAX_TIER for asset_id in entry_map.keys()}
        
        # BFS from main domain(s)
        tiers: Dict[str, int] = {}
        visited = set()
        queue = deque()
        
        # Initialize with main domains at tier 0
        for main_id in main_domains:
            queue.append((main_id, 0))
            visited.add(main_id)
            tiers[main_id] = 0
        
        while queue:
            current_id, current_tier = queue.popleft()
            
            # Get all domains that point to current domain
            for source_id in graph.get(current_id, []):
                if source_id not in visited:
                    visited.add(source_id)
                    new_tier = min(current_tier + 1, self.MAX_TIER)
                    tiers[source_id] = new_tier
                    queue.append((source_id, new_tier))
        
        # Mark any unvisited domains as max tier (orphans)
        for asset_id in entry_map.keys():
            if asset_id not in tiers:
                tiers[asset_id] = self.MAX_TIER
                logger.debug(f"Orphan domain {asset_id} assigned tier {self.MAX_TIER}")
        
        return tiers
    
    async def calculate_domain_tier(
        self, 
        network_id: str, 
        asset_domain_id: str
    ) -> Tuple[int, str]:
        """
        Calculate tier for a single domain.
        
        Args:
            network_id: ID of the SEO network
            asset_domain_id: ID of the asset domain
        
        Returns:
            Tuple of (tier_number, tier_label)
        """
        tiers = await self.calculate_network_tiers(network_id)
        tier = tiers.get(asset_domain_id, self.MAX_TIER)
        return tier, get_tier_label(tier)
    
    async def get_tier_distribution(self, network_id: str) -> Dict[str, int]:
        """
        Get distribution of domains across tiers for a network.
        
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
    
    async def get_domains_at_tier(
        self, 
        network_id: str, 
        tier: int
    ) -> List[str]:
        """
        Get all domain IDs at a specific tier.
        
        Args:
            network_id: ID of the SEO network
            tier: Tier level (0-5)
        
        Returns:
            List of asset_domain_ids at the specified tier
        """
        tiers = await self.calculate_network_tiers(network_id)
        return [
            domain_id 
            for domain_id, domain_tier in tiers.items() 
            if domain_tier == tier
        ]
    
    async def validate_hierarchy(self, network_id: str) -> Dict[str, List[str]]:
        """
        Validate the hierarchy for potential issues.
        
        Returns:
            Dictionary of issues found:
            - orphans: Domains not connected to main domain
            - cycles: Domains involved in circular references
            - multiple_mains: Multiple main domains (may be valid)
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
        
        # Find main domains
        main_domains = [
            entry["asset_domain_id"]
            for entry in entries
            if entry.get("domain_role") == DomainRole.MAIN.value
        ]
        
        if len(main_domains) > 1:
            issues["multiple_mains"] = main_domains
        
        # Calculate tiers to find orphans
        tiers = await self.calculate_network_tiers(network_id)
        
        for entry in entries:
            asset_id = entry["asset_domain_id"]
            
            # Check for orphans (not main but not connected)
            if entry.get("domain_role") != DomainRole.MAIN.value:
                if tiers.get(asset_id, self.MAX_TIER) == self.MAX_TIER:
                    # Check if it has no target
                    if not entry.get("target_asset_domain_id"):
                        issues["orphans"].append(asset_id)
        
        # TODO: Add cycle detection if needed
        
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
        
        # Calculate tiers for each network
        network_tiers: Dict[str, Dict[str, int]] = {}
        for nid in networks.keys():
            network_tiers[nid] = await self.calculate_network_tiers(nid)
        
        # Enrich entries
        for entry in entries:
            nid = entry.get("network_id") or network_id
            asset_id = entry.get("asset_domain_id")
            
            if nid and asset_id:
                tier = network_tiers.get(nid, {}).get(asset_id, self.MAX_TIER)
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
