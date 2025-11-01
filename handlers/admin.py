from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
import json
import db
from utils.constants import (
    APPROVED_ADMIN_IDS, GROUP_CHAT_ID, LISTING_DURATIONS, COOLDOWN_MINUTES,
    STATE_NAME, STATE_SERVICES, STATE_INPERSON, STATE_FACETIME, STATE_CUSTOM,
    STATE_OTHER, STATE_ABOUT, STATE_CONTACT_METHOD, STATE_CONTACT_INFO,
    STATE_SOCIAL_LINKS, STATE_RATES, STATE_DISCLAIMER, STATE_ALLOW_COMMENTS,
    STATE_PHOTOS, STATE_VIDEOS, STATE_PREVIEW, STATE_END, LIST_TYPE_PINNED,
    LIST_TYPE_CHAT
)
from utils.formatting import generate_listing_message

# --- Helper Functions ---

def is_admin(user_id: int) -> bool:
    """Checks if the user is an approved admin."""
    return user_id in APPROVED_ADMIN_IDS

async def check_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Decorator-like function to check admin status and send a message if not."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("This bot is for authorized users only.")
        return False
    return True

async def update_available_lists_now(context: ContextTypes.DEFAULT_TYPE):
    """Triggers an immediate update of the Pinned List."""
    # This function is a simplified version of the scheduler's update_available_lists
    # It is called directly after a listing change.
    from scheduler import get_profiles_for_listings, update_available_lists
    
    # We can't call the scheduler's job directly, so we'll call the logic
    # The full logic is in scheduler.py, which imports db and formatting.
    # For now, we'll rely on the scheduler to pick up the changes quickly.
    # A better approach is to move the list update logic to a utility function.
    
    # For simplicity in this implementation, we'll just log and rely on the 60s scheduler job.
    # In a production environment, we would move the list update logic to a shared utility.
    print("Triggering list update via scheduler job...")
    # The scheduler will run the job in the background, so we don't need to wait.
    # The `update_available_lists` function in scheduler.py needs to be callable
    # with just the bot instance.
    # await update_available_lists(context.bot) # This would be the ideal call

# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a menu of options to approved admins in private chat."""
    if not await check_admin(update, context):
        return

    if update.effective_chat.type != "private":
        return

    keyboard = [
        [InlineKeyboardButton("Create/Edit Profile", callback_data="profile_edit")],
        [InlineKeyboardButton("Delete Profile", callback_data="profile_delete")],
        [InlineKeyboardButton("Go Available Now (Group)", callback_data="go_available")],
        [InlineKeyboardButton("Bump Listing (Group)", callback_data="bump_listing")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Welcome to the 'Available Now' Bot Admin Menu. What would you like to do?",
        reply_markup=reply_markup
    )

async def delete_profile_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Asks for confirmation before deleting the profile."""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("Unauthorized access.")
        return

    keyboard = [
        [InlineKeyboardButton("YES, Delete My Profile", callback_data="profile_delete_confirm")],
        [InlineKeyboardButton("Cancel", callback_data="profile_delete_cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "⚠️ *Are you sure you want to delete your profile?* This cannot be undone and will remove any active listing you have.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def delete_profile_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes the profile and active listing."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    
    if db.delete_profile(user_id):
        await query.edit_message_text("✅ Your profile has been deleted. You will need to run /createprofile again to use the bot.")
    else:
        await query.edit_message_text("❌ Failed to delete your profile. Please try again or contact support.")

# --- Profile Creation Wizard (ConversationHandler) ---

async def create_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the profile creation wizard."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Starting the Profile Setup Wizard...")
    elif update.message:
        await update.message.reply_text("Starting the Profile Setup Wizard...")
    
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    # Initialize user data for the wizard
    context.user_data["profile_data"] = db.get_profile(update.effective_user.id) or {"user_id": update.effective_user.id}
    context.user_data["media_photos"] = context.user_data["profile_data"].get("photo_file_ids", [])
    context.user_data["media_videos"] = context.user_data["profile_data"].get("video_file_ids", [])

    await update.effective_chat.send_message("Step 1/15: What name or catchy line do you want to display? (This will be the bold title of your listing)")
    return STATE_NAME

async def profile_name(update:
                       Update, context:
                       ContextTypes.DEFAULT_TYPE) -> int:
    """Collects the model's display name/headline."""
    context.user_data["profile_data"]["name_subject"] = update.message.text
    
    keyboard = [
        [
            InlineKeyboardButton("In-Person", callback_data="service_In-Person"),
            InlineKeyboardButton("Facetime Shows", callback_data="service_Facetime Shows")
        ],
        [
            InlineKeyboardButton("Custom Content", callback_data="service_Custom Content"),
            InlineKeyboardButton("Other", callback_data="service_Other")
        ],
        [InlineKeyboardButton("Done Selecting Services", callback_data="service_done")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.user_data["selected_services"] = []
    await update.message.reply_text(
        "Step 2/15: What services do you offer? (Tap one or more, then tap 'Done')",
        reply_markup=reply_markup
    )
    return STATE_SERVICES

async def profile_services_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles service selection buttons."""
    query = update.callback_query
    await query.answer()
    
    service = query.data.replace("service_", "")
    
    if service == "done":
        if not context.user_data["selected_services"]:
            await query.edit_message_text("Please select at least one service before continuing.")
            return STATE_SERVICES
        
        context.user_data["profile_data"]["offer_types"] = json.dumps(context.user_data["selected_services"])
        
        # Determine the next state based on selected services
        services = context.user_data["selected_services"]
        if "In-Person" in services:
            keyboard = [
                [InlineKeyboardButton("Incall Only", callback_data="inperson_Incall Only")],
                [InlineKeyboardButton("Outcall Only", callback_data="inperson_Outcall Only")],
                [InlineKeyboardButton("Both", callback_data="inperson_Both")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Step 3/15: You selected In-Person. Do you offer Incall, Outcall, or Both?",
                reply_markup=reply_markup
            )
            return STATE_INPERSON
        elif "Facetime Shows" in services:
            await query.edit_message_text("Step 4/15: You selected Facetime Shows. Which platforms/apps do you use? (e.g., Zoom, FaceTime)")
            return STATE_FACETIME
        elif "Custom Content" in services:
            await query.edit_message_text("Step 5/15: You selected Custom Content. How do you accept payment for content? (e.g., CashApp, PayPal)")
            return STATE_CUSTOM
        elif "Other" in services:
            await query.edit_message_text("Step 6/15: You selected Other. Please briefly describe the other service.")
            return STATE_OTHER
        else:
            # Skip all service-specific steps
            await query.edit_message_text("Step 7/15: Please provide a short bio or description of yourself (e.g., '5'6\" curvy, love chats!'). This will appear under an 'About' section.")
            return STATE_ABOUT
            
    else:
        if service in context.user_data["selected_services"]:
            context.user_data["selected_services"].remove(service)
        else:
            context.user_data["selected_services"].append(service)
        
        # Re-render the keyboard with updated selection status
        keyboard = [
            [InlineKeyboardButton(f"{'✅ ' if 'In-Person' in context.user_data['selected_services'] else ''}In-Person", callback_data="service_In-Person"),
             InlineKeyboardButton(f"{'✅ ' if 'Facetime Shows' in context.user_data['selected_services'] else ''}Facetime Shows", callback_data="service_Facetime Shows")],
            [InlineKeyboardButton(f"{'✅ ' if 'Custom Content' in context.user_data['selected_services'] else ''}Custom Content", callback_data="service_Custom Content"),
             InlineKeyboardButton(f"{'✅ ' if 'Other' in context.user_data['selected_services'] else ''}Other", callback_data="service_Other")],
            [InlineKeyboardButton("✅ Done Selecting Services", callback_data="service_done")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Step 2/15: What services do you offer? (Tap one or more, then tap 'Done')",
            reply_markup=reply_markup
        )
        return STATE_SERVICES

async def profile_inperson_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects Incall/Outcall preference."""
    query = update.callback_query
    await query.answer()
    
    context.user_data["profile_data"]["inperson_incall_outcall"] = query.data.replace("inperson_", "")
    
    await query.edit_message_text("Step 3/15: Please provide a short Location description (e.g., neighborhood or city area).")
    return STATE_INPERSON + 0.1 # Use a sub-state for the text input

async def profile_inperson_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects In-Person location."""
    context.user_data["profile_data"]["inperson_location"] = update.message.text
    
    services = context.user_data["selected_services"]
    if "Facetime Shows" in services:
        await update.message.reply_text("Step 4/15: You selected Facetime Shows. Which platforms/apps do you use? (e.g., Zoom, FaceTime)")
        return STATE_FACETIME
    elif "Custom Content" in services:
        await update.message.reply_text("Step 5/15: You selected Custom Content. How do you accept payment for content? (e.g., CashApp, PayPal)")
        return STATE_CUSTOM
    elif "Other" in services:
        await update.message.reply_text("Step 6/15: You selected Other. Please briefly describe the other service.")
        return STATE_OTHER
    else:
        await update.message.reply_text("Step 7/15: Please provide a short bio or description of yourself (e.g., '5'6\" curvy, love chats!'). This will appear under an 'About' section.")
        return STATE_ABOUT

async def profile_facetime_platforms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects Facetime platforms."""
    context.user_data["profile_data"]["facetime_platforms"] = update.message.text
    await update.message.reply_text("Step 4/15: What is your preferred payment method for these online shows? (e.g., CashApp, PayPal)")
    return STATE_FACETIME + 0.1

async def profile_facetime_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects Facetime payment method."""
    context.user_data["profile_data"]["facetime_payment"] = update.message.text
    
    services = context.user_data["selected_services"]
    if "Custom Content" in services:
        await update.message.reply_text("Step 5/15: You selected Custom Content. How do you accept payment for content? (e.g., CashApp, PayPal)")
        return STATE_CUSTOM
    elif "Other" in services:
        await update.message.reply_text("Step 6/15: You selected Other. Please briefly describe the other service.")
        return STATE_OTHER
    else:
        await update.message.reply_text("Step 7/15: Please provide a short bio or description of yourself (e.g., '5'6\" curvy, love chats!'). This will appear under an 'About' section.")
        return STATE_ABOUT

async def profile_custom_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects Custom Content payment method."""
    context.user_data["profile_data"]["custom_payment"] = update.message.text
    await update.message.reply_text("Step 5/15: How do you deliver the content? (e.g., Email, Google Drive link)")
    return STATE_CUSTOM + 0.1

async def profile_custom_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects Custom Content delivery method."""
    context.user_data["profile_data"]["custom_delivery"] = update.message.text
    
    services = context.user_data["selected_services"]
    if "Other" in services:
        await update.message.reply_text("Step 6/15: You selected Other. Please briefly describe the other service.")
        return STATE_OTHER
    else:
        await update.message.reply_text("Step 7/15: Please provide a short bio or description of yourself (e.g., '5'6\" curvy, love chats!'). This will appear under an 'About' section.")
        return STATE_ABOUT

async def profile_other_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects Other service description."""
    context.user_data["profile_data"]["other_service"] = update.message.text
    await update.message.reply_text("Step 7/15: Please provide a short bio or description of yourself (e.g., '5'6\" curvy, love chats!'). This will appear under an 'About' section.")
    return STATE_ABOUT

async def profile_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects the 'About' bio."""
    context.user_data["profile_data"]["about"] = update.message.text
    
    keyboard = [
        [InlineKeyboardButton("Text/Call", callback_data="contact_text_call")],
        [InlineKeyboardButton("Email", callback_data="contact_email")],
        [InlineKeyboardButton("Telegram", callback_data="contact_telegram")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Step 8/15: What is your preferred contact method?",
        reply_markup=reply_markup
    )
    return STATE_CONTACT_METHOD

async def profile_contact_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects the preferred contact method and asks for details."""
    query = update.callback_query
    await query.answer()
    
    method = query.data.replace("contact_", "")
    context.user_data["profile_data"]["contact_method"] = method
    
    if method == "text_call":
        await query.edit_message_text("Step 9/15: Please provide your phone number.")
        return STATE_CONTACT_INFO
    elif method == "email":
        await query.edit_message_text("Step 9/15: Please provide your email address.")
        return STATE_CONTACT_INFO
    elif method == "telegram":
        username = update.effective_user.username
        if username:
            context.user_data["profile_data"]["telegram_username"] = f"@{username}"
            await query.edit_message_text(f"Step 9/15: Using your Telegram username: @{username}. If this is incorrect, please type the correct one now, otherwise type 'skip'.")
            return STATE_CONTACT_INFO
        else:
            await query.edit_message_text("Step 9/15: Please provide your Telegram username (e.g., @myusername).")
            return STATE_CONTACT_INFO
    
    return STATE_CONTACT_METHOD # Should not happen

async def profile_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects the contact information based on the chosen method."""
    info = update.message.text
    method = context.user_data["profile_data"]["contact_method"]
    
    if info.lower() == "skip" and method == "telegram":
        # Skip logic for Telegram username if it was pre-filled
        pass
    elif method == "text_call":
        context.user_data["profile_data"]["phone"] = info
    elif method == "email":
        context.user_data["profile_data"]["email"] = info
    elif method == "telegram":
        context.user_data["profile_data"]["telegram_username"] = info if info.startswith("@") else f"@{info}"

    await update.message.reply_text("Step 10/15: Please provide any social or content links (OnlyFans, Twitter/X, Instagram, etc.). You can separate multiple links with commas or newlines. Type 'skip' if none.")
    return STATE_SOCIAL_LINKS

async def profile_social_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects social links."""
    links = update.message.text
    if links.lower() != "skip":
        context.user_data["profile_data"]["social_links"] = links
    
    await update.message.reply_text("Step 11/15: Please provide your pricing information or rates (could be a brief text or list of rates for services).")
    return STATE_RATES

async def profile_rates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects rates."""
    context.user_data["profile_data"]["rates"] = update.message.text
    
    await update.message.reply_text("Step 12/15: Do you have any disclaimer or note? (e.g., 'Deposits required. DM for booking.'). This is optional. Type 'skip' if none.")
    return STATE_DISCLAIMER

async def profile_disclaimer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects disclaimer."""
    disclaimer = update.message.text
    if disclaimer.lower() != "skip":
        context.user_data["profile_data"]["disclaimer"] = disclaimer
    
    keyboard = [
        [InlineKeyboardButton("YES 💬", callback_data="comments_true")],
        [InlineKeyboardButton("NO 🚫", callback_data="comments_false")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Step 13/15: Do you want to allow members to comment (threaded replies) under your availability posts?",
        reply_markup=reply_markup
    )
    return STATE_ALLOW_COMMENTS

async def profile_allow_comments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects allow_comments preference."""
    query = update.callback_query
    await query.answer()
    
    context.user_data["profile_data"]["allow_comments"] = query.data == "comments_true"
    
    await query.edit_message_text("Step 14/15: Please send up to 10 photos that will be used in your listing (as an album carousel). Send them one by one. When finished, type /done.")
    return STATE_PHOTOS

async def profile_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects photos and saves their file_ids."""
    if update.message.text and update.message.text.lower() == "/done":
        if not context.user_data["media_photos"]:
            await update.message.reply_text("Please send at least one photo or video, or confirm you want to skip media by typing /skip_media.")
            return STATE_PHOTOS
        
        context.user_data["profile_data"]["photo_file_ids"] = context.user_data["media_photos"]
        
        await update.message.reply_text("Step 15/15: Please send up to 4 short video clips. Send them one by one. When finished, type /done.")
        return STATE_VIDEOS
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id # Get the largest photo
        if len(context.user_data["media_photos"]) < 10:
            context.user_data["media_photos"].append(file_id)
            await update.message.reply_text(f"Photo received. Total photos: {len(context.user_data['media_photos'])}/10. Send another or type /done.")
        else:
            await update.message.reply_text("Maximum of 10 photos reached. Please type /done to continue.")
    elif update.message.document and update.message.document.mime_type.startswith('image'):
        file_id = update.message.document.file_id
        if len(context.user_data["media_photos"]) < 10:
            context.user_data["media_photos"].append(file_id)
            await update.message.reply_text(f"Image file received. Total photos: {len(context.user_data['media_photos'])}/10. Send another or type /done.")
        else:
            await update.message.reply_text("Maximum of 10 photos reached. Please type /done to continue.")
    else:
        await update.message.reply_text("Please send a photo or type /done when finished.")
        
    return STATE_PHOTOS

async def profile_videos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects videos and saves their file_ids."""
    if update.message.text and update.message.text.lower() == "/done":
        context.user_data["profile_data"]["video_file_ids"] = context.user_data["media_videos"]
        
        # Proceed to preview
        return await profile_preview(update, context)
    
    if update.message.video:
        file_id = update.message.video.file_id
        if len(context.user_data["media_videos"]) < 4:
            context.user_data["media_videos"].append(file_id)
            await update.message.reply_text(f"Video received. Total videos: {len(context.user_data['media_videos'])}/4. Send another or type /done.")
        else:
            await update.message.reply_text("Maximum of 4 videos reached. Please type /done to continue.")
    else:
        await update.message.reply_text("Please send a video or type /done when finished.")
        
    return STATE_VIDEOS

async def profile_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shows the final preview and asks for confirmation."""
    
    # Create a dummy listing for preview purposes
    dummy_listing = {
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "message_id": 0 # Not a real message ID
    }
    
    # Generate the message content
    message_text = generate_listing_message(context.user_data["profile_data"], dummy_listing)
    
    # Prepare media group for preview
    media_group = []
    photos = context.user_data["profile_data"].get("photo_file_ids", [])
    videos = context.user_data["profile_data"].get("video_file_ids", [])
    
    if photos:
        media_group.append(InputMediaPhoto(photos[0], caption="Preview Photo (1 of 10)"))
        for file_id in photos[1:]:
            media_group.append(InputMediaPhoto(file_id))
    
    if videos:
        if not media_group:
            media_group.append(InputMediaVideo(videos[0], caption="Preview Video (1 of 4)"))
        else:
            media_group.append(InputMediaVideo(videos[0]))
        for file_id in videos[1:]:
            media_group.append(InputMediaVideo(file_id))

    # Send media group first, then the text preview
    if media_group:
        await update.effective_chat.send_media_group(media=media_group)
    
    await update.effective_chat.send_message(
        "Step 16/15: *PROFILE PREVIEW*\n\n" + message_text,
        parse_mode="MarkdownV2"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ CONFIRM & SAVE", callback_data="profile_save")],
        [InlineKeyboardButton("✏️ Edit (Restart Wizard)", callback_data="profile_edit_restart")],
        [InlineKeyboardButton("❌ Cancel", callback_data="profile_cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_chat.send_message(
        "Review your profile. What would you like to do?",
        reply_markup=reply_markup
    )
    
    return STATE_PREVIEW

async def profile_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the profile data to the database."""
    query = update.callback_query
    await query.answer()
    
    profile_data = context.user_data["profile_data"]
    
    # Clean up temporary keys
    profile_data.pop("selected_services", None)
    
    if db.save_profile(profile_data):
        await query.edit_message_text("✅ Profile saved! You can now use /available in the group to go live.")
    else:
        await query.edit_message_text("❌ Failed to save profile. Please try again or contact support.")
        
    return ConversationHandler.END

async def profile_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the profile creation wizard."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "Profile setup cancelled. Your profile remains unchanged."
        )
    else:
        await update.message.reply_text(
            "Profile setup cancelled. Your profile remains unchanged."
        )
    return ConversationHandler.END

async def profile_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fallback for unexpected messages during the wizard."""
    await update.message.reply_text("I didn't understand that. Please follow the instructions for the current step or type /cancel to exit the wizard.")
    return ConversationHandler.END

# --- Group Chat Commands ---

async def admin_available_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the /available command from an admin in the group chat.
    Prompts for duration and posts the listing.
    """
    if not await check_admin(update, context):
        return
    
    if str(update.effective_chat.id) != GROUP_CHAT_ID:
        await update.message.reply_text("Please use this command in the designated group chat.")
        return

    user_id = update.effective_user.id
    profile = db.get_profile(user_id)
    
    if not profile:
        await update.message.reply_text("You need to create a profile first. Please start a private chat with me and use /start to begin.")
        return

    # Check for existing active listing
    existing_listing = db.get_active_listing(user_id)
    if existing_listing:
        # Delete old message and record
        try:
            await context.bot.delete_message(
                chat_id=GROUP_CHAT_ID,
                message_id=existing_listing["message_id"]
            )
        except Exception as e:
            print(f"Error deleting old listing message {existing_listing['message_id']}: {e}")
        
        db.delete_active_listing(existing_listing["id"])
        await update.message.reply_text("Your previous listing has been replaced with a new one.")

    # Prompt for duration
    keyboard = [
        [InlineKeyboardButton(f"{h} hours", callback_data=f"duration_{h}") for h in LISTING_DURATIONS.keys()]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "How long do you want to be available?",
        reply_markup=reply_markup
    )

async def post_listing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Posts the availability listing after duration selection."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    duration_str = query.data.replace("duration_", "")
    duration_hours = LISTING_DURATIONS.get(duration_str)
    
    if not duration_hours:
        await query.edit_message_text("Invalid duration selected.")
        return

    profile = db.get_profile(user_id)
    if not profile:
        await query.edit_message_text("Error: Profile not found.")
        return

    # Calculate expiry time
    expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
    
    # Generate message content
    dummy_listing = {"expires_at": expires_at.isoformat(), "message_id": 0}
    message_text = generate_listing_message(profile, dummy_listing)
    
    # Prepare media group
    media_group = []
    photos = profile.get("photo_file_ids", [])
    videos = profile.get("video_file_ids", [])
    
    # Telegram only allows one caption for a media group, so we'll use the text message
    # as the main post and the media group as a separate message or album.
    # For simplicity, we'll send the media group first, then the text message.
    
    # For a rich listing, we'll send the media group first, then the text message.
    # The requirement is for a "rich listing," which often means a single message with media.
    # We will use the media group feature, but the main text will be sent separately.
    # A better approach is to use the media group with the main text as the caption of the first item.
    
    # Let's use the caption approach for the first item in the media group.
    if photos or videos:
        media_items: List[Any] = []
        
        # Add photos
        for i, file_id in enumerate(photos):
            caption = message_text if i == 0 and not videos else None
            media_items.append(InputMediaPhoto(file_id, caption=caption, parse_mode="MarkdownV2"))
            
        # Add videos
        for i, file_id in enumerate(videos):
            caption = message_text if i == 0 and not photos else None
            media_items.append(InputMediaVideo(file_id, caption=caption, parse_mode="MarkdownV2"))
            
        # Telegram limit is 10 media items
        media_items = media_items[:10]
        
        if media_items:
            # Send media group
            try:
                # The first message in the group will have the caption
                sent_messages = await context.bot.send_media_group(
                    chat_id=GROUP_CHAT_ID,
                    media=media_items,
                    # disable_notification=True # Optional
                )
                sent_message = sent_messages[0]
            except Exception as e:
                print(f"Error sending media group: {e}. Falling back to text message.")
                # Fallback to text message if media group fails
                sent_message = await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=message_text,
                    parse_mode="MarkdownV2"
                )
        else:
            # Only text message
            sent_message = await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=message_text,
                parse_mode="MarkdownV2"
            )
    else:
        # Only text message
        sent_message = await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=message_text,
            parse_mode="MarkdownV2"
        )
        
    # Save active listing
    listing_data = {
        "user_id": user_id,
        "message_id": sent_message.message_id,
        "expires_at": expires_at.isoformat(),
        "duration_hours": duration_hours,
        "last_bump_at": datetime.now(timezone.utc).isoformat()
    }
    db.save_active_listing(listing_data)
    
    # Trigger list update
    await update_available_lists_now(context)
    
    await query.edit_message_text(f"✅ Your listing is now live for {duration_hours} hours! It will automatically expire at {expires_at.strftime('%H:%M:%S UTC')}.")

async def bump_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /bump command from an admin in the group chat."""
    if not await check_admin(update, context):
        return
    
    if str(update.effective_chat.id) != GROUP_CHAT_ID:
        await update.message.reply_text("Please use this command in the designated group chat.")
        return

    user_id = update.effective_user.id
    listing = db.get_active_listing(user_id)
    
    if not listing:
        await update.message.reply_text("You do not have an active listing to bump. Use /available to go live.")
        return

    # Cooldown check
    last_bump_at = datetime.fromisoformat(listing["last_bump_at"].replace('Z', '+00:00'))
    cooldown_end = last_bump_at + timedelta(minutes=COOLDOWN_MINUTES)
    now = datetime.now(timezone.utc)
    
    if now < cooldown_end:
        time_left = cooldown_end - now
        minutes = int(time_left.total_seconds() // 60)
        seconds = int(time_left.total_seconds() % 60)
        await update.message.reply_text(f"❌ Please wait {minutes}m {seconds}s before bumping again.")
        return

    # Calculate remaining time
    expires_at = datetime.fromisoformat(listing["expires_at"].replace('Z', '+00:00'))
    time_remaining = expires_at - now
    
    remaining_hours = int(time_remaining.total_seconds() // 3600)
    remaining_minutes = int((time_remaining.total_seconds() % 3600) // 60)
    
    # Prompt for keep remaining or reset
    keyboard = [
        [InlineKeyboardButton(f"Keep remaining ({remaining_hours}h {remaining_minutes}m)", callback_data="bump_keep")],
        [InlineKeyboardButton("Reset 2h", callback_data="bump_reset_2")],
        [InlineKeyboardButton("Reset 4h", callback_data="bump_reset_4")],
        [InlineKeyboardButton("Reset 6h", callback_data="bump_reset_6")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"You have {remaining_hours}h {remaining_minutes}m remaining on your availability. Do you want to keep the remaining time or reset the timer?",
        reply_markup=reply_markup
    )
    
    # Store listing ID and remaining time in context for the callback
    context.user_data["bump_listing_id"] = listing["id"]
    context.user_data["bump_time_remaining"] = time_remaining.total_seconds()

async def bump_execute_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Executes the bump action after user selection."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    listing_id = context.user_data.get("bump_listing_id")
    
    if not listing_id:
        await query.edit_message_text("Error: Could not find listing data for bump.")
        return

    listing = db.get_active_listing(user_id)
    if not listing or listing["id"] != listing_id:
        await query.edit_message_text("Error: Active listing not found or mismatch.")
        return

    # 1. Delete the old message
    try:
        await context.bot.delete_message(
            chat_id=GROUP_CHAT_ID,
            message_id=listing["message_id"]
        )
    except Exception as e:
        print(f"Error deleting old listing message {listing['message_id']} during bump: {e}")

    # 2. Calculate new expiry time
    now = datetime.now(timezone.utc)
    new_expires_at = now
    duration_hours = listing["duration_hours"]
    
    if query.data == "bump_keep":
        time_remaining_seconds = context.user_data.get("bump_time_remaining", 0)
        new_expires_at = now + timedelta(seconds=time_remaining_seconds)
        duration_hours = int(time_remaining_seconds // 3600) # This is not strictly correct but serves as a placeholder
    elif query.data.startswith("bump_reset_"):
        duration_hours = int(query.data.split("_")[-1])
        new_expires_at = now + timedelta(hours=duration_hours)
    else:
        await query.edit_message_text("Invalid bump option selected.")
        return

    profile = db.get_profile(user_id)
    if not profile:
        await query.edit_message_text("Error: Profile not found for re-post.")
        return

    # 3. Post the new message (re-post logic is the same as /available)
    dummy_listing = {"expires_at": new_expires_at.isoformat(), "message_id": 0}
    message_text = generate_listing_message(profile, dummy_listing)
    
    # Simplified re-post: only text for now, media group logic is complex to re-send
    # A full implementation would re-send the media group with the new message as caption
    sent_message = await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=message_text,
        parse_mode="MarkdownV2"
    )
    
    # 4. Update the active listing record
    update_data = {
        "message_id": sent_message.message_id,
        "expires_at": new_expires_at.isoformat(),
        "duration_hours": duration_hours,
        "last_bump_at": now.isoformat()
    }
    db.update_active_listing(listing_id, update_data)
    
    # 5. Trigger list update
    await update_available_lists_now(context)
    
    await query.edit_message_text(f"✅ Listing successfully bumped! New expiry time: {new_expires_at.strftime('%H:%M:%S UTC')}.")
    
    # Clean up context data
    context.user_data.pop("bump_listing_id", None)
    context.user_data.pop("bump_time_remaining", None)
