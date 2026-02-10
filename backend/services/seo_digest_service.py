"""
SEO Optimization Digest Service
================================
Generates and sends periodic summaries of SEO optimization activities.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class SeoDigestService:
    """Service for generating and sending SEO optimization digests"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def generate_weekly_digest(
        self, brand_id: Optional[str] = None, days: int = 7
    ) -> Dict[str, Any]:
        """
        Generate a weekly digest of SEO optimization activities.

        Args:
            brand_id: Optional brand filter
            days: Number of days to include (default 7)

        Returns:
            Dict with digest data
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Build query
        query = {
            "created_at": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}
        }
        if brand_id:
            query["brand_id"] = brand_id

        # Get optimizations
        optimizations = await self.db.seo_optimizations.find(query, {"_id": 0}).to_list(
            1000
        )

        # Get complaints
        complaint_query = {
            "created_at": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}
        }
        complaints = await self.db.optimization_complaints.find(
            complaint_query, {"_id": 0}
        ).to_list(500)

        # Aggregate stats
        total_optimizations = len(optimizations)
        by_status = {}
        by_activity_type = {}
        by_user = {}
        by_network = {}

        for opt in optimizations:
            # By status
            status = opt.get("status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1

            # By activity type
            activity_type = opt.get("activity_type", "other")
            by_activity_type[activity_type] = by_activity_type.get(activity_type, 0) + 1

            # By user
            user_name = opt.get("created_by", {}).get("display_name", "Unknown")
            by_user[user_name] = by_user.get(user_name, 0) + 1

            # By network
            network_id = opt.get("network_id")
            by_network[network_id] = by_network.get(network_id, 0) + 1

        # Get network names
        network_names = {}
        if by_network:
            networks = await self.db.seo_networks.find(
                {"id": {"$in": list(by_network.keys())}}, {"_id": 0, "id": 1, "name": 1}
            ).to_list(100)
            network_names = {n["id"]: n["name"] for n in networks}

        # Calculate complaint stats
        total_complaints = len(complaints)
        resolved_complaints = len(
            [c for c in complaints if c.get("status") == "resolved"]
        )

        # Top performers (most completions)
        completed_by_user = {}
        for opt in optimizations:
            if opt.get("status") == "completed":
                user_name = opt.get("created_by", {}).get("display_name", "Unknown")
                completed_by_user[user_name] = completed_by_user.get(user_name, 0) + 1

        top_performers = sorted(
            [{"name": k, "count": v} for k, v in completed_by_user.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        return {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "days": days,
            "total_optimizations": total_optimizations,
            "by_status": by_status,
            "by_activity_type": by_activity_type,
            "by_user": by_user,
            "by_network": {network_names.get(k, k): v for k, v in by_network.items()},
            "total_complaints": total_complaints,
            "resolved_complaints": resolved_complaints,
            "complaint_resolution_rate": (
                round(resolved_complaints / total_complaints * 100, 1)
                if total_complaints > 0
                else 0
            ),
            "top_performers": top_performers,
        }

    async def format_telegram_digest(self, digest: Dict[str, Any]) -> str:
        """Format digest data as a Telegram message"""

        # Status emoji mapping
        status_emoji = {
            "completed": "✅",
            "in_progress": "🔄",
            "planned": "📋",
            "reverted": "❌",
        }

        # Build message
        lines = [
            "📊 *LAPORAN MINGGUAN SEO OPTIMIZATIONS*",
            f"📅 Periode: {digest['period_start'][:10]} s/d {digest['period_end'][:10]}",
            "",
            f"📈 *Total Aktivitas:* {digest['total_optimizations']}",
            "",
        ]

        # Status breakdown
        if digest["by_status"]:
            lines.append("*Status:*")
            for status, count in sorted(
                digest["by_status"].items(), key=lambda x: x[1], reverse=True
            ):
                emoji = status_emoji.get(status, "•")
                lines.append(f"  {emoji} {status.replace('_', ' ').title()}: {count}")
            lines.append("")

        # Activity type breakdown
        if digest["by_activity_type"]:
            lines.append("*Jenis Aktivitas:*")
            for activity_type, count in sorted(
                digest["by_activity_type"].items(), key=lambda x: x[1], reverse=True
            )[:5]:
                lines.append(f"  • {activity_type.replace('_', ' ').title()}: {count}")
            lines.append("")

        # Top performers
        if digest["top_performers"]:
            lines.append("🏆 *Top Kontributor:*")
            for i, performer in enumerate(digest["top_performers"][:3], 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
                lines.append(
                    f"  {medal} {performer['name']}: {performer['count']} selesai"
                )
            lines.append("")

        # Complaints
        if digest["total_complaints"] > 0:
            lines.append("⚠️ *Komplain:*")
            lines.append(f"  • Total: {digest['total_complaints']}")
            lines.append(f"  • Terselesaikan: {digest['resolved_complaints']}")
            lines.append(
                f"  • Tingkat Resolusi: {digest['complaint_resolution_rate']}%"
            )
            lines.append("")

        # Network breakdown
        if digest["by_network"]:
            lines.append("🌐 *Per Network:*")
            for network, count in sorted(
                digest["by_network"].items(), key=lambda x: x[1], reverse=True
            )[:5]:
                network_display = network[:25] + "..." if len(network) > 25 else network
                lines.append(f"  • {network_display}: {count}")

        return "\n".join(lines)

    async def send_digest(self, brand_id: Optional[str] = None, days: int = 7) -> bool:
        """
        Generate and send a digest via Telegram.

        Returns:
            True if sent successfully
        """
        try:
            # Generate digest
            digest = await self.generate_weekly_digest(brand_id, days)

            if digest["total_optimizations"] == 0:
                logger.info("No optimizations in period, skipping digest")
                return True

            # Format message
            message = await self.format_telegram_digest(digest)

            # Get Telegram settings
            settings = await self.db.settings.find_one(
                {"_id": "seo_optimization_telegram"}, {"_id": 0}
            )

            if (
                not settings
                or not settings.get("enabled")
                or not settings.get("bot_token")
                or not settings.get("chat_id")
            ):
                logger.warning("Telegram not configured for SEO optimization digest")
                return False

            # Send via Telegram
            import aiohttp

            url = f"https://api.telegram.org/bot{settings['bot_token']}/sendMessage"
            payload = {
                "chat_id": settings["chat_id"],
                "text": message,
                "parse_mode": "Markdown",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info("Weekly digest sent successfully")
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"Failed to send digest: {error}")
                        return False

        except Exception as e:
            logger.error(f"Error sending digest: {e}")
            return False


# Global instance
seo_digest_service: Optional[SeoDigestService] = None


def init_seo_digest_service(db: AsyncIOMotorDatabase) -> SeoDigestService:
    """Initialize the global digest service instance"""
    global seo_digest_service
    seo_digest_service = SeoDigestService(db)
    return seo_digest_service
