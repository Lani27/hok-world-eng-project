"""
Gemini API client for AI-powered translation with glossary injection.

Provides chunking, rate limiting, glossary building via Aho-Corasick,
and translation validation. Extracted and generalized from the WOJD pipeline.
"""

import json
import os
import re
import asyncio
import time
import logging
from collections import defaultdict, Counter

try:
    import httpx
except ImportError:
    httpx = None

try:
    import ahocorasick
except ImportError:
    ahocorasick = None

from .utils import count_chinese_chars, get_json_size


# --- Translation Validation ---
_TAG_RE = re.compile(r'<[^>]+>|</>')
_PLACEHOLDER_RE = re.compile(r'\{[^}]*\}|%[dsfx%]|%\.\d+[dsfx]')
_CHINESE_CHAR_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')


def validate_translation(chinese_key, english_value):
    """
    Validate a Gemini translation for common errors.

    Returns:
        Tuple of (is_valid, reason).
        Reasons: "ok", "empty", "echo", "missing_tag", "missing_placeholder",
                 "still_chinese", "no_latin", "extreme_expansion"
    """
    if not isinstance(english_value, str) or not english_value.strip():
        return False, "empty"

    if english_value.strip() == chinese_key.strip():
        return False, "echo"

    # Tag preservation
    source_tags = _TAG_RE.findall(chinese_key)
    if source_tags:
        for tag in source_tags:
            if tag not in english_value:
                return False, "missing_tag"

    # Placeholder preservation
    source_placeholders = _PLACEHOLDER_RE.findall(chinese_key)
    if source_placeholders:
        for ph in source_placeholders:
            if ph not in english_value:
                return False, "missing_placeholder"

    # Still Chinese check - translation should be predominantly English
    cn_chars = len(_CHINESE_CHAR_RE.findall(english_value))
    latin_chars = len(re.findall(r'[a-zA-Z]', english_value))
    if cn_chars > 0 and cn_chars > latin_chars:
        return False, "still_chinese"

    # Must contain at least some Latin characters (unless source is pure numbers/symbols)
    source_cn_chars = len(_CHINESE_CHAR_RE.findall(chinese_key))
    if source_cn_chars > 2 and latin_chars == 0:
        return False, "no_latin"

    # Extreme text expansion check (>5x is almost certainly wrong)
    if len(chinese_key) > 3:
        ratio = len(english_value) / len(chinese_key)
        if ratio > 5.0:
            return False, "extreme_expansion"

    return True, "ok"


