"""
groq_engine.py
==============
Groq API integration layer for the AI Marketing Dashboard.

Responsibilities:
    1. GroqKeyRotator  — Manages 3 API keys with automatic failover on
                         rate-limit (429) or any API error. Tracks which key
                         is currently active and exposes a unified async call
                         interface.

    2. select_best_plugin_and_generate_copy()
                       — Passes scraped page content + the full plugin list to
                         Groq. The LLM picks the most contextually relevant
                         plugin and writes a 2-3 sentence promotional message
                         tailored to the content.

    3. Specialised prompt builders for each of the 5 workers:
        - build_contact_form_pitch()
        - build_blog_comment()
        - build_youtube_comment()
        - build_reddit_reply()
       (Pingback worker does not need LLM copy — it uses raw URLs.)

All public functions are async and designed to be called directly from the
worker coroutines in workers.py.
"""

import asyncio
import logging
from typing import Optional

from groq import AsyncGroq, RateLimitError, APIStatusError

import database as db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model constants — swap to any Groq-hosted model as needed
# ---------------------------------------------------------------------------
DEFAULT_MODEL   = "llama-3.3-70b-versatile"   # latest supported Groq model
FALLBACK_MODEL  = "llama-3.1-8b-instant"      # fast fallback

# Patch: older groq versions pass 'proxies' to httpx which is removed in httpx>=0.28
# This ensures compatibility across versions
import httpx as _httpx
try:
    _orig_init = _httpx.AsyncClient.__init__
    def _patched_init(self, *args, **kwargs):
        kwargs.pop("proxies", None)
        _orig_init(self, *args, **kwargs)
    _httpx.AsyncClient.__init__ = _patched_init
except Exception:
    pass
MAX_TOKENS      = 300                   # keep responses concise
TEMPERATURE     = 0.75                  # slight creativity, but grounded


# ---------------------------------------------------------------------------
# 1.  Groq Key Rotator
# ---------------------------------------------------------------------------

class GroqKeyRotator:
    """
    Wraps up to 3 Groq API keys and provides a single `chat()` method.

    Rotation strategy:
        • Try Key 1 first.
        • On RateLimitError (429) or any APIStatusError, move to Key 2.
        • On another failure, move to Key 3.
        • If all three keys fail, raise the last exception so the caller
          (worker) can log it and back off.

    The rotator is instantiated once per background thread (engine.py) so
    the active-key state is preserved across consecutive calls within the
    same worker loop iteration.
    """

    def __init__(self) -> None:
        # Load keys from DB each time the rotator is created (fresh start)
        keys_map = db.get_all_api_keys()
        # Build ordered list, filtering out empty strings
        self._keys: list[str] = [
            keys_map[slot] for slot in (1, 2, 3) if keys_map[slot].strip()
        ]
        self._current_index: int = 0
        self._clients: list[AsyncGroq] = [
            AsyncGroq(api_key=k) for k in self._keys
        ]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def active_key_slot(self) -> int:
        """Returns the 1-based slot number of the currently active key."""
        return self._current_index + 1

    @property
    def has_valid_keys(self) -> bool:
        """True if at least one non-empty key was loaded from the DB."""
        return len(self._keys) > 0

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = MAX_TOKENS,
        temperature: float = TEMPERATURE,
    ) -> str:
        """
        Send a chat completion request, rotating keys on failure.

        Returns:
            The LLM response text as a plain string.

        Raises:
            RuntimeError  — if no API keys are configured.
            Exception     — re-raises the last API error if all keys fail.
        """
        if not self.has_valid_keys:
            raise RuntimeError(
                "No Groq API keys configured. Please add at least one key "
                "in the Settings tab."
            )

        last_exception: Optional[Exception] = None

        # Try each remaining key starting from self._current_index
        for attempt in range(len(self._clients)):
            idx = (self._current_index + attempt) % len(self._clients)
            client = self._clients[idx]

            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                # ✅ Success — lock in this key as the active one
                self._current_index = idx
                text = response.choices[0].message.content.strip()
                logger.debug("Groq key slot %d succeeded.", idx + 1)
                return text

            except RateLimitError as exc:
                logger.warning(
                    "Groq key slot %d hit rate limit. Rotating to next key.", idx + 1
                )
                last_exception = exc
                # Rotate to next key immediately
                continue

            except APIStatusError as exc:
                logger.warning(
                    "Groq key slot %d returned API error %s. Rotating.",
                    idx + 1, exc.status_code
                )
                last_exception = exc
                continue

            except Exception as exc:
                logger.error("Unexpected Groq error on key slot %d: %s", idx + 1, exc)
                last_exception = exc
                continue

        # All keys exhausted — advance the starting index so next call
        # doesn't start on a key we know just failed
        self._current_index = (self._current_index + 1) % max(len(self._clients), 1)
        raise last_exception or RuntimeError("All Groq API keys failed.")


