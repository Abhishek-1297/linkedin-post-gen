# app.py
import os
import time
import re
import traceback
import json
import base64
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from groq import Groq

# -------------------------
# Paths & Assets
# -------------------------
HERE = Path(__file__).parent
ASSETS = HERE / "assets"

# -------------------------
# Load .env & init Groq client
# -------------------------
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=API_KEY) if API_KEY else None

# -------------------------
# Helpers
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

def local_css(file_path: str):
    p = Path(file_path)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

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

def remove_visual_lines_from_post(post_text: str):
    if not post_text:
        return ""
    lines = post_text.splitlines()
    filtered = []
    for ln in lines:
        if re.search(r"(?i)\b(visuals|image options|overlay text|slide \d|carousel|suggestion|image idea|visual)\b", ln):
            continue
        filtered.append(ln)
    return "\n".join(filtered).strip()

def split_post_and_visuals(raw_text: str):
    """
    Return (post, visuals). Heuristic splitting:
     - explicit "Visuals" header
     - trailing lines starting with Image/Slide
     - fallback: everything as post, visuals empty
    """
    if not raw_text:
        return "", ""
    text = raw_text.strip()

    # explicit Visuals header
    m = re.search(r"(?mi)^\s*(visuals(?:/image options)?\s*[:\-]?)", text)
    if m:
        split_index = m.start()
        post_part = text[:split_index].strip()
        visuals_part = text[split_index:].strip()
        visuals_part = re.sub(r"(?mi)^\s*(visuals(?:/image options)?\s*[:\-]?\s*)", "", visuals_part).strip()
        post_part = re.sub(r"(?mi)^\s*(post\s*[:\-]?\s*)", "", post_part).strip()
        post_part = remove_visual_lines_from_post(post_part)
        return post_part, visuals_part

    # search for "visuals" in later lines
    pos = re.search(r"(?mi)\nvisuals(?:/image options)?\s*[:\-]?", text)
    if pos:
        idx = pos.start()
        post_part = text[:idx].strip()
        visuals_part = text[idx:].strip()
        visuals_part = re.sub(r"(?mi)^\s*(visuals(?:/image options)?\s*[:\-]?\s*)", "", visuals_part).strip()
        post_part = re.sub(r"(?mi)^\s*(post\s*[:\-]?\s*)", "", post_part).strip()
        post_part = remove_visual_lines_from_post(post_part)
        return post_part, visuals_part

    # trailing heuristic
    lines = text.splitlines()
    for i in range(len(lines)-1, max(-1, len(lines)-8), -1):
        if re.match(r"(?i)^\s*[-\u2022]?\s*(image|slide|visual|overlay|carousel)\b", lines[i].strip()):
            post_part = "\n".join(lines[:i]).strip()
            visuals_part = "\n".join(lines[i:]).strip()
            post_part = remove_visual_lines_from_post(post_part)
            visuals_part = re.sub(r"(?mi)^\s*(visuals(?:/image options)?\s*[:\-]?\s*)", "", visuals_part).strip()
            return post_part, visuals_part

    # fallback
    return remove_visual_lines_from_post(text), ""

