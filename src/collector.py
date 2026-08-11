"""
Finds new uploads from the target channel, pulls the transcript, and samples
a handful of key frames (slide/code changes) for visual context.
"""
import base64
import os
import subprocess
import tempfile

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

CHANNEL_HANDLE = os.environ.get("CHANNEL_HANDLE", "aiDotEngineer")
MAX_FRAMES = int(os.environ.get("MAX_FRAMES", "6"))

# GitHub Actions runners share a small pool of well-known datacenter IPs that
# YouTube increasingly blocks for both transcript scraping and yt-dlp downloads.
# Set PROXY_URL (e.g. "http://user:pass@host:port") as a repo secret to route
# around this. Without it, both transcript and frame extraction may fail on
# every video while everything else in the pipeline keeps working.
PROXY_URL = os.environ.get("PROXY_URL")


def _requests_proxies():
    if not PROXY_URL:
        return None
    return {"http": PROXY_URL, "https": PROXY_URL}


def get_channel_uploads_playlist(youtube, handle):
    """Resolve a @handle to its 'uploads' playlist ID."""
    resp = youtube.channels().list(part="contentDetails", forHandle=handle).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError(f"No channel found for handle @{handle}")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def list_recent_videos(youtube, playlist_id, max_results=15):
    """Return recent videos (id, title, published_at, url) from the uploads playlist."""
    resp = youtube.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=playlist_id,
        maxResults=max_results,
    ).execute()
    videos = []
    for item in resp.get("items", []):
        vid = item["contentDetails"]["videoId"]
        videos.append({
            "id": vid,
            "title": item["snippet"]["title"],
            "published_at": item["contentDetails"].get("videoPublishedAt", ""),
            "url": f"https://www.youtube.com/watch?v={vid}",
        })
    return videos


def get_video_duration_seconds(youtube, video_id):
    resp = youtube.videos().list(part="contentDetails", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        return None
    import isodate  # lightweight, ships with google-api-python-client deps in most envs
    try:
        return int(isodate.parse_duration(items[0]["contentDetails"]["duration"]).total_seconds())
    except Exception:
        return None


def get_transcript(video_id):
    """Return the transcript as plain text with rough timestamps, or None if unavailable."""
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id, proxies=_requests_proxies())
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        print(f"  [transcript] {video_id}: no transcript available ({type(e).__name__})")
        return None
    except Exception as e:
        # Prints the real reason (commonly IP-block related) to the Actions log
        # instead of failing silently.
        print(f"  [transcript] {video_id}: FAILED - {type(e).__name__}: {e}")
        return None
    lines = []
    for seg in segments:
        t = int(seg["start"])
        mm, ss = divmod(t, 60)
        hh, mm = divmod(mm, 60)
        ts = f"{hh:02d}:{mm:02d}:{ss:02d}" if hh else f"{mm:02d}:{ss:02d}"
        lines.append(f"[{ts}] {seg['text']}")
    return "\n".join(lines)


def sample_key_frames(video_id, duration_seconds, max_frames=MAX_FRAMES):
    """
    Download a low-res copy of the video and extract frames at scene changes
    (catches slide/code switches better than evenly-spaced sampling).
    Returns a list of {timestamp_seconds, base64_jpeg}. Best-effort: returns
    [] on any failure rather than breaking the whole pipeline.
    """
    if not duration_seconds:
        return []
    with tempfile.TemporaryDirectory() as tmp:
        video_path = os.path.join(tmp, "video.mp4")
        yt_dlp_cmd = [
            "yt-dlp",
            "-f", "worst[height>=360][ext=mp4]/worst",
            "-o", video_path,
        ]
        if PROXY_URL:
            yt_dlp_cmd += ["--proxy", PROXY_URL]
        yt_dlp_cmd.append(f"https://www.youtube.com/watch?v={video_id}")
        try:
            subprocess.run(yt_dlp_cmd, check=True, capture_output=True, timeout=600)
        except subprocess.CalledProcessError as e:
            stderr_tail = e.stderr.decode(errors="replace")[-1500:] if e.stderr else ""
            print(f"  [frames] {video_id}: yt-dlp FAILED - {stderr_tail}")
            return []
        except Exception as e:
            print(f"  [frames] {video_id}: yt-dlp FAILED - {type(e).__name__}: {e}")
            return []

        frames_dir = os.path.join(tmp, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        try:
            # Scene-change detection via ffmpeg; threshold 0.3 tends to catch slide/code
            # switches without firing on every camera cut. Capped to max_frames.
            subprocess.run(
                [
                    "ffmpeg", "-i", video_path,
                    "-vf", f"select='gt(scene,0.3)',showinfo",
                    "-vsync", "vfr",
                    "-frames:v", str(max_frames),
                    os.path.join(frames_dir, "frame_%03d.jpg"),
                ],
                check=True, capture_output=True, timeout=600,
            )
        except Exception as e:
            print(f"  [frames] {video_id}: ffmpeg FAILED - {type(e).__name__}: {e}")
            return []

        frames = []
        for fname in sorted(os.listdir(frames_dir)):
            fpath = os.path.join(frames_dir, fname)
            with open(fpath, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            frames.append({"filename": fname, "base64_jpeg": b64})
        return frames


def build_youtube_client(api_key):
    return build("youtube", "v3", developerKey=api_key)
