import streamlit as st
import datetime
import re
import json
import os
from collections import Counter

st.set_page_config(page_title="Tweet Factory 🐦", layout="wide")

# --- Persistent Storage ---
CALENDAR_FILE = "content_calendar.json"
USE_SUPABASE = False

try:
    from supabase import create_client
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        USE_SUPABASE = True
except:
    pass

def load_json(filepath, default):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_calendar():
    if USE_SUPABASE:
        try:
            res = supabase.table("content_calendar").select("*").order("id").execute()
            cal = {}
            for r in res.data:
                d = r["date"]
                entry = {"id": r["id"], "tweet": r["tweet"], "category": r["category"], "status": r["status"]}
                if d not in cal:
                    cal[d] = []
                cal[d].append(entry)
            return cal
        except:
            return {}
    raw = load_json(CALENDAR_FILE, {})
    cal = {}
    for date_str, val in raw.items():
        if isinstance(val, list):
            cal[date_str] = val
        elif isinstance(val, dict):
            cal[date_str] = [val]
    if cal != raw:
        save_json(CALENDAR_FILE, cal)
    return cal

def save_calendar_entry(date_str, tweet, category, status="Scheduled"):
    if USE_SUPABASE:
        try:
            supabase.table("content_calendar").insert({"date": date_str, "tweet": tweet, "category": category, "status": status}).execute()
        except Exception as e:
            st.error(f"Supabase error: {e}")
    else:
        cal = load_calendar()
        if date_str not in cal:
            cal[date_str] = []
        cal[date_str].append({"tweet": tweet, "category": category, "status": status})
        save_json(CALENDAR_FILE, cal)

def delete_calendar_entry(date_str, entry_index):
    if USE_SUPABASE:
        cal = load_calendar()
        if date_str in cal and entry_index < len(cal[date_str]):
            entry = cal[date_str][entry_index]
            if "id" in entry:
                supabase.table("content_calendar").delete().eq("id", entry["id"]).execute()
    else:
        cal = load_calendar()
        if date_str in cal and entry_index < len(cal[date_str]):
            cal[date_str].pop(entry_index)
            if not cal[date_str]:
                del cal[date_str]
            save_json(CALENDAR_FILE, cal)

def update_calendar_entry_status(date_str, entry_index, status):
    if USE_SUPABASE:
        cal = load_calendar()
        if date_str in cal and entry_index < len(cal[date_str]):
            entry = cal[date_str][entry_index]
            if "id" in entry:
                supabase.table("content_calendar").update({"status": status}).eq("id", entry["id"]).execute()
    else:
        cal = load_calendar()
        if date_str in cal and entry_index < len(cal[date_str]):
            cal[date_str][entry_index]["status"] = status
            save_json(CALENDAR_FILE, cal)

if "calendar" not in st.session_state:
    st.session_state.calendar = load_calendar()

