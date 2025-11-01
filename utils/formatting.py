from datetime import datetime, timezone
from typing import List, Dict, Any
import json

def format_time_remaining(expires_at: str) -> str:
    """Calculates and formats the time remaining until expiration."""
    try:
        # Parse the ISO format string from the database
        expiry_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        time_diff = expiry_time - now
        
        if time_diff.total_seconds() <= 0:
            return "EXPIRED"

        total_seconds = int(time_diff.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except Exception:
        return "N/A"

def generate_listing_message(profile: Dict[str, Any], listing: Dict[str, Any]) -> str:
    """
    Generates the rich Telegram message content for a model's availability listing.
    Uses MarkdownV2 for formatting.
    """
    
    # Escape characters for MarkdownV2: _, *, [, ], (, ), ~, `, >, #, +, -, =, |, {, }, ., !
    def escape_markdown_v2(text: str) -> str:
        if not text:
            return ""
        # Only escape characters that are not part of a link or already escaped
        # This is a simplified escape, full implementation is complex.
        # For simplicity, we'll focus on common ones and assume we control the structure.
        # A safer approach is to use HTML parsing mode, but requirements specified Markdown.
        # Let's use a basic escape for now.
        return text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')

    # --- Header ---
    name_subject = escape_markdown_v2(profile.get("name_subject", "Model Available"))
    message = f"*{name_subject}*\n\n"

    # --- About ---
    about = escape_markdown_v2(profile.get("about", "No description provided."))
    message += f"\\_About\\_\n{about}\n\n"

    # --- Services Offered ---
    offer_types = json.loads(profile.get("offer_types", "[]"))
    if offer_types:
        message += "*Services Offered:*\n"
        for service in offer_types:
            message += f"• {escape_markdown_v2(service)}\n"
        message += "\n"
        
        # Detailed service info
        if "In-Person" in offer_types:
            incall_outcall = escape_markdown_v2(profile.get("inperson_incall_outcall", "N/A"))
            location = escape_markdown_v2(profile.get("inperson_location", "N/A"))
            message += f"\\_In\\-Person Details\\_\nLocation: {location}\nType: {incall_outcall}\n\n"
        
        if "Facetime Shows" in offer_types:
            platforms = escape_markdown_v2(profile.get("facetime_platforms", "N/A"))
            payment = escape_markdown_v2(profile.get("facetime_payment", "N/A"))
            message += f"\\_Facetime Details\\_\nPlatforms: {platforms}\nPayment: {payment}\n\n"

        if "Custom Content" in offer_types:
            payment = escape_markdown_v2(profile.get("custom_payment", "N/A"))
            delivery = escape_markdown_v2(profile.get("custom_delivery", "N/A"))
            message += f"\\_Custom Content Details\\_\nPayment: {payment}\nDelivery: {delivery}\n\n"

        if "Other" in offer_types:
            other_service = escape_markdown_v2(profile.get("other_service", "N/A"))
            message += f"\\_Other Service\\_\n{other_service}\n\n"

    # --- Rates ---
    rates = escape_markdown_v2(profile.get("rates", "Rates available upon request."))
    message += f"*Rates:*\n{rates}\n\n"

    # --- Contact ---
    contact_method = profile.get("contact_method", "telegram")
    contact_info = ""
    if contact_method == "text_call":
        contact_info = escape_markdown_v2(profile.get("phone", "N/A"))
        message += f"*Contact (Text/Call):* {contact_info}\n"
    elif contact_method == "email":
        contact_info = escape_markdown_v2(profile.get("email", "N/A"))
        message += f"*Contact (Email):* {contact_info}\n"
    elif contact_method == "telegram":
        username = profile.get("telegram_username", "")
        if username.startswith("@"):
            username = username[1:]
        contact_info = f"@{username}"
        message += f"*Contact (Telegram):* [{contact_info}](https://t.me/{username})\n"
    
    # --- Social Links ---
    social_links_raw = profile.get("social_links", "")
    if social_links_raw:
        message += "*Social Links:*\n"
        # Simple split by comma or newline
        links = [link.strip() for link in social_links_raw.replace('\n', ',').split(',') if link.strip()]
        for link in links:
            # Assuming the link is a full URL or a recognizable handle
            message += f"• {escape_markdown_v2(link)}\n"
        message += "\n"

    # --- Disclaimer ---
    disclaimer = escape_markdown_v2(profile.get("disclaimer", ""))
    if disclaimer:
        message += f"\\_Disclaimer\\_\n{disclaimer}\n\n"

    # --- Countdown ---
    time_remaining = format_time_remaining(listing["expires_at"])
    message += f"\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\n"
    message += f"*Expires in:* {time_remaining}"

    return message

def generate_list_message(active_listings: List[Dict[str, Any]], profiles: Dict[int, Dict[str, Any]], chat_id: int) -> str:
    """
    Generates the content for the Pinned or Chat list message.
    Uses MarkdownV2 for formatting.
    """
    
    # Escape characters for MarkdownV2
    def escape_markdown_v2(text: str) -> str:
        if not text:
            return ""
        return text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')

    count = len(active_listings)
    message = f"*AVAILABLE NOW ({count} available)*\n\n"

    if count == 0:
        message += "No models are currently available\\. Check back soon\\!"
        return message

    for i, listing in enumerate(active_listings):
        user_id = listing["user_id"]
        profile = profiles.get(user_id)
        
        if not profile:
            continue

        name_subject = escape_markdown_v2(profile.get("name_subject", f"Model {user_id}"))
        allow_comments = profile.get("allow_comments", False)
        
        # Telegram message link format: t.me/c/{chat_id}/{message_id}
        # The chat_id needs to be converted for public link format: remove the -100 prefix
        # For private groups, the link might not work, but we use the official format.
        # The group chat ID is usually -100XXXXXXXXXX. We need the XXXXXXXXXX part.
        link_chat_id = str(chat_id).replace("-100", "")
        message_link = f"https://t.me/c/{link_chat_id}/{listing['message_id']}"
        
        comment_icon = "💬" if allow_comments else ""
        
        # Numbered list with link to the post
        message += f"{i+1}\\. {name_subject} {comment_icon} [View Post]({message_link})\n"

    return message
