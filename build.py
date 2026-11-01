"""Build the portfolio into dist/.

    python build.py            # build
    python build.py --serve    # build, then serve dist/ on http://localhost:8000

Content lives in content/<lang>.json, static files in static/, screenshot sizes in
assets-src/images.json (written by tools/process_images.py). Standard library only.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import re
import shutil
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
STATIC = ROOT / "static"
DIST = ROOT / "dist"
IMAGES = json.loads((ROOT / "assets-src" / "images.json").read_text(encoding="utf-8"))

SITE_URL = "https://sepehrkhasto.github.io"
PAGES = {"en": "", "fa": "fa/"}  # language -> folder under the site root
DEFAULT_LANG = "en"
# GitHub Pages can't send response headers, so the policy ships as a meta tag.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'"
)


# --------------------------------------------------------------------------- helpers

def e(text) -> str:
    return escape(str(text), quote=True)


def code(text: str) -> str:
    """Escape text and set identifiers such as transaction.atomic or [a-z0-9_]{3,20} in <code>."""
    pattern = r"(\[a-z0-9_\]\{3,20\}|transaction\.atomic|AbstractBaseUser|SECRET_KEY|\.env|DEBUG|secrets|frame-ancestors 'none'|SECURITY\.md)"
    return "".join(f"<code>{e(p)}</code>" if i % 2 else e(p) for i, p in enumerate(re.split(pattern, str(text))))


_TOKEN = r"[A-Za-z0-9](?:[A-Za-z0-9.+#_/@'\-]*[A-Za-z0-9+#])?"
# A run of Latin words; it never ends on punctuation, so a sentence's final period stays Persian.
LATIN_RUN = re.compile(rf"[A-Za-z](?:[A-Za-z0-9.+#_/@'\-]*[A-Za-z0-9+#])?(?: {_TOKEN})*")
SKIP_TAGS = {"script", "style", "textarea", "code", "svg", "title"}


def isolate_latin(html: str) -> str:
    """Wrap Latin runs in Persian body text in <bdi>, so the bidi algorithm keeps
    "(Zero-Knowledge)" and "AES-256-GCM" whole inside right-to-left sentences."""
    head_end = html.index("<body")
    out, skip = [html[:head_end]], []
    for part in re.split(r"(<[^>]+>)", html[head_end:]):
        if part.startswith("<"):
            name = re.match(r"</?([a-zA-Z0-9]+)", part)
            if name:
                tag = name.group(1).lower()
                if tag in SKIP_TAGS and not part.endswith("/>"):
                    if part.startswith("</"):
                        if skip and skip[-1] == tag:
                            skip.pop()
                    else:
                        skip.append(tag)
            out.append(part)
        elif skip or not part.strip():
            out.append(part)
        else:
            def wrap(m: re.Match) -> str:
                run = m.group(0)
                cls = ' class="nw"' if " " not in run and len(run) <= 28 else ""
                return f'<bdi dir="ltr"{cls}>{run}</bdi>'
            out.append(LATIN_RUN.sub(wrap, part))
    return "".join(out)


def load(lang: str) -> dict:
    return json.loads((CONTENT / f"{lang}.json").read_text(encoding="utf-8"))


def other(lang: str) -> str:
    return next(code_ for code_ in PAGES if code_ != lang)


def page_url(lang: str) -> str:
    return f"{SITE_URL}/{PAGES[lang]}"


ICONS = {
    "download": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    "file": '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5M12 11v6M9.5 14.5 12 17l2.5-2.5"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "external": '<path d="M14 5h5v5M19 5l-8 8M17 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h4"/>',
    "lock": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "expand": '<path d="M15 4h5v5M9 20H4v-5M20 4l-6 6M4 20l6-6"/>',
    "arrow-up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
    "github": '<path d="M9 19c-4.3 1.4-4.3-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/>',
}


def icon(name: str) -> str:
    return (
        '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>'
    )


MARK = (
    '<svg class="mark" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="#16264d"/>'
    '<path d="M16.00 4.80L18.49 10.00L23.92 8.08L22.00 13.51L27.20 16.00L22.00 18.49L23.92 23.92L18.49 22.00L16.00 27.20L13.51 22.00L8.08 23.92L10.00 18.49L4.80 16.00L10.00 13.51L8.08 8.08L13.51 10.00Z" fill="none" stroke="#34B3B0" stroke-width="1.8" stroke-linejoin="round"/></svg>'
)


def picture(key: str, alt: str, sizes: str, cls: str, eager: bool = False) -> str:
    info = IMAGES[key]
    files = info["files"]
    srcset = ", ".join(f"assets/img/work/{name} {w}w" for name, w in files)
    largest = files[-1][0]
    loading = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (
        f'<img class="{cls}" src="{{P}}assets/img/work/{largest}" srcset="{srcset.replace("assets/", "{P}assets/")}" '
        f'sizes="{sizes}" width="{info["w"]}" height="{info["h"]}" alt="{e(alt)}" {loading} decoding="async">'
    )


# --------------------------------------------------------------------------- components

def head(c: dict, lang: str) -> str:
    alt = other(lang)
    person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": "Sepehr Khastoo",
        "alternateName": "سپهر خستو",
        "jobTitle": "Backend Engineer",
        "url": SITE_URL + "/",
        "email": f"mailto:{c['contact']['email']}",
        "sameAs": [link["href"] for link in c["contact"]["links"]],
        "knowsAbout": ["Python", "Django", "PostgreSQL", "Application security", "Web Crypto API", "FastAPI"],
        "alumniOf": {"@type": "CollegeOrUniversity", "name": "Islamic Azad University, West Tehran Branch"},
        "address": {"@type": "PostalAddress", "addressLocality": "Tehran", "addressCountry": "IR"},
    }
    works = [
        {"@type": "SoftwareSourceCode", "name": f'{p["name"]} ({p["kind"]})', "codeRepository": p["repo"], "description": p["tagline"]}
        for p in c["work"]["projects"] if p["repo"]
    ]
    person.pop("@context")
    graph = {"@context": "https://schema.org", "@graph": [person, *works]}
    fonts = ["ibm-plex-sans-arabic-arabic-600-normal", "ibm-plex-sans-arabic-arabic-400-normal"] if lang == "fa" else ["ibm-plex-sans-latin-600-normal", "ibm-plex-sans-latin-400-normal"]
    preload = "\n".join(f'<link rel="preload" href="{{P}}assets/fonts/{f}.woff2" as="font" type="font/woff2" crossorigin>' for f in fonts)
    return f"""<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{e(c['meta']['title'])}</title>