# --- Prompt Categories ---
PROMPT_CATEGORIES = {
    "📈 Storytelling & 10 EMA Importance": [
        """Research {stock_name} (NSE) and write a single tweet in storytelling format about a friend who bought this stock during its recent hype phase for a short-term swing trade of 15-25 sessions.

You must research and fill in ALL of the following yourself:
- Find the real news catalyst that drove the stock's rally
- Identify which media outlets and platforms hyped it (ET Now, Moneycontrol, YouTube finfluencers, WhatsApp groups, Instagram reels)
- Find how much the stock had already rallied before the hype peak entry
- Create a realistic week-by-week price breakdown — stock initially goes up, then slowly cracks while media stays bullish, then crashes
- Use the actual current price to calculate the total loss %
- He didn't sell because the story felt too strong, turning a swing trade into a fake 'long-term investment'

The lesson part:
- Show how the chart revealed the stock was parabolic/overextended with no structure or base near the highs
- Show how a simple '10 EMA daily close exit rule' would have gotten him out early with just a 3-8% loss
- End with a one-line raw lesson contrasting media vs chart

Tone: Raw, real, conversational. Like telling a story at a chai stall.
Format: Under 1000 characters. Short punchy lines. Emojis sparingly (only 🚀 for hype sarcasm).
End with: #SwingTrading #PriceAction #SwingDNA #TechnicalAnalysis #FOMO #TradingPsychology #ChartStudy #NiftyTrader and the stock's ticker hashtag.""",

        """Research {stock_name} (NSE) and write a single tweet as a quiet, reflective observation about a trader you know who got stuck in this stock.

You must research and fill in ALL of the following yourself:
- The real catalyst/news that drove the stock's rally
- How much the stock had already run up before this person entered near the top
- The current price and approximate loss % from peak
- One specific media headline or hype source that gave him conviction to hold

Structure (keep under 1400 characters):
1. Open with a calm one-liner about the person — not dramatic, just factual.
2. Briefly mention why — the news, the hype, the "obvious" trade
3. One line on what the chart actually looked like at entry (parabolic, no base, far from any moving average)
4. Where the stock is now. The loss %. No panic — just quiet math.
5. How "quick swing trade" quietly became "I'll hold for long term" without him ever saying it out loud
6. What the 10 EMA daily close rule would have done — small loss, capital intact, next trade ready
7. Final one-liner lesson — quiet truth about stories vs charts.

Tone: No exclamation marks. No ALL CAPS. No sarcasm. Write like you're journaling. Short lines. Only emoji: 📉 (once).
End with: #SwingTrading #SwingDNA and the stock's ticker hashtag.""",
    ],
    "🎓 Educational / Teaching": [
        "Explain {concept} in a simple tweet for beginner traders.",
        "Write a 'Did you know?' style tweet about a lesser-known trading concept: {concept}.",
        "Create a tweet thread outline (3-5 tweets) teaching {topic} to new traders.",
        "Write a tweet busting a common trading myth: {myth}.",
    ],
    "💡 Trading Tips & Mindset": [
        "Write a motivational trading discipline tweet about {topic}.",
        "Create a 'Mistake I made early in trading' style tweet about {mistake}.",
        "Write a tweet sharing one actionable swing trading tip for the week.",
        "Draft a tweet about the importance of {habit} in a trader's routine.",
    ],
    "🔥 Engagement / Viral": [
        "Write a polarizing opinion tweet about {topic} in the Indian stock market.",
        "Create a 'Hot take' tweet about {topic} that will get replies.",
        "Write a relatable 'trader life' tweet that swing traders will relate to.",
        "Draft a tweet asking followers a question about their trading: {question}.",
    ],
    "🛠️ Tool / Dashboard Promo": [
        "Write a tweet promoting my Swing DNA dashboard. Highlight {feature} without being too salesy.",
        "Create a tweet showing a sneak peek of a new feature I built: {feature}.",
        "Write a tweet about why I built my own trading tools instead of relying on paid ones.",
        "Draft a tweet inviting traders to try my free sector rotation dashboard.",
    ],
    "📊 Chart / Setup Sharing": [
        "Write a caption tweet for a {stock} chart screenshot showing a {pattern} setup.",
        "Create a tweet sharing a watchlist of 3-5 stocks with brief reasoning for each.",
        "Write a tweet about a textbook {pattern} forming on {stock} chart.",
        "Draft a tweet about a breakout/breakdown happening on {stock} with key levels.",
    ],
}

CATEGORY_SHORT = {
    "📈 Storytelling & 10 EMA Importance": "📈 Storytelling",
    "🎓 Educational / Teaching": "🎓 Educational",
    "💡 Trading Tips & Mindset": "💡 Mindset",
    "🔥 Engagement / Viral": "🔥 Viral",
    "🛠️ Tool / Dashboard Promo": "🛠️ Promo",
    "📊 Chart / Setup Sharing": "📊 Chart Setup",
}

DAY_THEMES = {
    "Monday": "📈 Storytelling & 10 EMA Importance",
    "Tuesday": "🎓 Educational / Teaching",
    "Wednesday": "💡 Trading Tips & Mindset",
    "Thursday": "📊 Chart / Setup Sharing",
    "Friday": "📈 Storytelling & 10 EMA Importance",
    "Saturday": "🔥 Engagement / Viral",
    "Sunday": "🛠️ Tool / Dashboard Promo",
}

ALL_CATEGORIES = list(PROMPT_CATEGORIES.keys())

# --- Helper: get all tweets from calendar ---
def get_all_tweets_from_calendar(cal):
    all_tweets = []
    for date_str in sorted(cal.keys()):
        for entry in cal[date_str]:
            all_tweets.append({**entry, "date": date_str})
    return all_tweets

# ============ UI ============
st.title("🐦 Tweet Factory")
tab_generate, tab_calendar, tab_archive = st.tabs(["✍️ Generate", "📅 Content Calendar", "📝 All Tweets"])