# ---------------------------------------------------------------------------
# 2.  Context-Aware Plugin Selector + Copy Generator
# ---------------------------------------------------------------------------

async def select_best_plugin_and_generate_copy(
    rotator: GroqKeyRotator,
    page_content: str,
    plugins: list[dict],
    copy_type: str = "general",
) -> tuple[dict, str]:
    """
    Given scraped page content and the full plugin list, ask Groq to:
        a) Identify the SINGLE most relevant plugin.
        b) Write a 2-3 sentence promotional message tailored to the content.

    Args:
        rotator      : An initialised GroqKeyRotator instance.
        page_content : Raw text extracted from the target page (truncated
                       to 1500 chars to stay within token budget).
        plugins      : List of plugin dicts from db.get_all_plugins().
        copy_type    : Hint for tone — 'contact', 'blog', 'youtube',
                       'reddit', or 'general'.

    Returns:
        (selected_plugin_dict, promotional_copy_string)

    Raises:
        ValueError  — if the plugin list is empty.
        RuntimeError / Exception — propagated from GroqKeyRotator.chat().
    """
    if not plugins:
        raise ValueError("No plugins available in the database.")

    # Truncate content to avoid blowing the token budget
    content_snippet = page_content[:1500].replace("\n", " ").strip()

    # Build a numbered plugin menu for the LLM
    plugin_menu = "\n".join(
        f"{i+1}. Name: {p['name']} | Link: {p['shortlink']} | "
        f"Description: {p['description']}"
        for i, p in enumerate(plugins)
    )

    tone_hints = {
        "contact": "professional, empathetic, fear-of-missing-out driven",
        "blog":    "natural, helpful, like a knowledgeable commenter",
        "youtube": "casual, encouraging, like a fellow creator",
        "reddit":  "sympathetic, community-minded, not overtly salesy",
        "general": "concise and persuasive",
    }
    tone = tone_hints.get(copy_type, tone_hints["general"])

    system_prompt = (
        "You are an expert digital marketing copywriter specialising in "
        "WordPress plugins. Your job is to:\n"
        "1. Read a snippet of web content.\n"
        "2. Choose the SINGLE most relevant plugin from the provided list.\n"
        "3. Write a 2-3 sentence promotional message that fits the page's "
        f"context. Tone: {tone}.\n\n"
        "ALWAYS include the plugin's shortlink naturally within the copy.\n"
        "Respond ONLY in this exact JSON format (no markdown, no extra text):\n"
        '{"plugin_index": <1-based integer>, "copy": "<promotional message>"}'
    )

    user_prompt = (
        f"PAGE CONTENT SNIPPET:\n{content_snippet}\n\n"
        f"AVAILABLE PLUGINS:\n{plugin_menu}\n\n"
        "Select the best plugin and write the promotional copy."
    )

    raw_response = await rotator.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=250,
        temperature=0.7,
    )

    # Parse the JSON response safely
    selected_plugin, copy_text = _parse_plugin_selection(raw_response, plugins)
    return selected_plugin, copy_text


def _parse_plugin_selection(
    raw_response: str, plugins: list[dict]
) -> tuple[dict, str]:
    """
    Safely parse Groq's JSON response for plugin selection.
    Falls back gracefully if the response is malformed.
    """
    import json, re

    # Strip any accidental markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", raw_response).strip()

    try:
        data = json.loads(cleaned)
        idx  = int(data.get("plugin_index", 1)) - 1   # convert to 0-based
        idx  = max(0, min(idx, len(plugins) - 1))      # clamp to valid range
        copy = str(data.get("copy", "")).strip()
        return plugins[idx], copy
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        # Fallback: use first plugin + raw response as copy
        logger.warning("Could not parse Groq plugin-selection JSON: %r", raw_response)
        return plugins[0], raw_response.strip()


# ---------------------------------------------------------------------------
# 3.  Specialised Prompt Builders
# ---------------------------------------------------------------------------

