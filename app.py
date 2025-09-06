# app.py
import os
import time
import json
import base64
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from groq import Groq

# -------------------------
# Paths & Assets
# -------------------------
HERE = Path(__file__).parent
ASSETS = HERE / "assets"

# -------------------------
# Load secrets / client
# -------------------------
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=API_KEY) if API_KEY else None

# -------------------------
# Helper: load image as base64 (for embedding in HTML)
# -------------------------
def load_image_base64(path: Path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
        ext = path.suffix.lower().lstrip(".")
        mime = "image/png"
        if ext in ("jpg", "jpeg"):
            mime = "image/jpeg"
        elif ext == "svg":
            mime = "image/svg+xml"
        return f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    except Exception:
        return None

# pick a sensible logo candidate from assets
_logo_candidates = [
    ASSETS / "logo.png",
    ASSETS / "logo 1.png",
    ASSETS / "logo1.png",
    ASSETS / "icon.png",
    ASSETS / "fav icon 1.png",
]
logo_base64 = None
for p in _logo_candidates:
    if p.exists():
        logo_base64 = load_image_base64(p)
        break

# -------------------------
# Page config (must run before other st.* UI calls)
# -------------------------
# Use emoji as page_icon to avoid path issues; the header will embed the real logo
st.set_page_config(page_title="InkLink — LinkedIn Post Generator", page_icon="🖋", layout="wide")

# -------------------------
# Load CSS (if exists)
# -------------------------
css_file = ASSETS / "styles.css"
if css_file.exists():
    try:
        with open(css_file, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception as e:
        st.write("Could not load custom CSS:", e)

# -------------------------
# App Header (inline logo + text), safe if logo missing
# -------------------------
if logo_base64:
    header_html = f"""
    <div class="app-header">
        <img src="{logo_base64}" class="app-logo" alt="InkLink logo" />
        <div class="app-text">
            <h1 class="app-title">InkLink</h1>
            <p class="app-subtitle">AI-powered LinkedIn Post Generator</p>
        </div>
    </div>
    <hr>
    """
else:
    # fallback: text-only header
    header_html = """
    <div class="app-header">
        <div class="app-text">
            <h1 class="app-title">InkLink</h1>
            <p class="app-subtitle">AI-powered LinkedIn Post Generator</p>
        </div>
    </div>
    <hr>
    """

st.markdown(header_html, unsafe_allow_html=True)

# -------------------------
# Behaviour maps (from your JSON)
# -------------------------
POST_TYPE_MAP = {
    "Actionable": "Write a short practical post that teaches a clear task or framework. Use numbered steps or bite-size tips, include one concrete example, and end with a simple call-to-action (try this, comment, save). Aim for clarity and immediate usefulness.",
    "Inspiring": "Craft an uplifting post that motivates and energizes. Use vivid but concise language, a small illustrative example or metaphor, and end with an inclusive call-to-action (share your wins, keep going). Focus on emotion and belief.",
    "Introspective": "Write a reflective first-person post exploring a lesson or mistake. Use narrative beats (situation → thought → lesson), honest specifics, and a thoughtful closing question that invites reflection or comment.",
    "Awareness": "Create an informative post that explains a problem, trend, or misconception. Present the issue, evidence or impact, and 2–3 implications or recommended next steps. Keep tone neutral-to-concerned; invite discussion.",
    "Promotional": "Produce a concise value-first post that highlights an offering or event. Lead with the benefit, include 2–3 specific features or outcomes, a proof point (metric/testimonial), and a clear CTA (register, message, book).",
    "Storytelling": "Tell a short, relatable story with a clear arc: opening hook, rising situation, reveal/lesson, and a crisp takeaway or CTA. Use sensory details, specific characters or events, and keep it human.",
    "No Preference": "No specific structural constraint; follow other parameters."
}

POST_CATEGORY_MAP = {
    "Explanation/analysis": "Provide a clear breakdown of a concept or data point. Use short paragraphs, define terms, and conclude with bottom-line takeaways (1–3). Prefer logical flow and clarity.",
    "Best practices-Sharing tips": "List 2–7 practical, ordered tips or mistakes + fixes. Each item should be 1–2 sentences: the problem, the fix, and an example where applicable.",
    "Striking Advice": "Deliver one sharp, bold statement that prompts action. Keep it direct, brief (1–3 sentences), and end with a one-line challenge or next step.",
    "List of tips": "Rapid-fire list of 8+ concise tips. Each tip 4–12 words or one short sentence. Use bullets or numbered format for scannability.",
    "Quirky": "Micro-post (1–2 snappy lines) with playful language or a witty twist. Prioritize surprise and brevity over explanation.",
    "Personal-Reflection": "Short personal story or reflection (3–6 sentences) with a clear lesson. Use first-person if expression prefers 'I'.",
    "Rant": "A high-energy, opinionated post. Use short paragraphs, strong verbs, and rhetorical questions. Keep it punchy, not abusive; include a constructive takeaway."
}

TONE_MAP = {
    "Standard": "Neutral, professional, LinkedIn-appropriate voice. Moderate sentence length, few contractions, clear signposting.",
    "Casual": "Informal and direct. Use contractions, analogies, short sentences, and a friendly, conversational pace.",
    "Engaging": "Inviting and interactive. Use questions, prompts to comment, and second-person ('you') to draw readers in.",
    "Formal": "Polished, reserved, and professional. Longer sentences, precise vocabulary, no slang, and minimal emojis.",
    "Humorous": "Light humor and clever phrasing. Use mild hyperbole, short comedic beats, and playful metaphors—avoid aggressive sarcasm.",
    "None": "No explicit tonal preference — keep neutral professional unless other parameters push style."
}

EMOJI_MAP = {
    "None": "Do not include emojis.",
    "less (1-4 emojis)": "Include 1–4 relevant emojis that support tone or highlight key lines. Place them naturally (lead, inline, or as a closing).",
    "more (5-8 emojis)": "Include 5–8 emojis spread across the post to add personality—use for emphasis and to separate bullets/sections.",
    "little more (8-12 emojis)": "Use 8–12 emojis for a lively, highly visual post. Sprinkle them as inline accents and at line ends; ensure they don't replace important text."
}

EXPRESSION_MAP = {
    "I": "Use first-person singular (I) — personal voice and ownership of opinions.",
    "We": "Use first-person plural (We) — company or team perspective, community framing.",
    "Simple present tense": "Prefer simple present tense (I write, we do, this works).",
    "No Preference": "No enforced pronoun or tense: choose what's most natural."
}

POST_SIZE_MAP = {
    "Micro (Snack)": {
        "desc": "1–2 short sentences (~15–40 words). Single idea; optional 1 emoji; no bullets.",
        "prompt": "PostSize: Micro — 1–2 sentences (15–40 words). Single idea, punchy ending; optional 1 emoji; no bullets."
    },
    "Short (Quick value)": {
        "desc": "3–6 sentences (~40–100 words). Single focused idea, 1 supporting example or tip, soft CTA.",
        "prompt": "PostSize: Short — 3–6 sentences (~40–100 words). Single focused idea, 1 supporting example or tip, soft CTA."
    },
    "Standard (Recommended)": {
        "desc": "80–180 words (6–12 sentences). Opening, 2 supporting points, clear takeaway/CTA; allow 1 short list if needed.",
        "prompt": "PostSize: Standard — 80–180 words (6–12 sentences). Opening, 2 supporting points, clear takeaway/CTA; allow 1 short list if needed."
    },
    "Long (In-depth)": {
        "desc": "200–350 words: intro, 3–7 sub-points or steps, example or metric, and strong CTA; minimal emojis.",
        "prompt": "PostSize: Long — 200–350 words. Multi-paragraph: intro, 3–7 sub-points or steps, example or metric, and strong CTA; minimal emojis."
    }
}

# -------------------------
# UI layout
# -------------------------
# Row 1: Post Type + Post Category
col1, col2 = st.columns([1, 1])
with col1:
    post_type = st.selectbox(
        "🧭 Post Type",
        options=list(POST_TYPE_MAP.keys()),
        index=0,
        help="Choose the broad approach (structure & expected behavior)."
    )
with col2:
    post_category = st.selectbox(
        "📚 Post Category",
        options=list(POST_CATEGORY_MAP.keys()),
        index=0,
        help="Choose the micro-structure / format for the post."
    )
    st.markdown(
        f"<div style='color:#6c757d; font-style:italic; margin-top:6px'>{POST_CATEGORY_MAP.get(post_category,'')}</div>",
        unsafe_allow_html=True
    )

# Row 2: Tone + Emojis
col3, col4 = st.columns([1, 1])
with col3:
    tone = st.selectbox(
        "🎙 Tone",
        options=list(TONE_MAP.keys()),
        index=0,
        help="Choose voice style (how the words should feel)."
    )
    st.markdown(
        f"<div style='color:#6c757d; font-style:italic; margin-top:6px'>{TONE_MAP.get(tone,'')}</div>",
        unsafe_allow_html=True
    )
with col4:
    emojis = st.selectbox(
        "😊 Emojis",
        options=list(EMOJI_MAP.keys()),
        index=0,
        help="Control emoji density."
    )

# Row 3: Expression + Industry
col5, col6 = st.columns([1, 1])
with col5:
    expression = st.selectbox(
        "🗣 Expression",
        options=list(EXPRESSION_MAP.keys()),
        index=3,
        help="I / We / Simple present tense / No Preference"
    )
with col6:
    industry = st.selectbox(
        "🏷 Industry / Domain",
        options=["General", "Technology", "Health & Fitness", "Marketing & Advertising",
                 "Finance", "Education & Learning", "Retail & E-commerce", "Energy & Environment"],
        index=0,
        help="Pick domain to ground examples and vocabulary."
    )
    st.markdown(
        "<div style='color:#6c757d; font-style:italic; margin-top:6px'>Select the domain so the AI uses relevant examples and language.</div>",
        unsafe_allow_html=True
    )

st.markdown("---")

# Two side-by-side textareas
left, right = st.columns(2)
with left:
    user_thoughts = st.text_area(
        "Your Thoughts",
        placeholder="Input keywords, ideas, topics, or your own draft",
        height=220
    )
with right:
    competitor_post = st.text_area(
        "Reference Post (style only, optional)",
        placeholder="Input a reference post to match its style, tone, and flow",
        height=220
    )

st.markdown("")  # spacing

# Post Size and Draft count
col7, col8 = st.columns([1, 1])
with col7:
    post_size = st.selectbox(
        "📏 Post Size",
        options=list(POST_SIZE_MAP.keys()),
        index=2,
        help="How long / deep should the generated post be?"
    )
    st.markdown(
        f"<div style='color:#6c757d; font-style:italic; margin-top:6px'>{POST_SIZE_MAP.get(post_size)['desc']}</div>",
        unsafe_allow_html=True
    )

with col8:
    num_drafts = st.select_slider("Number of Drafts", options=[1, 3, 5], value=3)

st.markdown("")  # spacing
generate = st.button("🚀 Generate Content", use_container_width=True)

# -------------------------
# Helper utils
# -------------------------
def is_incomplete_text(text: str) -> bool:
    if not text:
        return True
    t = text.strip()
    if len(t) < 40:
        return True
    if t.endswith(("...", "…", "-", "—")):
        return True
    if all(ch in "*- \n\r\t" for ch in t):
        return True
    return False

def build_system_prompt():
    # Build a clear, directive system prompt by pulling fine-grained instructions
    parts = [
        "You are an expert LinkedIn content creator with strong experience in content writing, copywriting, and research.",
        "Follow these instructions EXACTLY."
    ]

    # Role instructions from chosen parameters
    parts.append(f"PostType behavior: {POST_TYPE_MAP.get(post_type)}")
    parts.append(f"PostCategory behavior: {POST_CATEGORY_MAP.get(post_category)}")
    parts.append(f"Tone behavior: {TONE_MAP.get(tone)}")
    parts.append(f"Emoji behavior: {EMOJI_MAP.get(emojis)}")
    parts.append(f"Expression behavior: {EXPRESSION_MAP.get(expression)}")
    parts.append(f"Industry: Use vocabulary, examples and metaphors relevant to {industry}.")
    parts.append(f"PostSize: {POST_SIZE_MAP.get(post_size)['prompt']}")

    # Clear constraints to avoid copying competitor content
    parts.extend([
        "Content rules:",
        "1) The text in 'Your Thoughts' is the MAIN CONTENT (use ideas/keywords/topics provided).",
        "2) The 'Reference Post' (if present) is for STYLE ONLY: match tone, sentence length, cadence, and structure. DO NOT copy or reuse content, facts, or unique examples from it.",
        "3) Output EXACTLY one ready-to-post LinkedIn post (no labels, no 'Draft 1', no extra commentary).",
        "4) If the chosen PostCategory implies a list (e.g., 'List of tips' or 'Best practices'), follow that format.",
        "5) Respect emoji limits, expression (I/We/simple present), and the requested post size.",
        "6) Keep posts professional and not abusive; if the user request would cause harm or violate policy, refuse politely.",
        "7) End with a short CTA or engagement prompt consistent with the PostType (if applicable).",
        "8) If you cannot fit requested length exactly, prefer self-contained complete sentences at natural boundaries."
    ])

    return "\n".join(parts)

# -------------------------
# Generation logic
# -------------------------
if generate:
    # Input validation
    if not API_KEY:
        st.error("Missing GROQ API key. Add GROQ_API_KEY=gsk_... to your .env or Streamlit Secrets and restart.")
    elif not user_thoughts or not user_thoughts.strip():
        st.warning("Please add your main ideas / keywords in 'Your Thoughts' before generating.")
    else:
        if client is None:
            st.error("Groq client not initialized (missing API key).")
        else:
            with st.spinner("Generating drafts (separate calls for reliability)..."):
                system_prompt = build_system_prompt()
                drafts = []
                for idx in range(num_drafts):
                    attempt = 0
                    generated = ""
                    while attempt < 2:  # up to 2 attempts per draft
                        attempt += 1
                        try:
                            user_prompt = (
                                f"User main content / thoughts:\n{user_thoughts.strip()}\n\n"
                                f"Reference post for STYLE ONLY:\n{competitor_post.strip() if competitor_post and competitor_post.strip() else 'None'}\n\n"
                                "Now generate the single final LinkedIn post exactly as instructed in the system prompt. Return only the post text."
                            )

                            resp = client.chat.completions.create(
                                model="llama-3.1-8b-instant",
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt}
                                ],
                                temperature=0.65,
                                max_tokens=900
                            )

                            raw = resp.choices[0].message.content.strip()

                            # remove common accidental prefixes
                            lines = raw.splitlines()
                            if lines and lines[0].lower().startswith(("draft", "---", "1)")):
                                # try to remove the first line if it's a label
                                raw = "\n".join(lines[1:]).strip()

                            # if incomplete, allow one retry
                            if is_incomplete_text(raw) and attempt < 2:
                                time.sleep(0.3)
                                continue
                            generated = raw
                            break

                        except Exception as exc:
                            generated = f"[Error generating draft: {exc}]"
                            break

                    drafts.append(generated if generated else "[No content generated]")

                # Display results in clean UI: each draft as a text_area + download button
                st.subheader("✨ Generated Drafts")
                all_for_download = []
                for i, d in enumerate(drafts, start=1):
                    st.markdown(f"**Draft {i}**")
                    # text_area for easy selection + copy
                    st.text_area(label=f"Draft {i} (select to copy)", value=d, height=180, key=f"draft_{i}")
                    # per-draft download
                    st.download_button(
                        label=f"⬇️ Download Draft {i}",
                        data=d,
                        file_name=f"linkedin_draft_{i}.txt",
                        mime="text/plain",
                        key=f"download_{i}"
                    )
                    st.markdown("---")
                    all_for_download.append(f"--- Draft {i} ---\n{d}\n\n")

                # combined download
                joined = "\n".join(all_for_download)
                st.download_button("⬇️ Download ALL Drafts (.txt)", data=joined, file_name="linkedin_all_drafts.txt", mime="text/plain")

                st.success("Done — review drafts above. Select any draft to copy it to your clipboard, or use the download buttons.")