# ============ TAB 1: GENERATE ============
with tab_generate:

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("1️⃣ Category & Prompt")
        category = st.selectbox("Content Category", ALL_CATEGORIES)
        prompts = PROMPT_CATEGORIES[category]
        prompt_labels = []
        for idx, p in enumerate(prompts):
            first_line = p.strip().split("\n")[0][:70]
            prompt_labels.append(f"Prompt {idx+1}: {first_line}...")
        selected_idx = st.selectbox("Prompt Template", range(len(prompts)), format_func=lambda x: prompt_labels[x])
        selected_prompt = prompts[selected_idx]

        st.markdown("---")
        st.subheader("2️⃣ Customize")

        variables = re.findall(r'\{(\w+)\}', selected_prompt)
        seen = set()
        unique_vars = []
        for v in variables:
            if v not in seen:
                seen.add(v)
                unique_vars.append(v)

        var_values = {}
        for var in unique_vars:
            label = var.replace("_", " ").title()
            var_values[var] = st.text_input(f"{label}", key=f"var_{category}_{selected_idx}_{var}", placeholder=f"Enter {label}")

        tone = st.selectbox("Tone", ["Raw & Conversational", "Calm & Observational", "Professional", "Casual", "Bold / Edgy", "Motivational", "Humorous"])
        col_a, col_b = st.columns(2)
        with col_a:
            add_hashtags = st.checkbox("Include hashtags", value=True)
        with col_b:
            add_emoji = st.checkbox("Include emojis", value=True)

        custom_instruction = st.text_area("Additional instructions (optional)", height=60,
                                           placeholder="e.g., mention @SwingDNA, keep it punchy...")

        final_prompt = selected_prompt
        for var, val in var_values.items():
            if val:
                final_prompt = final_prompt.replace("{" + var + "}", val)

        system_prompt = f"""You are a finance content creator on Twitter/X focused on Indian stock market swing trading and technical analysis.
Tone: {tone}
{"Add relevant hashtags at the end." if add_hashtags else "No hashtags."}
{"Use emojis as specified in the prompt." if add_emoji else "No emojis."}
{custom_instruction if custom_instruction else ""}"""

        full_prompt = f"SYSTEM: {system_prompt}\n\nTASK: {final_prompt}"

        st.markdown("---")
        st.subheader("4️⃣ Paste & Save")
        generated = st.text_area("Paste AI-generated tweet", height=150, key="gen_tweet")

        if generated:
            char_count = len(generated)
            if char_count <= 280:
                st.success(f"✅ {char_count}/280 chars")
            elif char_count <= 1400:
                st.info(f"📝 {char_count}/1400 chars")
            else:
                st.warning(f"⚠️ {char_count} chars — trim it")

        save_category = st.selectbox("Save as category", ALL_CATEGORIES, key="save_cat")
        schedule_date = st.date_input("Schedule for", value=datetime.date.today(), key="schedule_date")

        if st.button("📅 Save to Calendar", use_container_width=True):
            if generated:
                save_calendar_entry(str(schedule_date), generated, save_category)
                st.session_state.calendar = load_calendar()
                st.success(f"✅ Saved to {schedule_date}!")
            else:
                st.warning("Paste a tweet first!")

    with col_right:
        st.subheader("3️⃣ Copy Prompt")
        st.code(full_prompt, language="text")
        st.caption("👆 Copy → Perplexity (Claude Sonnet) → Paste on the left")

        st.markdown("---")
        st.subheader("📊 Week Plan")

        today = datetime.date.today()
        start_of_week = today - datetime.timedelta(days=today.weekday())
        week_dates = [start_of_week + datetime.timedelta(days=i) for i in range(7)]
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        cal = load_calendar()
        st.session_state.calendar = cal

        week_categories = []
        for d in week_dates:
            ds = str(d)
            if ds in cal:
                for entry in cal[ds]:
                    week_categories.append(entry["category"])

        total_scheduled = len(week_categories)
        days_with_content = sum(1 for d in week_dates if str(d) in cal)
        empty_days = 7 - days_with_content

        if empty_days > 0:
            st.warning(f"⚠️ {empty_days} day{'s' if empty_days > 1 else ''} empty!")
        else:
            st.success("🎯 All days covered!")

        st.caption(f"**{total_scheduled} tweets** across **{days_with_content} days**")

        day_col, mix_col = st.columns([1.8, 1])

        with day_col:
            st.markdown("#### Day View")
            for i, d in enumerate(week_dates):
                ds = str(d)
                is_today = d == today
                prefix = "→ " if is_today else "  "
                day_label = f"{prefix}{day_names[i]} {d.strftime('%d')}"

                if ds in cal:
                    entries = cal[ds]
                    cat_tags = []
                    for e in entries:
                        short = CATEGORY_SHORT.get(e["category"], e["category"])
                        tag = "(P)" if e.get("status") == "Posted" else "(S)"
                        cat_tags.append(f"{short} {tag}")
                    cats_str = ", ".join(cat_tags)
                    st.markdown(f"**{day_label}** — {cats_str}")
                else:
                    if d < today:
                        st.markdown(f"**{day_label}** — 🔴 Missed")
                    elif is_today:
                        st.markdown(f"**{day_label}** — ⚠️ Empty")
                    else:
                        st.markdown(f"**{day_label}** — ⬜ Empty")

        with mix_col:
            st.markdown("#### Category Mix")
            if week_categories:
                counts = Counter(week_categories)
                for cat, count in counts.most_common():
                    short = CATEGORY_SHORT.get(cat, cat)
                    st.markdown(f"**{count}x** {short}")
            else:
                st.caption("Nothing scheduled yet.")

            st.markdown("---")
            st.markdown("#### Next Week")
            next_start = start_of_week + datetime.timedelta(weeks=1)
            next_dates = [next_start + datetime.timedelta(days=i) for i in range(7)]
            next_cats = []
            for d in next_dates:
                ds = str(d)
                if ds in cal:
                    for entry in cal[ds]:
                        next_cats.append(entry["category"])

            if not next_cats:
                st.caption("Nothing scheduled yet.")
            else:
                next_counts = Counter(next_cats)
                for cat, count in next_counts.most_common():
                    short = CATEGORY_SHORT.get(cat, cat)
                    st.markdown(f"**{count}x** {short}")