<meta name="description" content="{e(c['meta']['description'])}">
<meta name="author" content="Sepehr Khastoo">
<link rel="canonical" href="{page_url(lang)}">
<link rel="alternate" hreflang="{lang}" href="{page_url(lang)}">
<link rel="alternate" hreflang="{alt}" href="{page_url(alt)}">
<link rel="alternate" hreflang="x-default" href="{page_url(DEFAULT_LANG)}">
<meta property="og:type" content="profile">
<meta property="og:site_name" content="Sepehr Khastoo">
<meta property="og:title" content="{e(c['meta']['title'])}">
<meta property="og:description" content="{e(c['meta']['description'])}">
<meta property="og:url" content="{page_url(lang)}">
<meta property="og:image" content="{SITE_URL}/assets/img/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{c['locale']}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0E1A36">
<link rel="icon" href="{{P}}assets/img/favicon.svg" type="image/svg+xml">
{preload}
<link rel="stylesheet" href="{{P}}assets/css/site.css">
<script type="application/ld+json">{json.dumps(graph, ensure_ascii=False)}</script>
<script src="{{P}}assets/js/site.js" defer></script>
</head>"""


def site_header(c: dict, lang: str) -> str:
    n = c["nav"]
    alt = other(lang)
    alt_href = "{P}" + PAGES[alt] if PAGES[alt] else "{P}" or "./"
    links = "".join(f'<li><a href="#{k}" data-nav>{e(n[k])}</a></li>' for k in ("work", "approach", "skills", "contact"))
    return f"""<a class="skip" href="#main">{e(n['skip'])}</a>