async def build_contact_form_pitch(
    rotator: GroqKeyRotator,
    business_name: str,
    business_context: str,
    plugin: dict,
) -> str:
    """
    Generate a fear+solution pitch for a business contact form.

    Args:
        business_name    : Name or domain of the target business.
        business_context : Brief description scraped from their site.
        plugin           : The plugin dict to promote.

    Returns:
        A short, personalised pitch string (3-4 sentences).
    """
    system_prompt = (
        "You are a B2B outreach specialist. Write a short, personalised "
        "cold-contact message for a business's contact form. "
        "Use a fear+solution structure: briefly name a pain point the "
        "business likely faces, then present the plugin as the solution. "
        "Keep it under 80 words. Sound human, not like spam. "
        "Always include the plugin shortlink."
    )

    user_prompt = (
        f"Business: {business_name}\n"
        f"Context from their website: {business_context[:500]}\n\n"
        f"Plugin to promote:\n"
        f"  Name       : {plugin['name']}\n"
        f"  Shortlink  : {plugin['shortlink']}\n"
        f"  Description: {plugin['description']}\n\n"
        "Write the contact form message."
    )

    return await rotator.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=200,
        temperature=0.80,
    )


async def build_blog_comment(
    rotator: GroqKeyRotator,
    article_title: str,
    article_snippet: str,
    plugin: dict,
) -> str:
    """
    Generate a natural-sounding blog comment that promotes the plugin.

    The comment must feel like genuine participation in the discussion,
    not a spam post. It adds value first, then mentions the plugin.
    """
    system_prompt = (
        "You are a helpful WordPress community member leaving a blog comment. "
        "Write a 2-3 sentence comment that:\n"
        "1. Genuinely engages with the article topic.\n"
        "2. Naturally mentions the plugin as something you personally found useful.\n"
        "3. Includes the shortlink only once, embedded naturally.\n"
        "Sound like a real person. No excessive exclamation marks. "
        "No 'Great post!' openers."
    )

    user_prompt = (
        f"Article title  : {article_title}\n"
        f"Article snippet: {article_snippet[:600]}\n\n"
        f"Plugin to mention:\n"
        f"  Name       : {plugin['name']}\n"
        f"  Shortlink  : {plugin['shortlink']}\n"
        f"  Description: {plugin['description']}\n\n"
        "Write the blog comment."
    )

    return await rotator.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=180,
        temperature=0.85,
    )


async def build_youtube_comment(
    rotator: GroqKeyRotator,
    video_title: str,
    video_description: str,
    plugin: dict,
) -> str:
    """
    Generate a helpful YouTube comment promoting the plugin as an
    alternative/complement to what is discussed in the video.
    """
    system_prompt = (
        "You are a helpful YouTube commenter in the WordPress niche. "
        "Write a 2-3 sentence comment that:\n"
        "1. Adds something genuinely useful related to the video topic.\n"
        "2. Mentions the plugin as a tool that complements or improves on "
        "   what the video covers.\n"
        "3. Includes the shortlink once, naturally.\n"
        "Tone: friendly, casual, like a fellow creator sharing a tip."
    )

    user_prompt = (
        f"Video title      : {video_title}\n"
        f"Video description: {video_description[:500]}\n\n"
        f"Plugin to mention:\n"
        f"  Name       : {plugin['name']}\n"
        f"  Shortlink  : {plugin['shortlink']}\n"
        f"  Description: {plugin['description']}\n\n"
        "Write the YouTube comment."
    )

    return await rotator.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=180,
        temperature=0.85,
    )


async def build_reddit_reply(
    rotator: GroqKeyRotator,
    post_title: str,
    post_snippet: str,
    trigger_words: list[str],
    plugin: dict,
) -> str:
    """
    Generate a sympathetic Reddit reply that promotes the plugin.

    The reply must lead with empathy or a useful tip, not a hard sell.
    Reddit is notoriously hostile to obvious spam, so the tone is critical.
    """
    triggers_str = ", ".join(f'"{w}"' for w in trigger_words)

    system_prompt = (
        "You are a helpful member of a WordPress subreddit. "
        "Write a 2-3 sentence reply to a post where someone is struggling. "
        "Rules:\n"
        "1. Open with empathy or a concrete tip — NOT with a product name.\n"
        "2. Mention the plugin as something that helped you solve the same issue.\n"
        "3. Include the shortlink naturally, once.\n"
        "4. Sound like a real Redditor. No marketing speak. No 'Check out X!'"
    )

    user_prompt = (
        f"Post title  : {post_title}\n"
        f"Post snippet: {post_snippet[:500]}\n"
        f"Trigger words detected: {triggers_str}\n\n"
        f"Plugin to mention:\n"
        f"  Name       : {plugin['name']}\n"
        f"  Shortlink  : {plugin['shortlink']}\n"
        f"  Description: {plugin['description']}\n\n"
        "Write the Reddit reply."
    )

    return await rotator.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=200,
        temperature=0.80,
    )