# ============ TAB 2: CONTENT CALENDAR ============
with tab_calendar:
    st.subheader("📅 Content Calendar")

    today = datetime.date.today()

    col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])
    if "week_offset" not in st.session_state:
        st.session_state.week_offset = 0
    with col_nav1:
        if st.button("← Previous Week"):
            st.session_state.week_offset -= 1
            st.rerun()
    with col_nav3:
        if st.button("Next Week →"):
            st.session_state.week_offset += 1
            st.rerun()
    with col_nav2:
        if st.button("📍 This Week"):
            st.session_state.week_offset = 0
            st.rerun()

    start_of_week = today + datetime.timedelta(weeks=st.session_state.week_offset)
    start_of_week = start_of_week - datetime.timedelta(days=start_of_week.weekday())
    week_dates = [start_of_week + datetime.timedelta(days=i) for i in range(7)]

    cal = load_calendar()
    st.session_state.calendar = cal

    st.markdown(f"### Week of {week_dates[0].strftime('%b %d')} — {week_dates[6].strftime('%b %d, %Y')}")

    total_entries = sum(len(cal.get(str(d), [])) for d in week_dates)
    days_filled = sum(1 for d in week_dates if str(d) in cal)
    total_posted = sum(1 for d in week_dates for e in cal.get(str(d), []) if e.get("status") == "Posted")
    empty_days = 7 - days_filled

    s1, s2, s3 = st.columns(3)
    with s1:
        st.metric("📝 Scheduled", total_entries)
    with s2:
        st.metric("✅ Posted", total_posted)
    with s3:
        if empty_days > 0:
            st.metric("⚠️ Empty Days", empty_days)
        else:
            st.metric("🎯 Empty Days", "0 — All set!")

    st.markdown("---")

    day_names_full = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for i, d in enumerate(week_dates):
        date_str = str(d)
        day_name = day_names_full[i]
        theme = DAY_THEMES.get(day_name, "")
        is_today = d == today
        has_content = date_str in cal and len(cal[date_str]) > 0
        entry_count = len(cal.get(date_str, []))

        if is_today:
            header = f"🔵 {day_name}, {d.strftime('%b %d')} — TODAY ({entry_count} tweet{'s' if entry_count != 1 else ''})"
        elif d < today and not has_content:
            header = f"🔴 {day_name}, {d.strftime('%b %d')} — MISSED"
        elif has_content:
            all_posted = all(e.get("status") == "Posted" for e in cal[date_str])
            if all_posted:
                header = f"✅ {day_name}, {d.strftime('%b %d')} — ALL POSTED ({entry_count})"
            else:
                header = f"📝 {day_name}, {d.strftime('%b %d')} — {entry_count} tweet{'s' if entry_count != 1 else ''} ready"
        else:
            header = f"⬜ {day_name}, {d.strftime('%b %d')} — EMPTY"

        with st.expander(header, expanded=is_today):
            st.caption(f"Suggested theme: {theme}")

            if has_content:
                for ei, entry in enumerate(cal[date_str]):
                    short = CATEGORY_SHORT.get(entry["category"], entry["category"])
                    status = entry.get("status", "Scheduled")
                    st.markdown(f"---")
                    st.markdown(f"**Tweet {ei+1}** — {short} [{status}]")
                    st.text_area("", entry["tweet"], height=100, key=f"cal_{date_str}_{ei}", disabled=True)

                    b1, b2, b3 = st.columns(3)
                    with b1:
                        if st.button("📋 Copy", key=f"copy_{date_str}_{ei}"):
                            st.code(entry["tweet"])
                            st.info("👆 Select all & copy")
                    with b2:
                        if status != "Posted":
                            if st.button("✅ Posted", key=f"calpost_{date_str}_{ei}"):
                                update_calendar_entry_status(date_str, ei, "Posted")
                                st.session_state.calendar = load_calendar()
                                st.rerun()
                    with b3:
                        if st.button("🗑️ Remove", key=f"caldel_{date_str}_{ei}"):
                            delete_calendar_entry(date_str, ei)
                            st.session_state.calendar = load_calendar()
                            st.rerun()
            else:
                st.warning("No posts scheduled. Go to Generate tab to create one.")

