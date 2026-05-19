#!/usr/bin/env python3
"""每日 AI 趋势抓取脚本 — 自动写入 llm-wiki"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

# ── 翻译 ──────────────────────────────────────────────
_translator = None

def translate(text, target="zh-CN"):
    """将英文文本翻译为中文，如果已是中文则跳过"""
    if not text or not text.strip():
        return text
    # 检查是否已有中文字符
    if re.search(r'[\u4e00-\u9fff]', text):
        return text.strip()
    global _translator
    try:
        if _translator is None:
            from deep_translator import GoogleTranslator
            _translator = GoogleTranslator(source="en", target=target)
        result = _translator.translate(text.strip())
        return result if result else text.strip()
    except Exception as e:
        print(f"  [WARN] 翻译失败 ({text[:30]}...): {e}")
        return text.strip()

# ── 配置 ──────────────────────────────────────────────
WIKI_ROOT = Path(os.environ.get("WIKI_ROOT", "."))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AI-Trending-Bot/1.0)"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

TODAY = datetime.now().strftime("%Y-%m-%d")


def req(url, timeout=20):
    """HTTP GET helper"""
    r = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(r, timeout=timeout)


def safe_json(url, timeout=20):
    try:
        return json.loads(req(url, timeout).read())
    except Exception as e:
        print(f"  [WARN] JSON fetch failed: {url[:60]} — {e}")
        return None


def safe_text(url, timeout=20):
    try:
        return req(url, timeout).read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] Text fetch failed: {url[:60]} — {e}")
        return ""


# ── 1. GitHub Trending ────────────────────────────────
def fetch_github(since_days=30):
    """获取 GitHub 热门 AI 项目，since_days: 查询过去几天内创建的项目"""
    projects = []
    seen = set()
    since = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")

    urls = [
        f"https://api.github.com/search/repositories?q=created:>{since}+AI&sort=stars&order=desc&per_page=10",
        f"https://api.github.com/search/repositories?q=created:>{since}+machine+learning&sort=stars&order=desc&per_page=10",
        f"https://api.github.com/search/repositories?q=created:>{since}+agent&sort=stars&order=desc&per_page=5",
    ]

    for url in urls:
        data = safe_json(url)
        if not data:
            continue
        for item in data.get("items", []):
            name = item["full_name"]
            if name in seen:
                continue
            seen.add(name)
            projects.append({
                "name": name,
                "stars": item["stargazers_count"],
                "desc": translate((item["description"] or "").strip()),
                "url": item["html_url"],
                "source": "github",
            })

    # 按 stars 排序，取前 10
    projects.sort(key=lambda x: -x["stars"])
    return projects[:10]


# ── 2. HuggingFace Daily Papers ───────────────────────
def fetch_hf_papers():
    papers = []
    data = safe_json("https://huggingface.co/api/daily_papers?limit=10")
    if not data:
        return papers
    for p in data[:8]:
        papers.append({
            "title": translate(p.get("title", "N/A")),
            "summary": translate((p.get("summary") or "")[:200]),
            "url": f"https://huggingface.co/papers/{p.get('id', '')}",
            "source": "huggingface",
        })
    return papers


# ── 3. HuggingFace Trending Models ────────────────────
def fetch_hf_models():
    models = []
    data = safe_json(
        "https://huggingface.co/api/models?search=trending&sort=downloads&direction=-1&limit=10"
    )
    if not data:
        return models
    for m in data[:5]:
        mid = m.get("modelId", m.get("id", "N/A"))
        models.append({
            "name": mid,
            "desc": translate((m.get("pipeline_tag") or m.get("cardData", {}).get("library_name", "") or "").strip()),
            "url": f"https://huggingface.co/{mid}",
            "source": "huggingface",
        })
    return models


# ── 4. arXiv AI Papers ────────────────────────────────
def fetch_arxiv():
    papers = []
    url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=desc&max_results=10"
    text = safe_text(url)
    if not text:
        return papers

    try:
        root = ET.fromstring(text)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in list(root.findall("a:entry", ns))[:5]:
            title = translate(entry.find("a:title", ns).text.strip().replace("\n", " "))
            summary = translate(entry.find("a:summary", ns).text.strip()[:250].replace("\n", " "))
            link = entry.find("a:id", ns).text
            published = entry.find("a:published", ns).text[:10]
            papers.append({
                "title": title,
                "summary": summary,
                "url": link,
                "date": published,
                "source": "arxiv",
            })
    except Exception as e:
        print(f"  [WARN] arXiv XML parse error: {e}")
    return papers


# ── 写入 wiki ─────────────────────────────────────────
def write_raw(projects_daily, projects_weekly, projects_monthly, hf_papers, models, arxiv_papers):
    path = WIKI_ROOT / "raw" / "articles" / f"ai-trending-{TODAY}.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "---",
        f"source_url: https://github.com/trending",
        f"ingested: {TODAY}",
        "sha256: placeholder",
        "---",
        "",
        f"# AI Trending — {TODAY}（原始数据）",
        "",
    ]

    def write_gh_section(label, projects):
        if not projects:
            return
        lines.append(f"## GitHub {label} 热门项目\n")
        for p in projects:
            lines.append(f"- **{p['name']}** | ⭐{p['stars']}")
            lines.append(f"  {p['desc']}")
            lines.append(f"  {p['url']}")
            lines.append("")

    write_gh_section("今日", projects_daily)
    write_gh_section("本周", projects_weekly)
    write_gh_section("本月", projects_monthly)

    if hf_papers:
        lines.append("## HuggingFace 热门论文\n")
        for p in hf_papers:
            lines.append(f"- **{p['title']}**")
            lines.append(f"  {p['summary']}")
            lines.append(f"  {p['url']}")
            lines.append("")

    if arxiv_papers:
        lines.append("## arXiv AI 论文\n")
        for p in arxiv_papers:
            lines.append(f"- **{p['title']}** ({p['date']})")
            lines.append(f"  {p['summary']}")
            lines.append(f"  {p['url']}")
            lines.append("")

    if models:
        lines.append("## HuggingFace 热门模型\n")
        for m in models:
            lines.append(f"- **{m['name']}** — {m['desc']}")
            lines.append(f"  {m['url']}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✓ raw/articles/ai-trending-{TODAY}.md")
    return path


def write_concept(projects_daily, projects_weekly, projects_monthly, hf_papers, models, arxiv_papers):
    path = WIKI_ROOT / "concepts" / f"ai-trending-{TODAY}.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "---",
        f"title: AI 趋势汇总 — {TODAY}",
        f"created: {TODAY}",
        f"updated: {TODAY}",
        "type: summary",
        "tags: [ai, trend, summary]",
        f"sources: [raw/articles/ai-trending-{TODAY}.md]",
        "---",
        "",
        f"# AI 趋势汇总 — {TODAY}",
        "",
    ]

    def write_gh_section(label, projects):
        if not projects:
            return
        lines.append(f"## 📦 {label}热门项目\n")
        for p in projects:
            desc = f" — {p['desc']}" if p['desc'] else ""
            lines.append(f"- **{p['name']}** ⭐{p['stars']}{desc}")
            lines.append(f"  {p['url']}")
            lines.append("")

    write_gh_section("今日", projects_daily)
    write_gh_section("本周", projects_weekly)
    write_gh_section("本月", projects_monthly)

    if hf_papers:
        lines.append("## 📄 热门论文\n")
        for p in hf_papers:
            lines.append(f"- **{p['title']}**")
            if p['summary']:
                lines.append(f"  {p['summary']}")
            lines.append(f"  {p['url']}")
            lines.append("")

    if arxiv_papers:
        lines.append("## 📄 arXiv 论文\n")
        for p in arxiv_papers:
            lines.append(f"- **{p['title']}** ({p['date']})")
            if p['summary']:
                lines.append(f"  {p['summary']}")
            lines.append(f"  {p['url']}")
            lines.append("")

    if models:
        lines.append("## 🧠 热门模型\n")
        for m in models:
            desc = f" — {m['desc']}" if m['desc'] else ""
            lines.append(f"- **{m['name']}**{desc}")
            lines.append(f"  {m['url']}")
            lines.append("")

    # 趋势观察
    obs = []
    if projects_daily:
        obs.append(f"今日热门 AI 项目 {len(projects_daily)} 个")
    if projects_weekly:
        obs.append(f"本周热门 AI 项目 {len(projects_weekly)} 个")
    if projects_monthly:
        obs.append(f"本月热门 AI 项目 {len(projects_monthly)} 个")
    if hf_papers:
        obs.append(f"HuggingFace 今日 {len(hf_papers)} 篇热门论文")
    if models:
        obs.append(f"HF 模型下载榜出现 {len(models)} 个 trending 模型")
    if obs:
        lines.append("## 📌 趋势观察\n")
        for o in obs:
            lines.append(f"- {o}")
        lines.append("")

    # 如果数据很少
    total = len(projects_daily) + len(projects_weekly) + len(projects_monthly) + len(hf_papers) + len(models)
    if total == 0:
        lines.append("> 当日无显著趋势数据。")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✓ concepts/ai-trending-{TODAY}.md")
    return path


def update_index(new_pages):
    """追加页面到 index.md"""
    path = WIKI_ROOT / "index.md"
    if not path.exists():
        return

    content = path.read_text(encoding="utf-8")

    # 更新总页面数
    count_match = re.search(r"总页面数: (\d+)", content)
    current_count = int(count_match.group(1)) if count_match else 0
    new_count = current_count + len(new_pages)
    content = re.sub(r"总页面数: \d+", f"总页面数: {new_count}", content)

    # 追加到 Concepts 下方
    for slug, summary in new_pages:
        entry = f"\n- [[{slug}]] — {summary}"
        # 放在 ## Concepts 下面
        content = content.replace("## Concepts（概念/主题）\n",
                                   f"## Concepts（概念/主题）\n{entry}")

    content = re.sub(r"最后更新: \d{4}-\d{2}-\d{2}",
                     f"最后更新: {TODAY}", content)
    path.write_text(content, encoding="utf-8")
    print(f"  ✓ index.md 已更新")


def update_log(created_pages, updated_pages):
    """追加日志"""
    path = WIKI_ROOT / "log.md"
    lines = [
        "",
        f"## [{TODAY}] ingest | AI Trending Projects 汇总",
    ]
    if created_pages:
        lines.append(f"- 新建: {', '.join(created_pages)}")
    if updated_pages:
        lines.append(f"- 更新: {', '.join(updated_pages)}")
    lines.append("")

    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  ✓ log.md 已更新")


# ── 主流程 ────────────────────────────────────────────
def main():
    print(f"🚀 AI Trending 开始 — {TODAY}")
    print()

    # 1. 抓取数据
    print("📡 获取 GitHub 热门项目...")
    projects_daily = fetch_github(1)
    print(f"   → 今日: {len(projects_daily)} 个")
    projects_weekly = fetch_github(7)
    print(f"   → 本周: {len(projects_weekly)} 个")
    projects_monthly = fetch_github(30)
    print(f"   → 本月: {len(projects_monthly)} 个")

    print("📡 获取 HuggingFace 论文...")
    hf_papers = fetch_hf_papers()
    print(f"   → {len(hf_papers)} 篇论文")

    print("📡 获取 arXiv 论文...")
    arxiv_papers = fetch_arxiv()
    print(f"   → {len(arxiv_papers)} 篇论文")

    print("📡 获取 HuggingFace 模型...")
    models = fetch_hf_models()
    print(f"   → {len(models)} 个模型")
    print()

    # 2. 写入 wiki
    print("✍️ 写入 wiki...")
    raw_path = write_raw(projects_daily, projects_weekly, projects_monthly, hf_papers, models, arxiv_papers)
    concept_path = write_concept(projects_daily, projects_weekly, projects_monthly, hf_papers, models, arxiv_papers)

    created_pages = [
        f"raw/articles/ai-trending-{TODAY}.md",
        f"concepts/ai-trending-{TODAY}.md",
    ]
    update_index([
        (f"ai-trending-{TODAY}", f"{TODAY} AI 趋势汇总"),
    ])
    update_log(created_pages, [])
    print()

    # 3. 输出报告
    print("📊 汇总报告")
    print("─" * 40)
    if projects_daily:
        print(f"🔥 今日热门项目: {len(projects_daily)} 个")
        for p in projects_daily[:5]:
            print(f"   {p['name']} ⭐{p['stars']}")
    if projects_weekly:
        print(f"📅 本周热门项目: {len(projects_weekly)} 个")
    if projects_monthly:
        print(f"📆 本月热门项目: {len(projects_monthly)} 个")
    if hf_papers:
        print(f"📄 热门论文: {len(hf_papers)} 篇")
    if models:
        print(f"🧠 热门模型: {len(models)} 个")
    print(f"📝 Wiki 更新: {len(created_pages)} 个新页面")
    print()


if __name__ == "__main__":
    main()