<header class="site-header">
  <div class="wrap bar">
    <a class="brand" href="#top" aria-label="{e(n['home'])}">{MARK}<span>{e(c['name'])}</span></a>
    <button class="menu-btn" type="button" aria-expanded="false" aria-controls="site-nav" data-open="{e(n['menu'])}" data-close="{e(n['close'])}">{icon('menu')}<span>{e(n['menu'])}</span></button>
    <nav id="site-nav" class="site-nav" aria-label="{e(n['menu'])}">
      <ul class="nav-links">{links}</ul>
      <a class="lang-link" href="{alt_href}" hreflang="{alt}" lang="{alt}" aria-label="{e(c['switch']['aria'])}">{e(c['switch']['label'])}</a>
      <a class="btn btn-tile btn-small" href="#contact">{e(n['cta'])}</a>
    </nav>
  </div>
</header>"""


def demo(c: dict) -> str:
    d = c["demo"]
    steps = "".join(f'<li data-step="{i}"><span>{e(s)}</span></li>' for i, s in enumerate(d["steps"], 1))
    return f"""<div class="vault" id="vault">
  <div class="vault-head">
    <h2>{icon('lock')}<span>{e(d['title'])}</span></h2>
    <p>{e(d['intro'])}</p>
  </div>
  <div class="vault-fields">
    <div class="field"><label for="vault-note">{e(d['note_label'])}</label>
      <textarea id="vault-note" rows="2" spellcheck="false">{e(d['note_default'])}</textarea></div>
    <div class="field"><label for="vault-pass">{e(d['pass_label'])}</label>
      <input id="vault-pass" type="text" dir="ltr" autocomplete="off" spellcheck="false" value="correct horse battery"></div>
  </div>
  <ol class="vault-steps">{steps}</ol>
  <div class="vault-server" aria-live="polite">
    <div class="vault-server-head"><h3>{e(d['server_title'])}</h3><span id="vault-status"></span></div>
    <dl dir="ltr">
      <div><dt>salt</dt><dd id="vault-salt">…</dd></div>
      <div><dt>iterations</dt><dd>600000</dd></div>
      <div><dt>{e(d['row_wrapped'])}</dt><dd id="vault-wrapped">…</dd></div>
      <div><dt>{e(d['row_cipher'])}</dt><dd id="vault-cipher">…</dd></div>
    </dl>
  </div>
  <div class="vault-unlock">
    <label for="vault-try">{e(d['unlock_label'])}</label>
    <div class="unlock-row">
      <input id="vault-try" type="text" dir="ltr" autocomplete="off" spellcheck="false" placeholder="correct horse battery">
      <button class="btn btn-tile" id="vault-unlock" type="button">{e(d['unlock_button'])}</button>
    </div>
    <p class="vault-result" id="vault-result" aria-live="polite"></p>
  </div>