# ============ TAB 3: ALL TWEETS (ARCHIVE) ============
with tab_archive:
    st.subheader("📝 All Tweets")
    st.caption("Every tweet saved to the calendar — your complete archive.")

    cal = load_calendar()
    all_tweets = get_all_tweets_from_calendar(cal)

    if all_tweets:
        filter_status = st.radio("Filter", ["All", "Scheduled", "Posted"], horizontal=True, key="archive_filter")
        if filter_status != "All":
            all_tweets = [t for t in all_tweets if t.get("status") == filter_status]

        st.caption(f"Showing {len(all_tweets)} tweets")

        for i, tweet in enumerate(all_tweets):
            short = CATEGORY_SHORT.get(tweet["category"], tweet["category"])
            status = tweet.get("status", "Scheduled")
            with st.expander(f"{short} — {tweet['date']} [{status}]"):
                st.write(tweet["tweet"])
                if status != "Posted":
                    if st.button("✅ Mark Posted", key=f"arc_post_{tweet['date']}_{i}"):
                        date_entries = cal.get(tweet["date"], [])
                        for ei, e in enumerate(date_entries):
                            if e["tweet"] == tweet["tweet"]:
                                update_calendar_entry_status(tweet["date"], ei, "Posted")
                                st.session_state.calendar = load_calendar()
                                st.rerun()
                                break

        st.markdown("---")
        csv_data = "Date,Category,Status,Tweet\n"
        for t in all_tweets:
            tweet_escaped = t['tweet'].replace('"', '""')
            csv_data += f"{t['date']},\"{t['category']}\",{t.get('status','Scheduled')},\"{tweet_escaped}\"\n"
        st.download_button("📥 Export All Tweets CSV", csv_data, "all_tweets.csv", "text/csv")
    else:
        st.info("No tweets yet. Go to Generate tab!")

# --- Sidebar: Stats from Calendar ---
with st.sidebar:
    st.header("📊 Stats")
    cal = st.session_state.calendar
    all_tweets = get_all_tweets_from_calendar(cal)
    total = len(all_tweets)
    posted = len([t for t in all_tweets if t.get("status") == "Posted"])
    scheduled = total - posted

    st.metric("Total Tweets", total)
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Scheduled", scheduled)
    with c2:
        st.metric("Posted", posted)

    st.markdown("---")
    today = datetime.date.today()
    next_7 = [str(today + datetime.timedelta(days=i)) for i in range(7)]
    upcoming_days = sum(1 for d in next_7 if d in cal)
    upcoming_tweets = sum(len(cal.get(d, [])) for d in next_7)
    st.metric("Next 7 Days", f"{upcoming_days}/7 days covered")
    st.caption("Tweets Lined Up", upcoming_tweets)
    if upcoming_days < 7:
        st.warning(f"⚠️ {7 - upcoming_days} days need content!")
    else:
        st.success("🎯 Week fully planned!")

    if USE_SUPABASE:
        st.markdown("---")
        st.success("☁️ Supabase connected")
    else:
        st.markdown("---")
        st.warning("💾 Local storage mode")
