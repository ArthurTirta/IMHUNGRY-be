"""
Fungsi-fungsi untuk interaksi dengan YouTube:
- _youtube_search : cari video berdasarkan query
- fetch_transcript : ambil transcript video (fallback ke kosong jika tidak tersedia)
"""
import os

import googleapiclient.discovery
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled


def _get_youtube_api_key() -> str:
    """Ambil YouTube Data API key dari env (YOUTUBE_API_KEY atau YOUTUBE_API)."""
    for name in ("YOUTUBE_API_KEY", "YOUTUBE_API"):
        value = os.getenv(name)
        if value:
            return value.strip()
    raise RuntimeError(
        "YouTube API key tidak ditemukan. Set YOUTUBE_API_KEY di file .env"
    )


def youtube_search(query: str, max_results: int = 5) -> list:
    """Cari video YouTube menggunakan API key, kembalikan list metadata video."""
    api_key = _get_youtube_api_key()

    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
    response = youtube.search().list(
        part="snippet",
        q=query,
        maxResults=max_results,
        type="video",
    ).execute()

    return [
        {
            "video_id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "description": item["snippet"]["description"],
        }
        for item in response.get("items", [])
    ]


def fetch_transcript(video_id: str) -> str:
    """
    Ambil transcript video YouTube.
    Prioritas bahasa: Indonesia (id) → English (en).
    Kembalikan string kosong jika transcript tidak tersedia.
    """
    try:
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id, languages=["id", "en"])
        lines = [f"[{entry.start:.0f}s] {entry.text}" for entry in transcript]
        print(
            f"📄 [Transcript] video={video_id} lang={transcript.language_code} "
            f"lines={len(lines)}",
            flush=True,
        )
        return "\n".join(lines)
    except (NoTranscriptFound, TranscriptsDisabled):
        print(f"⚠️ [Transcript] Tidak tersedia untuk video={video_id}", flush=True)
        return ""
    except Exception as e:
        print(f"⚠️ [Transcript] Error video={video_id}: {e}", flush=True)
        return ""
