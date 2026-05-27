"""
groq_engine.py
==============
Jarvis-Level Groq API Integration Layer

Improvements over v1:
    - Better prompt engineering for more natural, undetectable copy
    - Strategy-aware content generation (adapts tone based on retry strategy)
    - Multi-language support (English + Hindi explanations)
    - Smarter plugin selection with weighted scoring
    - Fallback content generation if API fails
    - Temperature/style variance to avoid pattern detection
"""

import asyncio
import json
import logging
import random
import re
from typing import Optional

from groq import AsyncGroq, RateLimitError, APIStatusError

import database as db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model constants
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "llama3-8b-8192"
FALLBACK_MODEL = "mixtral-8x7b-32768"
MAX_TOKENS = 350
TEMPERATURE = 0.78

# Strategy-based temperature adjustments
STRATEGY_TEMPS = {
    "default": 0.75,
    "slow": 0.70,
    "stealth": 0.85,   # more creative/varied to avoid detection
    "alternate": 0.80,
}


# ---------------------------------------------------------------------------
# 1. Groq Key Rotator
# ---------------------------------------------------------------------------

class GroqKeyRotator:
    """
    Wraps up to 3 Groq API keys with automatic failover on rate-limit.
    """

    def __init__(self) -> None:
        keys_map = db.get_all_api_keys()
        self._keys: list[str] = [
            keys_map[slot] for slot in (1, 2, 3) if keys_map[slot].strip()
        ]
        self._current_index: int = 0
        self._clients: list[AsyncGroq] = [
            AsyncGroq(api_key=k) for k in self._keys
        ]

    @property
    def active_key_slot(self) -> int:
        return self._current_index + 1

    @property
    def has_valid_keys(self) -> bool:
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
        Returns the LLM response text.
        """
        if not self.has_valid_keys:
            raise RuntimeError("No Groq API keys configured.")

        last_exception: Optional[Exception] = None

        for attempt in range(len(self._clients)):
            idx = (self._current_index + attempt) % len(self._clients)
            client = self._clients[idx]

            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                self._current_index = idx
                text = response.choices[0].message.content.strip()
                return text

            except RateLimitError as exc:
                logger.warning("Key slot %d rate limited. Rotating.", idx + 1)
                last_exception = exc
                continue

            except APIStatusError as exc:
                logger.warning("Key slot %d API error %s. Rotating.", idx + 1, exc.status_code)
                last_exception = exc
                continue

            except Exception as exc:
                logger.error("Unexpected Groq error on key %d: %s", idx + 1, exc)
                last_exception = exc
                continue

        self._current_index = (self._current_index + 1) % max(len(self._clients), 1)
        raise last_exception or RuntimeError("All Groq API keys failed.")


# ---------------------------------------------------------------------------
# 2. Context-Aware Plugin Selector + Copy Generator
# ---------------------------------------------------------------------------

async def select_best_plugin_and_generate_copy(
    rotator: GroqKeyRotator,
    page_content: str,
    plugins: list[dict],
    copy_type: str = "general",
    strategy: str = "default",
) -> tuple[dict, str]:
    """
    Given scraped page content and plugin list, ask Groq to:
        a) Identify the most relevant plugin
        b) Write promotional copy tailored to the context

    Strategy affects tone and style for anti-detection.
    """
    if not plugins:
        raise ValueError("No plugins available.")

    content_snippet = page_content[:1800].replace("\n", " ").strip()

    plugin_menu = "\n".join(
        f"{i+1}. Name: {p['name']} | Link: {p['shortlink']} | "
        f"Description: {p['description']}"
        for i, p in enumerate(plugins)
    )

    tone_hints = {
        "contact": "professional, empathetic, urgency-driven, solution-focused",
        "blog": "natural, helpful, like a genuine community member sharing experience",
        "youtube": "casual, encouraging, like a fellow creator sharing a discovery",
        "reddit": "sympathetic, community-minded, anti-spam, genuinely helpful",
        "general": "concise, persuasive, and authentic",
    }
    tone = tone_hints.get(copy_type, tone_hints["general"])

    # Strategy modifiers
    strategy_hints = {
        "default": "",
        "slow": " Be extra cautious and subtle. Minimize promotional language.",
        "stealth": " Sound extremely natural. Use imperfect grammar occasionally. Be very conversational.",
        "alternate": " Take a completely different angle than a typical marketer would.",
    }
    extra_hint = strategy_hints.get(strategy, "")

    system_prompt = (
        "You are an expert digital marketing copywriter. Your job:\n"
        "1. Read the web content snippet.\n"
        "2. Choose the SINGLE most relevant plugin from the list.\n"
        "3. Write a 2-3 sentence promotional message fitting the context.\n"
        f"   Tone: {tone}.{extra_hint}\n\n"
        "ALWAYS include the plugin's shortlink naturally.\n"
        "DO NOT start with 'Great post!' or similar generic openers.\n"
        "Sound like a REAL person, not a bot.\n\n"
        "Respond ONLY in this JSON format (no markdown):\n"
        '{"plugin_index": <1-based int>, "copy": "<message>"}'
    )

    user_prompt = (
        f"PAGE CONTENT:\n{content_snippet}\n\n"
        f"PLUGINS:\n{plugin_menu}\n\n"
        "Select the best plugin and write the copy."
    )

    temp = STRATEGY_TEMPS.get(strategy, TEMPERATURE)

    raw_response = await rotator.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=280,
        temperature=temp,
    )

    selected_plugin, copy_text = _parse_plugin_selection(raw_response, plugins)
    return selected_plugin, copy_text


def _parse_plugin_selection(
    raw_response: str, plugins: list[dict]
) -> tuple[dict, str]:
    """Safely parse Groq's JSON response for plugin selection."""
    cleaned = re.sub(r"```(?:json)?", "", raw_response).strip()

    try:
        data = json.loads(cleaned)
        idx = int(data.get("plugin_index", 1)) - 1
        idx = max(0, min(idx, len(plugins) - 1))
        copy = str(data.get("copy", "")).strip()
        return plugins[idx], copy
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.warning("Could not parse plugin-selection JSON: %r", raw_response)
        return plugins[0], raw_response.strip()


