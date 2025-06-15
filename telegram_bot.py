import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from video_downloader import download_video, get_video_info

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation handler
SELECTING_QUALITY, SELECTING_FORMAT, SELECTING_CLIP = range(3)

# Store active downloads
active_downloads = {}

# Get token from environment variable
TELEGRAM_TOKEN = "7870727682:AAFXz1mvzcXZH7lJEuvw2wDyX3ZzNAdOWxA"
if not TELEGRAM_TOKEN:
    raise ValueError("Please set the TELEGRAM_TOKEN environment variable")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        '👋 Welcome to the Video Downloader Bot!\n\n'
        'I can help you download videos from YouTube.\n\n'
        'Available commands:\n'
        '/info <url> - Get video information\n'
        '/download <url> - Download in best quality\n'
        '/quality <url> - Choose video quality\n'
        '/format <url> - Choose specific format\n'
        '/clip <url> - Download a portion\n'
        '/cancel - Cancel current download\n'
        '/help - Show this help message\n\n'
        'Just send a YouTube URL to download it directly!'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        '📝 Available commands:\n\n'
        '/info <url> - Get video information and available formats\n'
        '/download <url> - Download video in best quality\n'
        '/quality <url> - Show and select video quality options\n'
        '/format <url> - Download in specific format\n'
        '/clip <url> - Download a specific portion of the video\n'
        '/cancel - Cancel current download\n'
        '/help - Show this help message\n\n'
        'Just send a YouTube URL to download it directly!'
    )