def render_copy_button_iframe(text: str, label: str = "Copy", bg: str = "#2563eb"):
    """
    Render an iframe-based copy button to avoid HTML leakage.
    """
    uid = "btn_" + uuid.uuid4().hex
    safe_text = json.dumps(text)
    html = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width,initial-scale=1"/>
        <style>
          body {{ margin:0; padding:0; background:transparent; }}
          .btn {{
            padding:8px 12px;
            border-radius:8px;
            border:none;
            background:{bg};
            color:white;
            cursor:pointer;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial;
            font-size:14px;
          }}
        </style>
      </head>
      <body>
        <button id="{uid}" class="btn">{label}</button>
        <script>
          const txt = {safe_text};
          const btn = document.getElementById("{uid}");
          btn.addEventListener('click', function(e) {{
            navigator.clipboard.writeText(txt).then(function() {{
               btn.innerText = 'Copied';
               setTimeout(()=>{{ btn.innerText = {json.dumps(label)} }}, 1500);
            }}).catch(function(){{
               alert('Copy failed — please select and copy manually.');
            }});
          }});
        </script>
      </body>
    </html>
    """
    components.html(html, height=46, scrolling=False)

# -------------------------
# Page config + CSS load
# -------------------------
st.set_page_config(page_title="InkLink — LinkedIn Post Generator", page_icon="🖋", layout="wide")
# load CSS (your assets/styles.css)
local_css(ASSETS / "styles.css")

# -------------------------
# Header (compact branded bar)
# -------------------------
logo_base64 = None
for p in [ASSETS / "logo.png", ASSETS / "icon.png", ASSETS / "logo 1.png"]:
    if p.exists():
        logo_base64 = load_image_base64(p)
        break

if logo_base64:
    header_html = f"""
    <div class="app-header" style="align-items:center;">
      <img src="{logo_base64}" style="width:42px;height:42px;border-radius:8px;margin-right:12px"/>
      <div style="display:flex;flex-direction:column;">
        <div class="app-title">InkLink</div>
        <div class="app-subtitle">Smart LinkedIn Post Generator</div>
      </div>
    </div>
    """
else:
    header_html = """
    <div class="app-header" style="align-items:center;">
      <div style="display:flex;flex-direction:column;">
        <div class="app-title">InkLink</div>
        <div class="app-subtitle">Smart LinkedIn Post Generator</div>
      </div>
    </div>
    """
st.markdown(header_html, unsafe_allow_html=True)

# -------------------------
# Prompts & UI maps (full prompts for AI + short UI hints)
# -------------------------
TOPIC_PROMPT = (
    "Write a social media post centered on the given topic or keywords. The content should fully address "
    "this topic in a clear, engaging way and incorporate any provided keywords or ideas. Tailor the post "
    "according to the other parameters (objective, tone, length, etc.), ensuring relevance to the topic. "
    "Also include a separate note titled \"Visuals/Image options\" that suggests appropriate images or videos "
    "to accompany the post."
)

OBJECTIVE_PROMPTS = {
  "Engage": "Write an interactive social media post designed to engage the audience. Use a casual, friendly tone and start with a hook (for example, a question or playful challenge) that draws readers in. Encourage interaction by inviting comments or opinions. Make it concise and upbeat. Also include a separate note 'Visuals/Image options' suggesting relevant images or graphics that fit the question or theme.",
  "Educate": "Write an informative post that clearly explains the topic. Present key information or steps in a logical order (using bullet points or numbered lists if helpful). Use a neutral, authoritative tone and include any important facts or data. Highlight 2–3 key takeaways or conclusions. Also include a separate 'Visuals/Image options' note with ideas (e.g., infographics, diagrams, or illustrative images related to the explanation).",
  "Announce": "Write an enthusiastic announcement post about the topic (for example, a launch, event, or news update). Clearly explain what is happening and why it is important or exciting. Use an upbeat tone and include any details like dates or deadlines. Encourage readers to participate or stay tuned. Also include a separate 'Visuals/Image options' note suggesting images (e.g., event photos, product images) or design ideas for the announcement.",
  "Recruit": "Write a recruitment post aimed at attracting candidates or members. Describe the opportunity (role, program, etc.), highlight its benefits or impact, and speak to why someone would want to join. Use a motivating and positive tone that reflects the organization’s culture. End with a clear call-to-action (apply, DM, or learn more). Also include a separate 'Visuals/Image options' note with suggestions (e.g., team photos, workplace images, or career-themed graphics).",
  "Sell": "Write a promotional post highlighting a product, service, or offering. Start by emphasizing the main benefit to the reader. Include 2–3 key features or outcomes that demonstrate value. Use persuasive, benefit-focused language and include a proof point or testimonial if available. End with a strong call-to-action (like 'Sign up now', 'Get started', or 'Visit our website'). Also include a separate 'Visuals/Image options' note with ideas for complementary visuals (e.g., product photos, charts of results, or happy user images)."
}
OBJECTIVE_UI = {
  "Engage": "Spark conversation and get people to respond.",
  "Educate": "Share useful insights or tips clearly.",
  "Announce": "Highlight a milestone, launch, or news update.",
  "Recruit": "Invite people to join your team or project.",
  "Sell": "Promote your product, service, or solution."
}

TONE_PROMPTS = {
  "Professional": "Write in a formal, businesslike tone. Use clear and precise language, complete sentences, and avoid slang or casual expressions. Focus on credibility and authority. Also include a separate 'Visuals/Image options' note with suitable professional images (e.g., office or industry-related visuals).",
  "Friendly": "Write in a warm, conversational tone as if talking to a peer. Use simple language and contractions, and a friendly voice. Be approachable and upbeat. Also include a separate 'Visuals/Image options' note suggesting inviting visuals (e.g., a smiling person, friendly team photo).",
  "Inspirational": "Write in a motivational, uplifting tone. Use positive language and perhaps a brief metaphor or example that inspires. Encourage the reader to take action or feel hopeful. Also include a 'Visuals/Image options' note (e.g., an image of someone achieving a goal or an inspirational scene).",
  "Storytelling": "Write as a storyteller. Start with a hook (scene or personal anecdote), build a narrative with details (who, what, where), and finish with a clear lesson or takeaway. Use vivid, sensory language. Also include a 'Visuals/Image options' note (e.g., illustrations or photos that reflect key moments in the story).",
  "Witty or Quirky": "Write in a humorous, playful tone. Add a clever twist, pun, or light joke relevant to the topic (while keeping it respectful). Make it engaging and entertaining. Also include a 'Visuals/Image options' note (e.g., a funny illustration or meme-style image that matches the quirkiness).",
  "Thought Leader": "Write in an authoritative, expert tone. Present insights or opinions backed by knowledge or data. Use confident language and industry terminology appropriately. Position the speaker as an industry leader. Also include a 'Visuals/Image options' note (e.g., charts, graphs, or a photo of a speaking engagement)."
}
TONE_UI = {
  "Professional": "Polished, businesslike, and authoritative.",
  "Friendly": "Warm, conversational, and approachable.",
  "Inspirational": "Motivational, uplifting, short metaphors allowed.",
  "Storytelling": "Narrative-style: hook → story → lesson.",
  "Witty or Quirky": "Playful, light humor and wordplay.",
  "Thought Leader": "Confident, expert-level commentary."
}

TARGET_AUDIENCE_PROMPTS = {
  "Health & Wellbeing": "Tailor the post to an audience interested in health and wellness. Use examples and language relevant to health, fitness, or wellness trends. Emphasize well-being benefits. Also include a 'Visuals/Image options' note (e.g., healthy lifestyle images or wellness infographics).",
  "Engineering & Manufacturing": "Write for professionals in engineering or manufacturing. Use technical or industry-specific terms where appropriate. Highlight practical applications or innovations. Also include a 'Visuals/Image options' note (e.g., machinery photos, engineering diagrams).",
  "Real Estate & Construction": "Target real estate or construction professionals. Use terms like building, development, or market trends. Address industry challenges (e.g., sustainability or project management). Also include a 'Visuals/Image options' note (e.g., construction site photos or property images).",
  "Food & Beverages": "Focus on food and beverage industry readers. Use sensory language about taste or quality, and mention food trends or culinary terms. Also include a 'Visuals/Image options' note (e.g., appetizing food photos or kitchen scenes).",
  "Travel & Hospitality": "Write for travel and hospitality professionals or enthusiasts. Use vivid descriptions of places or service quality, and mention travel trends. Also include a 'Visuals/Image options' note (e.g., scenic travel images or happy guests).",
  "Retail & E-comm": "Target retail or e-commerce professionals. Use terms like shopping experience, customer service, or online sales. Mention trends like omnichannel or personalization. Also include a 'Visuals/Image options' note (e.g., product photos or store visuals).",
  "Finance": "Address financial industry readers. Use appropriate finance terms (e.g., investment, ROI) and focus on data or economic insights. Also include a 'Visuals/Image options' note (e.g., charts, graphs, or business imagery).",
  "Transportation & Logistics": "Write for transportation and logistics professionals. Use terms like supply chain, shipping, or freight. Mention efficiency or innovation in logistics. Also include a 'Visuals/Image options' note (e.g., trucks, shipping containers, or route maps).",
  "Marketing & Advertising": "Target marketing or advertising experts. Use industry buzzwords (e.g., branding, engagement, campaigns) and focus on strategy insights. Also include a 'Visuals/Image options' note (e.g., campaign graphics or creative imagery).",
  "Education & EdTech": "Write for educators or edtech professionals. Use terms like learning, curriculum, or technology in education. Emphasize teaching insights or tools. Also include a 'Visuals/Image options' note (e.g., classroom photos or educational graphics).",
  "Architecture & Design": "Address architects or designers. Use terms like design, innovation, or sustainability. Mention aesthetics or functionality. Also include a 'Visuals/Image options' note (e.g., building designs, design sketches, or blueprints).",
  "IT/SaaS/Technology": "Target IT and tech professionals. Use technical language (e.g., software, cloud, AI) and focus on innovation or problem-solving. Also include a 'Visuals/Image options' note (e.g., tech devices, code snippets, or futuristic graphics).",
  "For Everyone": "Write for a general audience. Use clear, non-technical language and broad examples. Avoid jargon. Make it engaging and inclusive. Also include a 'Visuals/Image options' note (e.g., general stock images or simple diagrams)."
}
TARGET_AUDIENCE_UI = {k: (v if len(v) < 60 else v.split('.')[0] + '.') for k, v in TARGET_AUDIENCE_PROMPTS.items()}

INDUSTRY_PROMPTS = {
  "Health & Wellbeing": "Assume the author is a professional in health and wellbeing. Write the post from that perspective, using industry knowledge or experience. Include terminology relevant to health and fitness. Also include a 'Visuals/Image options' note with health-related visuals.",
  "Engineering & Manufacturing": "Assume the author works in engineering or manufacturing. Use relevant technical terms and examples (e.g., products or processes). Write with an insider’s perspective. Also include a 'Visuals/Image options' note with industrial visuals.",
  "Real Estate & Construction": "Assume the author is in real estate or construction. Use industry terms (e.g., development, property). Refer to projects or market insights from that perspective. Also include a 'Visuals/Image options' note with real estate imagery.",
  "Food & Beverages": "Assume the author works in food and beverage. Use culinary language and examples. Discuss quality, taste, or production from a professional standpoint. Also include a 'Visuals/Image options' note with food industry images.",
  "Travel & Hospitality": "Assume the author is in travel or hospitality. Use terms like itinerary, guest experience, or tourism. Write with knowledge of travel industry trends. Also include a 'Visuals/Image options' note with travel-related photos.",
  "Retail & E-comm": "Assume the author works in retail or e-commerce. Use retail terminology and refer to online sales or customer experience. Also include a 'Visuals/Image options' note with retail visuals (stores, products, etc.).",
  "Finance": "Assume the author is a finance professional. Use financial terms (e.g., investment, market). Write with authority on economic or financial topics. Also include a 'Visuals/Image options' note with finance imagery (charts, currency, etc.).",
  "Transportation & Logistics": "Assume the author works in transportation or logistics. Use terms like supply chain, shipping, or fleet. Write as someone familiar with logistics operations. Also include a 'Visuals/Image options' note with transport images.",
  "Marketing & Advertising": "Assume the author is in marketing or advertising. Use marketing jargon (e.g., SEO, branding) and examples. Write from a marketer’s strategic perspective. Also include a 'Visuals:' note with marketing campaign visuals.",
  "Education & EdTech": "Assume the author works in education or edtech. Use education terminology (e.g., learning outcomes, edtech tools). Write with insight into teaching or educational tech. Also include a 'Visuals/Image options' note with educational visuals.",
  "Architecture & Design": "Assume the author is an architect or designer. Use design-related terms (e.g., blueprint, creativity). Discuss design principles or projects. Also include a 'Visuals/Image options' note with design/architecture imagery.",
  "IT/SaaS/Technology": "Assume the author works in technology or SaaS. Use tech terms (e.g., software, cloud). Write as a tech professional offering insight or expertise. Also include a 'Visuals/Image options' note with tech visuals.",
  "General post": "Make the post broadly resonant for maximum audience reach — avoid industry jargon and use universally relatable examples."
}
INDUSTRY_UI = {k: (v if len(v) < 70 else v.split('.')[0] + '.') for k, v in INDUSTRY_PROMPTS.items()}

CTA_PROMPTS = {
  "Surprise me": "No specific CTA is required; allow the AI to decide if a CTA fits organically.",
  "Visit a link": "Include a clear CTA inviting readers to visit a link or website.",
  "Comment": "Include a call-to-action asking readers to comment or share their opinions.",
  "Apply": "Include a CTA encouraging readers to apply or register.",
  "DM": "Include a CTA inviting readers to send a direct message for more information."
}
CTA_UI = {
  "Surprise me": "Let AI choose if a CTA fits.",
  "Visit a link": "Ask readers to visit a link (e.g., site).",
  "Comment": "Invite comments or opinions.",
  "Apply": "Ask people to apply/register.",
  "DM": "Prompt readers to DM for more info."
}

LENGTH_MAP = {
  "Short": "20–25 words: punchy hook + one line CTA.",
  "Medium": "50–80 words: hook + insight + CTA.",
  "Long": "100–150 words: more detail, maybe bullets.",
  "Really Long": "150–250 words: deep context, multiple paragraphs."
}
LENGTH_UI = LENGTH_MAP.copy()

# -------------------------
# UI Inputs
# -------------------------
st.markdown("### Inputs")
st.markdown("Fill the fields below. **Reference Post** is optional and will be used for *style only* (do not copy content).")

topic = st.text_area("Topic / Keywords / Your idea", placeholder="Enter the topic, keywords, or a short idea that the post should cover", height=120)

col1, col2 = st.columns(2)
with col1:
    objective = st.selectbox("Objective", options=list(OBJECTIVE_PROMPTS.keys()), index=0)
    st.markdown(f"<div style='color:#6c757d; font-style:italic'>{OBJECTIVE_UI[objective]}</div>", unsafe_allow_html=True)
with col2:
    tone = st.selectbox("Tone", options=list(TONE_PROMPTS.keys()), index=0)
    st.markdown(f"<div style='color:#6c757d; font-style:italic'>{TONE_UI[tone]}</div>", unsafe_allow_html=True)

humor_level = 0
humor_format = None
if tone == "Witty or Quirky":
    hcol1, hcol2 = st.columns([1,1])
    with hcol1:
        humor_level = st.slider("Humor intensity (0 = subtle, 10 = bold)", 0, 10, 6)
    with hcol2:
        humor_format = st.radio("Humor format", options=["One pun per paragraph", "Single joke line in parentheses"], index=1)
    st.markdown("<div style='color:#6c757d; font-style:italic'>How bold should the humor be?</div>", unsafe_allow_html=True)

col3, col4 = st.columns(2)
with col3:
    audience = st.selectbox("Target Audience", options=list(TARGET_AUDIENCE_PROMPTS.keys()), index=11)
    st.markdown(f"<div style='color:#6c757d; font-style:italic'>{TARGET_AUDIENCE_UI[audience]}</div>", unsafe_allow_html=True)
with col4:
    industry_options = list(INDUSTRY_PROMPTS.keys())
    industry = st.selectbox("Your Industry (author perspective)", options=industry_options, index=len(industry_options)-1)
    st.markdown(f"<div style='color:#6c757d; font-style:italic'>{INDUSTRY_UI[industry]}</div>", unsafe_allow_html=True)

col5, col6 = st.columns(2)
with col5:
    length = st.selectbox("Length", options=list(LENGTH_MAP.keys()), index=1)
    st.markdown(f"<div style='color:#6c757d; font-style:italic'>{LENGTH_UI[length]}</div>", unsafe_allow_html=True)
with col6:
    cta = st.selectbox("Call to Action (CTA)", options=list(CTA_PROMPTS.keys()), index=0)
    st.markdown(f"<div style='color:#6c757d; font-style:italic'>{CTA_UI[cta]}</div>", unsafe_allow_html=True)

ref_col1, ref_col2 = st.columns([2,1])
with ref_col1:
    reference_post = st.text_area("Reference Post (style only, optional)", placeholder="Paste a reference post to match its style, tone, and flow (optional)", height=160)
with ref_col2:
    num_drafts = st.select_slider("Number of drafts", options=[1,3,5], value=3)
    st.markdown("<div style='color:#6c757d; font-style:italic'>Choose 1, 3 or 5 variations.</div>", unsafe_allow_html=True)

style_strength = 0
if reference_post and reference_post.strip():
    style_strength = st.slider("Style Strength — how closely to match reference post's style (if provided)", 0, 100, 40)
    st.markdown("<div style='color:#6c757d; font-style:italic'>0% = ignore style; 100% = mimic punctuation & cadence closely (do NOT copy content).</div>", unsafe_allow_html=True)

st.markdown("---")
generate = st.button("🚀 Generate Posts", use_container_width=True)

# -------------------------
# Build system prompt
# -------------------------
def build_system_prompt():
    parts = [
        "You are an expert LinkedIn content creator and copywriter with experience producing high-performing professional social posts.",
        "Follow the instructions EXACTLY."
    ]
    parts.append(f"Topic prompt: {TOPIC_PROMPT}")
    parts.append(f"Objective prompt: {OBJECTIVE_PROMPTS[objective]}")
    parts.append(f"Tone prompt: {TONE_PROMPTS[tone]}")
    parts.append(f"Target audience prompt: {TARGET_AUDIENCE_PROMPTS[audience]}")
    parts.append(f"Industry prompt: {INDUSTRY_PROMPTS[industry]}")
    parts.append(f"Length guidance: {LENGTH_MAP[length]}")
    parts.append(f"CTA guidance: {CTA_PROMPTS[cta]}")

    if reference_post and reference_post.strip():
        parts.append(f"Style imitation: Mimic punctuation, sentence length, cadence, and flow of the Reference Post proportional to Style Strength: {style_strength}%. DO NOT copy factual content, unique examples, or exact phrasing — USE ONLY STYLE + RHYTHM.")

    if tone == "Witty or Quirky":
        parts.append("Humor rules: Keep humor light, constructive and LinkedIn-appropriate. Avoid insulting or mean humor.")
        if humor_format == "One pun per paragraph":
            parts.append("Humor format: Include one tasteful pun or piece of wordplay per paragraph (short phrase).")
        else:
            parts.append("Humor format: Include exactly one short joke/aside in parentheses somewhere in the post.")
        parts.append(f"Humor intensity (0-10): {humor_level} — higher means bolder puns and more playful metaphors.")

    parts.append(
        "Formatting rules — OUTPUT EXACTLY the following TWO labeled sections and nothing else:\n\n"
        "1) Post:\n<the LinkedIn-ready post text only — DO NOT include ANY visual/image suggestions or 'Visuals' wording here>.\n\n"
        "2) Visuals / Image options:\n<2–4 concrete image/video/creative suggestions with brief notes on usage (e.g., 'Slide 1: ...', 'Overlay text: ...')>.\n\n"
        "Additional constraints:\n"
        "- Use Reference Post only for STYLE (when provided). DO NOT copy examples/facts.\n"
        "- Keep posts LinkedIn-appropriate and non-abusive.\n"
        "- If Objective implies interaction, include a clear audience prompt in 'Post:'."
    )
    return "\n\n".join(parts)

# -------------------------
# Generate logic
# -------------------------
if generate:
    if not API_KEY:
        st.error("Missing GROQ API key. Add GROQ_API_KEY=gsk_... to your .env or Streamlit Secrets and restart.")
    elif not topic or not topic.strip():
        st.warning("Please add Topic / Keywords / Idea before generating.")
    else:
        if client is None:
            st.error("Groq client not initialized (missing key).")
        else:
            with st.spinner("Generating drafts..."):
                system_prompt = build_system_prompt()

                base_temp = 0.55
                if tone == "Witty or Quirky":
                    temp = min(0.95, base_temp + (humor_level * 0.04))
                else:
                    temp = min(0.8, base_temp + (style_strength / 500.0))

                drafts = []
                for idx in range(num_drafts):
                    attempt = 0
                    generated_raw = ""
                    while attempt < 2:
                        attempt += 1
                        try:
                            user_message = (
                                f"Topic/Keywords (MAIN CONTENT):\n{topic.strip()}\n\n"
                                f"Reference Post (style only):\n{reference_post.strip() if reference_post and reference_post.strip() else 'None'}\n\n"
                                "Produce output with EXACTLY two labeled sections: 'Post:' and 'Visuals / Image options:'."
                            )
                            resp = client.chat.completions.create(
                                model="llama-3.1-8b-instant",
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_message}
                                ],
                                temperature=float(temp),
                                max_tokens=900
                            )
                            raw = resp.choices[0].message.content.strip()

                            lines = raw.splitlines()
                            if lines and lines[0].lower().startswith(("draft", "1)", "---")):
                                raw = "\n".join(lines[1:]).strip()

                            if is_incomplete_text(raw) and attempt < 2:
                                time.sleep(0.35)
                                continue

                            generated_raw = raw
                            break
                        except Exception as exc:
                            generated_raw = f"[Error generating draft: {exc}]\n\n{traceback.format_exc()}"
                            break

                    drafts.append(generated_raw if generated_raw else "[No content generated]")

                # Output UI
                st.subheader("✨ Generated Drafts")
                all_for_download = []
                for i, raw in enumerate(drafts, start=1):
                    st.markdown(f"### Draft {i}")
                    post_text, visuals_text = split_post_and_visuals(raw)
                    post_text = remove_visual_lines_from_post(post_text)

                    colL, colR = st.columns([3, 1])
                    with colL:
                        st.markdown("**Post (ready to publish)**")
                        st.text_area(f"Draft {i} — Post (select to copy)", value=post_text, height=220, key=f"post_{i}")
                        render_copy_button_iframe(post_text, label=f"📋 Copy Post {i}", bg="#2563eb")
                        st.download_button(label=f"⬇️ Download Post {i}", data=post_text, file_name=f"linkedin_post_{i}.txt", mime="text/plain", key=f"dl_post_{i}")

                    with colR:
                        st.markdown("**Visuals / Image options**")
                        if not visuals_text.strip():
                            visuals_text = ("Image idea: e.g., a clean photo of a professional at work; "
                                            "Infographic: 3 bullet benefits; Short video idea: 15s talking head with captions.")
                        st.text_area(f"Draft {i} — Visuals", value=visuals_text, height=220, key=f"vis_{i}")
                        render_copy_button_iframe(visuals_text, label="📋 Copy Visuals", bg="#10b981")
                        st.download_button(label=f"⬇️ Download Visuals {i}", data=visuals_text, file_name=f"linkedin_post_{i}_visuals.txt", mime="text/plain", key=f"dl_vis_{i}")

                    st.markdown("---")
                    all_for_download.append(f"--- Draft {i} ---\nPost:\n{post_text}\n\nVisuals:\n{visuals_text}\n\n")

                joined = "\n".join(all_for_download)
                st.download_button("⬇️ Download ALL Drafts (.txt)", data=joined, file_name="linkedin_all_drafts.txt", mime="text/plain")

                # end (no success banner to avoid layout clutter)