# ---------------------------------------------------------------------------
# 3. Specialised Prompt Builders
# ---------------------------------------------------------------------------

async def build_contact_form_pitch(
    rotator: GroqKeyRotator,
    business_name: str,
    business_context: str,
    plugin: dict,
    strategy: str = "default",
) -> str:
    """Generate a fear+solution pitch for a business contact form."""

    strategy_mods = {
        "default": "Use a fear+solution structure.",
        "slow": "Be extremely polite and non-pushy. Ask a question first.",
        "stealth": "Sound like a genuine potential customer asking about their services, then naturally mention the plugin.",
        "alternate": "Lead with a compliment about their business, then offer the plugin as a partnership opportunity.",
    }
    approach = strategy_mods.get(strategy, strategy_mods["default"])

    system_prompt = (
        "You are a B2B outreach specialist. Write a short, personalised "
        f"cold-contact message for a business's contact form. {approach} "
        "Keep it under 80 words. Sound human, not like spam. "
        "Include the plugin shortlink naturally."
    )

    user_prompt = (
        f"Business: {business_name}\n"
        f"Context: {business_context[:600]}\n\n"
        f"Plugin: {plugin['name']}\n"
        f"Link: {plugin['shortlink']}\n"
        f"Description: {plugin['description']}\n\n"
        "Write the message."
    )

    temp = STRATEGY_TEMPS.get(strategy, TEMPERATURE)
    return await rotator.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=220,
        temperature=temp,
    )


async def build_blog_comment(
    rotator: GroqKeyRotator,
    article_title: str,
    article_snippet: str,
    plugin: dict,
    strategy: str = "default",
) -> str:
    """Generate a natural blog comment promoting the plugin."""

    strategy_mods = {
        "default": "Add value first, then mention the plugin you found useful.",
        "slow": "Write a thoughtful 3-sentence comment. Only hint at the plugin in the last sentence.",
        "stealth": "Sound like you're sharing personal experience. Use 'I' statements. Be imperfect.",
        "alternate": "Ask a genuine question about the article, then answer it yourself mentioning the plugin.",
    }
    approach = strategy_mods.get(strategy, strategy_mods["default"])

    system_prompt = (
        "You are a WordPress community member leaving a blog comment. "
        f"Write a 2-3 sentence comment. {approach}\n"
        "Include the shortlink once, naturally. No 'Great post!' openers. "
        "Sound like a real person."
    )

    user_prompt = (
        f"Article: {article_title}\n"
        f"Content: {article_snippet[:700]}\n\n"
        f"Plugin: {plugin['name']} | Link: {plugin['shortlink']}\n"
        f"Description: {plugin['description']}\n\n"
        "Write the comment."
    )

    temp = STRATEGY_TEMPS.get(strategy, TEMPERATURE)
    return await rotator.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=200,
        temperature=temp,
    )


