# Editorial Guidelines

These guidelines define how we write the project's content — the README, CHANGELOG,
release notes, documentation, issue and PR templates, and any blog or announcement
posts. The goal is a consistent voice, predictable structure, and content that a busy
developer can scan and trust.

When in doubt, match the tone already established in `README.md` and `CONTRIBUTING.MD`.

## Table of contents

- [Voice and tone](#voice-and-tone)
- [Audience](#audience)
- [Structure and formatting](#structure-and-formatting)
- [Language and grammar](#language-and-grammar)
- [Code, commands, and technical content](#code-commands-and-technical-content)
- [Links and references](#links-and-references)
- [Emoji and visual elements](#emoji-and-visual-elements)
- [Document-specific conventions](#document-specific-conventions)
- [Accessibility and inclusivity](#accessibility-and-inclusivity)
- [Review checklist](#review-checklist)

## Voice and tone

- **Direct and confident.** Tell the reader what to do and why. Avoid hedging
  ("maybe", "sort of", "we think"). State requirements plainly.
- **Friendly, not formal.** Write as one developer talking to another. First person
  ("I", "we") and second person ("you") are both fine and encouraged.
- **Honest about limitations.** If a feature is experimental, deprecated, or unmaintained,
  say so up front — as the README does about active maintenance. Never oversell.
- **Respectful of the reader's time.** Lead with the most important information. Cut
  filler. A reader should be able to get the gist from headings and the first sentence
  of each section.

## Audience

Our primary reader is a **developer integrating or contributing to the MCP server** —
comfortable with the command line, Python, SQL, and Git, but not necessarily familiar
with this project's internals.

- Assume technical literacy; do not explain what a terminal or a pull request is.
- Do **not** assume project-specific knowledge; explain our concepts (safety tiers,
  query validation, transaction handling) the first time they appear.
- Define acronyms and product names on first use (e.g., "Model Context Protocol (MCP)").

## Structure and formatting

- **Headings are a map.** Use sentence case for headings ("Getting started", not
  "Getting Started" — though existing top-level headings vary; stay consistent within a
  document). Nest logically with `##` and `###`; don't skip levels.
- **Short paragraphs.** Aim for 1–4 sentences. Break dense material into lists.
- **Lists for steps and options.** Use ordered lists for sequential steps, unordered
  lists for non-sequential items.
- **Bold for the key term** in a list item or callout, so readers scanning can find it.
- **One idea per sentence** where practical. Prefer periods over semicolons.
- **Line length.** Wrap prose in Markdown source at a reasonable width (~100 chars) to
  keep diffs readable. Don't hard-wrap inside links or code.

## Language and grammar

- **American English** spelling ("behavior", "color", "canceled").
- **Oxford comma** in lists of three or more ("safe, write, and destructive").
- **Active voice.** "The server validates the query," not "The query is validated."
- **Present tense** for describing how things work. Reserve future tense for genuinely
  upcoming changes.
- **Numbers.** Spell out one through nine in prose; use numerals for 10+ and for any
  number with a unit (`3.12+`, `2s`, `17k installs`).
- **Capitalization of product names.** Write Supabase, PostgreSQL, Cursor, Windsurf,
  Cline, GitHub, PyPI, Smithery — exactly as their owners style them.
- **Avoid jargon for its own sake.** Prefer the simplest accurate word.

## Code, commands, and technical content

- **Inline code** for identifiers, file names, flags, env vars, and commands referenced
  in prose: `pytest`, `uv`, `supabase_mcp`, `--read-only`.
- **Fenced code blocks** with a language hint for multi-line examples:

  ````
  ```bash
  pytest
  ```
  ````

- **Commands must be copy-pasteable.** Show the exact command; don't paraphrase. If a
  placeholder is required, make it obvious (`<your-project-ref>`) and explain it.
- **Show expected output** when it helps the reader confirm success, but keep it short.
- **Keep examples current.** If an API or flag changes, update every example that uses
  it. Out-of-date commands erode trust faster than missing ones.

## Links and references

- **Descriptive link text.** Link the words that describe the destination, not "click
  here" or a bare URL: "the [official MCP server](https://github.com/supabase-community/supabase-mcp)".
- **Prefer relative links** for files within the repo (`LICENSE`, `CONTRIBUTING.MD`).
- **Check links before publishing.** Broken links are a content bug.

## Emoji and visual elements

This project uses emoji deliberately, and that's part of its voice — but with restraint.

- **One emoji per heading or list item, at most.** Use them as visual anchors (🔐, 🛡️,
  📝), not decoration sprinkled through sentences.
- **Be consistent.** If feature bullets lead with an emoji, all of them should.
- **Never rely on emoji to carry meaning.** The sentence must read correctly if the
  emoji is stripped (screen readers and plain-text renderers).
- **Badges** belong at the top of the README only, grouped together.

## Document-specific conventions

### README

- Open with a one-line description of what the server is and who it's for.
- Surface critical status (maintenance, deprecation) in a blockquote at the very top.
- Keep a table of contents for navigation.
- Order: what it is → key features → getting started → feature details →
  troubleshooting → changelog link.

### CHANGELOG

- Follow the existing format and keep entries newest-first.
- Group changes under headings like Added, Changed, Fixed, Removed.
- Write entries from the user's perspective: what changed for them, not how it was
  implemented.
- Reference issues/PRs where relevant.

### Release notes

- Summarize the user-facing impact first; link to the full changelog for detail.
- Call out breaking changes prominently and explain the migration path.

### Issue and PR templates

- Keep prompts short and specific. Ask only for information that will actually be used.
- Use the imperative ("Describe the bug", "Steps to reproduce").

### Commit messages

- Use clear, descriptive messages. Conventional-commit prefixes (`feat:`, `fix:`,
  `docs:`) are encouraged, matching the style shown in `CONTRIBUTING.MD`.

## Accessibility and inclusivity

- **Alt text** for every meaningful image; mark decorative images as such.
- **Don't convey information by color or emoji alone.**
- **Plain, inclusive language.** Avoid idioms that don't translate, ableist metaphors,
  and unnecessarily gendered terms. Use "they" as a singular pronoun.
- **Meaningful link text** (see above) doubles as an accessibility requirement.

## Review checklist

Before publishing any content, confirm:

- [ ] The first sentence/section states the point clearly.
- [ ] Headings are scannable and correctly nested.
- [ ] Spelling and grammar follow the rules above (American English, Oxford comma, active voice).
- [ ] All commands and code samples are correct and copy-pasteable.
- [ ] Links work and use descriptive text.
- [ ] Product names are capitalized correctly.
- [ ] Emoji are used sparingly and never as the sole carrier of meaning.
- [ ] Limitations and status are stated honestly.
- [ ] Content reads as if one developer is helping another.
