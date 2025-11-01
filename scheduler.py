from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot
from datetime import datetime, timezone
from typing import Dict, Any
import db
from utils.constants import (
    GROUP_CHAT_ID, TABLE_ACTIVE_LISTINGS, LIST_TYPE_PINNED, LIST_TYPE_CHAT
)
from utils.formatting import format_time_remaining, generate_list_message

scheduler = BackgroundScheduler()

def get_profiles_for_listings(listings: list[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """Helper to fetch profiles for a list of listings."""
    user_ids = [listing["user_id"] for listing in listings]
    profiles = {}
    for user_id in user_ids:
        profile = db.get_profile(user_id)
        if profile:
            profiles[user_id] = profile
    return profiles

def update_available_lists(bot: Bot):
    """Updates both the Pinned List and the Chat List."""
    print("Running update_available_lists job...")
    
    active_listings = db.get_all_active_listings()
    profiles = get_profiles_for_listings(active_listings)
    
    if not active_listings:
        print("No active listings found. Skipping list update.")
        return

    list_content = generate_list_message(active_listings, profiles, int(GROUP_CHAT_ID))
    
    # 1. Update Pinned List
    pinned_msg_data = db.get_list_message(LIST_TYPE_PINNED)
    if pinned_msg_data:
        try:
            bot.edit_message_text(
                chat_id=GROUP_CHAT_ID,
                message_id=pinned_msg_data["message_id"],
                text=list_content,
                parse_mode="MarkdownV2"
            )
            print(f"Updated Pinned List message {pinned_msg_data['message_id']}")
        except Exception as e:
            print(f"Error updating Pinned List: {e}")
            # If message is gone, we should probably try to re-pin a new one, but for now, just log.
    else:
        print("Pinned List message ID not found in DB. Cannot update.")

    # 2. Update Chat List (No need to delete/repost, as member handler does that)
    # The member handler's /available command is the primary way to refresh the chat list.
    # We only update the pinned list here to keep it current.

def update_countdown_timers(bot: Bot):
    """Job to update the countdown timer on all active listing messages."""
    print("Running update_countdown_timers job...")
    active_listings = db.get_all_active_listings()
    
    for listing in active_listings:
        time_remaining = format_time_remaining(listing["expires_at"])
        
        # We need the full message content to edit the caption/text
        # For simplicity, we'll re-generate the entire message with the new countdown
        profile = db.get_profile(listing["user_id"])
        if not profile:
            print(f"Profile not found for listing {listing['id']}")
            continue
            
        new_message_text = db.generate_listing_message(profile, listing)
        
        try:
            # Assuming the listing is a text message or a media group with a caption
            # We use edit_message_text for simplicity, assuming the media is handled separately
            # A full implementation would need to check if it's a media group and use edit_message_caption
            bot.edit_message_text(
                chat_id=GROUP_CHAT_ID,
                message_id=listing["message_id"],
                text=new_message_text,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            print(f"Error updating countdown for listing {listing['id']}: {e}")
            # If the message is gone, it will be cleaned up by the next job run

def cleanup_expired_listings(bot: Bot):
    """Job to find and delete expired listings."""
    print("Running cleanup_expired_listings job...")
    active_listings = db.get_all_active_listings()
    now = datetime.now(timezone.utc)
    
    listings_expired = False
    
    for listing in active_listings:
        expiry_time = datetime.fromisoformat(listing["expires_at"].replace('Z', '+00:00'))
        
        if expiry_time <= now:
            listings_expired = True
            print(f"Listing {listing['id']} for user {listing['user_id']} has expired.")
            
            # 1. Delete message from group chat
            try:
                bot.delete_message(chat_id=GROUP_CHAT_ID, message_id=listing["message_id"])
                print(f"Deleted message {listing['message_id']} from chat.")
            except Exception as e:
                print(f"Error deleting message {listing['message_id']}: {e}")
                
            # 2. Delete record from active_listings table
            if db.delete_active_listing(listing["id"]):
                print(f"Deleted listing record {listing['id']} from DB.")
            else:
                print(f"Failed to delete listing record {listing['id']} from DB.")

    if listings_expired:
        # 3. Update the available lists if any listing expired
        update_available_lists(bot)

def start_scheduler(bot: Bot):
    """Starts the APScheduler with the defined jobs."""
    # Pass the bot instance to the job functions
    scheduler.add_job(update_countdown_timers, 'interval', seconds=60, args=[bot], id='countdown_timer')
    scheduler.add_job(cleanup_expired_listings, 'interval', seconds=60, args=[bot], id='expired_cleanup')
    
    # Also add a job to update the lists periodically, just in case
    scheduler.add_job(update_available_lists, 'interval', minutes=5, args=[bot], id='list_periodic_update')
    
    scheduler.start()
    print("APScheduler started.")

def stop_scheduler():
    """Stops the APScheduler."""
    if scheduler.running:
        scheduler.shutdown()
        print("APScheduler stopped.")