async def build_youtube_comment(
    rotator: GroqKeyRotator,
    video_title: str,
    video_description: str,
    plugin: dict,
    strategy: str = "default",
) -> str:
    """Generate a YouTube comment promoting the plugin."""

    strategy_mods = {
        "default": "Add something useful about the video topic, then mention the plugin.",
        "slow": "Start with genuine appreciation for a specific point in the video, then casually mention the plugin.",
        "stealth": "Sound like an excited viewer who just discovered something. Be casual with typos/slang.",
        "alternate": "Ask a question that the plugin answers, then share it as your own discovery.",
    }
    approach = strategy_mods.get(strategy, strategy_mods["default"])

    system_prompt = (
        "You are a YouTube commenter in the WordPress niche. "
        f"Write a 2-3 sentence comment. {approach}\n"
        "Include the shortlink once. Tone: friendly, casual. "
        "Sound like a real viewer, not a marketer."
    )

    user_prompt = (
        f"Video: {video_title}\n"
        f"Description: {video_description[:500]}\n\n"
        f"Plugin: {plugin['name']} | Link: {plugin['shortlink']}\n"
        f"Description: {plugin['description']}\n\n"
        "Write the comment."
    )

    temp = STRATEGY_TEMPS.get(strategy, TEMPERATURE)
    return await rotator.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=200,
        temperature=temp,
    )


async def build_reddit_reply(
    rotator: GroqKeyRotator,
    post_title: str,
    post_snippet: str,
    trigger_words: list[str],
    plugin: dict,
    strategy: str = "default",
) -> str:
    """Generate a Reddit reply promoting the plugin."""

    triggers_str = ", ".join(f'"{w}"' for w in trigger_words)

    strategy_mods = {
        "default": "Open with empathy, then mention the plugin as something that helped you.",
        "slow": "Write 3 sentences of genuine help FIRST. Only in the last sentence hint at the plugin.",
        "stealth": "Sound like a frustrated Redditor who finally found a solution. Be raw and honest.",
        "alternate": "Disagree mildly with another approach, then share the plugin as what actually worked for you.",
    }
    approach = strategy_mods.get(strategy, strategy_mods["default"])

    system_prompt = (
        "You are a helpful Redditor in a WordPress subreddit. "
        f"Write a 2-3 sentence reply. {approach}\n"
        "Include the shortlink once. No marketing speak. "
        "Sound like a REAL Redditor. No 'Check out X!'"
    )

    user_prompt = (
        f"Post: {post_title}\n"
        f"Content: {post_snippet[:500]}\n"
        f"Triggers: {triggers_str}\n\n"
        f"Plugin: {plugin['name']} | Link: {plugin['shortlink']}\n"
        f"Description: {plugin['description']}\n\n"
        "Write the reply."
    )

    temp = STRATEGY_TEMPS.get(strategy, TEMPERATURE)
    return await rotator.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=220,
        temperature=temp,
    )


# ---------------------------------------------------------------------------
# 4. Fallback Content (when API is completely down)
# ---------------------------------------------------------------------------

def generate_fallback_copy(plugin: dict, copy_type: str = "general") -> str:
    """
    Generate basic promotional copy without LLM when all API keys are exhausted.
    Used as last resort to keep the engine moving.
    """
    templates = {
        "contact": [
            f"Hi! I came across your site and thought you might find {plugin['name']} useful. "
            f"It {plugin['description'].lower()[:80]}. Check it out: {plugin['shortlink']}",
            f"Hey, quick note — if you're looking to improve your WordPress setup, "
            f"{plugin['name']} might be worth a look: {plugin['shortlink']}",
        ],
        "blog": [
            f"This is really helpful. I've been using {plugin['name']} for something similar "
            f"and it's been great — {plugin['shortlink']}",
            f"Thanks for sharing this. Reminded me of {plugin['name']} which I've been "
            f"using lately: {plugin['shortlink']}",
        ],
        "youtube": [
            f"Super helpful video! I found {plugin['name']} works great alongside what "
            f"you showed here: {plugin['shortlink']}",
            f"This is exactly what I was looking for. Also been using {plugin['name']} "
            f"which complements this nicely: {plugin['shortlink']}",
        ],
        "reddit": [
            f"Had the same issue. Ended up trying {plugin['name']} and it actually "
            f"solved it for me: {plugin['shortlink']}",
            f"I feel you. What worked for me was {plugin['name']} — might be worth "
            f"checking out: {plugin['shortlink']}",
        ],
    }

    options = templates.get(copy_type, templates["contact"])
    return random.choice(options)