class GeminiTranslator:
    """
    Gemini API client for batch Chinese-to-English translation.

    Features:
    - Configurable API endpoint, model, and rate limiting
    - Automatic chunking to stay within API size limits
    - Per-chunk glossary injection via Aho-Corasick for consistency
    - Translation validation with tag/placeholder preservation checks
    - Retry logic with exponential backoff
    """

    def __init__(self, config):
        """
        Initialize from a config dict (typically loaded from config.json's "gemini" section).

        Expected keys: api_key, model, api_url, requests_per_minute,
                       max_chunk_size_kb, system_prompt,
                       glossary_min_chinese_chars, glossary_max_chinese_chars,
                       glossary_max_entries_per_chunk
        """
        if not httpx:
            raise ImportError("httpx is required. Install with: pip install httpx")

        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "gemini-3.1-flash-lite-preview")
        self.api_url_template = config.get(
            "api_url",
            "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        )
        self.rpm = config.get("requests_per_minute", 10)
        self.seconds_per_request = 60 / self.rpm
        self.max_chunk_bytes = config.get("max_chunk_size_kb", 19) * 1024
        self.system_prompt = config.get("system_prompt", "")
        self.glossary_min_chars = config.get("glossary_min_chinese_chars", 2)
        self.glossary_max_chars = config.get("glossary_max_chinese_chars", 8)
        self.glossary_max_per_chunk = config.get("glossary_max_entries_per_chunk", 200)

    @property
    def api_url(self):
        """Build the full API URL with model and key."""
        url = self.api_url_template.format(model=self.model)
        if self.api_key:
            url += f"?key={self.api_key}"
        return url

    # --- Chunking ---

    def chunk_strings(self, untranslated_data):
        """
        Split namespaced untranslated data into chunks within API size limits.

        Args:
            untranslated_data: dict of {namespace: {chinese: ""}}

        Returns:
            List of chunk dicts, each fitting within max_chunk_bytes.
        """
        chunks = []
        current_chunk = {}
        current_size = 2  # {}

        for namespace, items in untranslated_data.items():
            if not isinstance(items, dict):
                continue
            for key, value in items.items():
                try:
                    item_str = json.dumps({key: value}, ensure_ascii=False, separators=(',', ':'))
                    item_size = len(item_str.encode('utf-8')) - 2
                    if item_size < 0:
                        item_size = 0
                except Exception:
                    continue

                ns_overhead = 0
                if namespace not in current_chunk:
                    ns_overhead = len(json.dumps(namespace, ensure_ascii=False).encode('utf-8')) + 4
                    if current_chunk:
                        ns_overhead += 1
                elif current_chunk[namespace]:
                    ns_overhead = 1

                if (current_size + item_size + ns_overhead) > self.max_chunk_bytes:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = {namespace: {key: value}}
                    current_size = get_json_size(current_chunk)
                else:
                    current_chunk.setdefault(namespace, {})[key] = value
                    current_size += item_size + ns_overhead

        if current_chunk:
            chunks.append(current_chunk)

        logging.info(f"Split into {len(chunks)} chunks")
        return chunks

    # --- Glossary ---

    def build_glossary_automaton(self, glossary):
        """
        Build an Aho-Corasick automaton from glossary keys for fast substring matching.

        Args:
            glossary: dict of {chinese_term: english_translation}

        Returns:
            Tuple of (automaton, glossary_dict) or (None, None) if unavailable.
        """
        if not ahocorasick or not glossary:
            return None, None

        A = ahocorasick.Automaton()
        for term in glossary:
            A.add_word(term, term)
        A.make_automaton()
        logging.info(f"Built glossary automaton with {len(glossary)} terms")
        return A, glossary

    def _get_chunk_glossary_text(self, chunk_data, automaton, glossary):
        """Build a glossary prompt section for terms found in this chunk."""
        if not automaton or not glossary:
            return ""

        all_keys = []
        for ns_data in chunk_data.values():
            if isinstance(ns_data, dict):
                all_keys.extend(ns_data.keys())
        if not all_keys:
            return ""

        combined = "\n".join(all_keys)
        term_counts = Counter()
        for _, matched in automaton.iter(combined):
            term_counts[matched] += 1

        if not term_counts:
            return ""

        # Longer terms first, then by frequency
        selected = sorted(term_counts.keys(),
                          key=lambda t: (len(t), term_counts[t]),
                          reverse=True)[:self.glossary_max_per_chunk]

        lines = [f"{term} = {glossary[term]}" for term in selected]
        return (
            "GLOSSARY - Use these established translations for consistency:\n"
            + "\n".join(lines)
            + "\n\nNow translate the following JSON:\n"
        )

    # --- API Translation ---

    async def translate_chunk(self, client, chunk_data, automaton=None, glossary=None):
        """
        Send a single chunk to the Gemini API for translation.

        Returns:
            dict of translated data, or None on failure.
        """
        chunk_json = json.dumps(chunk_data, ensure_ascii=False, indent=2)

        # Build prompt with context and glossary
        ns_names = [ns for ns in chunk_data if isinstance(chunk_data[ns], dict)]
        context = f"Context: These strings come from game systems: {', '.join(ns_names)}\n\n" if ns_names else ""
        glossary_text = self._get_chunk_glossary_text(chunk_data, automaton, glossary) if automaton else ""
        user_message = context + glossary_text + chunk_json

        payload = {
            "contents": [{"parts": [{"text": user_message}]}],
            "systemInstruction": {"parts": [{"text": self.system_prompt}]},
            "generationConfig": {"responseMimeType": "application/json"}
        }

        for attempt in range(3):
            try:
                response = await client.post(self.api_url, json=payload, timeout=300.0)
                if response.status_code != 200:
                    response.raise_for_status()

                result = response.json()
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                extracted = self._extract_json(text)
                if extracted:
                    parsed = json.loads(extracted)
                    if isinstance(parsed, dict):
                        return parsed

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait = 60 + (attempt * 30)
                    logging.warning(f"Rate limited (429). Waiting {wait}s...")
                    await asyncio.sleep(wait)
                elif e.response.status_code >= 500:
                    await asyncio.sleep(15 * (attempt + 1))
                else:
                    logging.error(f"HTTP {e.response.status_code}: {e}")
                    break
            except Exception as e:
                logging.error(f"Translation error (attempt {attempt + 1}): {e}")
                await asyncio.sleep(5 * (attempt + 1))

        return None

    async def translate_all(self, chunks, glossary=None):
        """
        Translate all chunks sequentially with rate limiting.

        Args:
            chunks: List of chunk dicts from chunk_strings().
            glossary: Optional glossary dict for consistency.

        Returns:
            dict of merged translated data {namespace: {chinese: english}}.
        """
        from tqdm import tqdm

        automaton, glossary_dict = self.build_glossary_automaton(glossary) if glossary else (None, None)
        merged = {}
        success_count = 0

        async with httpx.AsyncClient() as client:
            for chunk in tqdm(chunks, desc="Translating chunks"):
                start = time.monotonic()

                result = await self.translate_chunk(client, chunk, automaton, glossary_dict)
                if result:
                    # Validate and merge
                    for ns, items in result.items():
                        if not isinstance(items, dict):
                            continue
                        if ns not in merged:
                            merged[ns] = {}
                        for chinese, english in items.items():
                            is_valid, reason = validate_translation(chinese, english)
                            if is_valid:
                                merged[ns][chinese] = english
                    success_count += 1

                # Rate limiting
                elapsed = time.monotonic() - start
                if elapsed < self.seconds_per_request:
                    await asyncio.sleep(self.seconds_per_request - elapsed)

        logging.info(f"Translated {success_count}/{len(chunks)} chunks successfully")
        return merged

    # --- Helpers ---

    @staticmethod
    def _extract_json(text):
        """Extract JSON from API response text (handles code blocks)."""
        if not isinstance(text, str):
            return None

        # ```json { ... } ```
        match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return match.group(1)

        # ``` { ... } ```
        match = re.search(r'```\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return match.group(1)

        # Raw JSON
        stripped = text.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            return stripped

        return None
