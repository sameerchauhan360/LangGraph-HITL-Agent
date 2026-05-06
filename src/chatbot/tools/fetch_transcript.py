from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)
from langchain_core.tools import tool


@tool
def fetch_transcript(video_id: str, languages=None) -> str:
    """Return the plain‑text transcript for a YouTube video.
    Uses the YouTube Transcript API which works for auto‑generated captions as well.
    """
    if languages is None:
        languages = ["en"]
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=languages)
        text = " ".join(snippet.text for snippet in fetched)
        return text
    except TranscriptsDisabled:
        raise RuntimeError("Transcripts are disabled for this video")
    except NoTranscriptFound:
        raise RuntimeError("No transcript found for the requested languages")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch transcript: {e}")
