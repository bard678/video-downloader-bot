# 1) Install yt-dlp (run once in your Colab):


# 2) Downloader function:
import os
from yt_dlp import YoutubeDL
import datetime
import sys

def format_duration(seconds: float) -> str:
    """Convert seconds to HH:MM:SS."""
    return str(datetime.timedelta(seconds=int(seconds)))

def get_video_info(url: str) -> dict:
    """Get video information including length and available formats."""
    ydl_opts = {'quiet': True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    
    # Print video information
    print("\n=== Video Information ===")
    print(f"Title: {info.get('title', 'Unknown')}")
    duration = info.get('duration')
    if duration is not None:
        print(f"Length: {format_duration(duration)}")
    else:
        print("Length: Unknown")
    print(f"Views: {info.get('view_count', 'Unknown')}")
    
    # Print available formats
    print("\n=== Available Formats ===")
    for f in info.get('formats', []):
        tag = f.get('format_id')
        ext = f.get('ext')
        res = f.get('height') or f.get('abr') or ''
        note = f.get('format_note', '')
        print(f"  [{tag:>5}]  {ext:<4}  @ {res:<4}   {note}")
    
    return info

def download_video(url: str, output_path: str = None, format_id: str = None, 
                  start_time: str = None, end_time: str = None) -> bool:
    """
    Download a video with optional clipping.
    
    Args:
        url: YouTube URL
        output_path: Where to save the video
        format_id: Specific format ID to download
        start_time: Start time for clipping (HH:MM:SS or seconds)
        end_time: End time for clipping (HH:MM:SS or seconds)
    
    Returns:
        bool: True if download was successful, False otherwise
    """
    if output_path is None:
        output_path = os.getcwd()
    else:
        os.makedirs(output_path, exist_ok=True)
    
    # Build options
    ydl_opts = {
        'format': format_id if format_id else 'best[ext=mp4]/best',
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'postprocessor_args': [
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-strict', 'experimental'
        ],
        # Add common options for better compatibility
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'no_warnings': True,
        'quiet': False,
        'verbose': True
    }
    
    # Add Instagram specific options
    if 'instagram.com' in url:
        print("\n⚠️ For Instagram downloads, please follow these steps:")
        print("1. Close all Chrome windows")
        print("2. Open Chrome and log into Instagram")
        print("3. Try downloading again")
        print("\nIf you still get errors, try using Firefox instead.")
        
        ydl_opts.update({
            'cookiesfrombrowser': ('firefox',),  # Try Firefox first
            'extractor_args': {
                'instagram': {
                    'login': True,
                    'username': None,
                    'password': None,
                }
            }
        })
        
        # Try to get cookies from Firefox first, then Chrome
        try:
            import subprocess
            import json
            import tempfile
            
            # Create a temporary file for cookies
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_cookie_file:
                cookie_file = temp_cookie_file.name
            
            # Try Firefox first
            try:
                subprocess.run([
                    'yt-dlp',
                    '--cookies-from-browser', 'firefox',
                    '--cookies', cookie_file,
                    '--dump-json',
                    url
                ], capture_output=True, check=True)
                print("\n✅ Successfully loaded cookies from Firefox")
            except:
                # If Firefox fails, try Chrome
                print("\n⚠️ Firefox cookies not found, trying Chrome...")
                subprocess.run([
                    'yt-dlp',
                    '--cookies-from-browser', 'chrome',
                    '--cookies', cookie_file,
                    '--dump-json',
                    url
                ], capture_output=True, check=True)
                print("\n✅ Successfully loaded cookies from Chrome")
            
            # Add cookies file to options
            ydl_opts['cookiefile'] = cookie_file
            
        except Exception as e:
            print(f"\n⚠️ Error getting cookies: {str(e)}")
            print("\nTrying without cookies...")
            print("Note: Some Instagram videos may require authentication.")
    
    # Add clipping if specified
    if start_time or end_time:
        if not ydl_opts.get('postprocessor_args'):
            ydl_opts['postprocessor_args'] = []
        if start_time:
            ydl_opts['postprocessor_args'].extend(['-ss', str(start_time)])
        if end_time:
            ydl_opts['postprocessor_args'].extend(['-to', str(end_time)])
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Check if file was downloaded successfully
        files = os.listdir(output_path)
        if not files:
            print("\n❌ No file was downloaded")
            return False
            
        latest_file = max([os.path.join(output_path, f) for f in files], key=os.path.getctime)
        if not os.path.exists(latest_file) or os.path.getsize(latest_file) == 0:
            print("\n❌ Downloaded file is empty or missing")
            return False
            
        print("\n✅ Download complete!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}", file=sys.stderr)
        if "Postprocessing" in str(e):
            print("\nTrying alternative download method...")
            try:
                # Try without post-processing
                ydl_opts.pop('postprocessors', None)
                ydl_opts.pop('postprocessor_args', None)
                ydl_opts['format'] = 'best[ext=mp4]/best'
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                # Check if file was downloaded successfully
                files = os.listdir(output_path)
                if not files:
                    print("\n❌ No file was downloaded")
                    return False
                    
                latest_file = max([os.path.join(output_path, f) for f in files], key=os.path.getctime)
                if not os.path.exists(latest_file) or os.path.getsize(latest_file) == 0:
                    print("\n❌ Downloaded file is empty or missing")
                    return False
                    
                print("\n✅ Download complete!")
                return True
            except Exception as e2:
                print(f"\n❌ Error: {str(e2)}", file=sys.stderr)
                return False
        return False
    finally:
        # Clean up temporary cookie file if it exists
        if 'instagram.com' in url and 'cookiefile' in ydl_opts:
            try:
                os.remove(ydl_opts['cookiefile'])
            except:
                pass

def main():
    print("\n=== YouTube Video Downloader & Clipper ===")
    
    # Get URL
    url = input("\nEnter YouTube URL: ").strip()
    if not url:
        print("No URL provided. Exiting.")
        return
    
    # Get video info and formats
    info = get_video_info(url)
    
    # Get format choice
    print("\n=== Download Options ===")
    format_id = input("Enter format ID (press Enter for best quality): ").strip()
    
    # Get clipping options
    print("\n=== Clipping Options ===")
    print("Leave blank for full video")
    start_time = input("Start time (HH:MM:SS or seconds): ").strip()
    end_time = input("End time (HH:MM:SS or seconds): ").strip()
    
    # Get output path
    output_path = input("\nOutput directory (press Enter for current directory): ").strip()
    if not output_path:
        output_path = None
    
    # Download
    print("\nStarting download...")
    success = download_video(url, output_path, format_id, start_time, end_time)
    if not success:
        print("Download failed. Please try again with different options.")

if __name__ == "__main__":
    main()
