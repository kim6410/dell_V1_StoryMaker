# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 Core 패키지 초기화
"""

from .prompt_builder import (
    build_prompt_markdown,
    build_preset_header,
    build_style_guidance
)
from .result_parser import (
    parse_result_blocks,
    extract_primary_code_block,
    join_result_blocks,
    RESULT_BLOCK_LABELS
)
from .text_cleaner import (
    strip_markdown,
    remove_trailing_hashtag_lines,
    normalize_podcast_block
)
from .keyword_extractor import (
    extract_keyword_candidates
)
from .persona_manager import (
    list_personas,
    load_persona_text,
    save_persona_text
)

__all__ = [
    "build_prompt_markdown",
    "build_preset_header",
    "build_style_guidance",
    "parse_result_blocks",
    "extract_primary_code_block",
    "join_result_blocks",
    "RESULT_BLOCK_LABELS",
    "strip_markdown",
    "remove_trailing_hashtag_lines",
    "normalize_podcast_block",
    "extract_keyword_candidates",
    "list_personas",
    "load_persona_text",
    "save_persona_text"
]
