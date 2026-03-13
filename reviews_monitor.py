from apify_client import ApifyClient
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from datetime import datetime
from collections import Counter
from jinja2 import Template
import base64
import re
from io import BytesIO
from config import APIFY_TOKEN


CONFIG = {
    "apify_token": APIFY_TOKEN,

    "brands": [
        {
            "name": "Hoa Nail Beauty",
            "google_maps_url": "https://www.google.com/maps/place/Hoa+Nail+%26+Beauty/@50.8357334,4.3536228,17z/data=!3m1!4b1!4m6!3m5!1s0x47c3c5bd1a6c50c5:0x44d5970a2d11a01b!8m2!3d50.8357334!4d4.3561977!16s%2Fg%2F11gy00q0wd?entry=ttu&g_ep=EgoyMDI2MDMxMC4wIKXMDSoASAFQAw%3D%3D",
        },
        {
            "name": "Happy Nails",
            "google_maps_url": "https://www.google.com/maps/place/Happy+Nails/@50.8487327,4.3441999,17z/data=!3m1!4b1!4m6!3m5!1s0x47c3c3315ad98be7:0xb149d0678ceb4b4b!8m2!3d50.8487327!4d4.3467748!16s%2Fg%2F11h5rfrrdy?entry=ttu&g_ep=EgoyMDI2MDMxMC4wIKXMDSoASAFQAw%3D%3D",
        },
        {
            "name": "TY Nails",
            "google_maps_url": "https://www.google.com/maps/place/TY+Nails+%26+Spa+-+Brussel/@50.85166,4.3421581,17z/data=!3m1!4b1!4m6!3m5!1s0x47c3c3171cb4634d:0x347948ca6f76cba0!8m2!3d50.85166!4d4.344733!16s%2Fg%2F11fkcdqrdh?entry=ttu&g_ep=EgoyMDI2MDMxMC4wIKXMDSoASAFQAw%3D%3D",
        },
    ],

    "reviews_per_brand": 100,      
    "output_file": "reviews_report.html",
    "language": "en",               
}


POSITIVE_KEYWORDS = [
    "great", "excellent", "amazing", "love", "best", "perfect",
    "professional", "recommend", "helpful", "fast", "easy", "good"
]


NEGATIVE_KEYWORDS = [
    "bad", "terrible", "awful", "worst", "slow", "rude", "wrong",
    "never", "disappointed", "poor", "horrible", "waste", "useless"
]

BRAND_COLORS = ["#0077B6", "#1a6b4a", "#c8401a", "#7b2d8b", "#e07b00"]


def fetch_reviews(client, brand):
    """Pull Google reviews for a brand using Apify."""
    print(f"  → Fetching reviews for: {brand['name']}")
    run_input = {
        "startUrls": [{"url": brand["google_maps_url"]}],
        "maxReviews": CONFIG["reviews_per_brand"],
        "reviewsSort": "newest",
        "language": CONFIG["language"],
    }
    try:
        run = client.actor("Xb8osYTtOjlsgI6k9").call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        reviews = []

        def clean(val, default=""):
            """Return val if it's a non-empty string, else default."""
            return val if isinstance(val, str) and val.strip() else default

        def clean_rating(val):
            try:
                return int(float(val))
            except (TypeError, ValueError):
                return 0

        for item in items:
            if "text" in item or "stars" in item:
                reviews.append({
                    "brand":    brand["name"],
                    "rating":   clean_rating(item.get("stars", item.get("rating", 0))),
                    "text":     clean(item.get("text", item.get("reviewText", ""))),
                    "date":     clean(item.get("publishedAtDate", item.get("date", ""))),
                    "likes":    int(item.get("likesCount", 0) or 0),
                    "reviewer": clean(item.get("name", item.get("reviewerName", "")), "Anonymous"),
                })
            elif "reviews" in item:
                for review in item.get("reviews", []):
                    reviews.append({
                        "brand":    brand["name"],
                        "rating":   clean_rating(review.get("stars", review.get("rating", 0))),
                        "text":     clean(review.get("text", review.get("reviewText", ""))),
                        "date":     clean(review.get("publishedAtDate", review.get("date", ""))),
                        "likes":    int(review.get("likesCount", 0) or 0),
                        "reviewer": clean(review.get("name", review.get("reviewerName", "")), "Anonymous"),
                    })
        print(f"     ✓ {len(reviews)} reviews fetched")
        return reviews
    except Exception as e:
        print(f"     ⚠ Error fetching {brand['name']}: {e}")
        return []


