#!/usr/bin/env python3
"""每日社招面经抓取 — GitHub 面经资源搜索 + 汇总"""

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────
WIKI_ROOT = Path(os.environ.get("WIKI_ROOT", "."))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Interview-Bot/1.0)"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

TODAY = datetime.now().strftime("%Y-%m-%d")
COMPANIES = ["字节跳动", "美团", "百度", "京东"]
COMPANY_TAGS = {
    "字节跳动": "bytedance",
    "美团": "meituan",
    "百度": "baidu",
    "京东": "jd",
}

# 知名面经仓库（持续跟踪更新）
WATCHED_REPOS = [
    "CyC2018/CS-Notes",
    "Snailclimb/JavaGuide",
    "doocs/advanced-java",
    "crossoverJie/JCSprout",
    "itwanger/toBeBetterJavaer",
    "ipfs-gui/awesome-interview",
    "jsonchao/Android-Notes",
]


def req(url, timeout=20):
    r = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(r, timeout=timeout)


def safe_json(url, timeout=20):
    try:
        return json.loads(req(url, timeout).read())
    except Exception as e:
        print(f"  [WARN] JSON failed: {url[:60]} — {e}")
        return None


# ── 1. 检查已知面经仓库的更新 ─────────────────────────
def check_watched_repos():
    """检查知名面经仓库是否有新更新"""
    results = []
    for repo in WATCHED_REPOS:
        data = safe_json(f"https://api.github.com/repos/{repo}")
        if not data:
            continue
        pushed = data.get("pushed_at", "")[:10]
        desc = (data.get("description") or "").strip()
        stars = data.get("stargazers_count", 0)
        results.append({
            "name": repo,
            "desc": desc,
            "stars": stars,
            "pushed": pushed,
            "url": f"https://github.com/{repo}",
            "type": "watched_repo",
        })
    return results


# ── 2. 搜索面经相关的新仓库 ───────────────────────────
def search_new_repos():
    """搜索近期创建/更新的面经仓库"""
    results = []
    queries = [
        "interview+backend",
        "面经",
        "面试+后端",
        "interview+experience",
        "八股文",
    ]

    for q in queries:
        # 最近一个月有推送的
        url = (f"https://api.github.com/search/repositories"
               f"?q={q}+pushed:>{TODAY}&sort=stars&order=desc&per_page=5")
        data = safe_json(url)
        if not data:
            continue
        for item in data.get("items", []):
            results.append({
                "name": item["full_name"],
                "desc": (item.get("description") or "").strip(),
                "stars": item["stargazers_count"],
                "pushed": item.get("pushed_at", "")[:10],
                "url": item["html_url"],
                "type": "new_repo",
            })
        # 近7天新建的
        url2 = (f"https://api.github.com/search/repositories"
                f"?q={q}+created:>{TODAY}&sort=stars&order=desc&per_page=3")
        data2 = safe_json(url2)
        if not data2:
            continue
        for item in data2.get("items", []):
            results.append({
                "name": item["full_name"],
                "desc": (item.get("description") or "").strip(),
                "stars": item["stargazers_count"],
                "pushed": item.get("pushed_at", "")[:10],
                "url": item["html_url"],
                "type": "new_repo",
            })

    # 去重
    seen = set()
    deduped = []
    for r in results:
        if r["name"] not in seen:
            seen.add(r["name"])
            deduped.append(r)
    return deduped[:15]


# ── 3. 按公司搜索面经内容 ────────────────────────────
def search_company_experiences():
    """搜索各公司的面经内容"""
    results = []
    for company in COMPANIES:
        # 搜索仓库
        q = f"{company}+面经+backend"
        url = (f"https://api.github.com/search/repositories"
               f"?q={q}&sort=stars&order=desc&per_page=5")
        data = safe_json(url)
        if data:
            for item in data.get("items", [])[:5]:
                results.append({
                    "name": item["full_name"],
                    "company": company,
                    "desc": (item.get("description") or "").strip(),
                    "stars": item["stargazers_count"],
                    "pushed": item.get("pushed_at", "")[:10],
                    "url": item["html_url"],
                    "type": "company_repo",
                })

        # 搜索 issues（面经常以 issue 形式存在）
        issue_url = (f"https://api.github.com/search/issues"
                     f"?q={company}+面经+label:interview&sort=created&order=desc&per_page=5")
        issue_data = safe_json(issue_url)
        if issue_data:
            for item in issue_data.get("items", [])[:5]:
                repo_name = "/".join(item["repository_url"].split("/")[-2:])
                results.append({
                    "name": f"{repo_name}#{item['number']}",
                    "company": company,
                    "desc": item["title"][:120],
                    "stars": 0,
                    "pushed": item.get("created_at", "")[:10],
                    "url": item["html_url"],
                    "type": "company_issue",
                })

    return results


