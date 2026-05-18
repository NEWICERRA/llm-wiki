# Wiki Schema

## Domain
个人知识管理（Personal Knowledge Management）— 涵盖生活、工作、学习中的知识、经验、思考和参考资料。

## Conventions
- File names: lowercase, hyphens, no spaces（如 `reading-list-2026.md`）
- Every wiki page starts with YAML frontmatter（见下）
- Use `[[wikilinks]]` 在页面之间建立链接（每页至少 2 个出链）
- 更新页面时务必更新 `updated` 日期
- 每新建一个页面，必须在 `index.md` 对应 section 下添加条目
- 每次操作必须在 `log.md` 末尾追加记录
- **Provenance markers:** 综合 3+ 来源的页面，在段落末尾用 `^[raw/articles/source-file.md]` 标注出处

## Frontmatter

```yaml
---
title: 页面标题
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query | summary
tags: [from taxonomy below]
sources: [raw/articles/source-name.md]
confidence: high | medium | low
contested: true
contradictions: [other-page-slug]
---
```

### raw/ 源材料 Frontmatter

```yaml
---
source_url: https://example.com/article
ingested: YYYY-MM-DD
sha256: <hex digest of the raw content below the frontmatter>
---
```

`sha256` 用于重复摄取时检测内容是否变化。只对正文部分（frontmatter 结束后的内容）计算哈希。

## Tag Taxonomy

### People（人）
- person, family, friend, colleague, mentor

### Life（生活）
- health, finance, travel, home, hobby, habit

### Work & Career（工作与职业）
- career, project, skill, tool, productivity, meeting

### Knowledge（知识）
- book, article, course, podcast, idea, summary

### Meta（元信息）
- reference, reflection, goal, plan, review, journal

### Tech（技术）
- programming, software, hardware, ai, data, security

规则：页面上的每个 tag 都必须在以上分类中出现。如果新 tag 需要添加，先在 SCHEMA.md 中补充，之后再使用。

## Page Thresholds
- **创建页面** — 当一个实体/概念出现在 2+ 个来源中，或是一个来源的核心主题
- **添加到现有页面** — 当新来源提及已有页面覆盖的内容
- **不要创建页面** — 对于随口提及、次要细节、或不在领域范围内的事情
- **拆分页面** — 当页面超过 ~200 行时，拆分为子主题并建立交叉链接
- **归档页面** — 当内容完全被取代时，移到 `_archive/`，从 index 中移除

## Entity Pages
每个值得记录的人、组织、产品。包含：
- 概述 / 是什么
- 关键事实和日期
- 与其他实体的关系（`[[wikilinks]]`）
- 来源引用

## Concept Pages
每个概念或主题。包含：
- 定义 / 解释
- 当前了解程度
- 未解决的问题或思考
- 相关概念（`[[wikilinks]]`）

## Comparison Pages
对比分析。包含：
- 比较什么以及为什么
- 比较维度（优先用表格格式）
- 结论或综合观点
- 来源

## Update Policy
当新信息与现有内容冲突时：
1. 检查日期 — 较新的来源通常优于旧的
2. 如果确实矛盾，注明两方观点及其日期和来源
3. 在 frontmatter 中标记矛盾：`contradictions: [page-name]`
4. 在 lint 报告中标记供用户审阅