</div>"""


def hero(c: dict) -> str:
    h = c["hero"]
    resume = c["contact"]["resume_files"][0]["file"]
    facts = "".join(f"<div><dt>{e(f['label'])}</dt><dd>{e(f['value'])}</dd></div>" for f in h["facts"])
    r = c["repos"]
    repos = []
    for item in r["items"]:
        inner = f'<span class="repo-name" dir="ltr">{e(item["name"])}</span><span class="repo-desc">{e(item["desc"])}</span><span class="repo-meta">{e(item["meta"])}</span>'
        if item["url"]:
            repos.append(f'<li><a class="repo" href="{e(item["url"])}" rel="noopener">{icon("github")}{inner}</a></li>')
        else:
            repos.append(f'<li><div class="repo repo-private">{icon("lock")}{inner}</div></li>')
    return f"""<section class="hero" id="top" aria-labelledby="hero-name">
  <div class="hero-art" aria-hidden="true"></div>
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <p class="hero-role">{e(h['role'])}</p>
      <h1 id="hero-name">{e(c['name'])}</h1>
      <p class="hero-statement">{e(h['statement'])}</p>
      <p class="hero-summary">{e(h['summary'])}</p>
      <div class="hero-actions">
        <a class="btn btn-tile" href="#work">{e(h['cta_work'])}</a>
        <a class="btn btn-ghost" href="{{P}}resume/{resume}" download>{icon('download')}<span>{e(h['cta_resume'])}</span></a>
      </div>
      <dl class="hero-facts">{facts}</dl>
    </div>
    {demo(c)}
  </div>
  <div class="wrap repos">
    <h2 class="repos-title">{e(r['title'])}</h2>
    <ul class="repo-list">{''.join(repos)}</ul>
  </div>
</section>"""


def shot(key: str, alt: str, sizes: str, cls: str, label: str) -> str:
    """A screenshot that links to its largest file; site.js opens it in a dialog instead."""
    largest = IMAGES[key]["files"][-1][0]
    return (
        f'<a class="shot" href="{{P}}assets/img/work/{largest}" data-lightbox>'
        f'{picture(key, alt, sizes, cls)}<span class="shot-hint">{icon("expand")}<span class="sr-only">{e(label)}</span></span></a>'
    )


def stage(p: dict, L: dict) -> str:
    media = p.get("media")
    if media:
        main = shot(media["main"]["src"], media["main"]["alt"], "(min-width: 1180px) 860px, 88vw", "shot-main", L["enlarge"])
        inset_key = media["inset"]["src"]
        portrait = IMAGES[inset_key]["h"] > IMAGES[inset_key]["w"]
        inset = shot(inset_key, media["inset"]["alt"], "(min-width: 900px) 240px, 34vw" if portrait else "(min-width: 900px) 420px, 46vw", "shot-inset", L["enlarge"])
        kind = "phone" if portrait else "window"
        return f"""<div class="stage stage-shots">
      <div class="frame frame-main"><span class="frame-bar" aria-hidden="true"><i></i><i></i><i></i></span>{main}</div>
      <div class="frame frame-{kind}">{'<span class="frame-bar" aria-hidden="true"><i></i><i></i><i></i></span>' if kind == 'window' else ''}{inset}</div>
    </div>"""
    t = p["tree"]
    rows = "".join(
        f'<tr><th scope="row" dir="ltr">{e(r["v"])}</th><td>{e(r["scope"])}</td><td><span class="pill{" pill-live" if i == 0 else ""}">{e(r["status"])}</span></td></tr>'
        for i, r in enumerate(p["roadmap"])
    )
    return f"""<div class="stage stage-andarun">
      <figure class="tree">
        <svg viewBox="0 0 420 250" role="img" aria-label="{e(t['caption'])}">
          <g class="tree-edges">
            <path d="M210 44V78H90V118M210 78H330V118M210 78V118"/>
            <path d="M90 150V178H50V208M90 178H130V208M330 150V178H290V208M330 178H370V208"/>
          </g>
          <g class="tree-nodes">
            <rect class="node-root" x="160" y="14" width="100" height="32" rx="16"/><text x="210" y="35">{e(t['you'])}</text>
            <rect x="45" y="118" width="90" height="32" rx="16"/><text x="90" y="139">{e(t['member'])}</text>
            <rect x="165" y="118" width="90" height="32" rx="16"/><text x="210" y="139">{e(t['member'])}</text>
            <rect x="285" y="118" width="90" height="32" rx="16"/><text x="330" y="139">{e(t['member'])}</text>
            <circle cx="50" cy="216" r="9"/><circle cx="130" cy="216" r="9"/><circle cx="290" cy="216" r="9"/>
            <circle class="node-pending" cx="370" cy="216" r="9"/>
          </g>
          <text class="tree-note" x="370" y="244">{e(t['pending'])}</text>
        </svg>
        <figcaption>{e(t['caption'])}</figcaption>
      </figure>
      <div class="roadmap">
        <h4>{{ROADMAP}}</h4>
        <table><tbody>{rows}</tbody></table>
      </div>
    </div>"""


def case(p: dict, L: dict) -> str:
    pid = e(p["id"])
    if p["repo"]:
        repo = f'<a class="btn btn-line btn-small" href="{e(p["repo"])}" rel="noopener">{icon("github")}<span>{e(L["repo"])}</span></a>'
    else:
        repo = f'<span class="private-note">{icon("lock")}<span>{e(L["private"])}</span></span>'
    meta = "".join(
        f"<div><dt>{e(L[k])}</dt><dd>{e(p[k])}</dd></div>" for k in ("role", "license", "status")
    )
    stack = "".join(f"<li>{e(s)}</li>" for s in p["stack"])
    if p.get("highlights"):
        detail = f'<h4>{e(L["highlights"])}</h4><ul class="highlights">{"".join(f"<li>{code(h)}</li>" for h in p["highlights"])}</ul>'
    else:
        rows = "".join(f"<tr><td>{code(d['decision'])}</td><td>{e(d['reason'])}</td></tr>" for d in p["decisions"])
        detail = (
            f'<h4>{e(L["decisions"])}</h4><table class="decisions"><thead><tr><th scope="col">{e(L["decision"])}</th>'
            f'<th scope="col">{e(L["reason"])}</th></tr></thead><tbody>{rows}</tbody></table>'
        )
    proof = ""
    if p.get("verification"):
        proof += f'<div class="proof"><h4>{icon("check")}<span>{e(L["verification"])}</span></h4><p>{e(p["verification"])}</p></div>'
    if p.get("limits"):
        proof += f'<div class="limits"><h4>{e(L["limits"])}</h4><p>{code(p["limits"])}</p></div>'
    return f"""<article class="case" id="work-{pid}" aria-labelledby="work-{pid}-title">
  <header class="case-head">
    <div class="case-titles">
      <p class="case-kind"><span>{e(p['kind'])}</span><span>{e(p['year'])}</span></p>
      <h3 id="work-{pid}-title">{e(p['name'])}</h3>
      <p class="case-tagline">{e(p['tagline'])}</p>
    </div>
    <div class="case-side">
      <dl class="case-meta">{meta}</dl>
      {repo}
    </div>
  </header>
  {stage(p, L).replace('{ROADMAP}', e(L['roadmap']))}
  <div class="case-body">
    <div class="case-story">
      <h4>{e(L['problem'])}</h4><p>{e(p['problem'])}</p>
      <h4>{e(L['design'])}</h4><p>{e(p['design'])}</p>
      <h4>{e(L['stack'])}</h4><ul class="chips" dir="ltr">{stack}</ul>
    </div>
    <div class="case-detail">{detail}{proof}</div>
  </div>