def simple_sentiment(text):
    """Basic keyword-based sentiment scoring."""
    if not text or not isinstance(text, str):
        return "neutral"
    text_lower = text.lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"

def extract_top_keywords(texts, n=15):
    """Extract most common meaningful words from review texts."""
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "is", "was", "are", "were", "be", "been", "have", "had",
        "has", "this", "that", "they", "them", "their", "it", "its", "i", "my",
        "we", "our", "you", "your", "very", "so", "not", "no", "just", "really",
        "also", "from", "by", "as", "if", "would", "will", "can", "could", "get"
    }
    words = []
    for text in texts:
        if text and isinstance(text, str):
            tokens = re.findall(r'\b[a-z]{3,}\b', text.lower())
            words.extend([w for w in tokens if w not in stopwords])
    return Counter(words).most_common(n)


def analyze(df):
    """Build per-brand summary stats."""
    results = []
    for brand in df["brand"].unique():
        sub = df[df["brand"] == brand]
        sentiments = sub["sentiment"].value_counts()
        results.append({
            "brand":        brand,
            "total":        len(sub),
            "avg_rating":   round(sub["rating"].mean(), 2),
            "positive":     int(sentiments.get("positive", 0)),
            "neutral":      int(sentiments.get("neutral", 0)),
            "negative":     int(sentiments.get("negative", 0)),
            "positive_pct": round(sentiments.get("positive", 0) / len(sub) * 100, 1),
            "negative_pct": round(sentiments.get("negative", 0) / len(sub) * 100, 1),
            "top_keywords": extract_top_keywords(sub["text"].tolist(), n=8),
        })
    return results


def fig_to_base64(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=130)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

def chart_avg_ratings(summary):
    brands = [s["brand"] for s in summary]
    ratings = [s["avg_rating"] for s in summary]
    colors = BRAND_COLORS[:len(brands)]
    fig, ax = plt.subplots(figsize=(8, 3.5))
    bars = ax.bar(brands, ratings, color=colors, width=0.5)
    ax.set_ylim(0, 5.5)
    ax.set_ylabel("Average Rating")
    ax.set_title("Average Rating by Brand", fontsize=12, fontweight="bold")
    for bar, val in zip(bars, ratings):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f"⭐ {val}", ha="center", fontsize=10, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig_to_base64(fig)

