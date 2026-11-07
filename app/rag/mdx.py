import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
FENCE = re.compile(r"^\s*(```|~~~)")
IMPORT = re.compile(r"^import\s.+\sfrom\s+['\"].+['\"];?\s*$")
COMMENT = re.compile(r"\{/\*.*?\*/\}", re.S)
PARAM_FIELD = re.compile(r'<ParamField\s+((?:[^>"]|"[^"]*")*)>')
ATTRIBUTE = re.compile(r'(\w+)="([^"]*)"')
JSX_TAG = re.compile(r"</?[A-Z][\w.]*(?:\s[^<>]*?)?/?>")
REFERENCE = re.compile(r"@\[`([^`]+)`\]")  # @[`create_agent`] is a docs-internal link
LANG_OPEN = re.compile(r"^:{3,}(python|js)\s*$")
LANG_CLOSE = re.compile(r"^:{3,}\s*$")
DOCS_HOST = "https://docs.langchain.com/"

@dataclass
class Page: 
    rel_path: str # path inside the repo e.g. src/oss/langchain/tools.mdx
    title: str 
    product: str 
    folder_language: str | None # python/js
    content_hash: str 
    segments: list[tuple[str, str]] # (language, cleaned text); language is "all" if shared

def split_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), text[match.end() :]


def split_languages(body: str) -> list[tuple[str, str]]:
    """Split a page into (language, text) pieces using the `:::python` / `:::js` markers."""
    pieces: list[tuple[str, str]] = []
    current, buffer = "all", []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            pieces.append((current, text))
        buffer.clear()

    for line in body.splitlines():
        opener = LANG_OPEN.match(line.strip())
        if opener:
            flush()
            current = "javascript" if opener.group(1) == "js" else "python"
        elif LANG_CLOSE.match(line.strip()):
            flush()
            current = "all"
        else:
            buffer.append(line)
    flush()
    return pieces


def _param_field(match: re.Match) -> str:
    """`<ParamField body="retries" type="number" default="2">` becomes `**retries** (number, default 2):`."""
    attrs = dict(ATTRIBUTE.findall(match.group(1)))
    name = attrs.get("body") or attrs.get("path") or attrs.get("query") or attrs.get("header")
    if not name:
        return ""
    details = ", ".join(
        x
        for x in (attrs.get("type"), f"default {attrs['default']}" if "default" in attrs else "")
        if x
    )
    return f"**{name}** ({details}):" if details else f"**{name}**:"


def _clean_line(line: str) -> str:
    line = REFERENCE.sub(r"`\1`", line)
    line = PARAM_FIELD.sub(_param_field, line)
    # Only touch text outside `inline code`, so `List<Foo>` survives.
    parts = line.split("`")
    for i in range(0, len(parts), 2):
        parts[i] = JSX_TAG.sub("", parts[i])
    return "`".join(parts)


def clean_mdx(text: str) -> str:
    """Remove imports, comments and JSX tags outside code blocks. Keep code blocks verbatim."""
    text = COMMENT.sub("", text)
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
        elif in_fence:
            out.append(line)
        elif IMPORT.match(line) or line.startswith("export "):
            continue
        else:
            out.append(_clean_line(line))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def classify(rel_path: str) -> tuple[str, str | None]:
    """Guess (product, folder_language) from the path. Heuristic: see docs/05-rag-ingestion.md."""
    parts = Path(rel_path).parts
    folder_language = next((p for p in parts[:4] if p in ("python", "javascript")), None)
    if "langsmith" in parts[:2]:
        product = "langsmith"
    elif "integrations" in parts:
        product = "integrations"
    elif "langgraph" in parts:
        product = "langgraph"
    else:
        product = "langchain"
    return product, folder_language


def page_url(rel_path: str, language: str) -> str:
    """Best-effort public URL. The GitHub `source_url` is the exact reference."""
    parts = rel_path.removeprefix("src/").removesuffix(".mdx").split("/")
    if parts[-1] == "index":
        parts.pop()
    shared = parts[0] == "oss" and len(parts) > 1 and parts[1] not in ("python", "javascript")
    if shared and language in ("python", "javascript"):  # "all" keeps the language-neutral URL
        parts.insert(1, language)
    return DOCS_HOST + "/".join(parts)


def load_page(path: Path, repo_root: Path) -> Page:
    raw = path.read_text(encoding="utf-8")
    meta, body = split_frontmatter(raw)
    rel_path = path.relative_to(repo_root).as_posix()
    product, folder_language = classify(rel_path)
    segments = [(lang, clean_mdx(text)) for lang, text in split_languages(body)]
    return Page(
        rel_path=rel_path,
        title=str(meta.get("title") or path.stem),
        product=product,
        folder_language=folder_language,
        content_hash=hashlib.sha256(raw.encode()).hexdigest(),
        segments=[(lang, text) for lang, text in segments if text],
    )