# ── 4. 搜索八股文 / 面经文章 ─────────────────────────
def search_gists_articles():
    """搜索面经相关 Gist 和文章类仓库"""
    results = []
    queries = ["八股文+后端", "面试题+Java", "面经+2026"]

    for q in queries:
        # 搜索仓库
        url = (f"https://api.github.com/search/repositories"
               f"?q={q}&sort=stars&order=desc&per_page=5")
        data = safe_json(url)
        if data:
            for item in data.get("items", [])[:3]:
                results.append({
                    "name": item["full_name"],
                    "desc": (item.get("description") or "").strip(),
                    "stars": item["stargazers_count"],
                    "pushed": item.get("pushed_at", "")[:10],
                    "url": item["html_url"],
                    "type": "article_repo",
                })

    return results


# ── 写入 wiki ─────────────────────────────────────────
def write_raw(all_data, company_data):
    path = WIKI_ROOT / "raw" / "articles" / f"interview-trending-{TODAY}.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "---",
        f"ingested: {TODAY}",
        "sha256: placeholder",
        "---",
        "",
        f"# 社招面经资源汇总 — {TODAY}（原始数据）",
        "",
    ]

    for company in COMPANIES:
        items = [d for d in company_data if d.get("company") == company]
        if items:
            lines.append(f"## {company}\n")
            for item in items[:10]:
                lines.append(f"- {item['name']}")
                lines.append(f"  {item['desc'] or 'N/A'}")
                lines.append(f"  {item['url']}")
                lines.append("")

    if all_data:
        lines.append("## 面经相关仓库\n")
        for item in all_data[:20]:
            lines.append(f"- **{item['name']}** ⭐{item.get('stars', 0)} — {item.get('desc', 'N/A')}")
            lines.append(f"  {item['url']}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✓ raw/articles/interview-trending-{TODAY}.md")


def write_concept(all_data, company_data):
    path = WIKI_ROOT / "concepts" / f"interview-trending-{TODAY}.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "---",
        f"title: 社招面经汇总 — {TODAY}",
        f"created: {TODAY}",
        f"updated: {TODAY}",
        "type: summary",
        "tags: [interview, backend, job-hunting]",
        f"sources: [raw/articles/interview-trending-{TODAY}.md]",
        "---",
        "",
        f"# 社招面经汇总 — {TODAY}",
        "",
    ]

    for company in COMPANIES:
        items = [d for d in company_data if d.get("company") == company]
        if items:
            lines.append(f"## {company}\n")
            for item in items[:5]:
                tag = COMPANY_TAGS.get(company, "")
                lines.append(f"- [[{tag}-interview]] **{item['name']}**")
                if item.get("desc"):
                    lines.append(f"  {item['desc'][:100]}")
                lines.append(f"  {item['url']}")
                lines.append("")
        else:
            lines.append(f"## {company}\n")
            lines.append("（今日未发现新的面经资源）\n")

    if all_data:
        lines.append("## 📦 其他面经资源\n")
        for item in all_data[:10]:
            lines.append(f"- **{item['name']}** ⭐{item.get('stars', 0)} — {item.get('desc', 'N/A')}")
            lines.append(f"  {item['url']}")
            lines.append("")

    lines.append("> 数据来源：GitHub Search API，每日自动更新。\n")
    lines.append("> Obsidian 中可用 `Ctrl+O` 搜索 [[${company}-interview]] 快速跳转。")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✓ concepts/interview-trending-{TODAY}.md")


