from typing import List
from app.gpt.base import GPT
from app.utils.openai_client import build_openai_client
from app.gpt.prompt import BASE_PROMPT, AI_SUM, SCREENSHOT
from app.gpt.utils import fix_markdown
from app.models.gpt_model import GPTSource
from app.models.transcriber_model import TranscriptSegment
from datetime import timedelta


class DeepSeekGPT(GPT):
    def __init__(self):
        from os import getenv
        self.api_key = getenv("DEEP_SEEK_API_KEY")
        self.base_url = getenv("DEEP_SEEK_API_BASE_URL")
        self.model=getenv('DEEP_SEEK_MODEL')
        print(self.model)
        self.client = build_openai_client(self.api_key, self.base_url, key_label="DeepSeek 的 API Key")
        self.screenshot = False

    def _format_time(self, seconds: float) -> str:
        # Total minutes, never wrapping at the hour: "65:30", not "05:30" (timedelta[2:] dropped the
        # hour, so in a 3 h video every hour reused 00:00-59:59). Matches the frame-grid labels and
        # the *Content-/*Screenshot-[mm:ss] parser, which already take minutes above 59.
        s = int(seconds)
        return f"{s // 60:02d}:{s % 60:02d}"

    def _build_segment_text(self, segments: List[TranscriptSegment]) -> str:
        return "\n".join(
            f"{self._format_time(seg.start)} - {seg.text.strip()}"
            for seg in segments
        )

    def ensure_segments_type(self, segments) -> List[TranscriptSegment]:
        return [
            TranscriptSegment(**seg) if isinstance(seg, dict) else seg
            for seg in segments
        ]

    def create_messages(self, segments: List[TranscriptSegment], title: str,tags:str):
        content = BASE_PROMPT.format(
            video_title=title,
            segment_text=self._build_segment_text(segments),
            tags=tags
        )
        if self.screenshot:
            print(":需要截图")
            content += SCREENSHOT
        print(content)
        return [{"role": "user", "content": content + AI_SUM}]

    def summarize(self, source: GPTSource) -> str:
        self.screenshot = source.screenshot
        source.segment = self.ensure_segments_type(source.segment)
        messages = self.create_messages(source.segment, source.title,source.tags)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()


