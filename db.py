from supabase import create_client, Client
from datetime import datetime, timezone
from utils.constants import (
    SUPABASE_URL, SUPABASE_KEY, TABLE_PROFILES, TABLE_ACTIVE_LISTINGS,
    TABLE_LIST_MESSAGES, LIST_TYPE_PINNED, LIST_TYPE_CHAT
)

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_profile(user_id: int) -> dict | None:
    """Fetches a model's profile from the database."""
    try:
        response = supabase.table(TABLE_PROFILES).select("*").eq("user_id", user_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error fetching profile for {user_id}: {e}")
        return None

def save_profile(data: dict) -> bool:
    """Inserts or updates a model's profile."""
    user_id = data.get("user_id")
    if not user_id:
        return False
    
    # Add updated_at timestamp
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        # Check if profile exists
        existing_profile = get_profile(user_id)
        
        if existing_profile:
            # Update existing profile
            response = supabase.table(TABLE_PROFILES).update(data).eq("user_id", user_id).execute()
        else:
            # Insert new profile
            data["created_at"] = data["updated_at"]
            response = supabase.table(TABLE_PROFILES).insert(data).execute()
        
        return bool(response.data)
    except Exception as e:
        print(f"Error saving profile for {user_id}: {e}")
        return False

def delete_profile(user_id: int) -> bool:
    """Deletes a model's profile and cascade-deletes active listings."""
    try:
        # Deleting from profiles should cascade to active_listings due to foreign key
        response = supabase.table(TABLE_PROFILES).delete().eq("user_id", user_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error deleting profile for {user_id}: {e}")
        return False

def get_active_listing(user_id: int) -> dict | None:
    """Fetches a model's active listing."""
    try:
        response = supabase.table(TABLE_ACTIVE_LISTINGS).select("*").eq("user_id", user_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error fetching active listing for {user_id}: {e}")
        return None

def get_all_active_listings() -> list[dict]:
    """Fetches all active listings, ordered by last_bump_at for list generation."""
    try:
        response = supabase.table(TABLE_ACTIVE_LISTINGS).select("*").order("last_bump_at", desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Error fetching all active listings: {e}")
        return []

def save_active_listing(data: dict) -> bool:
    """Inserts a new active listing."""
    try:
        # Set initial last_bump_at
        if "last_bump_at" not in data:
            data["last_bump_at"] = datetime.now(timezone.utc).isoformat()
            
        response = supabase.table(TABLE_ACTIVE_LISTINGS).insert(data).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error saving active listing: {e}")
        return False

def update_active_listing(listing_id: str, data: dict) -> bool:
    """Updates an existing active listing."""
    try:
        response = supabase.table(TABLE_ACTIVE_LISTINGS).update(data).eq("id", listing_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error updating active listing {listing_id}: {e}")
        return False

def delete_active_listing(listing_id: str) -> bool:
    """Deletes an active listing."""
    try:
        response = supabase.table(TABLE_ACTIVE_LISTINGS).delete().eq("id", listing_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error deleting active listing {listing_id}: {e}")
        return False

def get_list_message(list_type: str) -> dict | None:
    """Fetches the message ID for the pinned or chat list."""
    try:
        response = supabase.table(TABLE_LIST_MESSAGES).select("*").eq("type", list_type).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error fetching list message for {list_type}: {e}")
        return None

def save_list_message(list_type: str, message_id: int) -> bool:
    """Inserts or updates the message ID for the pinned or chat list."""
    data = {
        "type": list_type,
        "message_id": message_id,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    try:
        # Upsert logic: Supabase handles this with on_conflict
        response = supabase.table(TABLE_LIST_MESSAGES).upsert(data, on_conflict="type").execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error saving list message for {list_type}: {e}")
        return False

# --- Schema Creation (Manual for now, but good to have a function) ---
# NOTE: In a real-world scenario, the schema would be created via Supabase migration.
# For this task, we assume the tables exist or the user will create them.
# The SQL is in the requirements document.
# The required tables are: profiles, active_listings, list_messages