async def get_video_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get video information when /info command is issued."""
    if not context.args:
        await update.message.reply_text('Please provide a YouTube URL after /info')
        return

    url = context.args[0]
    try:
        processing_msg = await update.message.reply_text('🔍 Getting video information...')
        info = get_video_info(url)
        
        response = (
            f"📹 *Video Information*\n\n"
            f"*Title:* {info.get('title', 'Unknown')}\n"
            f"*Length:* {info.get('duration', 'Unknown')} seconds\n"
            f"*Views:* {info.get('view_count', 'Unknown')}\n\n"
            f"*Available Formats:*\n"
        )
        
        for f in info.get('formats', [])[:5]:
            tag = f.get('format_id')
            ext = f.get('ext')
            res = f.get('height') or f.get('abr') or ''
            note = f.get('format_note', '')
            response += f"• {ext} @ {res} {note}\n"
        
        await processing_msg.edit_text(response, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')

async def quality_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show quality options when /quality command is issued."""
    if not context.args:
        await update.message.reply_text('Please provide a YouTube URL after /quality')
        return

    url = context.args[0]
    try:
        processing_msg = await update.message.reply_text('🔍 Getting quality options...')
        info = get_video_info(url)
        
        # Create quality selection keyboard with better organization
        keyboard = []
        current_row = []
        
        # Sort formats by resolution (height)
        formats = sorted(
            [f for f in info.get('formats', []) if f.get('height')],
            key=lambda x: x.get('height', 0),
            reverse=True
        )
        
        for f in formats:
            quality = f"{f.get('height')}p"
            format_id = f.get('format_id')
            # Add FPS if available
            fps = f.get('fps')
            if fps:
                quality += f" {fps}fps"
            
            # Calculate file size
            filesize = f.get('filesize')
            if not filesize:
                # Try to get filesize from format_id
                format_info = next((fmt for fmt in info.get('formats', []) if fmt.get('format_id') == format_id), None)
                if format_info:
                    filesize = format_info.get('filesize')
            
            # Format file size
            if filesize:
                if filesize < 1024 * 1024:  # Less than 1MB
                    size_str = f"{filesize/1024:.1f}KB"
                else:
                    size_str = f"{filesize/(1024*1024):.1f}MB"
                quality += f" ({size_str})"
            
            button = InlineKeyboardButton(quality, callback_data=f"quality_{format_id}")
            current_row.append(button)
            
            # Create new row after every 2 buttons
            if len(current_row) == 2:
                keyboard.append(current_row)
                current_row = []
        
        # Add any remaining buttons
        if current_row:
            keyboard.append(current_row)
        
        # Add a "Best Quality" button at the top
        keyboard.insert(0, [InlineKeyboardButton("🎯 Best Quality", callback_data="quality_best")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await processing_msg.edit_text(
            f"📹 *{info.get('title', 'Video')}*\n\n"
            "Select video quality:\n"
            "Note: Files larger than 50MB will be compressed or split",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        context.user_data['url'] = url
        
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')

async def format_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show format options when /format command is issued."""
    if not context.args:
        await update.message.reply_text('Please provide a YouTube URL after /format')
        return

    url = context.args[0]
    try:
        processing_msg = await update.message.reply_text('🔍 Getting format options...')
        info = get_video_info(url)
        
        # Create format selection keyboard with better organization
        keyboard = []
        current_row = []
        
        # Group formats by type (video, audio, etc.)
        video_formats = []
        audio_formats = []
        
        for f in info.get('formats', []):
            format_id = f.get('format_id')
            ext = f.get('ext')
            res = f.get('height') or f.get('abr') or ''
            note = f.get('format_note', '')
            
            # Add FPS if available
            fps = f.get('fps')
            fps_text = f" {fps}fps" if fps else ""
            
            if f.get('height'):  # Video format
                text = f"🎥 {ext} {res}p{fps_text}"
                video_formats.append((text, format_id, f.get('height', 0)))
            elif f.get('abr'):  # Audio format
                text = f"🎵 {ext} {res}kbps"
                audio_formats.append((text, format_id, float(f.get('abr', 0))))
        
        # Add video formats
        if video_formats:
            keyboard.append([InlineKeyboardButton("📹 Video Formats", callback_data="format_header")])
            for text, format_id, _ in sorted(video_formats, key=lambda x: x[2], reverse=True):
                button = InlineKeyboardButton(text, callback_data=f"format_{format_id}")
                current_row.append(button)
                if len(current_row) == 2:
                    keyboard.append(current_row)
                    current_row = []
            if current_row:
                keyboard.append(current_row)
                current_row = []
        
        # Add audio formats
        if audio_formats:
            keyboard.append([InlineKeyboardButton("🎵 Audio Formats", callback_data="format_header")])
            for text, format_id, _ in sorted(audio_formats, key=lambda x: x[2], reverse=True):
                button = InlineKeyboardButton(text, callback_data=f"format_{format_id}")
                current_row.append(button)
                if len(current_row) == 2:
                    keyboard.append(current_row)
                    current_row = []
            if current_row:
                keyboard.append(current_row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await processing_msg.edit_text(
            f"📹 *{info.get('title', 'Video')}*\n\n"
            "Select format:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        context.user_data['url'] = url
        
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')

async def clip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start clip selection process."""
    if not context.args:
        await update.message.reply_text('Please provide a YouTube URL after /clip')
        return

    url = context.args[0]
    context.user_data['url'] = url
    await update.message.reply_text(
        'Please enter the clip duration in this format:\n'
        'start_time-end_time\n\n'
        'Example: 1:30-2:45\n'
        'Or: 90-165 (in seconds)'
    )
    return SELECTING_CLIP

async def handle_clip_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle clip duration input."""
    try:
        start_time, end_time = update.message.text.split('-')
        url = context.user_data.get('url')
        if not url:
            await update.message.reply_text('❌ No URL found. Please use /clip <url> again.')
            return ConversationHandler.END

        await download_video_command(update, context, start_time=start_time.strip(), end_time=end_time.strip())
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text('❌ Invalid format. Please use start-end format (e.g., 1:30-2:45)')
        return SELECTING_CLIP

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel current download."""
    user_id = update.effective_user.id
    if user_id in active_downloads:
        # Implement download cancellation logic here
        del active_downloads[user_id]
        await update.message.reply_text('✅ Download cancelled')
    else:
        await update.message.reply_text('No active download to cancel')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "format_header":
            # Ignore header button clicks
            return
            
        if query.data.startswith('quality_'):
            format_id = query.data.split('_')[1]
            url = context.user_data.get('url')
            if url:
                # Send new message for download status
                status_msg = await query.message.reply_text('⏳ Starting download...')
                context.user_data['status_msg'] = status_msg
                await download_video_command(update, context, format_id=format_id)
        
        elif query.data.startswith('format_'):
            format_id = query.data.split('_')[1]
            url = context.user_data.get('url')
            if url:
                # Send new message for download status
                status_msg = await query.message.reply_text('⏳ Starting download...')
                context.user_data['status_msg'] = status_msg
                await download_video_command(update, context, format_id=format_id)
    
    except Exception as e:
        await query.message.reply_text(f'❌ Error: {str(e)}')

async def send_video_part(update: Update, part_file: str, part_num: int, total_parts: int, max_retries: int = 3) -> bool:
    """Send a video part with retries."""
    for attempt in range(max_retries):
        try:
            if update.callback_query:
                await update.callback_query.message.reply_video(
                    video=open(part_file, 'rb'),
                    supports_streaming=True,
                    caption=f'Part {part_num}/{total_parts}'
                )
            else:
                await update.message.reply_video(
                    video=open(part_file, 'rb'),
                    supports_streaming=True,
                    caption=f'Part {part_num}/{total_parts}'
                )
            return True
        except Exception as e:
            print(f"Error sending part {part_num} (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)  # Wait before retry
            continue
    return False

async def cleanup_file(file_path: str, max_retries: int = 5) -> bool:
    """Clean up a file with retries."""
    for attempt in range(max_retries):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception as e:
            print(f"Error cleaning up {file_path} (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Wait before retry
            continue
    return False

async def split_and_send_video(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                             video_file: str, max_size: int, processing_msg) -> bool:
    """Split large video into parts and send them."""
    try:
        import subprocess
        # Get video duration
        duration = float(subprocess.check_output([
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', video_file
        ]).decode().strip())
        
        # Calculate number of parts needed
        file_size = os.path.getsize(video_file)
        num_parts = (file_size // max_size) + 1
        part_duration = duration / num_parts
        
        # Create a list to track successful parts
        successful_parts = []
        failed_parts = []
        
        # Split video into parts
        for i in range(num_parts):
            part_file = os.path.join(os.path.dirname(video_file), f'part{i+1}_{os.path.basename(video_file)}')
            start_time = i * part_duration
            
            # Try to split the part
            try:
                # Update progress message
                await processing_msg.edit_text(f'📦 Splitting video... Part {i+1}/{num_parts}')
                
                # Split with error checking
                result = subprocess.run([
                    'ffmpeg', '-i', video_file,
                    '-ss', str(start_time),
                    '-t', str(part_duration),
                    '-c', 'copy',  # Use copy to avoid re-encoding
                    '-y',  # Overwrite output file if it exists
                    part_file
                ], capture_output=True, text=True, check=True)
                
                # Check if part file exists and has content
                if os.path.exists(part_file) and os.path.getsize(part_file) > 0:
                    successful_parts.append((i+1, part_file))
                else:
                    failed_parts.append(i+1)
                    print(f"Part {i+1} was created but is empty")
                    
            except subprocess.CalledProcessError as e:
                print(f"Error splitting part {i+1}: {e.stderr}")
                failed_parts.append(i+1)
                continue
        
        # If we have failed parts, try to recover them
        if failed_parts:
            await processing_msg.edit_text('⚠️ Some parts failed, attempting to recover...')
            
            for part_num in failed_parts[:]:  # Create a copy of the list to modify during iteration
                part_file = os.path.join(os.path.dirname(video_file), f'part{part_num}_{os.path.basename(video_file)}')
                start_time = (part_num - 1) * part_duration
                
                # Try alternative splitting method
                try:
                    await processing_msg.edit_text(f'🔄 Retrying part {part_num}/{num_parts}...')
                    
                    # Try with different parameters
                    result = subprocess.run([
                        'ffmpeg', '-i', video_file,
                        '-ss', str(start_time),
                        '-t', str(part_duration),
                        '-c:v', 'libx264',  # Use h264 codec
                        '-preset', 'ultrafast',  # Fastest encoding
                        '-c:a', 'aac',  # Use AAC audio
                        '-y',  # Overwrite output file
                        part_file
                    ], capture_output=True, text=True, check=True)
                    
                    if os.path.exists(part_file) and os.path.getsize(part_file) > 0:
                        successful_parts.append((part_num, part_file))
                        failed_parts.remove(part_num)
                        
                except Exception as e:
                    print(f"Failed to recover part {part_num}: {str(e)}")
                    continue
        
        # Send successful parts
        for part_num, part_file in sorted(successful_parts):
            try:
                # Try to send the part with retries
                if await send_video_part(update, part_file, part_num, num_parts):
                    print(f"Successfully sent part {part_num}")
                else:
                    print(f"Failed to send part {part_num} after all retries")
                    failed_parts.append(part_num)
            finally:
                # Clean up part file with retries
                await cleanup_file(part_file)
        
        # Report any remaining failed parts
        if failed_parts:
            failed_parts_str = ', '.join(map(str, sorted(failed_parts)))
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    f'⚠️ Some parts failed to process: {failed_parts_str}\n'
                    'Please try downloading in a lower quality.'
                )
            else:
                await update.message.reply_text(
                    f'⚠️ Some parts failed to process: {failed_parts_str}\n'
                    'Please try downloading in a lower quality.'
                )
            # Clean up download folder after sending all parts (even if some failed)
            try:
                download_dir = os.path.dirname(video_file)
                if os.path.exists(download_dir):
                    shutil.rmtree(download_dir)
                    print(f"Cleaned up download folder: {download_dir}")
            except Exception as e:
                print(f"Error cleaning up download folder {download_dir}: {str(e)}")
            return False
        
        # Clean up download folder after sending all parts
        try:
            download_dir = os.path.dirname(video_file)
            if os.path.exists(download_dir):
                shutil.rmtree(download_dir)
                print(f"Cleaned up download folder: {download_dir}")
        except Exception as e:
            print(f"Error cleaning up download folder {download_dir}: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"Error in split_and_send_video: {str(e)}")
        if update.callback_query:
            await update.callback_query.message.reply_text('❌ Error processing video. Please try a lower quality.')
        else:
            await update.message.reply_text('❌ Error processing video. Please try a lower quality.')
        # Clean up download folder on error
        try:
            download_dir = os.path.dirname(video_file)
            if os.path.exists(download_dir):
                shutil.rmtree(download_dir)
                print(f"Cleaned up download folder: {download_dir}")
        except Exception as e:
            print(f"Error cleaning up download folder {download_dir}: {str(e)}")
        return False

async def download_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               format_id: str = None, start_time: str = None, end_time: str = None) -> None:
    """Download video with specified options."""
    url = context.args[0] if context.args else context.user_data.get('url')
    if not url:
        if update.callback_query:
            await update.callback_query.message.reply_text('Please provide a YouTube URL')
        else:
            await update.message.reply_text('Please provide a YouTube URL')
        return

    processing_msg = context.user_data.get('status_msg')
    downloaded_file = None
    download_dir = os.path.join(os.getcwd(), 'downloads')
    
    try:
        if not processing_msg:
            if update.callback_query:
                processing_msg = await update.callback_query.message.reply_text('⏳ Starting download...')
            else:
                processing_msg = await update.message.reply_text('⏳ Starting download...')
        
        os.makedirs(download_dir, exist_ok=True)
        
        success = download_video(url, download_dir, format_id, start_time, end_time)
        if not success:
            if update.callback_query:
                await update.callback_query.message.reply_text('❌ Download failed. Please try again with different options.')
            else:
                await update.message.reply_text('❌ Download failed. Please try again with different options.')
            # Clean up download folder on failure
            try:
                if os.path.exists(download_dir):
                    shutil.rmtree(download_dir)
                    print(f"Cleaned up download folder: {download_dir}")
            except Exception as e:
                print(f"Error cleaning up download folder {download_dir}: {str(e)}")
            return
        
        files = os.listdir(download_dir)
        if files:
            latest_file = max([os.path.join(download_dir, f) for f in files], key=os.path.getctime)
            downloaded_file = latest_file
            
            # Check if file exists and has content
            if not os.path.exists(latest_file) or os.path.getsize(latest_file) == 0:
                if update.callback_query:
                    await update.callback_query.message.reply_text('❌ Downloaded file is empty or missing. Please try again.')
                else:
                    await update.message.reply_text('❌ Downloaded file is empty or missing. Please try again.')
                # Clean up download folder
                try:
                    if os.path.exists(download_dir):
                        shutil.rmtree(download_dir)
                        print(f"Cleaned up download folder: {download_dir}")
                except Exception as e:
                    print(f"Error cleaning up download folder {download_dir}: {str(e)}")
                return
            
            # Check file size
            file_size = os.path.getsize(latest_file)
            max_size = 40 * 1024 * 1024  # 40MB
            
            if file_size > max_size:
                # File is too large, split it into parts
                await processing_msg.edit_text('📦 File is too large, splitting into parts...')
                success = await split_and_send_video(update, context, latest_file, max_size, processing_msg)
                if not success:
                    return
                # split_and_send_video will clean up the download folder
                downloaded_file = None  # Prevent double cleanup below
            else:
                # Send the video if it's small enough
                try:
                    if update.callback_query:
                        await update.callback_query.message.reply_video(
                            video=open(latest_file, 'rb'),
                            supports_streaming=True
                        )
                    else:
                        await update.message.reply_video(
                            video=open(latest_file, 'rb'),
                            supports_streaming=True
                        )
                except Exception as e:
                    print(f"Error sending video: {str(e)}")
                    if update.callback_query:
                        await update.callback_query.message.reply_text('❌ Error sending video. Please try again.')
                    else:
                        await update.message.reply_text('❌ Error sending video. Please try again.')
                # Clean up download folder after sending the video
                try:
                    if os.path.exists(download_dir):
                        shutil.rmtree(download_dir)
                        print(f"Cleaned up download folder: {download_dir}")
                except Exception as e:
                    print(f"Error cleaning up download folder {download_dir}: {str(e)}")
        else:
            if update.callback_query:
                await update.callback_query.message.reply_text('❌ No file was downloaded')
            else:
                await update.message.reply_text('❌ No file was downloaded')
            # Clean up download folder
            try:
                if os.path.exists(download_dir):
                    shutil.rmtree(download_dir)
                    print(f"Cleaned up download folder: {download_dir}")
            except Exception as e:
                print(f"Error cleaning up download folder {download_dir}: {str(e)}")
            
    except Exception as e:
        if update.callback_query:
            await update.callback_query.message.reply_text(f'❌ Error: {str(e)}')
        else:
            await update.message.reply_text(f'❌ Error: {str(e)}')
        # Clean up download folder on error
        try:
            if os.path.exists(download_dir):
                shutil.rmtree(download_dir)
                print(f"Cleaned up download folder: {download_dir}")
        except Exception as e:
            print(f"Error cleaning up download folder {download_dir}: {str(e)}")
    finally:
        if downloaded_file and os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
                print(f"Cleaned up: {downloaded_file}")
            except Exception as e:
                print(f"Error cleaning up file {downloaded_file}: {str(e)}")
        
        if processing_msg:
            try:
                await processing_msg.delete()
            except Exception as e:
                print(f"Error deleting processing message: {str(e)}")
        
        # Clean up status message from user_data
        context.user_data.pop('status_msg', None)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle direct URL messages."""
    url = update.message.text
    if 'youtube.com' in url or 'youtu.be' in url:
        try:
            # Get video info first
            info = get_video_info(url)
            
            # Find highest resolution format
            formats = [f for f in info.get('formats', []) if f.get('height')]
            if formats:
                highest_format = max(formats, key=lambda x: x.get('height', 0))
                format_id = highest_format.get('format_id')
                resolution = highest_format.get('height')
                fps = highest_format.get('fps')
                
                # Send info message
                info_text = (
                    f"📹 *{info.get('title', 'Video')}*\n\n"
                    f"Downloading in highest quality:\n"
                    f"🎥 {resolution}p{f' {fps}fps' if fps else ''}\n\n"
                    f"Use /quality or /format for other options"
                )
                await update.message.reply_text(info_text, parse_mode='Markdown')
                
                # Start download with highest quality
                context.args = [url]
                await download_video_command(update, context, format_id=format_id)
            else:
                # If no video formats found, download best quality
                await update.message.reply_text("🎥 Downloading in best available quality...")
                context.args = [url]
                await download_video_command(update, context)
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add conversation handler for clip command
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('clip', clip_command)],
        states={
            SELECTING_CLIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_clip_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", get_video_info_command))
    application.add_handler(CommandHandler("download", download_video_command))
    application.add_handler(CommandHandler("quality", quality_command))
    application.add_handler(CommandHandler("format", format_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 