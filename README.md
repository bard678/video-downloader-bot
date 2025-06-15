# Video Downloader Telegram Bot

A powerful Telegram bot that allows users to download videos from various platforms, including YouTube and Instagram. The bot supports multiple features like quality selection, format selection, and video clipping.

## Features

- 📥 Download videos from YouTube and Instagram
- 🎯 Choose video quality
- 📝 Select specific formats
- ✂️ Download video clips (specific portions)
- 📊 Get video information and available formats
- 🔄 Automatic video splitting for large files
- 🎨 Modern and user-friendly interface

## Prerequisites

- Python 3.7 or higher
- FFmpeg installed on your system
- Telegram Bot Token (get it from [@BotFather](https://t.me/BotFather))

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd video_downloader
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg:
- Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to PATH
- Linux: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`

4. Set up your Telegram Bot Token:
- Get a token from [@BotFather](https://t.me/BotFather)
- Replace the token in `telegram_bot.py` or set it as an environment variable

## Usage

1. Start the bot:
```bash
python telegram_bot.py
```

2. Available commands in Telegram:
- `/start` - Start the bot and see welcome message
- `/help` - Show help message
- `/info <url>` - Get video information
- `/download <url>` - Download in best quality
- `/quality <url>` - Choose video quality
- `/format <url>` - Choose specific format
- `/clip <url>` - Download a portion
- `/cancel` - Cancel current download

## Features in Detail

### Video Information
- Title, duration, and view count
- Available formats and qualities
- File size estimates

### Quality Selection
- Multiple resolution options
- FPS information
- File size estimates
- Best quality option

### Format Selection
- Video formats (MP4, WebM, etc.)
- Audio formats
- Resolution and bitrate options

### Video Clipping
- Select start and end times
- Support for HH:MM:SS format
- Automatic format conversion

## Notes

- For Instagram downloads, you may need to be logged in to your browser
- Large files (>50MB) will be automatically split or compressed
- The bot supports various video platforms through yt-dlp

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License - see the LICENSE file for details. 