def chart_sentiment_breakdown(summary):
    brands = [s["brand"] for s in summary]
    positives = [s["positive_pct"] for s in summary]
    negatives = [s["negative_pct"] for s in summary]
    neutrals = [100 - s["positive_pct"] - s["negative_pct"] for s in summary]
    x = range(len(brands))
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.bar(x, positives, label="Positive", color="#1a6b4a")
    ax.bar(x, neutrals, bottom=positives, label="Neutral", color="#d9d4c7")
    ax.bar(x, negatives, bottom=[p + n for p, n in zip(positives, neutrals)],
           label="Negative", color="#c8401a")
    ax.set_xticks(list(x))
    ax.set_xticklabels(brands)
    ax.set_ylabel("% of Reviews")
    ax.set_title("Sentiment Breakdown by Brand", fontsize=12, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig_to_base64(fig)

def chart_rating_distribution(df):
    fig, axes = plt.subplots(1, len(df["brand"].unique()),
                             figsize=(4 * len(df["brand"].unique()), 3.5),
                             sharey=True)
    if len(df["brand"].unique()) == 1:
        axes = [axes]
    for ax, (brand, color) in zip(axes, zip(df["brand"].unique(), BRAND_COLORS)):
        sub = df[df["brand"] == brand]
        counts = sub["rating"].value_counts().sort_index()
        ax.bar(counts.index, counts.values, color=color)
        ax.set_title(brand, fontsize=10, fontweight="bold")
        ax.set_xlabel("Stars")
        ax.set_xticks([1, 2, 3, 4, 5])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[0].set_ylabel("Reviews")
    fig.suptitle("Rating Distribution", fontsize=12, fontweight="bold")
    fig.tight_layout()
    return fig_to_base64(fig)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Reviews & Sentiment Report — {{ generated_at }}</title>
<style>
  :root {
    --ink: #0d1117; --paper: #f5f2eb; --accent: #0077B6;
    --green: #1a6b4a; --red: #c8401a; --muted: #6b6560;
    --border: #d9d4c7; --card: #ffffff;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: var(--paper); color: var(--ink); font-size: 15px; line-height: 1.6; }
  .container { max-width: 1100px; margin: auto; padding: 40px 24px; }
  h1 { font-size: 26px; color: var(--accent); margin-bottom: 4px; }
  .subtitle { color: var(--muted); font-size: 13px; margin-bottom: 32px; font-family: monospace; }

  /* KPI grid */
  .brand-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 16px; margin-bottom: 32px; }
  .brand-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
                padding: 20px 24px; border-top: 4px solid var(--accent); }
  .brand-card:nth-child(2) { border-top-color: var(--green); }
  .brand-card:nth-child(3) { border-top-color: var(--red); }
  .brand-name { font-size: 13px; font-weight: 600; color: var(--muted);
                text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
  .brand-rating { font-size: 36px; font-weight: 700; color: var(--ink); line-height: 1; }
  .brand-rating span { font-size: 14px; color: var(--muted); font-weight: 400; }
  .brand-meta { font-size: 12px; color: var(--muted); margin-top: 8px; }
  .sentiment-bar { display: flex; height: 6px; border-radius: 3px; overflow: hidden;
                   margin-top: 12px; gap: 2px; }
  .bar-pos { background: var(--green); }
  .bar-neu { background: var(--border); }
  .bar-neg { background: var(--red); }

  /* Charts */
  .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }
  .chart-box { background: var(--card); border: 1px solid var(--border);
               border-radius: 10px; padding: 20px; }
  img.chart { width: 100%; }

  /* Section */
  .section { background: var(--card); border: 1px solid var(--border);
             border-radius: 10px; padding: 24px; margin-bottom: 24px; }
  .section h2 { font-size: 16px; font-weight: 600; margin-bottom: 16px;
                padding-bottom: 10px; border-bottom: 2px solid #f0f0f0; }

  /* Keywords */
  .keyword-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; }
  .keyword-group h3 { font-size: 13px; font-weight: 600; color: var(--muted);
                      text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }
  .kw-item { display: flex; justify-content: space-between; align-items: center;
             padding: 6px 0; border-bottom: 1px solid #f5f5f5; font-size: 13px; }
  .kw-count { background: #e8f4f8; color: var(--accent); border-radius: 4px;
              padding: 2px 8px; font-size: 11px; font-family: monospace; font-weight: 600; }

  /* Reviews table */
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { background: #f5f5f5; padding: 9px 12px; text-align: left; font-weight: 600; color: #444; }
  td { padding: 8px 12px; border-bottom: 1px solid #f5f5f5; vertical-align: top; }
  tr:hover td { background: #fafafa; }
  .stars { color: #f59e0b; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 3px;
          font-size: 11px; font-weight: 600; }
  .pill-pos { background: #e8f5ef; color: var(--green); }
  .pill-neg { background: #fef2f0; color: var(--red); }
  .pill-neu { background: #f5f5f5; color: var(--muted); }

  footer { text-align: center; color: #aaa; font-size: 12px; margin-top: 32px; }
</style>
</head>
<body>
<div class="container">
  <h1>⭐ Reviews & Sentiment Monitor</h1>
  <p class="subtitle">Source: Google Reviews &nbsp;|&nbsp; Generated: {{ generated_at }} &nbsp;|&nbsp; Reviews per brand: {{ reviews_per_brand }}</p>

  <!-- Brand scorecards -->
  <div class="brand-grid">
    {% for s in summary %}
    <div class="brand-card">
      <div class="brand-name">{{ s.brand }}</div>
      <div class="brand-rating">{{ s.avg_rating }} <span>/ 5.0</span></div>
      <div class="brand-meta">{{ s.total }} reviews &nbsp;·&nbsp;
        <span style="color: var(--green)">{{ s.positive_pct }}% positive</span> &nbsp;·&nbsp;
        <span style="color: var(--red)">{{ s.negative_pct }}% negative</span>
      </div>
      <div class="sentiment-bar">
        <div class="bar-pos" style="width: {{ s.positive_pct }}%"></div>
        <div class="bar-neu" style="width: {{ 100 - s.positive_pct - s.negative_pct }}%"></div>
        <div class="bar-neg" style="width: {{ s.negative_pct }}%"></div>
      </div>
    </div>
    {% endfor %}
  </div>

  <!-- Charts -->
  <div class="charts-row">
    <div class="chart-box">
      <img class="chart" src="data:image/png;base64,{{ chart_ratings }}" alt="Avg Ratings">
    </div>
    <div class="chart-box">
      <img class="chart" src="data:image/png;base64,{{ chart_sentiment }}" alt="Sentiment">
    </div>
  </div>

  <!-- Rating distribution -->
  <div class="section">
    <h2>Rating Distribution</h2>
    <img class="chart" src="data:image/png;base64,{{ chart_distribution }}" alt="Distribution">
  </div>

  <!-- Top keywords per brand -->
  <div class="section">
    <h2>Most Mentioned Keywords</h2>
    <div class="keyword-grid">
      {% for s in summary %}
      <div class="keyword-group">
        <h3>{{ s.brand }}</h3>
        {% for word, count in s.top_keywords %}
        <div class="kw-item">
          <span>{{ word }}</span>
          <span class="kw-count">{{ count }}</span>
        </div>
        {% endfor %}
      </div>
      {% endfor %}
    </div>
  </div>

  <!-- Top reviews per brand -->
  {% for s in summary %}
  <div class="section">
    <h2>Recent Reviews — {{ s.brand }}</h2>
    <table>
      <thead>
        <tr>
          <th>Rating</th>
          <th>Review</th>
          <th>Sentiment</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody>
        {% for row in reviews_by_brand[s.brand] %}
        <tr>
          <td class="stars">{{ row.rating }}/5</td>
          <td>{{ row.text[:200] if row.text else "—" }}{% if row.text and row.text|length > 200 %}…{% endif %}</td>
          <td>
            {% if row.sentiment == "positive" %}
              <span class="pill pill-pos">positive</span>
            {% elif row.sentiment == "negative" %}
              <span class="pill pill-neg">negative</span>
            {% else %}
              <span class="pill pill-neu">neutral</span>
            {% endif %}
          </td>
          <td style="white-space:nowrap; color: var(--muted)">{{ row.date[:10] if row.date else "—" }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endfor %}

  <footer>Generated by reviews_monitor.py &nbsp;|&nbsp; Data source: Google Reviews via Apify</footer>
</div>
</body>
</html>
"""


def main():
    print("━" * 50)
    print("  Google Reviews & Sentiment Monitor")
    print("━" * 50)

    client = ApifyClient(CONFIG["apify_token"])

    all_reviews = []
    for brand in CONFIG["brands"]:
        reviews = fetch_reviews(client, brand)
        all_reviews.extend(reviews)

    if not all_reviews:
        print("\n  ⚠ No reviews fetched. Check your CONFIG URLs and API token.")
        return

    print(f"\n  Total reviews fetched: {len(all_reviews)}")

    df = pd.DataFrame(all_reviews)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(0).astype(int)
    df["text"] = df["text"].fillna("").astype(str)
    df["date"] = df["date"].fillna("").astype(str)
    df["sentiment"] = df["text"].apply(simple_sentiment)

    print("  Analysing sentiment...")
    summary = analyze(df)

    print("  Building charts...")
    chart_ratings = chart_avg_ratings(summary)
    chart_sentiment = chart_sentiment_breakdown(summary)
    chart_dist = chart_rating_distribution(df)

    # Top 20 reviews per brand for the table
    reviews_by_brand = {}
    for brand in df["brand"].unique():
        sub = df[df["brand"] == brand].head(20)
        reviews_by_brand[brand] = sub.to_dict("records")

    print("  Rendering HTML report...")
    tmpl = Template(HTML_TEMPLATE)
    html = tmpl.render(
        generated_at=datetime.now().strftime("%d %b %Y, %H:%M"),
        reviews_per_brand=CONFIG["reviews_per_brand"],
        summary=summary,
        chart_ratings=chart_ratings,
        chart_sentiment=chart_sentiment,
        chart_distribution=chart_dist,
        reviews_by_brand=reviews_by_brand,
    )

    with open(CONFIG["output_file"], "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  ✅ Report saved: {CONFIG['output_file']}")
    print("━" * 50)


if __name__ == "__main__":
    main()