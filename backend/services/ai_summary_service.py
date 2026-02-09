"""
AI Summary Service for SEO Optimizations
==========================================
Uses LLM to generate intelligent summaries of SEO optimization activities.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class AiSummaryService:
    """Service for generating AI-powered summaries of SEO optimizations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.api_key = os.environ.get("EMERGENT_LLM_KEY")
    
    async def generate_optimization_summary(
        self,
        network_id: Optional[str] = None,
        brand_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Generate an AI-powered summary of SEO optimization activities.
        
        Args:
            network_id: Optional network filter
            brand_id: Optional brand filter  
            days: Number of days to include
            
        Returns:
            Dict with AI-generated summary
        """
        if not self.api_key:
            return {
                "error": "EMERGENT_LLM_KEY not configured",
                "summary": None
            }
        
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
        except ImportError:
            return {
                "error": "emergentintegrations library not installed",
                "summary": None
            }
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Build query
        query = {
            "created_at": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            }
        }
        if network_id:
            query["network_id"] = network_id
        if brand_id:
            query["brand_id"] = brand_id
        
        # Get optimizations
        optimizations = await self.db.seo_optimizations.find(
            query, {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        
        if not optimizations:
            return {
                "summary": "Tidak ada aktivitas optimasi SEO dalam periode ini.",
                "data": {"total": 0}
            }
        
        # Get complaints for context
        opt_ids = [o["id"] for o in optimizations]
        complaints = await self.db.optimization_complaints.find(
            {"optimization_id": {"$in": opt_ids}},
            {"_id": 0}
        ).to_list(100)
        
        # Get network names
        network_ids = list(set(o.get("network_id") for o in optimizations))
        networks = await self.db.seo_networks.find(
            {"id": {"$in": network_ids}},
            {"_id": 0, "id": 1, "name": 1}
        ).to_list(100)
        network_map = {n["id"]: n["name"] for n in networks}
        
        # Prepare context for AI
        activities_text = []
        for opt in optimizations[:30]:  # Limit to prevent too long prompt
            network_name = network_map.get(opt.get("network_id"), "Unknown")
            activities_text.append(
                f"- [{opt.get('activity_type', 'unknown')}] {opt['title']} "
                f"(Network: {network_name}, Status: {opt['status']}, "
                f"By: {opt.get('created_by', {}).get('display_name', 'Unknown')})"
            )
        
        complaints_text = []
        for comp in complaints[:10]:
            complaints_text.append(
                f"- Complaint: {comp.get('reason', 'No reason')[:100]} (Status: {comp.get('status', 'unknown')})"
            )
        
        # Build prompt
        prompt = f"""Anda adalah analis SEO senior. Buatlah ringkasan eksekutif dalam Bahasa Indonesia tentang aktivitas optimasi SEO berikut dalam {days} hari terakhir.

AKTIVITAS OPTIMASI ({len(optimizations)} total):
{chr(10).join(activities_text)}

{f"KOMPLAIN ({len(complaints)} total):{chr(10)}{chr(10).join(complaints_text)}" if complaints_text else "Tidak ada komplain dalam periode ini."}

Buatlah ringkasan yang mencakup:
1. Gambaran umum aktivitas (apa yang paling banyak dilakukan)
2. Insight tentang fokus tim (network/aktivitas mana yang paling aktif)
3. Status penyelesaian (berapa yang selesai vs in-progress)
4. Jika ada komplain, sebutkan ringkasan masalah utama
5. Rekomendasi untuk periode berikutnya

Format output dalam paragraf yang mudah dibaca, maksimal 300 kata. Gunakan bullet points jika perlu."""

        try:
            # Initialize LLM chat
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"seo_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                system_message="Anda adalah analis SEO profesional yang membantu tim membuat laporan aktivitas. Selalu gunakan Bahasa Indonesia yang profesional."
            ).with_model("openai", "gpt-4o")
            
            # Send message
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
            
            # Calculate stats
            status_counts = {}
            type_counts = {}
            for opt in optimizations:
                status = opt.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
                
                activity_type = opt.get("activity_type", "other")
                type_counts[activity_type] = type_counts.get(activity_type, 0) + 1
            
            return {
                "summary": response,
                "data": {
                    "period_days": days,
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                    "total_optimizations": len(optimizations),
                    "total_complaints": len(complaints),
                    "by_status": status_counts,
                    "by_activity_type": type_counts
                },
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"AI summary generation failed: {e}")
            return {
                "error": str(e),
                "summary": None
            }
    
    async def generate_single_optimization_summary(
        self,
        optimization_id: str
    ) -> Dict[str, Any]:
        """
        Generate an AI summary for a single optimization.
        Useful for quick overview in the detail view.
        """
        if not self.api_key:
            return {"error": "EMERGENT_LLM_KEY not configured", "summary": None}
        
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
        except ImportError:
            return {"error": "emergentintegrations library not installed", "summary": None}
        
        # Get optimization
        opt = await self.db.seo_optimizations.find_one(
            {"id": optimization_id},
            {"_id": 0}
        )
        if not opt:
            return {"error": "Optimization not found", "summary": None}
        
        # Get complaints and responses
        complaints = await self.db.optimization_complaints.find(
            {"optimization_id": optimization_id},
            {"_id": 0}
        ).to_list(10)
        
        responses = opt.get("responses", [])
        
        # Build prompt
        prompt = f"""Buatlah ringkasan singkat (50-100 kata) dalam Bahasa Indonesia untuk aktivitas optimasi SEO berikut:

Judul: {opt['title']}
Tipe: {opt.get('activity_type', 'unknown')}
Status: {opt['status']}
Deskripsi: {opt.get('description', 'Tidak ada deskripsi')}
Alasan: {opt.get('reason_note', 'Tidak disebutkan')}

Jumlah Komplain: {len(complaints)}
Jumlah Respon Tim: {len(responses)}

Berikan ringkasan yang mencakup: apa yang dilakukan, mengapa, dan status saat ini. Buat singkat dan informatif."""

        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"opt_summary_{optimization_id}",
                system_message="Anda adalah asisten yang meringkas aktivitas SEO secara singkat dan jelas."
            ).with_model("openai", "gpt-4o")
            
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
            
            return {
                "summary": response,
                "optimization_id": optimization_id,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Single optimization summary failed: {e}")
            return {"error": str(e), "summary": None}


# Global instance
ai_summary_service: Optional[AiSummaryService] = None


def init_ai_summary_service(db: AsyncIOMotorDatabase) -> AiSummaryService:
    """Initialize the global AI summary service instance"""
    global ai_summary_service
    ai_summary_service = AiSummaryService(db)
    return ai_summary_service