</article>"""


def work(c: dict) -> str:
    w = c["work"]
    cases = "".join(case(p, w["labels"]) for p in w["projects"])
    tabs = "".join(
        f'<li><a href="#work-{e(p["id"])}" data-case><span class="ct-name">{e(p["name"])}</span><span class="ct-kind">{e(p["kind"])}</span></a></li>'
        for p in w["projects"]
    )
    return f"""<section class="section work" id="work" aria-labelledby="work-title">
  <div class="wrap">
    <div class="sec-head"><h2 id="work-title">{e(w['title'])}</h2>{f"<p>{e(w['intro'])}</p>" if w['intro'] else ""}</div>
  </div>
  <nav class="case-tabs" aria-label="{e(w['labels']['tabs'])}"><div class="wrap"><ol>{tabs}</ol></div></nav>
  <div class="wrap">
    <div class="cases">{cases}</div>
  </div>
</section>"""


def approach(c: dict) -> str:
    a = c["approach"]
    about = "".join(f"<p>{e(p)}</p>" for p in a["about"])
    principles = "".join(
        f'<li><h3>{e(p["title"])}</h3><p class="principle">{e(p["text"])}</p><p class="evidence">{e(p["evidence"])}</p></li>'
        for p in a["principles"]
    )
    return f"""<section class="section approach" id="approach" aria-labelledby="approach-title">
  <div class="wrap approach-grid">
    <div class="approach-intro"><h2 id="approach-title">{e(a['title'])}</h2>{about}</div>
    <ul class="principles">{principles}</ul>
  </div>
