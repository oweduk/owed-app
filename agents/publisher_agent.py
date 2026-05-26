import json
import os
import datetime
import re

MEMORY_PATH = "memory/store.json"
BLOG_DIR = "blog"

def read_memory():
    with open(MEMORY_PATH, "r") as f:
        return json.load(f)

def write_memory(memory):
    with open(MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=2)

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text.strip())
    return text[:60]

def extract_title(article):
    for line in article.split('\n'):
        if line.startswith('# '):
            return line[2:].strip()
    return "UK Benefits Guide"

def create_blog_index(posts):
    links = ""
    for post in reversed(posts):
        links += f'<li><a href="{post["slug"]}.html">{post["title"]}</a> <span style="color:#888;font-size:13px;">{post["date"]}</span></li>\n'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Owed — UK Benefits Guides</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 680px; margin: 60px auto; padding: 0 20px; color: #111; }}
  h1 {{ font-size: 2rem; margin-bottom: 8px; }}
  p.sub {{ color: #555; margin-bottom: 32px; }}
  ul {{ list-style: none; padding: 0; }}
  li {{ padding: 12px 0; border-bottom: 1px solid #eee; }}
  a {{ color: #111; text-decoration: none; font-weight: 500; }}
  a:hover {{ text-decoration: underline; }}
  .cta {{ display: inline-block; margin-top: 32px; background: #111; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; }}
</style>
</head>
<body>
<h1>Owed</h1>
<p class="sub">Guides to help you find and claim the UK benefits you're entitled to.</p>
<ul>
{links}
</ul>
<a href="https://owed-app.vercel.app" class="cta">Check what I'm owed →</a>
</body>
</html>"""

def markdown_to_html(markdown, title):
    html = markdown
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    paragraphs = []
    for block in html.split('\n\n'):
        block = block.strip()
        if not block:
            continue
        if block.startswith('<h'):
            paragraphs.append(block)
        else:
            paragraphs.append(f'<p>{block}</p>')
    return '\n'.join(paragraphs)

def create_post_html(article, title, date):
    body = markdown_to_html(article, title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Owed</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 680px; margin: 60px auto; padding: 0 20px; color: #111; line-height: 1.7; }}
  h1 {{ font-size: 2rem; margin-bottom: 8px; }}
  h2 {{ font-size: 1.4rem; margin-top: 2rem; }}
  p {{ margin: 1rem 0; }}
  .meta {{ color: #888; font-size: 13px; margin-bottom: 32px; }}
  .cta {{ display: inline-block; margin-top: 32px; background: #111; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; }}
  .back {{ color: #555; font-size: 13px; text-decoration: none; display: block; margin-bottom: 32px; }}
</style>
</head>
<body>
<a href="/owed-app/blog/" class="back">← All guides</a>
{body}
<p class="meta">Published {date} by Owed</p>
<a href="https://owed-app.vercel.app" class="cta">Check what I'm owed →</a>
</body>
</html>"""

def run():
    memory = read_memory()
    content_outputs = memory.get("content_outputs", [])

    if not content_outputs:
        print("No articles to publish.")
        return

    os.makedirs(BLOG_DIR, exist_ok=True)

    if "published_posts" not in memory:
        memory["published_posts"] = []

    published_slugs = {p["slug"] for p in memory["published_posts"]}
    new_posts = []

    for output in content_outputs:
        article = output.get("article", "")
        title = extract_title(article)
        slug = slugify(title)
        date = output.get("timestamp", "")[:10]

        if slug in published_slugs:
            continue

        post_html = create_post_html(article, title, date)
        filepath = os.path.join(BLOG_DIR, f"{slug}.html")

        with open(filepath, "w") as f:
            f.write(post_html)

        memory["published_posts"].append({
            "slug": slug,
            "title": title,
            "date": date,
            "filepath": filepath
        })
        published_slugs.add(slug)
        new_posts.append({"slug": slug, "title": title, "date": date})
        print(f"Published: {title}")

    index_html = create_blog_index(memory["published_posts"])
    with open(os.path.join(BLOG_DIR, "index.html"), "w") as f:
        f.write(index_html)

    write_memory(memory)
    print(f"\nBlog index updated. {len(new_posts)} new posts published.")

if __name__ == "__main__":
    run()