def create_company_pages(company_data):
    """为每家公司创建独立面经页面（如果还没有）"""
    for company in COMPANIES:
        tag = COMPANY_TAGS[company]
        path = WIKI_ROOT / "entities" / f"{tag}-interview.md"
        if path.exists():
            continue

        items = [d for d in company_data if d.get("company") == company]
        lines = [
            "---",
            f"title: {company} 社招面经",
            f"created: {TODAY}",
            f"updated: {TODAY}",
            "type: entity",
            f"tags: [interview, backend, {tag}]",
            f"sources: []",
            "---",
            "",
            f"# {company} 社招面经",
            "",
            "## 面经资源\n",
        ]
        if items:
            for item in items[:10]:
                lines.append(f"- {item['name']} — {item['url']}")
                lines.append("")
        else:
            lines.append("（待收录）\n")

        lines.append("## 相关页面")
        lines.append(f"- [[interview-trending-{TODAY}]] — 每日面经汇总")
        lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  ✓ entities/{tag}-interview.md")


def update_index(new_pages):
    path = WIKI_ROOT / "index.md"
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")

    count_match = re.search(r"总页面数: (\d+)", content)
    current_count = int(count_match.group(1)) if count_match else 0
    new_count = current_count + len(new_pages)
    content = re.sub(r"总页面数: \d+", f"总页面数: {new_count}", content)

    for slug, summary, section in new_pages:
        entry = f"\n- [[{slug}]] — {summary}"
        content = content.replace(f"## {section}\n", f"## {section}\n{entry}")

    content = re.sub(r"最后更新: \d{4}-\d{2}-\d{2}",
                     f"最后更新: {TODAY}", content)
    path.write_text(content, encoding="utf-8")
    print(f"  ✓ index.md 已更新")


def update_log(created_pages):
    path = WIKI_ROOT / "log.md"
    lines = [
        "",
        f"## [{TODAY}] ingest | 社招面经汇总",
        f"- 新建: {', '.join(created_pages)}" if created_pages else "- 无新增",
        "",
    ]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  ✓ log.md 已更新")


# ── 主流程 ────────────────────────────────────────────
def main():
    print(f"🚀 社招面经抓取开始 — {TODAY}")
    print()

    print("📡 检查面经仓库更新...")
    watched = check_watched_repos()
    print(f"   → {len(watched)} 个仓库")

    print("📡 搜索新面经仓库...")
    new_repos = search_new_repos()
    print(f"   → {len(new_repos)} 个新仓库")

    print("📡 按公司搜索面经...")
    company_data = search_company_experiences()
    print(f"   → {len(company_data)} 条结果")

    print("📡 搜索八股文/文章资源...")
    articles = search_gists_articles()
    print(f"   → {len(articles)} 条结果")
    print()

    # 合并去重
    seen_names = set()
    all_data = []
    for item in watched + new_repos + articles:
        if item["name"] not in seen_names:
            seen_names.add(item["name"])
            all_data.append(item)

    print("✍️ 写入 wiki...")
    write_raw(all_data, company_data)
    write_concept(all_data, company_data)
    create_company_pages(company_data)

    created = [
        f"raw/articles/interview-trending-{TODAY}.md",
        f"concepts/interview-trending-{TODAY}.md",
    ]
    for c in COMPANIES:
        tag = COMPANY_TAGS[c]
        p = WIKI_ROOT / "entities" / f"{tag}-interview.md"
        if p.exists():
            created.append(f"entities/{tag}-interview.md")

    update_index([
        ("interview-trending-{TODAY}", f"{TODAY} 社招面经汇总", "Concepts（概念/主题）"),
    ])
    for c in COMPANIES:
        tag = COMPANY_TAGS[c]
        p = WIKI_ROOT / "entities" / f"{tag}-interview.md"
        if p.exists():
            update_index([
                (f"{tag}-interview", f"{c} 社招面经", "Entities（人物/组织/产品）"),
            ])

    update_log(created)
    print()
    print("📊 汇总")
    print("─" * 40)
    print(f"📦 面经资源总计: {len(all_data)} 条")
    print(f"🏢 公司面经: {len(company_data)} 条")
    print(f"📝 Wiki 更新: {len(created)} 个文件")
    print()


if __name__ == "__main__":
    main()