</section>"""


def skills(c: dict) -> str:
    s = c["skills"]
    ed = c["education"]
    tiers = []
    for t in s["tiers"]:
        groups = "".join(
            (f'<h4>{e(g["label"])}</h4>' if g["label"] else "") + f'<ul{" class=\"inline\"" if g["label"] and all(len(i) <= 30 for i in g["items"]) else ""}>{"".join(f"<li>{e(i)}</li>" for i in g["items"])}</ul>'
            for g in t["groups"]
        )
        tiers.append(f'<div class="tier"><h3>{e(t["name"])}</h3>{groups}</div>')
    used = "".join(f"<li>{e(i)}</li>" for i in s["used_items"])
    return f"""<section class="section skills" id="skills" aria-labelledby="skills-title">
  <div class="wrap">
    <div class="sec-head"><h2 id="skills-title">{e(s['title'])}</h2></div>
    <div class="tiers">{''.join(tiers[:2])}<div class="tier-stack">{''.join(tiers[2:])}</div></div>
    <div class="skills-foot">
      <div><h3>{e(s['used_label'])}</h3><ul class="chips" dir="ltr">{used}</ul></div>
      <div><h3>{e(ed['title'])}</h3><p><strong>{e(ed['degree'])}</strong><br>{e(ed['school'])}, {e(ed['years'])}</p></div>
      <div><h3>{e(s['spoken_label'])}</h3><p>{e(s['spoken'])}</p></div>
    </div>
  </div>
</section>"""


def contact(c: dict) -> str:
    k = c["contact"]
    links = "".join(f'<li><a href="{e(l["href"])}" rel="me noopener">{e(l["label"])}{icon("external")}</a></li>' for l in k["links"])
    files = []
    for f in k["resume_files"]:
        kb = round((STATIC / "resume" / f["file"]).stat().st_size / 1024)
        files.append(
            f'<li><a class="dl" href="{{P}}resume/{e(f["file"])}" download>{icon("file")}<span class="dl-text">'
            f'<b>{e(f["label"])}</b><small><span dir="ltr">PDF, {kb} KB</span></small></span></a></li>'
        )
    return f"""<section class="section contact" id="contact" aria-labelledby="contact-title">
  <div class="hero-art hero-art-soft" aria-hidden="true"></div>
  <div class="wrap contact-grid">
    <div>
      <h2 id="contact-title">{e(k['title'])}</h2>
      <p class="contact-text">{e(k['text'])}</p>
      <p class="mail-row"><a class="mail" href="mailto:{e(k['email'])}" dir="ltr">{e(k['email'])}</a></p>
      <div class="contact-actions">
        <button class="btn btn-ghost btn-small copy-btn" type="button" data-copy="{e(k['email'])}" data-done="{e(k['copied'])}">{icon('copy')}{icon('check')}<span>{e(k['copy'])}</span></button>
        <span class="sr-only" role="status" data-copy-status></span>
        <ul class="profile-links" dir="ltr">{links}</ul>
      </div>
    </div>
    <div class="resume-box">
      <h3>{e(k['resume_title'])}</h3>
      <ul class="downloads">{''.join(files)}</ul>
    </div>
  </div>
