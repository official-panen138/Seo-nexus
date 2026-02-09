"""
Timezone Helper for SEO-NOC
===========================

Centralized timezone conversion for monitoring and alerts.
All times are STORED in UTC but DISPLAYED in the configured timezone.

Default: Asia/Jakarta (GMT+7)
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def format_to_local_time(
    dt_input,
    timezone_str: str = "Asia/Jakarta",
    timezone_label: str = "GMT+7"
) -> str:
    """
    Convert UTC datetime to local timezone for display.
    Storage remains UTC - this is DISPLAY-LEVEL only.
    
    Args:
        dt_input: datetime object or ISO format string (UTC)
        timezone_str: Target timezone (default: Asia/Jakarta = GMT+7)
        timezone_label: Human-readable label for the timezone
    
    Returns:
        Formatted string like "2026-02-09 23:02 GMT+7 (Asia/Jakarta)"
    """
    try:
        from zoneinfo import ZoneInfo
        
        # Handle string input
        if isinstance(dt_input, str):
            # Handle various formats
            if 'T' in dt_input:
                dt_input = dt_input.replace('Z', '+00:00')
            try:
                dt = datetime.fromisoformat(dt_input)
            except:
                dt = datetime.strptime(dt_input[:19], '%Y-%m-%d %H:%M:%S')
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt_input
        
        # If naive datetime, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        # Convert to target timezone
        local_tz = ZoneInfo(timezone_str)
        local_dt = dt.astimezone(local_tz)
        
        # Format with timezone label
        return f"{local_dt.strftime('%Y-%m-%d %H:%M')} {timezone_label} ({timezone_str})"
    except Exception as e:
        logger.warning(f"Timezone conversion error: {e}")
        # Fallback to UTC format
        if isinstance(dt_input, datetime):
            return dt_input.strftime('%Y-%m-%d %H:%M UTC')
        return str(dt_input)


def format_now_local(timezone_str: str = "Asia/Jakarta", timezone_label: str = "GMT+7") -> str:
    """Get current time formatted in local timezone"""
    return format_to_local_time(datetime.now(timezone.utc), timezone_str, timezone_label)


async def get_system_timezone(db) -> Tuple[str, str]:
    """
    Get the configured system timezone from database settings.
    
    Returns:
        Tuple of (timezone_str, timezone_label) e.g. ("Asia/Jakarta", "GMT+7")
    """
    try:
        settings = await db.settings.find_one({"key": "timezone"}, {"_id": 0})
        if settings:
            return (
                settings.get("default_timezone", "Asia/Jakarta"),
                settings.get("timezone_label", "GMT+7")
            )
    except Exception as e:
        logger.warning(f"Error fetching timezone settings: {e}")
    
    return "Asia/Jakarta", "GMT+7"


# Common timezone options for UI dropdown
TIMEZONE_OPTIONS = [
    {"value": "Asia/Jakarta", "label": "GMT+7 (Asia/Jakarta)", "offset": "+07:00"},
    {"value": "Asia/Singapore", "label": "GMT+8 (Asia/Singapore)", "offset": "+08:00"},
    {"value": "Asia/Tokyo", "label": "GMT+9 (Asia/Tokyo)", "offset": "+09:00"},
    {"value": "Asia/Bangkok", "label": "GMT+7 (Asia/Bangkok)", "offset": "+07:00"},
    {"value": "Asia/Kolkata", "label": "GMT+5:30 (Asia/Kolkata)", "offset": "+05:30"},
    {"value": "Europe/London", "label": "GMT+0 (Europe/London)", "offset": "+00:00"},
    {"value": "Europe/Paris", "label": "GMT+1 (Europe/Paris)", "offset": "+01:00"},
    {"value": "America/New_York", "label": "GMT-5 (America/New_York)", "offset": "-05:00"},
    {"value": "America/Los_Angeles", "label": "GMT-8 (America/Los_Angeles)", "offset": "-08:00"},
    {"value": "UTC", "label": "UTC", "offset": "+00:00"},
]
