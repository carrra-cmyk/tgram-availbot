from telegram import Update, Bot
from telegram.ext import ContextTypes
import db
from utils.constants import LIST_TYPE_CHAT, GROUP_CHAT_ID
from utils.formatting import generate_list_message

async def member_available_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the /available command from a regular member.
    Deletes the old chat list message, posts a new one, and updates the DB.
    """
    # Only respond in the designated group chat
    if str(update.effective_chat.id) != GROUP_CHAT_ID:
        return

    bot: Bot = context.bot
    
    # 1. Get all active listings
    active_listings = db.get_all_active_listings()
    
    # 2. Fetch profiles for all active listings
    user_ids = [listing["user_id"] for listing in active_listings]
    profiles = {}
    for user_id in user_ids:
        profile = db.get_profile(user_id)
        if profile:
            profiles[user_id] = profile
            
    # 3. Generate the new list content
    list_content = generate_list_message(active_listings, profiles, update.effective_chat.id)
    
    # 4. Get the old chat list message ID
    old_chat_msg_data = db.get_list_message(LIST_TYPE_CHAT)
    
    # 5. Delete the old chat list message (to avoid clutter)
    if old_chat_msg_data:
        try:
            await bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=old_chat_msg_data["message_id"]
            )
        except Exception as e:
            # Log error but continue, the message might have been deleted by a user
            print(f"Error deleting old chat list message {old_chat_msg_data['message_id']}: {e}")

    # 6. Post the new chat list message
    try:
        new_message = await update.effective_chat.send_message(
            text=list_content,
            parse_mode="MarkdownV2"
        )
        
        # 7. Update the list_messages table with the new message ID
        db.save_list_message(LIST_TYPE_CHAT, new_message.message_id)
        
    except Exception as e:
        print(f"Error posting new chat list message: {e}")
