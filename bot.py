import logging
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ConversationHandler
)
from telegram import Update
from handlers.admin import (
    start_command, delete_profile_confirm, delete_profile_execute,
    create_profile_start, profile_name, profile_services_callback,
    profile_inperson_type, profile_inperson_location, profile_facetime_platforms,
    profile_facetime_payment, profile_custom_payment, profile_custom_delivery,
    profile_other_service, profile_about, profile_contact_method,
    profile_contact_info, profile_social_links, profile_rates,
    profile_disclaimer, profile_allow_comments, profile_photos,
    profile_videos, profile_preview, profile_save, profile_cancel,
    admin_available_command, post_listing_callback, bump_command,
    bump_execute_callback
)
from handlers.member import member_available_command
from scheduler import start_scheduler, stop_scheduler
from utils.constants import (
    TELEGRAM_BOT_TOKEN, STATE_NAME, STATE_SERVICES, STATE_INPERSON,
    STATE_FACETIME, STATE_CUSTOM, STATE_OTHER, STATE_ABOUT,
    STATE_CONTACT_METHOD, STATE_CONTACT_INFO, STATE_SOCIAL_LINKS,
    STATE_RATES, STATE_DISCLAIMER, STATE_ALLOW_COMMENTS, STATE_PHOTOS,
    STATE_VIDEOS, STATE_PREVIEW
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def main() -> None:
    """Start the bot."""
    # Create the Application and pass your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # --- Conversation Handler for Profile Creation ---
    profile_wizard_handler = ConversationHandler(
        entry_points=[
            CommandHandler("createprofile", create_profile_start, filters=filters.ChatType.PRIVATE),
            CallbackQueryHandler(create_profile_start, pattern="^profile_edit$"),
        ],
        states={
            STATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_name)],
            STATE_SERVICES: [CallbackQueryHandler(profile_services_callback, pattern="^service_")],
            STATE_INPERSON: [
                CallbackQueryHandler(profile_inperson_type, pattern="^inperson_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, profile_inperson_location),
            ],
            STATE_FACETIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, profile_facetime_platforms),
                MessageHandler(filters.TEXT & ~filters.COMMAND, profile_facetime_payment),
            ],
            STATE_CUSTOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, profile_custom_payment),
                MessageHandler(filters.TEXT & ~filters.COMMAND, profile_custom_delivery),
            ],
            STATE_OTHER: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_other_service)],
            STATE_ABOUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_about)],
            STATE_CONTACT_METHOD: [CallbackQueryHandler(profile_contact_method, pattern="^contact_")],
            STATE_CONTACT_INFO: [MessageHandler(filters.TEXT, profile_contact_info)],
            STATE_SOCIAL_LINKS: [MessageHandler(filters.TEXT, profile_social_links)],
            STATE_RATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_rates)],
            STATE_DISCLAIMER: [MessageHandler(filters.TEXT, profile_disclaimer)],
            STATE_ALLOW_COMMENTS: [CallbackQueryHandler(profile_allow_comments, pattern="^comments_")],
            STATE_PHOTOS: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE | filters.Regex("^/done$"), profile_photos),
                CommandHandler("skip_media", profile_photos), # Allow skipping media
            ],
            STATE_VIDEOS: [
                MessageHandler(filters.VIDEO | filters.Regex("^/done$"), profile_videos),
            ],
            STATE_PREVIEW: [
                CallbackQueryHandler(profile_save, pattern="^profile_save$"),
                CallbackQueryHandler(create_profile_start, pattern="^profile_edit_restart$"),
                CallbackQueryHandler(profile_cancel, pattern="^profile_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", profile_cancel),
            MessageHandler(filters.ALL, profile_cancel), # Catch all unexpected messages to exit
        ],
        allow_reentry=True,
    )
    application.add_handler(profile_wizard_handler)

    # --- Admin Private Chat Handlers ---
    application.add_handler(CommandHandler("start", start_command, filters=filters.ChatType.PRIVATE))
    application.add_handler(CallbackQueryHandler(delete_profile_confirm, pattern="^profile_delete$"))
    application.add_handler(CallbackQueryHandler(delete_profile_execute, pattern="^profile_delete_confirm$"))
    
    # --- Admin Group Chat Handlers ---
    # /available command (for posting a new listing)
    application.add_handler(CommandHandler("available", admin_available_command, filters=filters.ChatType.GROUPS))
    application.add_handler(CallbackQueryHandler(post_listing_callback, pattern="^duration_"))
    
    # /bump command
    application.add_handler(CommandHandler("bump", bump_command, filters=filters.ChatType.GROUPS))
    application.add_handler(CallbackQueryHandler(bump_execute_callback, pattern="^bump_"))

    # --- Member Group Chat Handlers ---
    # /available command (for refreshing the chat list)
    application.add_handler(CommandHandler("available", member_available_command, filters=filters.ChatType.GROUPS))

    # --- Start Scheduler ---
    # The scheduler needs the bot instance to send messages
    start_scheduler(application.bot)

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot started. Press Ctrl-C to stop.")
    application.run_polling(stop_signals=None)
    
    # --- Stop Scheduler on Exit ---
    stop_scheduler()

if __name__ == "__main__":
    main()
