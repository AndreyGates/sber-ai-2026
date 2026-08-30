"""Sliding-window tokenization with character offset mapping."""
from __future__ import annotations

from dataclasses import dataclass

from transformers import PreTrainedTokenizerFast


@dataclass
class WindowChunk:
    """A window of token indices with the character span it covers."""
    token_ids: list[int]
    char_start: int
    char_end: int
    token_start: int
    token_end: int


def create_windows(
    text: str,
    tokenizer: PreTrainedTokenizerFast,
    max_length: int = 512,
    overlap: int = 64,
) -> list[WindowChunk]:
    """Split text into overlapping token windows with character offset tracking.

    Uses the tokenizer's offset_mapping to map tokens back to character positions.
    """
    encoding = tokenizer(
        text,
        return_offsets_mapping=True,
        add_special_tokens=True,
        truncation=False,
    )
    all_input_ids: list[int] = encoding["input_ids"]
    offset_mapping: list[tuple[int, int]] = encoding["offset_mapping"]

    if len(all_input_ids) <= max_length:
        return [WindowChunk(
            token_ids=all_input_ids,
            char_start=0,
            char_end=len(text),
            token_start=0,
            token_end=len(all_input_ids),
        )]

    stride = max_length - overlap
    if stride <= 0:
        raise ValueError(f"overlap ({overlap}) must be < max_length ({max_length})")

    chunks: list[WindowChunk] = []
    total = len(all_input_ids)
    start = 0

    while start < total:
        end = min(start + max_length, total)
        token_ids = all_input_ids[start:end]

        char_start = _find_char_start(offset_mapping, start, end)
        char_end = _find_char_end(offset_mapping, start, end, len(text))

        chunks.append(WindowChunk(
            token_ids=token_ids,
            char_start=char_start,
            char_end=char_end,
            token_start=start,
            token_end=end,
        ))

        if end >= total:
            break
        start += stride

    return chunks


def _find_char_start(offset_mapping: list[tuple[int, int]], tok_start: int, tok_end: int) -> int:
    for i in range(tok_start, tok_end):
        s, e = offset_mapping[i]
        if s != e:
            return s
    return 0


def _find_char_end(
    offset_mapping: list[tuple[int, int]],
    tok_start: int,
    tok_end: int,
    text_len: int,
) -> int:
    for i in range(tok_end - 1, tok_start - 1, -1):
        s, e = offset_mapping[i]
        if s != e:
            return e
    return text_len


def get_token_char_offsets(
    text: str,
    token_ids: list[int],
    tokenizer: PreTrainedTokenizerFast,
) -> list[tuple[int, int]]:
    """Get character offsets for a list of token IDs by re-tokenizing with offset mapping."""
    sub_text = text
    encoding = tokenizer(
        text,
        return_offsets_mapping=True,
        add_special_tokens=False,
        truncation=False,
    )
    return encoding["offset_mapping"][:len(token_ids)]
