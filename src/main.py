import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from collector import (
    build_youtube_client,
    get_channel_uploads_playlist,
    get_transcript,
    get_video_duration_seconds,
    list_recent_videos,
    sample_key_frames,
)
from analyze import analyze_video

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "state.json")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "results.json")


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def main():
    youtube_key = os.environ["YOUTUBE_API_KEY"]
    grok_key = os.environ["GROK_API_KEY"]

    state = load_json(STATE_PATH, {"processed_ids": []})
    results = load_json(RESULTS_PATH, {"videos": [], "last_run": None})

    youtube = build_youtube_client(youtube_key)
    playlist_id = get_channel_uploads_playlist(youtube, os.environ.get("CHANNEL_HANDLE", "aiDotEngineer"))
    recent = list_recent_videos(youtube, playlist_id)

    new_videos = [v for v in recent if v["id"] not in state["processed_ids"]]
    print(f"Found {len(recent)} recent uploads, {len(new_videos)} new.")

    for video in new_videos:
        print(f"Processing: {video['title']}")
        try:
            duration = get_video_duration_seconds(youtube, video["id"])
            transcript = get_transcript(video["id"])
            frames = sample_key_frames(video["id"], duration)
            briefing = analyze_video(grok_key, video["title"], transcript, frames, video["url"])

            results["videos"].insert(0, {
                **video,
                "duration_seconds": duration,
                "had_transcript": transcript is not None,
                "frame_count": len(frames),
                "briefing": briefing,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            })
            state["processed_ids"].append(video["id"])
        except Exception as e:
            print(f"  Failed on {video['id']}: {e}")
            # Don't mark as processed - retry next run
            continue

    results["last_run"] = datetime.now(timezone.utc).isoformat()
    save_json(STATE_PATH, state)
    save_json(RESULTS_PATH, results)
    print("Done.")


if __name__ == "__main__":
    main()