</section>"""


def footer(c: dict, lang: str) -> str:
    f = c["footer"]
    n = c["nav"]
    alt = other(lang)
    alt_href = "{P}" + PAGES[alt] if PAGES[alt] else "{P}"
    sections = "".join(f'<li><a href="#{k}">{e(n[k])}</a></li>' for k in ("work", "approach", "skills", "contact"))
    links = "".join(f'<li><a href="{e(l["href"])}" rel="me noopener">{e(l["label"])}</a></li>' for l in c["contact"]["links"])
    links += f'<li><a href="mailto:{e(c["contact"]["email"])}">{icon("mail")}<span dir="ltr">{e(c["contact"]["email"])}</span></a></li>'
    return f"""<footer class="site-footer">
  <div class="wrap footer-grid">
    <div class="footer-id">{MARK}<div><p class="footer-name">{e(c['name'])}</p><p>{e(f['statement'])}</p></div></div>
    <ul class="footer-links">{sections}</ul>
    <ul class="footer-links">{links}</ul>
  </div>
  <div class="wrap footer-base">
    <p>{e(f['note'])}</p>
    <p class="footer-actions"><a class="lang-link" href="{alt_href}" hreflang="{alt}" lang="{alt}">{e(c['switch']['label'])}</a><a href="#top">{icon('arrow-up')}<span>{e(f['top'])}</span></a></p>
  </div>
</footer>"""


def page(lang: str) -> str:
    c = load(lang)
    prefix = "../" * PAGES[lang].count("/")
    strings = json.dumps(c["demo"], ensure_ascii=False).replace("</", "<\\/")
    html = f"""<!DOCTYPE html>
<html lang="{lang}" dir="{c['dir']}">
{head(c, lang)}
<body>
{site_header(c, lang)}
<main id="main">
{hero(c)}
{work(c)}
{approach(c)}
{skills(c)}
{contact(c)}
</main>
{footer(c, lang)}
<dialog class="lightbox" id="lightbox" aria-label="{e(c['work']['labels']['enlarge'])}">
  <figure><img alt="" decoding="async"><figcaption></figcaption></figure>
  <button class="lightbox-close btn btn-ghost btn-small" type="button" data-close>{e(c['work']['labels']['close'])}</button>
</dialog>
<script type="application/json" id="i18n">{strings}</script>
</body>
</html>
"""
    html = html.replace("{P}", prefix) if prefix else html.replace('href="{P}"', 'href="./"').replace("{P}", "")
    return isolate_latin(html) if c["dir"] == "rtl" else html


def not_found() -> str:
    blocks = []
    for lang in PAGES:
        c = load(lang)
        nf = c["notfound"]
        blocks.append(
            f'<div lang="{lang}" dir="{c["dir"]}"><h1>{e(nf["title"])}</h1><p>{e(nf["text"])}</p>'
            f'<p><a class="btn btn-tile" href="/{PAGES[lang]}">{e(nf["back"])}</a></p></div>'
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<title>Page not found, Sepehr Khastoo</title><meta name="robots" content="noindex">
<link rel="icon" href="/assets/img/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/css/site.css"></head>
<body class="notfound-page"><main class="wrap notfound">{''.join(blocks)}</main></body>
</html>
"""


def sitemap() -> str:
    today = date.today().isoformat()
    urls = []
    for lang in PAGES:
        alts = "".join(f'<xhtml:link rel="alternate" hreflang="{c}" href="{page_url(c)}"/>' for c in PAGES)
        urls.append(f"<url><loc>{page_url(lang)}</loc><lastmod>{today}</lastmod>{alts}</url>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">' + "".join(urls) + "</urlset>\n"
    )


def build() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(STATIC, DIST)
    for lang, folder in PAGES.items():
        out = DIST / folder / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(lang), encoding="utf-8")
        print(f"built /{folder}")
    (DIST / "404.html").write_text(not_found(), encoding="utf-8")
    (DIST / "sitemap.xml").write_text(sitemap(), encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")


def serve(port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
    print(f"serving http://localhost:{port}  (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--serve", action="store_true", help="serve dist/ after building")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    build()
    if args.serve:
        serve(args.port)
