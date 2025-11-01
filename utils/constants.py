import os
from dotenv import load_dotenv

load_dotenv()

# --- Environment Variables ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Comma-separated list of Telegram user IDs for approved admins
APPROVED_ADMIN_IDS = [int(uid.strip()) for uid in os.getenv("APPROVED_ADMIN_IDS", "").split(",") if uid.strip()]
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID") # The ID of the group chat where the bot operates

# --- Bot Configuration ---
COOLDOWN_MINUTES = 30
BUMP_COOLDOWN_SECONDS = COOLDOWN_MINUTES * 60
LISTING_DURATIONS = {
    "2h": 2,
    "4h": 4,
    "6h": 6,
}

# --- Database Table Names ---
TABLE_PROFILES = "profiles"
TABLE_ACTIVE_LISTINGS = "active_listings"
TABLE_LIST_MESSAGES = "list_messages"

# --- List Message Types ---
LIST_TYPE_PINNED = "pinned"
LIST_TYPE_CHAT = "chat"

# --- Conversation States for Profile Wizard ---
STATE_NAME = 1
STATE_SERVICES = 2
STATE_INPERSON = 3
STATE_FACETIME = 4
STATE_CUSTOM = 5
STATE_OTHER = 6
STATE_ABOUT = 7
STATE_CONTACT_METHOD = 8
STATE_CONTACT_INFO = 9
STATE_SOCIAL_LINKS = 10
STATE_RATES = 11
STATE_DISCLAIMER = 12
STATE_ALLOW_COMMENTS = 13
STATE_PHOTOS = 14
STATE_VIDEOS = 15
STATE_PREVIEW = 16
STATE_END = 17
