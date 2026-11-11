#!/usr/bin/env python3
"""Compiles a LaTeX paper (.tex + .bib/.bbl + optional paper.json) to HTML.

Uses LaTeXML (for exact TeX macro expansion, numbering, cross-references,
tables, code listings, and algorithms) plus KaTeX (pre-rendered to static HTML
at build time when `node` or `gjs` is available, with automatic client-side
KaTeX fallback otherwise). Requires zero non-standard Python packages (`Pillow`
is optional for PNG palette compression).

Quick start:
  python3 tex_to_html.py path/to/main.tex --out mypaper/
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import html
import html.parser
import importlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET

try:
  pil_image = importlib.import_module("PIL.Image")
  pil_image_draw = importlib.import_module("PIL.ImageDraw")
  pil_image_font = importlib.import_module("PIL.ImageFont")
  HAS_PIL = True
except ImportError:
  pil_image = None
  pil_image_draw = None
  pil_image_font = None
  HAS_PIL = False

LTX_NS = "http://dlmf.nist.gov/LaTeXML"
XML_ID_ATTR = "{http://www.w3.org/XML/1998/namespace}id"
LATEXML_TEXTWIDTH_PT = 433.62  # Default 6.0in LaTeXML article \textwidth in pt.
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
KATEX_VERSION = "0.16.22"
KATEX_CDN_CSS = (
    f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.css"
)
KATEX_CDN_JS = (
    f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.js"
)
KATEX_CDN_AUTORENDER = (
    f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}"
    "/dist/contrib/auto-render.min.js"
)
TEMPLATE_REPO_URL = (
    "https://github.com/jonbarron/jonbarron.github.io/tree/master/tex_to_html"
)
FOOTNOTE_SYMBOLS = ["*", "†", "‡", "§", "¶"]


@dataclasses.dataclass
class AuthorInfo:
  """Structured author metadata extracted from LaTeXML or paper.json."""

  name: str
  url: str
  affils: list[str]
  email: str
  notes: list[str]


def local_tag(el: ET.Element) -> str:
  """Strips any XML namespace prefix from an Element tag."""
  return el.tag.split("}", 1)[-1] if "}" in el.tag else el.tag


def label_key(raw: str | None) -> str:
  """Normalizes a LaTeXML `LABEL:...` attribute to a bare label ID."""
  if not raw:
    return ""
  first = raw.split()[0]
  return first[len("LABEL:") :] if first.startswith("LABEL:") else first


def parse_pt(val: str | None) -> float | None:
  """Extracts a floating-point dimension in TeX points (`pt`)."""
  if not val:
    return None
  m = re.search(r"([0-9.]+)\s*pt", val)
  return float(m.group(1)) if m else None


def read_image_dims_stdlib(data: bytes) -> tuple[int, int]:
  """Reads PNG, JPEG, or SVG dimensions using only Python stdlib."""
  if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
    w, h = struct.unpack(">II", data[16:24])
    return int(w), int(h)
  if data[:2] == b"\xff\xd8":
    i = 2
    n = len(data)
    while i + 9 < n:
      if data[i] != 0xFF:
        i += 1
        continue
      marker = data[i + 1]
      if marker == 0xFF:
        i += 1
        continue
      if marker in (0xD8, 0xD9) or (0xD0 <= marker <= 0xD7):
        i += 2
        continue
      seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
      if marker in (
          0xC0,
          0xC1,
          0xC2,
          0xC3,
          0xC5,
          0xC6,
          0xC7,
          0xC9,
          0xCA,
          0xCB,
          0xCD,
          0xCE,
          0xCF,
      ):
        h, w = struct.unpack(">HH", data[i + 5 : i + 9])
        return int(w), int(h)
      i += 2 + seg_len
  head = data[:2048].decode("utf-8", errors="ignore")
  if "<svg" in head:
    vb = re.search(
        r'viewBox=["\']\s*[-0-9.]+\s+[-0-9.]+\s+([0-9.]+)\s+([0-9.]+)', head
    )
    if vb:
      return int(float(vb.group(1))), int(float(vb.group(2)))
  return 800, 600


def favicon_link(emoji: str) -> str:
  """Returns an inline <link rel="icon"> tag rendered from `emoji`."""
  if not emoji:
    return ""
  if (
      HAS_PIL
      and pil_image is not None
      and pil_image_draw is not None
      and pil_image_font is not None
      and os.path.exists(EMOJI_FONT)
  ):
    font = pil_image_font.truetype(EMOJI_FONT, 109)
    im = pil_image.new("RGBA", (160, 160), (0, 0, 0, 0))
    pil_image_draw.Draw(im).text((0, 0), emoji, font=font, embedded_color=True)
    bbox = im.getbbox()
    if bbox:
      im = im.crop(bbox)
    side = max(im.size)
    square = pil_image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    buf = io.BytesIO()
    square.resize((32, 32), pil_image.Resampling.LANCZOS).save(
        buf, format="PNG", optimize=True
    )
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return (
        f'<link rel="icon" type="image/png" href="data:image/png;base64,{b64}">'
    )
  svg = (
      "<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22>"
      f"<text y=%22.9em%22 font-size=%2290%22>{emoji}</text></svg>"
  )
  return f'<link rel="icon" href="data:image/svg+xml,{svg}">'


def extract_braced(text: str, start: int) -> tuple[str, int]:
  """Extracts `{...}` starting at `start`, returning `(inner, next_idx)`."""
  depth = 0
  i = start
  n = len(text)
  while i < n:
    ch = text[i]
    if ch == "\\":
      i += 2
      continue
    if ch == "{":
      depth += 1
    elif ch == "}":
      depth -= 1
      if depth == 0:
        return text[start + 1 : i], i + 1
    i += 1
  raise ValueError(f"Unbalanced braces starting at {text[start:start+40]!r}")


def clean_tex_accents(s: str) -> str:
  """Converts common TeX accents, dashes, and non-breaking spaces to UTF-8."""
  s = (
      s.replace(r"\'a", "á")
      .replace(r"{\'a}", "á")
      .replace(r"\"a", "ä")
      .replace(r"{\"a}", "ä")
      .replace(r"\"o", "ö")
      .replace(r"{\"o}", "ö")
      .replace(r"\"u", "ü")
      .replace(r"{\"u}", "ü")
      .replace(r"\'e", "é")
      .replace(r"{\'e}", "é")
      .replace(r"\'\i", "í")
      .replace(r"{\'\i}", "í")
      .replace(r"\'i", "í")
      .replace(r"{\'i}", "í")
      .replace(r"\'o", "ó")
      .replace(r"{\'o}", "ó")
      .replace(r"\v{c}", "č")
      .replace(r"\v{s}", "š")
      .replace(r"\v{z}", "ž")
      .replace(r"\&", "&")
      .replace("~", " ")
      .replace("---", "—")
      .replace("--", "–")
  )
  for _ in range(3):
    s = re.sub(r"\{([^{}\\]*)\}", r"\1", s)
  return re.sub(r"\s+", " ", s).strip()


def parse_bbl(bbl_path: str) -> tuple[dict[str, dict[str, str]], list[str]]:
  """Parses a BibTeX .bbl file into (bib_dict, ordered_keys)."""
  bib_dict: dict[str, dict[str, str]] = {}
  ordered_keys: list[str] = []
  if not os.path.exists(bbl_path):
    return bib_dict, ordered_keys
  bbl_text = open(bbl_path, encoding="utf-8").read()
  for item in re.split(r"\\bibitem\s*(?=\[|\{)", bbl_text)[1:]:
    if item.startswith("["):
      m = re.match(r"\[([^\]]*)\]\s*\{([^}]+)\}\s*(.*)", item, re.S)
      if not m:
        continue
      opt_label, key, body = m.group(1), m.group(2).strip(), m.group(3)
    else:
      m2 = re.match(r"\{([^}]+)\}\s*(.*)", item, re.S)
      if not m2:
        continue
      opt_label = str(len(ordered_keys) + 1)
      key, body = m2.group(1).strip(), m2.group(2)

    body = re.sub(r"\\end\{thebibliography\}.*", "", body, flags=re.S).strip()
    m_ay = re.match(r"^(.*?)\((\d{4}[a-z]?)\)", opt_label, re.S)
    if m_ay:
      short_author = clean_tex_accents(m_ay.group(1))
      year = m_ay.group(2)
    else:
      short_author = clean_tex_accents(opt_label)
      year = ""

    blocks = [b.strip() for b in re.split(r"\\newblock\s*", body) if b.strip()]
    authors_raw = clean_tex_accents(blocks[0]) if blocks else short_author
    title_raw = blocks[1] if len(blocks) > 1 else ""
    venue_raw = " ".join(blocks[2:]) if len(blocks) > 2 else ""

    def format_bib_part(part: str) -> str:
      part = part.replace(r"\textit{", r"\emph{")
      out_parts: list[str] = []
      pos = 0
      while True:
        idx = part.find(r"\emph{", pos)
        if idx == -1:
          out_parts.append(html.escape(clean_tex_accents(part[pos:])))
          break
        out_parts.append(html.escape(clean_tex_accents(part[pos:idx])))
        inner, pos = extract_braced(part, idx + 5)
        out_parts.append(f"<em>{html.escape(clean_tex_accents(inner))}</em>")
      escaped = "".join(out_parts)
      return re.sub(
          r"arXiv:(\d{4}\.\d{4,5})",
          r'<a href="https://arxiv.org/abs/\1" target="_blank"'
          r' rel="noopener">arXiv:\1</a>',
          escaped,
      )

    authors_html = html.escape(authors_raw)
    title_html = format_bib_part(title_raw)
    venue_html = format_bib_part(venue_raw)
    full_html = (
        f'<span class="bib-authors">{authors_html}</span> <span'
        f' class="bib-title">{title_html}</span> <span'
        f' class="bib-venue">{venue_html}</span>'
    )
    bib_dict[key] = {
        "short_author": short_author,
        "year": year,
        "html": full_html,
    }
    ordered_keys.append(key)
  return bib_dict, ordered_keys


def highlight_python_line(line: str) -> str:
  """Applies lightweight keyword and comment highlighting to a Python line."""
  comment_part = ""
  code_part = line
  if "#" in line:
    idx = line.index("#")
    code_part = line[:idx]
    comment_part = line[idx:]
  esc_code = html.escape(code_part)
  kw_pat = r"\b(import|def|return|lambda|from|as|in|for|if|else)\b"
  esc_code = re.sub(kw_pat, r'<span class="tok-kw">\1</span>', esc_code)
  esc_comment = (
      f'<span class="tok-comment">{html.escape(comment_part)}</span>'
      if comment_part
      else ""
  )
  return esc_code + esc_comment


def render_lstlisting(code: str, idx: int) -> str:
  """Renders a LaTeX `lstlisting` block with a copy-to-clipboard button."""
  lines = code.strip("\n").splitlines()
  highlighted = "\n".join(highlight_python_line(ln) for ln in lines)
  raw_escaped = html.escape(code.strip("\n"))
  return (
      f'<div class="code-card" id="code-block-{idx}"><button'
      f' class="copy-code-btn" data-code="{raw_escaped}"'
      ' onclick="copyCodeBlock(this)" title="Copy code to'
      ' clipboard">Copy</button><pre'
      f' class="code-listing"><code>{highlighted}</code></pre></div>'
  )


def normalize_math_tex(tex: str) -> str:
  """Cleans LaTeXML line-continuation comments inside expanded TeX math."""
  tex = re.sub(r"%[ \t]*\n[ \t]*", "", tex)
  tex = re.sub(r"\s+", " ", tex).strip()
  return tex


def find_katex_bundle(*roots: str) -> str | None:
  """Locates a local or cached katex.min.js bundle (downloading if needed)."""
  candidates: list[str] = []
  if os.environ.get("KATEX_JS"):
    candidates.append(os.environ["KATEX_JS"])
  for root in roots:
    if not root:
      continue
    candidates.extend([
        os.path.join(root, "katex.min.js"),
        os.path.join(root, "node_modules/katex/dist/katex.min.js"),
    ])
    cur = os.path.abspath(root)
    for _ in range(6):
      candidates.append(
          os.path.join(cur, "node_modules/katex/dist/katex.min.js")
      )
      parent = os.path.dirname(cur)
      if parent == cur:
        break
      cur = parent
  candidates.append(
      os.path.expanduser(f"~/.cache/tex_to_html/katex-{KATEX_VERSION}.min.js")
  )

  for p in candidates:
    if p and os.path.exists(p):
      return p

  cache_path = os.path.expanduser(
      f"~/.cache/tex_to_html/katex-{KATEX_VERSION}.min.js"
  )
  try:
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with urllib.request.urlopen(KATEX_CDN_JS, timeout=5) as resp:
      js_bytes = resp.read()
    if b"renderToString" in js_bytes:
      with open(cache_path, "wb") as f:
        f.write(js_bytes)
      return cache_path
  except (OSError, ValueError):
    return None
  return None


def batch_prerender_katex(
    exprs: list[tuple[bool, str]], *search_roots: str
) -> tuple[dict[tuple[bool, str], str], str] | None:
  """Pre-renders unique (display_mode, tex) pairs via `node` or `gjs`."""
  js_bin = shutil.which("node") or shutil.which("gjs")
  if not js_bin:
    return None
  katex_js = find_katex_bundle(*search_roots)
  if not katex_js:
    return None
  if not exprs:
    m_ver = re.search(
        r'version\s*:\s*["\']([0-9]+\.[0-9]+\.[0-9]+)["\']',
        open(katex_js, encoding="utf-8").read(),
    )
    return {}, (m_ver.group(1) if m_ver else KATEX_VERSION)

  unique = sorted(set(exprs))
  payload = [{"d": d, "t": t} for d, t in unique]
  emit_fn = "print" if os.path.basename(js_bin) == "gjs" else "console.log"
  with tempfile.NamedTemporaryFile(
      "w", suffix=".js", delete=False, encoding="utf-8"
  ) as tf:
    tf.write(open(katex_js, encoding="utf-8").read())
    tf.write(
        '\nconst katexLib = typeof katex !== "undefined" ? katex :'
        " module.exports;\n"
    )
    tf.write("\nconst items = " + json.dumps(payload) + ";\n")
    tf.write(f"""
const macros = {{
  "\\\\sfrac": "{{{{}}^{{#1}}\\\\!/\\\\!{{}}_{{#2}}}}",
  "\\\\nicefrac": "{{{{}}^{{#1}}\\\\!/\\\\!{{}}_{{#2}}}}"
}};
const out = [];
for (const it of items) {{
  try {{
    const html = katexLib.renderToString(it.t, {{
      displayMode: it.d,
      throwOnError: true,
      macros: macros
    }});
    out.push({{ok: true, html: html}});
  }} catch (e) {{
    out.push({{ok: false, err: String(e.message || e), tex: it.t}});
  }}
}}
{emit_fn}(JSON.stringify({{version: katexLib.version || "{KATEX_VERSION}", items: out}}));
""")
    tf_path = tf.name

  try:
    res = subprocess.run(
        [js_bin, tf_path], capture_output=True, text=True, check=True
    )
  finally:
    os.remove(tf_path)

  parsed = json.loads(res.stdout.strip().splitlines()[-1])
  katex_ver = str(parsed.get("version") or KATEX_VERSION)
  results = parsed["items"]
  errors = [
      f"  [KaTeX] {r['tex']} => {r['err']}" for r in results if not r["ok"]
  ]
  if errors:
    raise RuntimeError("KaTeX build-time errors:\n" + "\n".join(errors))

  cache = {
      (unique[i][0], unique[i][1]): results[i]["html"]
      for i in range(len(unique))
  }
  return cache, katex_ver


def resolve_graphics_dirs(
    tex_dir: str, main_tex: str, build_dir: str
) -> list[str]:
  r"""Extracts \graphicspath{{...}} directories from main.tex + fallback dirs."""
  dirs: list[str] = []
  for m in re.finditer(r"\\graphicspath\{(.*)\}", main_tex):
    for sub in re.findall(r"\{([^{}]+)\}", m.group(1)):
      cand = os.path.normpath(os.path.join(tex_dir, sub.strip()))
      if os.path.isdir(cand) and cand not in dirs:
        dirs.append(cand)
  for fallback in (
      tex_dir,
      os.path.normpath(os.path.join(tex_dir, "../figures/out")),
      build_dir,
  ):
    if os.path.isdir(fallback) and fallback not in dirs:
      dirs.append(fallback)
  return dirs


def ensure_bbl(main_tex_path: str, tex_dir: str, build_dir: str) -> str:
  """Returns path to .bbl, running pdflatex+bibtex in build_dir if needed."""
  stem = os.path.splitext(os.path.basename(main_tex_path))[0]
  for cand in (
      os.path.join(build_dir, f"{stem}.bbl"),
      os.path.join(tex_dir, f"{stem}.bbl"),
  ):
    if os.path.exists(cand):
      if cand != os.path.join(build_dir, f"{stem}.bbl"):
        shutil.copy2(cand, os.path.join(build_dir, f"{stem}.bbl"))
      return cand

  tex_src = open(main_tex_path, encoding="utf-8").read()
  if r"\bibliography{" not in tex_src:
    return os.path.join(build_dir, f"{stem}.bbl")

  pdflatex = shutil.which("pdflatex")
  bibtex = shutil.which("bibtex")
  if not pdflatex or not bibtex:
    return os.path.join(build_dir, f"{stem}.bbl")

  env = os.environ.copy()
  fig_dirs = resolve_graphics_dirs(tex_dir, tex_src, build_dir)
  env["TEXINPUTS"] = ":".join([tex_dir] + fig_dirs + [env.get("TEXINPUTS", "")])
  env["BIBINPUTS"] = f"{tex_dir}:{env.get('BIBINPUTS', '')}"
  env["BSTINPUTS"] = f"{tex_dir}:{env.get('BSTINPUTS', '')}"
  subprocess.run(
      [pdflatex, "-interaction=nonstopmode", main_tex_path],
      cwd=build_dir,
      env=env,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      check=False,
  )
  subprocess.run(
      [bibtex, stem],
      cwd=build_dir,
      env=env,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      check=False,
  )
  return os.path.join(build_dir, f"{stem}.bbl")


def run_latexml_to_xml(
    main_tex_path: str,
    tex_dir: str,
    fig_dirs: list[str],
    build_dir: str,
    script_dir: str,
) -> str:
  """Runs `latexml` on main_tex_path to produce a macro-expanded XML AST."""
  latexml_bin = shutil.which("latexml") or "/usr/bin/latexml"
  if not os.path.exists(latexml_bin):
    raise RuntimeError(
        "`latexml` not found. Install via `apt install latexml` (Linux) or "
        "`brew install latexml` (macOS)."
    )

  main_tex = open(main_tex_path, encoding="utf-8").read()

  # Auto-stub local conference .sty files in tex_dir lacking a .ltxml binding.
  venue_pat = re.compile(
      r"^(neurips|nips|icml|iclr|cvpr|iccv|eccv|aaai|acl|emnlp|naacl|corl|rss|siggraph)",
      re.I,
  )
  for m in re.finditer(r"\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}", main_tex):
    for pkg in (p.strip() for p in m.group(1).split(",")):
      local_sty = os.path.join(tex_dir, f"{pkg}.sty")
      local_ltxml = os.path.join(tex_dir, f"{pkg}.sty.ltxml")
      if os.path.exists(local_sty) and not os.path.exists(local_ltxml):
        sty_src = open(local_sty, encoding="utf-8", errors="ignore").read()
        is_layout_sty = bool(venue_pat.match(pkg)) or any(
            kw in sty_src
            for kw in (
                "\\fancyhf",
                "\\twocolumn",
                "eso-pic",
                "\\@maketitle",
                "\\paperwidth",
            )
        )
        if not is_layout_sty:
          continue
        natbib_line = (
            "RequirePackage('natbib', options => ['round', 'authoryear']);\n"
            if "natbib" in sty_src
            else ""
        )
        stub_path = os.path.join(build_dir, f"{pkg}.sty.ltxml")
        with open(stub_path, "w", encoding="utf-8") as sf:
          sf.write(
              "package LaTeXML::Package::Pool;\n"
              "use strict;\nuse warnings;\nuse LaTeXML::Package;\n"
              f"{natbib_line}"
              "1;\n"
          )

  xml_out = os.path.join(build_dir, "main.xml")
  log_out = os.path.join(build_dir, "latexml.log")
  search_dirs = [build_dir, tex_dir, script_dir] + [
      d for d in fig_dirs if d not in (build_dir, tex_dir, script_dir)
  ]

  env = os.environ.copy()
  env["TEXINPUTS"] = ":".join(search_dirs + [env.get("TEXINPUTS", "")])
  env["BIBINPUTS"] = f"{tex_dir}:{env.get('BIBINPUTS', '')}"
  env["BSTINPUTS"] = f"{tex_dir}:{env.get('BSTINPUTS', '')}"

  cmd = [latexml_bin] + [f"--path={d}" for d in search_dirs]
  preload_ltxml = next(
      (
          os.path.join(d, "paper_latexml.ltxml")
          for d in (script_dir, tex_dir)
          if os.path.exists(os.path.join(d, "paper_latexml.ltxml"))
      ),
      None,
  )
  if preload_ltxml:
    cmd.append("--preload=paper_latexml.ltxml")
  cmd.extend([f"--dest={xml_out}", f"--log={log_out}", main_tex_path])

  subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)

  log_txt = open(log_out, encoding="utf-8").read()
  fatal_or_err = [
      ln for ln in log_txt.splitlines() if ln.startswith(("Error:", "Fatal:"))
  ]
  if fatal_or_err:
    raise RuntimeError(
        "LaTeXML reported errors:\n" + "\n".join(fatal_or_err[:20])
    )
  return xml_out


def strip_tags_plain(html_fragment: str) -> str:
  """Strips HTML and duplicate MathML markup into plain text."""
  text = re.sub(
      r'<span class="katex-mathml">.*?</span>', "", html_fragment, flags=re.S
  )
  text = re.sub(r"<[^>]+>", "", text)
  return re.sub(r"\s+", " ", html.unescape(text)).strip()


def format_grouped_emails(emails: list[str]) -> str:
  """Groups emails sharing a domain into `{u1, u2}@domain`."""
  domain_order: list[str] = []
  by_domain: dict[str, list[str]] = {}
  raw_others: list[str] = []
  for em in emails:
    em = em.strip()
    if not em:
      continue
    if "@" in em and not em.startswith("{"):
      user, dom = em.split("@", 1)
      if dom not in by_domain:
        domain_order.append(dom)
        by_domain[dom] = []
      if user not in by_domain[dom]:
        by_domain[dom].append(user)
    else:
      raw_others.append(em)

  groups: list[str] = []
  for dom in domain_order:
    users = by_domain[dom]
    if len(users) == 1:
      groups.append(f"{users[0]}@{dom}")
    else:
      groups.append("{" + ", ".join(users) + f"}}@{dom}")
  groups.extend(raw_others)
  return ", ".join(groups)


def _branch_math_nodes(container: ET.Element) -> set[ET.Element]:
  """Returns `<ltx:Math>` elements nested inside `<ltx:MathBranch>`."""
  out: set[ET.Element] = set()
  for br in container.findall(f".//{{{LTX_NS}}}MathBranch"):
    out.update(br.findall(f".//{{{LTX_NS}}}Math"))
  return out


class LaTeXMLPaperCompiler:
  """Walks LaTeXML's semantic XML AST and emits clean jonbarron.info HTML."""

  def __init__(
      self,
      main_tex_path: str,
      build_dir: str,
      external_img_dir: str | None = None,
      out_html_dir: str | None = None,
  ):
    self.main_tex_path = os.path.abspath(main_tex_path)
    self.tex_dir = os.path.dirname(self.main_tex_path)
    self.build_dir = os.path.abspath(build_dir)
    self.script_dir = os.path.dirname(os.path.abspath(__file__))
    self.external_img_dir = external_img_dir
    self.out_html_dir = out_html_dir

    main_tex_src = open(self.main_tex_path, encoding="utf-8").read()
    self.fig_dirs = resolve_graphics_dirs(
        self.tex_dir, main_tex_src, self.build_dir
    )

    meta_path = os.path.join(self.tex_dir, "paper.json")
    self.meta = (
        json.load(open(meta_path, encoding="utf-8"))
        if os.path.exists(meta_path)
        else {}
    )
    bbl_path = ensure_bbl(self.main_tex_path, self.tex_dir, self.build_dir)
    self.bib_dict, self.bib_order = parse_bbl(bbl_path)
    self.embedded_images: dict[str, tuple[str, int, int]] = {}
    self.listing_counter = 0

    xml_path = run_latexml_to_xml(
        self.main_tex_path,
        self.tex_dir,
        self.fig_dirs,
        self.build_dir,
        self.script_dir,
    )
    self.root = ET.parse(xml_path).getroot()

    # Map every LABEL:... in the XML tree to its human-readable refnum & type
    self.label_info: dict[str, tuple[str, str]] = {}
    self._index_labels()

    # Batch pre-render math expressions with KaTeX if node/gjs is available
    branch_math = _branch_math_nodes(self.root)
    math_reqs: list[tuple[bool, str]] = []
    for m in self.root.findall(f".//{{{LTX_NS}}}Math"):
      if m in branch_math:
        continue
      is_disp = m.get("mode") == "display"
      tex = normalize_math_tex(m.get("tex") or "")
      if tex:
        math_reqs.append((is_disp, tex))
    prerendered = batch_prerender_katex(
        math_reqs, self.script_dir, self.tex_dir
    )
    if prerendered is not None:
      self.katex_cache, self.katex_version = prerendered
    else:
      self.katex_cache = None
      self.katex_version = KATEX_VERSION

  def _elem_refnum(self, el: ET.Element, default: str = "") -> str:
    """Extracts `<ltx:tag role='refnum'>` from `el` (normalizing `1(a)`->`1a`)."""
    lbl = label_key(el.get("labels"))
    if lbl and lbl in self.label_info and self.label_info[lbl][1]:
      return self.label_info[lbl][1]
    tags_el = el.find(f"{{{LTX_NS}}}tags")
    if tags_el is not None:
      rn = tags_el.find(f"{{{LTX_NS}}}tag[@role='refnum']")
      if rn is not None and rn.text:
        val = rn.text.strip()
        return re.sub(r"^(\d+)\(([a-z])\)$", r"\1\2", val)
    return default

  def _index_labels(self) -> None:
    """Indexes all `labels` attributes in the XML tree for cross-references."""
    for el in self.root.iter():
      raw_labels = (el.get("labels") or "").split()
      if not raw_labels:
        continue
      t = local_tag(el)
      refnum = ""
      tags_el = el.find(f"{{{LTX_NS}}}tags")
      if tags_el is not None:
        rn = tags_el.find(f"{{{LTX_NS}}}tag[@role='refnum']")
        if rn is not None and rn.text:
          refnum = rn.text.strip()
      # Convert LaTeXML "1(a)" subfigure refnum to "1a" to match \ref{fig:fig1a}
      refnum = re.sub(r"^(\d+)\(([a-z])\)$", r"\1\2", refnum)
      for tok in raw_labels:
        lbl = label_key(tok)
        if lbl:
          self.label_info[lbl] = (t, refnum)

  def _find_figure_file(self, filename: str) -> str:
    """Resolves a figure stem or path across configured graphics directories."""
    exts = ("", ".png", ".jpg", ".jpeg", ".svg", ".pdf")
    for d in self.fig_dirs:
      for ext in exts:
        cand = os.path.join(d, filename + ext)
        if os.path.isfile(cand):
          return cand
    raise FileNotFoundError(
        f"Figure file {filename!r} not found in {self.fig_dirs}"
    )

  def get_image_asset(self, filename: str) -> tuple[str, int, int]:
    """Loads, optionally rasterizes/compresses, and emits a figure URI + size."""
    if filename in self.embedded_images:
      return self.embedded_images[filename]

    src_path = self._find_figure_file(filename)
    src_ext = os.path.splitext(src_path)[1]
    clean_rel = os.path.normpath(filename.replace("\\", "/").lstrip("/"))
    if clean_rel.startswith(".."):
      clean_rel = os.path.basename(src_path)
    elif not os.path.splitext(clean_rel)[1]:
      clean_rel += src_ext
    out_rel = clean_rel.replace(os.sep, "/")
    mime = "image/png"

    # Automatically rasterize PDF figures via pdftoppm if present
    if src_path.lower().endswith(".pdf"):
      pdftoppm = shutil.which("pdftoppm")
      if not pdftoppm:
        raise RuntimeError(
            f"PDF figure {src_path} requires `pdftoppm` (poppler-utils) to"
            " convert to PNG."
        )
      rel_stem = os.path.splitext(out_rel)[0]
      safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "__", rel_stem)
      png_prefix = os.path.join(self.build_dir, safe_stem)
      subprocess.run(
          [pdftoppm, "-png", "-r", "200", "-singlefile", src_path, png_prefix],
          check=True,
      )
      src_path = png_prefix + ".png"
      out_rel = rel_stem + ".png"

    ext_lower = os.path.splitext(out_rel)[1].lower()
    if ext_lower in (".jpg", ".jpeg"):
      mime = "image/jpeg"
    elif ext_lower == ".svg":
      mime = "image/svg+xml"

    raw_bytes = open(src_path, "rb").read()
    if HAS_PIL and pil_image is not None and ext_lower == ".png":
      im = pil_image.open(src_path)
      orig_w, orig_h = im.size
      buf = io.BytesIO()
      if self.meta.get("quantize_png", True):
        q_src = im
        if q_src.mode not in ("RGB", "RGBA", "L", "P"):
          q_src = q_src.convert("RGBA" if "A" in q_src.mode else "RGB")
        im_q = q_src.quantize(
            colors=256,
            method=pil_image.Quantize.FASTOCTREE,
            dither=pil_image.Dither.NONE,
        )
        im_q.save(buf, format="PNG", optimize=True)
      else:
        im.save(buf, format="PNG", optimize=True)
      opt_bytes = buf.getvalue()
      img_bytes = opt_bytes if len(opt_bytes) < len(raw_bytes) else raw_bytes
    elif HAS_PIL and pil_image is not None and ext_lower in (".jpg", ".jpeg"):
      im = pil_image.open(src_path)
      orig_w, orig_h = im.size
      img_bytes = raw_bytes
    else:
      img_bytes = raw_bytes
      orig_w, orig_h = read_image_dims_stdlib(img_bytes)

    if self.external_img_dir and self.out_html_dir:
      dest_path = os.path.join(
          self.out_html_dir, self.external_img_dir, *out_rel.split("/")
      )
      os.makedirs(os.path.dirname(dest_path), exist_ok=True)
      with open(dest_path, "wb") as f:
        f.write(img_bytes)
      uri = f"{self.external_img_dir.rstrip('/')}/{out_rel}"
    else:
      b64 = base64.b64encode(img_bytes).decode("ascii")
      uri = f"data:{mime};base64,{b64}"
    self.embedded_images[filename] = (uri, orig_w, orig_h)
    return uri, orig_w, orig_h

  def render_math_str(self, tex: str, is_disp: bool) -> str:
    """Returns pre-rendered KaTeX HTML or client-side delimiter fallback."""
    if self.katex_cache is not None:
      return self.katex_cache.get((is_disp, tex), html.escape(tex))
    delim_l, delim_r = (r"\[", r"\]") if is_disp else (r"\(", r"\)")
    return f"{delim_l}{html.escape(tex)}{delim_r}"

  def render_inline_children(self, parent: ET.Element) -> str:
    """Renders inline child nodes while binding adjacent punctuation to math."""
    parts: list[str] = []
    if parent.text:
      parts.append(html.escape(parent.text))
    for ch in parent:
      node_html = self.render_inline_node(ch)
      tail_str = ch.tail or ""
      # Glue adjacent opening '(' / '[' and closing punctuation ('.', ',', ';',
      # ':', ')', ']') to inline math so parens/periods never wrap alone.
      if node_html.startswith('<span class="math-inline">'):
        prefix = ""
        if parts and parts[-1] and parts[-1][-1] in "([":
          prefix = parts[-1][-1]
          parts[-1] = parts[-1][:-1]
        m_punct = re.match(r"^([.,;:!?)\]]+)", tail_str)
        suffix = ""
        if m_punct:
          suffix = html.escape(m_punct.group(1))
          tail_str = tail_str[len(m_punct.group(1)) :]
        if prefix or suffix:
          if len(strip_tags_plain(node_html)) <= 28:
            node_html = (
                f'<span class="math-nowrap">{prefix}{node_html}{suffix}</span>'
            )
          else:
            p_join = f"{prefix}\u2060" if prefix else ""
            s_join = f"\u2060{suffix}" if suffix else ""
            node_html = f"{p_join}{node_html}{s_join}"
      parts.append(node_html)
      if tail_str:
        parts.append(html.escape(tail_str))
    return "".join(parts).replace("\xa0", "&nbsp;")

  def render_inline_node(self, el: ET.Element) -> str:
    """Renders a single inline LaTeXML element (`Math`, `emph`, `ref`, etc.)."""
    t = local_tag(el)
    if t == "Math":
      tex = normalize_math_tex(el.get("tex") or "")
      is_disp = el.get("mode") == "display"
      rendered = self.render_math_str(tex, is_disp)
      cls = "math-display" if is_disp else "math-inline"
      return f'<span class="{cls}">{rendered}</span>'
    if t == "emph":
      return f"<em>{self.render_inline_children(el)}</em>"
    if t == "sup":
      return f"<sup>{self.render_inline_children(el)}</sup>"
    if t == "sub":
      return f"<sub>{self.render_inline_children(el)}</sub>"
    if t == "text":
      font = el.get("font", "")
      inner = self.render_inline_children(el)
      if font == "bold":
        return f"<strong>{inner}</strong>"
      if font == "italic":
        return f"<em>{inner}</em>"
      if font == "typewriter":
        return f"<code>{inner}</code>"
      if font == "smallcaps":
        return f'<span style="font-variant:small-caps">{inner}</span>'
      return inner
    if t == "verbatim":
      return f"<code>{html.escape(''.join(el.itertext()))}</code>"
    if t == "break":
      return "<br>"
    if t in ("url", "ref") and el.get("href"):
      href = el.get("href") or ""
      link_txt = self.render_inline_children(el) or html.escape(href)
      return (
          f'<a href="{html.escape(href)}" target="_blank"'
          f' rel="noopener">{link_txt}</a>'
      )
    if t == "ref":
      lbl = label_key(el.get("labelref"))
      _, refnum = self.label_info.get(lbl, ("", "??"))
      text = self.render_inline_children(el).strip() or html.escape(refnum)
      return (
          f'<a href="#{html.escape(lbl)}" class="xref"'
          f' data-ref="{html.escape(lbl)}">{text}</a>'
      )
    if t == "cite":
      return self.render_cite(el)
    if t in ("note", "tags", "toccaption", "indexmark"):
      return ""
    return self.render_inline_children(el)

  def render_cite(self, cite_el: ET.Element) -> str:
    """Renders a `natbib` or numeric `<ltx:cite>` element as hoverable links."""
    cls = cite_el.get("class") or ""
    bibref = cite_el.find(f"{{{LTX_NS}}}bibref")
    if bibref is None:
      return self.render_inline_children(cite_el)
    keys = [
        k.strip() for k in (bibref.get("bibrefs") or "").split(",") if k.strip()
    ]

    def link_key(k: str, mode: str) -> str:
      info = self.bib_dict.get(k)
      if not info:
        return "??"
      sa, yr = html.escape(info["short_author"]), html.escape(info["year"])
      if not yr:
        label = sa
      else:
        label = f"{sa} ({yr})" if mode == "citet" else f"{sa}, {yr}"
      return (
          f'<a href="#bib-{html.escape(k)}" class="cite-link"'
          f' data-bib="{html.escape(k)}">{label}</a>'
      )

    if "citet" in cls:
      return "; ".join(link_key(k, "citet") for k in keys)
    if "citealt" in cls:
      return "; ".join(link_key(k, "citealt") for k in keys)
    if keys and all(
        k in self.bib_dict and not self.bib_dict[k]["year"] for k in keys
    ):
      return "[" + ", ".join(link_key(k, "citep") for k in keys) + "]"
    return "(" + "; ".join(link_key(k, "citep") for k in keys) + ")"

  def render_equation(self, eq_el: ET.Element) -> str:
    """Renders a display equation row with an optional right-aligned number."""
    lbl = label_key(eq_el.get("labels"))
    eq_num = self._elem_refnum(eq_el)
    branch_math = _branch_math_nodes(eq_el)
    math_parts = []
    for m in eq_el.findall(f".//{{{LTX_NS}}}Math"):
      if m in branch_math:
        continue
      tex = normalize_math_tex(m.get("tex") or "")
      if tex:
        math_parts.append(self.render_math_str(tex, True))
    id_attr = f' id="{html.escape(lbl)}"' if lbl else ""
    num_html = (
        f'<span class="eq-num">({html.escape(eq_num)})</span>' if eq_num else ""
    )
    return (
        f'<div class="equation-row"{id_attr}>'
        f'<div class="math-display">{"".join(math_parts)}</div>'
        f"{num_html}</div>"
    )

  def render_graphics_img(
      self,
      g_el: ET.Element,
      css_class: str,
      alt_text: str,
      parent_pt: float = LATEXML_TEXTWIDTH_PT,
  ) -> str:
    """Renders an `<ltx:graphics>` element as a responsive `<img>` tag."""
    fname = g_el.get("graphic") or ""
    uri, orig_w, orig_h = self.get_image_asset(fname)
    opts = g_el.get("options") or ""
    w_pt = parse_pt(opts)
    w_pct = min(100.0, (w_pt / parent_pt) * 100.0) if w_pt else 100.0
    esc_alt = html.escape(alt_text or fname)
    return (
        f'<img src="{uri}" alt="{esc_alt}" width="{orig_w}" height="{orig_h}"'
        f' class="{css_class}" style="width:{w_pct:.1f}%;" loading="lazy">'
    )

  def render_subfigure(self, sf_el: ET.Element, idx: int) -> str:
    """Renders a `subcaption` subfigure column with proportional flex width."""
    sub_lbl = label_key(sf_el.get("labels"))
    sub_letter = chr(ord("a") + idx)
    w_pt = parse_pt(sf_el.get("width")) or LATEXML_TEXTWIDTH_PT
    w_pct = (w_pt / LATEXML_TEXTWIDTH_PT) * 100.0

    cap_el = sf_el.find(f"{{{LTX_NS}}}caption")
    cap_html = self.render_caption_inner(cap_el) if cap_el is not None else ""
    alt_plain = strip_tags_plain(f"({sub_letter}) {cap_html}")

    capmargin_el = sf_el.find(f"{{{LTX_NS}}}note[@role='capmargin']")
    subcap_style = ""
    if capmargin_el is not None and capmargin_el.text:
      margin_frac = float(capmargin_el.text.strip())
      subfig_frac = w_pt / LATEXML_TEXTWIDTH_PT
      if subfig_frac > 0:
        subcap_style = (
            f' style="padding-left: {margin_frac / subfig_frac * 100:.2f}%;"'
        )

    imgs_html = "".join(
        self.render_graphics_img(g, "fig-img zoomable", alt_plain)
        for g in sf_el.findall(f"{{{LTX_NS}}}graphics")
    )
    id_attr = f' id="{html.escape(sub_lbl)}"' if sub_lbl else ""
    return (
        f'<div class="subfigure"{id_attr} style="flex: 0 0 {w_pct:.2f}%;'
        f' max-width: {w_pct:.2f}%;">{imgs_html}<div'
        f' class="subcaption"{subcap_style}><strong>({sub_letter})</strong>'
        f" {cap_html}</div></div>"
    )

  def render_caption_inner(self, cap_el: ET.Element) -> str:
    """Renders inner caption markup while omitting LaTeXML's auto-tag prefix."""
    parts: list[str] = []
    if cap_el.text:
      parts.append(html.escape(cap_el.text))
    for ch in cap_el:
      if local_tag(ch) == "tag":
        if ch.tail:
          parts.append(html.escape(ch.tail))
        continue
      parts.append(self.render_inline_node(ch))
      if ch.tail:
        parts.append(html.escape(ch.tail))
    return "".join(parts).replace("\xa0", "&nbsp;").strip()

  def render_widget_note(self, note_el: ET.Element) -> str:
    r"""Renders an optional `\htmlwidget` note as a responsive `<iframe>`."""
    src = (note_el.text or "").strip()
    opts = note_el.get("class") or ""
    h_match = re.search(r"height\s*=\s*([0-9]+(?:px)?)", opts)
    height = h_match.group(1) if h_match else "520px"
    if height.isdigit():
      height += "px"
    return (
        f'<iframe class="widget-frame" src="{html.escape(src)}"'
        f' style="height:{html.escape(height)};" loading="lazy"></iframe>'
    )

  def render_figure(self, fig_el: ET.Element) -> str:
    """Renders `<ltx:figure>` (standard, subfigures, minipages, or widgets)."""
    cls = fig_el.get("class") or ""
    fig_lbl = label_key(fig_el.get("labels"))
    fig_num = self._elem_refnum(fig_el)

    # Optional in-place widget replacement inside \begin{figure}:
    widget_note = fig_el.find(f"{{{LTX_NS}}}note[@role='htmlwidget']")
    if widget_note is not None and "replace" in (
        widget_note.get("class") or ""
    ):
      cap_el = fig_el.find(f"{{{LTX_NS}}}caption")
      cap_html = self.render_caption_inner(cap_el) if cap_el is not None else ""
      cap_tag = ""
      if cap_html:
        cap_tag = (
            '<figcaption class="fig-caption"><strong class="fig-label">Figure'
            f" {html.escape(fig_num)}:</strong> {cap_html}</figcaption>"
        )
      id_attr = f' id="{html.escape(fig_lbl)}"' if fig_lbl else ""
      return (
          f'<figure class="paper-figure"{id_attr}>'
          f"{self.render_widget_note(widget_note)}{cap_tag}</figure>"
      )

    # Case 1a: Left minipage promoted to outer <ltx:figure class="ltx_minipage">
    trailing_mp = next(
        (
            ch
            for ch in fig_el
            if local_tag(ch) == "block"
            and "ltx_minipage" in (ch.get("class") or "")
        ),
        None,
    )
    if "ltx_minipage" in cls and trailing_mp is not None:
      w1_pct = (
          (parse_pt(fig_el.get("width")) or 214.6)
          / LATEXML_TEXTWIDTH_PT
          * 100.0
      )
      w2_pct = (
          (parse_pt(trailing_mp.get("width")) or 206.0)
          / LATEXML_TEXTWIDTH_PT
          * 100.0
      )
      cap_el = fig_el.find(f"{{{LTX_NS}}}caption")
      cap_html = self.render_caption_inner(cap_el) if cap_el is not None else ""
      alt_plain = strip_tags_plain(f"Figure {fig_num}: {cap_html}")
      left_parts = [
          self.render_graphics_img(g, "fig-img zoomable", alt_plain)
          for g in fig_el.findall(f"{{{LTX_NS}}}graphics")
      ]
      if cap_html:
        left_parts.append(
            '<figcaption class="fig-caption"><strong class="fig-label">Figure'
            f" {html.escape(fig_num)}:</strong> {cap_html}</figcaption>"
        )
      right_parts = [
          self.render_graphics_img(g, "fig-img zoomable", alt_plain)
          for g in trailing_mp.findall(f".//{{{LTX_NS}}}graphics")
      ]
      id_attr = f' id="{html.escape(fig_lbl)}"' if fig_lbl else ""
      return (
          f'<figure class="paper-figure"{id_attr}><div'
          ' class="fig-minipage-row"><div class="fig-minipage" style="flex: 0'
          f" 0 {w1_pct:.2f}%; max-width:"
          f' {w1_pct:.2f}%;">{"".join(left_parts)}</div><div'
          f' class="fig-minipage" style="flex: 0 0 {w2_pct:.2f}%; max-width:'
          f' {w2_pct:.2f}%;">{"".join(right_parts)}</div></div></figure>'
      )

    # Case 1b: Outer <ltx:figure> with child <ltx:figure class="ltx_minipage">
    mp_children = [
        ch
        for ch in fig_el
        if local_tag(ch) == "figure"
        and "ltx_minipage" in (ch.get("class") or "")
    ]
    if mp_children:
      cols_html = []
      for mp in mp_children:
        w_pct = (
            (parse_pt(mp.get("width")) or 216.0) / LATEXML_TEXTWIDTH_PT * 100.0
        )
        mp_subfigs = [
            ch
            for ch in mp
            if local_tag(ch) == "figure"
            and "ltx_minipage" not in (ch.get("class") or "")
        ]
        inner_parts = []
        if mp_subfigs:
          sub_html = "".join(
              self.render_subfigure(sf, i) for i, sf in enumerate(mp_subfigs)
          )
          inner_parts.append(f'<div class="subfigure-row">{sub_html}</div>')
        else:
          cap_el = mp.find(f"{{{LTX_NS}}}caption")
          cap_html = (
              self.render_caption_inner(cap_el) if cap_el is not None else ""
          )
          alt_plain = strip_tags_plain(f"Figure {fig_num}: {cap_html}")
          for g in mp.findall(f"{{{LTX_NS}}}graphics"):
            inner_parts.append(
                self.render_graphics_img(g, "fig-img zoomable", alt_plain)
            )
          if cap_html:
            inner_parts.append(
                '<figcaption class="fig-caption"><strong'
                f' class="fig-label">Figure {html.escape(fig_num)}:</strong>'
                f" {cap_html}</figcaption>"
            )
        cols_html.append(
            f'<div class="fig-minipage" style="flex: 0 0 {w_pct:.2f}%;'
            f' max-width: {w_pct:.2f}%;">{"".join(inner_parts)}</div>'
        )
      id_attr = f' id="{html.escape(fig_lbl)}"' if fig_lbl else ""
      return (
          f'<figure class="paper-figure"{id_attr}><div'
          f' class="fig-minipage-row">{"".join(cols_html)}</div></figure>'
      )

    # Case 2: Standard figure with optional top legend and optional subfigures.
    subfigs = [ch for ch in fig_el if local_tag(ch) == "figure"]
    cap_el = fig_el.find(f"{{{LTX_NS}}}caption")
    cap_html = self.render_caption_inner(cap_el) if cap_el is not None else ""
    alt_plain = strip_tags_plain(f"Figure {fig_num}: {cap_html}")

    parts = []
    img_cls = "fig-legend-img zoomable" if subfigs else "fig-img zoomable"
    for g in fig_el.findall(f"{{{LTX_NS}}}graphics"):
      img_tag = self.render_graphics_img(
          g, img_cls, "Legend" if subfigs else alt_plain
      )
      parts.append(f'<div class="fig-top-img-wrap">{img_tag}</div>')

    if subfigs:
      sub_html = "".join(
          self.render_subfigure(sf, i) for i, sf in enumerate(subfigs)
      )
      parts.append(f'<div class="subfigure-row">{sub_html}</div>')

    if cap_html:
      parts.append(
          '<figcaption class="fig-caption"><strong class="fig-label">Figure'
          f" {html.escape(fig_num)}:</strong> {cap_html}</figcaption>"
      )

    id_attr = f' id="{html.escape(fig_lbl)}"' if fig_lbl else ""
    return f'<figure class="paper-figure"{id_attr}>{"".join(parts)}</figure>'

  def render_algorithm_float(self, float_el: ET.Element) -> str:
    """Renders an {algorithm} + {algorithmic} / algpseudocode float."""
    alg_lbl = label_key(float_el.get("labels"))
    alg_num = self._elem_refnum(float_el)
    cap_el = float_el.find(f"{{{LTX_NS}}}caption")
    cap_html = self.render_caption_inner(cap_el) if cap_el is not None else ""
    hdr_prefix = (
        f'<strong class="fig-label">Algorithm {html.escape(alg_num)}:</strong> '
        if alg_num
        else '<strong class="fig-label">Algorithm:</strong> '
    )
    header_html = (
        f'<div class="algorithm-header">{hdr_prefix}{cap_html}</div>'
        if (cap_html or alg_num)
        else ""
    )

    def line_number_text(ll_el: ET.Element) -> str:
      rn = ll_el.find(f"{{{LTX_NS}}}tags/{{{LTX_NS}}}tag[@role='refnum']")
      if rn is None:
        rn = ll_el.find(f"{{{LTX_NS}}}tags/{{{LTX_NS}}}tag")
      return rn.text.strip() if (rn is not None and rn.text) else ""

    lines_html: list[str] = []
    listing_el = float_el.find(f".//{{{LTX_NS}}}listing")
    if listing_el is not None:
      all_ll = listing_el.findall(f"{{{LTX_NS}}}listingline")
      any_numbered = any(bool(line_number_text(ll)) for ll in all_ll)
      for ll in all_ll:
        lno = line_number_text(ll)

        code_parts: list[str] = []
        comment_html = ""
        if ll.text:
          code_parts.append(html.escape(ll.text))
        for ch in ll:
          if local_tag(ch) == "tags":
            if ch.tail:
              code_parts.append(html.escape(ch.tail))
            continue
          if local_tag(ch) == "text" and "float:right" in (
              ch.get("cssstyle") or ""
          ):
            comment_html = self.render_inline_children(ch).strip()
            if ch.tail:
              code_parts.append(html.escape(ch.tail))
            continue
          code_parts.append(self.render_inline_node(ch))
          if ch.tail:
            code_parts.append(html.escape(ch.tail))

        code_str = "".join(code_parts).replace("\xa0", "&nbsp;").strip()
        if not code_str and not comment_html:
          continue
        lno_span = (
            f'<span class="alg-lineno">{html.escape(lno)}</span>'
            if any_numbered
            else ""
        )
        cmt_span = (
            f'<span class="alg-comment">{comment_html}</span>'
            if comment_html
            else ""
        )
        lines_html.append(
            f'<div class="alg-line">{lno_span}'
            f'<span class="alg-code">{code_str}</span>{cmt_span}</div>'
        )

    id_attr = f' id="{html.escape(alg_lbl)}"' if alg_lbl else ""
    return (
        f'<div class="algorithm-card"{id_attr}>{header_html}'
        f'<div class="algorithm-body">{"".join(lines_html)}</div></div>'
    )

  def render_table(self, tab_el: ET.Element) -> str:
    """Renders a LaTeX `table` + `tabular` as a responsive booktabs table."""
    tab_lbl = label_key(tab_el.get("labels"))
    tab_num = self._elem_refnum(tab_el, default="1")
    cap_el = tab_el.find(f"{{{LTX_NS}}}caption")
    cap_html = self.render_caption_inner(cap_el) if cap_el is not None else ""

    tabular = tab_el.find(f".//{{{LTX_NS}}}tabular")
    if tabular is None:
      return ""
    all_trs = tabular.findall(f".//{{{LTX_NS}}}tr")

    body_start_idx = 1 if len(all_trs) > 1 else 0
    for idx, tr in enumerate(all_trs):
      tds = list(tr)
      if idx > 0 and tds and all("t" in (td.get("border") or "") for td in tds):
        body_start_idx = idx
        break

    thead_rows: list[str] = []
    tbody_rows: list[str] = []

    for r_idx, tr in enumerate(all_trs):
      in_head = r_idx < body_start_idx
      cell_tag = "th" if in_head else "td"
      tds = list(tr)
      all_top_border = bool(tds) and all(
          "t" in (td.get("border") or "") for td in tds
      )
      tr_cls = (
          ' class="row-midrule-top"'
          if (not in_head and r_idx > body_start_idx and all_top_border)
          else ""
      )

      next_tr = (
          all_trs[r_idx + 1]
          if (in_head and r_idx + 1 < body_start_idx)
          else None
      )
      next_col_borders: list[bool] = []
      if next_tr is not None:
        for ntd in next_tr:
          span = int(ntd.get("colspan") or 1)
          has_b = "t" in (ntd.get("border") or "")
          next_col_borders.extend([has_b] * span)

      col_pos = 0
      cell_htmls: list[str] = []
      for c_idx, td in enumerate(tds):
        span = int(td.get("colspan") or 1)
        align = td.get("align") or "left"
        cls_list = [f"align-{align}"]
        raw_cls = td.get("class") or ""
        if "ltx_nopad_l" in raw_cls:
          cls_list.append("nopad-l")
        if c_idx + 1 < len(tds) and "ltx_nopad_l" in (
            tds[c_idx + 1].get("class") or ""
        ):
          cls_list.append("nopad-r")

        if (
            in_head
            and span > 1
            and next_col_borders[col_pos : col_pos + span]
            and all(next_col_borders[col_pos : col_pos + span])
        ):
          cls_list.append("cmidrule-lr")

        rlap_child = next(
            (
                ch
                for ch in td
                if local_tag(ch) == "text" and ch.get("width") == "0.0pt"
            ),
            None,
        )
        if rlap_child is not None:
          cls_list.append("variant-eps-hdr")
          left_parts = []
          if td.text:
            left_parts.append(html.escape(td.text))
          for ch in td:
            if ch is rlap_child:
              break
            left_parts.append(self.render_inline_node(ch))
            if ch.tail:
              left_parts.append(html.escape(ch.tail))
          left_html = "".join(left_parts).strip()
          right_html = (
              self.render_inline_children(rlap_child)
              .replace("&nbsp;", "")
              .strip()
          )
          inner_html = (
              f"<span>{left_html}</span>"
              f'<span class="eps-hdr-label">{right_html}</span>'
          )
        else:
          inner_html = self.render_inline_children(td).strip()

        span_attr = f' colspan="{span}"' if span > 1 else ""
        cell_htmls.append(
            f'<{cell_tag}{span_attr} class="{" ".join(cls_list)}">'
            f"{inner_html}</{cell_tag}>"
        )
        col_pos += span

      row_html = f"<tr{tr_cls}>{''.join(cell_htmls)}</tr>"
      if in_head:
        thead_rows.append(row_html)
      else:
        tbody_rows.append(row_html)

    id_attr = f' id="{html.escape(tab_lbl)}"' if tab_lbl else ""
    cap_block = ""
    if cap_html:
      cap_block = (
          '<div class="table-caption"><strong class="fig-label">Table'
          f" {html.escape(tab_num)}:</strong> {cap_html}</div>"
      )
    return (
        f'<div class="table-card"{id_attr}>'
        '<div class="table-scroll"><table class="booktabs-table">'
        f'<thead>{"".join(thead_rows)}</thead>'
        f'<tbody>{"".join(tbody_rows)}</tbody>'
        f"</table></div>{cap_block}</div>"
    )

  def _reorder_leading_floats(
      self, children: list[ET.Element]
  ) -> list[ET.Element]:
    r"""Defers [t]/[b] floats placed right under \section{...} to first \ref."""
    leading_floats: list[tuple[ET.Element, set[str]]] = []
    idx = 0
    while idx < len(children):
      ch = children[idx]
      ct = local_tag(ch)
      placement = (ch.get("placement") or "").lower()
      if ct in ("figure", "table", "float") and not placement.startswith("h"):
        lbls = {
            label_key(sub.get("labels"))
            for sub in ch.iter()
            if label_key(sub.get("labels"))
        }
        leading_floats.append((ch, lbls))
        idx += 1
      else:
        break
    if not leading_floats:
      return children

    rest = list(children[idx:])
    for fl_el, fl_lbls in reversed(leading_floats):
      insert_at = None
      if fl_lbls:
        for r_i, blk in enumerate(rest):
          refs = {
              label_key(r.get("labelref"))
              for r in blk.findall(f".//{{{LTX_NS}}}ref")
          }
          if refs & fl_lbls:
            insert_at = r_i
            break
      if insert_at is None:
        insert_at = min(1, len(rest))
      rest.insert(insert_at, fl_el)
    return rest

  def render_block(
      self, el: ET.Element, toc_items: list[tuple[str, str]]
  ) -> str:
    """Renders a block-level LaTeXML AST element and records TOC headings."""
    t = local_tag(el)
    if t in (
        "section",
        "appendix",
        "subsection",
        "subsubsection",
        "paragraph",
        "subparagraph",
    ):
      lbl = label_key(el.get("labels")) or (el.get(XML_ID_ATTR) or "").lower()
      sec_num = self._elem_refnum(el)
      title_el = el.find(f"{{{LTX_NS}}}title")
      title_html = (
          self.render_caption_inner(title_el) if title_el is not None else ""
      )
      heading = ""
      if t in ("section", "appendix"):
        toc_label = f"{sec_num}. {title_html}" if sec_num else title_html
        toc_items.append((lbl, toc_label))
        num_span = (
            f'<span class="sec-num">{html.escape(sec_num)}.</span> '
            if sec_num
            else ""
        )
        heading = (
            f'<h2 id="{html.escape(lbl)}" class="section-heading">{num_span}'
            f'{title_html}<a class="heading-anchor" href="#{html.escape(lbl)}"'
            ' title="Permalink">#</a></h2>'
        )
      elif t in ("subsection", "subsubsection"):
        num_span = (
            f'<span class="sec-num">{html.escape(sec_num)}</span> '
            if sec_num
            else ""
        )
        heading = (
            f'<h3 id="{html.escape(lbl)}" class="subsec-heading">{num_span}'
            f'{title_html}<a class="heading-anchor" href="#{html.escape(lbl)}"'
            ' title="Permalink">#</a></h3>'
        )
      elif title_html:
        id_attr = f' id="{html.escape(lbl)}"' if lbl else ""
        heading = f'<h4{id_attr} class="subsec-heading">{title_html}</h4>'
      body_children = [
          ch
          for ch in el
          if local_tag(ch) not in ("title", "tags", "toccaption")
      ]
      body_children = self._reorder_leading_floats(body_children)
      children_html = [self.render_block(ch, toc_items) for ch in body_children]
      parts = ([heading] if heading else []) + [c for c in children_html if c]
      return "\n".join(parts)

    if t == "para":
      parts = [self.render_block(ch, toc_items) for ch in el]
      return "\n".join(p for p in parts if p)

    if t == "p":
      widget_note = el.find(f"{{{LTX_NS}}}note[@role='htmlwidget']")
      if widget_note is not None:
        return (
            '<figure class="paper-figure">'
            f"{self.render_widget_note(widget_note)}</figure>"
        )
      inner = self.render_inline_children(el).strip()
      return f"<p>{inner}</p>" if inner else ""

    if t == "note" and el.get("role") == "htmlwidget":
      return (
          f'<figure class="paper-figure">{self.render_widget_note(el)}</figure>'
      )

    if t in ("equation", "equationgroup"):
      if t == "equationgroup":
        eg_parts = []
        for ch in el:
          ct = local_tag(ch)
          if ct == "equation":
            eg_parts.append(self.render_equation(ch))
          elif ct not in ("tags", "toccaption"):
            rendered_ch = self.render_block(ch, toc_items)
            if rendered_ch:
              eg_parts.append(rendered_ch)
        return "\n".join(eg_parts)
      return self.render_equation(el)

    if t == "listing":
      b64 = el.get("data") or ""
      raw_code = (
          base64.b64decode(b64).decode("utf-8")
          if b64
          else "\n".join("".join(ln.itertext()) for ln in el)
      )
      idx = self.listing_counter
      self.listing_counter += 1
      return render_lstlisting(raw_code, idx)

    if t == "float":
      return self.render_algorithm_float(el)

    if t == "figure":
      return self.render_figure(el)

    if t == "table":
      return self.render_table(el)

    if t in ("itemize", "enumerate"):
      list_tag = "ul" if t == "itemize" else "ol"
      items = []
      for item in el.findall(f"{{{LTX_NS}}}item"):
        item_html = " ".join(
            self.render_inline_children(p).strip()
            for p in item.findall(f".//{{{LTX_NS}}}p")
        )
        items.append(f"<li>{item_html}</li>")
      return f'<{list_tag} class="paper-list">{"".join(items)}</{list_tag}>'

    if t in ("theorem", "proof"):
      lbl = label_key(el.get("labels"))
      id_attr = f' id="{html.escape(lbl)}"' if lbl else ""
      title_el = el.find(f"{{{LTX_NS}}}title")
      title_html = ""
      if title_el is not None:
        raw_t = self.render_inline_children(title_el).strip().rstrip(".")
        if raw_t:
          title_html = f"<strong>{raw_t}.</strong> "
      child_blocks = [
          self.render_block(ch, toc_items)
          for ch in el
          if local_tag(ch) not in ("title", "tags", "toccaption")
      ]
      child_blocks = [b for b in child_blocks if b]
      if title_html:
        if child_blocks and child_blocks[0].startswith("<p>"):
          child_blocks[0] = "<p>" + title_html + child_blocks[0][3:]
        else:
          child_blocks.insert(0, f"<p>{title_html.strip()}</p>")
      cls = "theorem-block" if t == "theorem" else "proof-block"
      return f'<div class="{cls}"{id_attr}>{"".join(child_blocks)}</div>'

    return ""

  def extract_authors(self) -> list[AuthorInfo]:
    """Extracts structured authors from paper.json or LaTeXML."""
    author_urls: dict[str, str] = self.meta.get("author_urls", {})
    if "authors" in self.meta:
      out: list[AuthorInfo] = []
      for a in self.meta["authors"]:
        aff = a.get("affil") or a.get("affiliation") or []
        if isinstance(aff, str):
          aff = [aff] if aff else []
        notes = a.get("notes") or ([] if not a.get("note") else [a["note"]])
        if a.get("equal") and "Equal contribution" not in notes:
          notes = ["Equal contribution"] + list(notes)
        name = str(a["name"])
        out.append(
            AuthorInfo(
                name=name,
                url=str(a.get("url") or author_urls.get(name, "")),
                affils=[str(x) for x in aff],
                email=str(a.get("email", "")),
                notes=[str(x) for x in notes],
            )
        )
      return out

    def push_author_str(
        target_chunks: list[tuple[list[str], list[str]]], s: str
    ) -> None:
      parts = re.split(r"\n\s*&", s)
      target_chunks[-1][0][-1] += parts[0]
      for p in parts[1:]:
        target_chunks.append(([p], []))

    authors: list[AuthorInfo] = []
    for cr in self.root.findall(f"{{{LTX_NS}}}creator[@role='author']"):
      pn = cr.find(f"{{{LTX_NS}}}personname")
      if pn is None:
        continue
      ext_affils = [
          "".join(c.itertext()).strip()
          for c in cr.findall(f"{{{LTX_NS}}}contact[@role='affiliation']")
          if "".join(c.itertext()).strip()
      ]
      ext_emails = [
          "".join(c.itertext()).strip()
          for c in cr.findall(f"{{{LTX_NS}}}contact[@role='email']")
          if "".join(c.itertext()).strip()
      ]
      ext_notes = [
          "".join(n.itertext()).strip()
          for n in cr.findall(
              f"{{{LTX_NS}}}contact[@role='thanks']"
          ) + cr.findall(f"{{{LTX_NS}}}note[@role='thanks']")
          if "".join(n.itertext()).strip()
      ]

      # Split <personname> into author chunks (handles \And / \AND -> "\n&")
      # and lines within each chunk (<ltx:break/>).
      chunks: list[tuple[list[str], list[str]]] = [([""], [])]
      if pn.text:
        push_author_str(chunks, pn.text)
      for ch in pn:
        ct = local_tag(ch)
        if ct == "break":
          chunks[-1][0].append("")
        elif ct == "note" and ch.get("role") in ("thanks", "footnote"):
          nt = re.sub(r"\s+", " ", "".join(ch.itertext())).strip()
          if nt:
            chunks[-1][1].append(nt)
        else:
          push_author_str(chunks, "".join(ch.itertext()))
        if ch.tail:
          push_author_str(chunks, ch.tail)

      for raw_lines, inline_notes in chunks:
        lines = [
            re.sub(r"\s+", " ", ln).strip()
            for ln in raw_lines
            if re.sub(r"\s+", " ", ln).strip()
        ]
        if not lines:
          continue
        name = lines[0]
        affils: list[str] = []
        email = ""
        for ln in lines[1:]:
          if "@" in ln and not email:
            email = ln
          else:
            affils.append(ln)
        for ea in ext_affils:
          if ea not in affils:
            affils.append(ea)
        if not email and ext_emails:
          email = ext_emails[0]
        notes = inline_notes + [n for n in ext_notes if n not in inline_notes]
        authors.append(
            AuthorInfo(
                name=name,
                url=author_urls.get(name, ""),
                affils=affils,
                email=email,
                notes=notes,
            )
        )

    # Fallback if paper.json only provided author_urls and LaTeX had no \author
    if not authors and author_urls:
      fallback_aff = str(self.meta.get("affiliation", ""))
      for name, url in author_urls.items():
        authors.append(
            AuthorInfo(
                name=name,
                url=url,
                affils=[fallback_aff] if fallback_aff else [],
                email="",
                notes=[],
            )
        )
    return authors

  def render_header_authors(
      self, authors: list[AuthorInfo]
  ) -> tuple[str, list[str]]:
    """Renders authors, mixed affiliations, emails, notes, and venue."""
    emails_mode = str(self.meta.get("emails", "per_author")).lower()
    affil_style = str(self.meta.get("affiliation_style", "superscript")).lower()

    unique_affils: list[str] = []
    for a in authors:
      for af in a.affils:
        if af and af not in unique_affils:
          unique_affils.append(af)
    if not unique_affils and self.meta.get("affiliation"):
      unique_affils.append(str(self.meta["affiliation"]))
      for a in authors:
        a.affils = list(unique_affils)

    unique_notes: list[str] = []
    for a in authors:
      for nt in a.notes:
        if nt and nt not in unique_notes:
          unique_notes.append(nt)

    is_mixed_affils = len(unique_affils) > 1 or (
        len(unique_affils) == 1
        and any(a.affils for a in authors)
        and not all(a.affils == unique_affils for a in authors)
    )
    any_email = any(bool(a.email) for a in authors)
    use_blocks = (emails_mode == "per_author" and any_email) or (
        affil_style == "blocks" and is_mixed_affils
    )

    author_items_html: list[str] = []
    author_names_plain: list[str] = []
    for a in authors:
      name = a.name
      author_names_plain.append(name)
      esc_name = html.escape(name)
      url = a.url
      name_core = (
          f'<a href="{html.escape(url)}">{esc_name}</a>' if url else esc_name
      )

      sups: list[str] = []
      if is_mixed_affils and affil_style != "blocks":
        for af in a.affils:
          sups.append(str(unique_affils.index(af) + 1))
      for nt in a.notes:
        n_idx = unique_notes.index(nt)
        sym = FOOTNOTE_SYMBOLS[n_idx % len(FOOTNOTE_SYMBOLS)]
        sups.append(sym)
      sup_html = (
          f'<sup class="author-sup">{html.escape(",".join(sups))}</sup>'
          if sups
          else ""
      )

      if use_blocks:
        sub_lines = [f'<span class="author-name">{name_core}{sup_html}</span>']
        if affil_style == "blocks":
          for af in a.affils:
            sub_lines.append(
                f'<span class="author-affil">{html.escape(af)}</span>'
            )
        if emails_mode == "per_author" and a.email:
          sub_lines.append(
              f'<span class="author-email">{html.escape(a.email)}</span>'
          )
        author_items_html.append(
            f'<div class="author-entry">{"".join(sub_lines)}</div>'
        )
      else:
        author_items_html.append(f"{name_core}{sup_html}")

    if use_blocks:
      authors_block = (
          '<div class="paper-authors author-blocks">\n          '
          + "\n          ".join(author_items_html)
          + "\n        </div>"
      )
    else:
      authors_block = (
          '<div class="paper-authors">\n          '
          + ",\n          ".join(author_items_html)
          + "\n        </div>"
      )

    extra_rows: list[str] = []
    if unique_affils and not (use_blocks and affil_style == "blocks"):
      if is_mixed_affils:
        aff_spans = "".join(
            f'<span class="affil-item"><sup>{i + 1}</sup>'
            f"{html.escape(af)}</span>"
            for i, af in enumerate(unique_affils)
        )
        extra_rows.append(f'<div class="paper-affil">{aff_spans}</div>')
      else:
        extra_rows.append(
            f'<div class="paper-affil">{html.escape(unique_affils[0])}</div>'
        )

    if emails_mode == "grouped" and any_email:
      grouped_str = format_grouped_emails([a.email for a in authors if a.email])
      if grouped_str:
        extra_rows.append(
            f'<div class="paper-emails">{html.escape(grouped_str)}</div>'
        )

    if unique_notes:
      note_parts: list[str] = []
      for i, nt in enumerate(unique_notes):
        sym_esc = html.escape(FOOTNOTE_SYMBOLS[i % len(FOOTNOTE_SYMBOLS)])
        note_parts.append(f"<span><sup>{sym_esc}</sup>{html.escape(nt)}</span>")
      note_spans = " &nbsp; ".join(note_parts)
      extra_rows.append(f'<div class="paper-notes">{note_spans}</div>')

    # Venue / award slot (defaults to arXiv:<id> when not overridden)
    arxiv_id = str(self.meta.get("arxiv_id", "")).strip()
    if "venue" in self.meta:
      venue_str = str(self.meta["venue"] or "").strip()
    elif arxiv_id:
      venue_str = f"arXiv:{arxiv_id}"
    else:
      venue_str = ""
    if venue_str:
      extra_rows.append(
          f'<div class="paper-venue">{html.escape(venue_str)}</div>'
      )

    header_body = "\n        ".join([authors_block] + extra_rows)
    return header_body, author_names_plain

  def _find_shared_asset(self, filename: str) -> str | None:
    """Locates shared `paper.css`, `paper.js`, or `stylesheet.css` nearby."""
    candidates = []
    if self.out_html_dir:
      candidates.append(
          os.path.join(os.path.dirname(self.out_html_dir), filename)
      )
      candidates.append(os.path.join(self.out_html_dir, filename))
    candidates.extend([
        os.path.join(self.script_dir, filename),
        os.path.join(os.path.dirname(self.script_dir), filename),
        os.path.join(self.tex_dir, filename),
    ])
    return next((p for p in candidates if os.path.isfile(p)), None)

  def compile(self) -> str:
    """Compiles the parsed LaTeXML AST into a complete HTML document string."""
    title_el = self.root.find(f"{{{LTX_NS}}}title")
    title_html = (
        self.render_inline_children(title_el).strip()
        if title_el is not None
        else html.escape(str(self.meta.get("title", "")))
    )
    title_plain = strip_tags_plain(title_html)
    # Keep hyphenated compounds (e.g. Cross-Entropy) intact outside HTML tags
    title_chunks: list[str] = []
    for part in re.split(r"(<[^>]+>)", title_html):
      if part.startswith("<"):
        title_chunks.append(part)
      else:
        title_chunks.append(
            re.sub(r"(?<=[A-Za-z])-(?=[A-Za-z])", "\u2011", part)
        )
    title_html = "".join(title_chunks)

    authors = self.extract_authors()
    authors_meta_html, author_names = self.render_header_authors(authors)

    abs_el = self.root.find(f"{{{LTX_NS}}}abstract")
    abs_paras: list[str] = []
    if abs_el is not None:
      abs_paras = [
          f"<p>{self.render_inline_children(p).strip()}</p>"
          for p in abs_el.findall(f".//{{{LTX_NS}}}p")
      ]
    abstract_html = "\n        ".join(abs_paras)

    toc_items: list[tuple[str, str]] = []
    body_blocks: list[str] = []
    for ch in self.root:
      if local_tag(ch) in ("title", "creator", "abstract", "bibliography"):
        continue
      rendered = self.render_block(ch, toc_items)
      if rendered:
        body_blocks.append(rendered)

    if self.bib_order:
      toc_items.append(("references", "References"))
      bib_lis = []
      for k in self.bib_order:
        sa = html.escape(self.bib_dict[k]["short_author"])
        yr = html.escape(self.bib_dict[k]["year"])
        tag_str = f"[{sa}, {yr}]" if yr else f"[{sa}]"
        bib_lis.append(
            f'<li id="bib-{html.escape(k)}" class="bib-item">'
            f'<span class="bib-tag">{tag_str}</span>'
            f' {self.bib_dict[k]["html"]}</li>'
        )
      body_blocks.append(
          '<h2 id="references" class="section-heading">References<a'
          ' class="heading-anchor" href="#references"'
          ' title="Permalink">#</a></h2><ol'
          f' class="bib-list">{"".join(bib_lis)}</ol>'
      )

    toc_html = "".join(
        f'<li><a href="#{html.escape(lbl)}">{strip_tags_plain(t)}</a></li>'
        for lbl, t in toc_items
        if lbl
    )

    arxiv_id = str(self.meta.get("arxiv_id", "")).strip()
    bib_key = self.meta.get(
        "bibtex_key",
        (author_names[0].split()[-1].lower() if author_names else "paper")
        + str(self.meta.get("year", 2026)),
    )
    year = self.meta.get("year", 2026)
    bib_venue = str(
        self.meta.get("bibtex_journal")
        or (f"arXiv:{arxiv_id}" if arxiv_id else self.meta.get("venue", ""))
    )
    bib_authors = " and ".join(
        f"{n.split()[-1]}, {' '.join(n.split()[:-1])}" if " " in n else n
        for n in author_names
    )
    paper_bibtex = (
        f"@article{{{bib_key},\n"
        f"  title={{{title_plain}}},\n"
        f"  author={{{bib_authors}}},\n"
        f"  journal={{{bib_venue}}},\n"
        f"  year={{{year}}}\n"
        "}"
    )

    back_cfg = self.meta.get(
        "back_link", {"label": "← jonbarron.info", "href": "../"}
    )
    links_cfg = self.meta.get("links")
    if links_cfg is None:
      links_cfg = (
          [{"label": "arXiv", "href": f"https://arxiv.org/abs/{arxiv_id}"}]
          if arxiv_id
          else []
      )
    nav_links = [
        f'<a href="{html.escape(lk["href"])}">{html.escape(lk["label"])}</a>'
        for lk in links_cfg
    ]
    nav_links.append(
        '<a href="#bibtex" id="copy-bibtex-btn"'
        f' data-bibtex="{html.escape(paper_bibtex)}"'
        ' onclick="copyBibtex(this); return false;">copy bibtex</a>'
    )
    nav_links_html = " /\n          ".join(nav_links)

    slug = self.meta.get("slug", "")
    site_base = str(self.meta.get("site_url", "https://jonbarron.info")).rstrip(
        "/"
    )
    desc = self.meta.get("social_description", "")
    soc_img = self.meta.get("social_image", "")
    soc_w = self.meta.get("social_image_width", 512)
    soc_h = self.meta.get("social_image_height", 512)
    tw_card = self.meta.get("twitter_card", "summary")
    page_url = f"{site_base}/{slug}/" if slug else ""
    soc_img_url = (
        f"{page_url}{soc_img.lstrip('/')}"
        if (page_url and soc_img and not soc_img.startswith("http"))
        else soc_img
    )

    meta_tags = [
        (
            '  <meta name="author"'
            f' content="{html.escape(", ".join(author_names))}">'
        ),
    ]
    if desc:
      esc_desc = html.escape(desc)
      meta_tags.extend([
          f'  <meta name="description" content="{esc_desc}">',
          f'  <meta property="og:title" content="{html.escape(title_plain)}">',
          f'  <meta property="og:description" content="{esc_desc}">',
          '  <meta property="og:type" content="article">',
      ])
      if page_url:
        meta_tags.append(
            f'  <meta property="og:url" content="{html.escape(page_url)}">'
        )
      if soc_img_url:
        meta_tags.extend([
            (
                '  <meta property="og:image"'
                f' content="{html.escape(soc_img_url)}">'
            ),
            f'  <meta property="og:image:width" content="{soc_w}">',
            f'  <meta property="og:image:height" content="{soc_h}">',
        ])
      meta_tags.extend([
          f'  <meta name="twitter:card" content="{html.escape(tw_card)}">',
          f'  <meta name="twitter:title" content="{html.escape(title_plain)}">',
          f'  <meta name="twitter:description" content="{esc_desc}">',
      ])
      tw_handle = self.meta.get("twitter_handle", "@jon_barron")
      if tw_handle:
        meta_tags.extend([
            f'  <meta name="twitter:site" content="{html.escape(tw_handle)}">',
            (
                '  <meta name="twitter:creator"'
                f' content="{html.escape(tw_handle)}">'
            ),
        ])
      if soc_img_url:
        meta_tags.append(
            '  <meta name="twitter:image"'
            f' content="{html.escape(soc_img_url)}">'
        )

    fav_html = favicon_link(self.meta.get("favicon_emoji", ""))

    # Site mode (shared ../stylesheet.css + ../tex_to_html/paper.{css,js}) vs
    # Standalone mode (self-contained single HTML file).
    parent_dir = os.path.dirname(self.out_html_dir) if self.out_html_dir else ""
    shared_prefix = ""
    if parent_dir and os.path.isfile(
        os.path.join(parent_dir, "tex_to_html", "paper.css")
    ):
      shared_prefix = "../tex_to_html"
    elif parent_dir and os.path.isfile(os.path.join(parent_dir, "paper.css")):
      shared_prefix = ".."
    is_site_mode = bool(self.external_img_dir and shared_prefix)
    if is_site_mode:
      style_links = []
      if os.path.isfile(os.path.join(parent_dir, "stylesheet.css")):
        style_links.append(
            '  <link rel="stylesheet" type="text/css" href="../stylesheet.css">'
        )
      style_links.append(
          '  <link rel="stylesheet" type="text/css"'
          f' href="{shared_prefix}/paper.css">'
      )
      style_assets = "\n".join(style_links)
      script_assets = (
          f'  <script defer src="{shared_prefix}/paper.js"></script>'
      )
    else:
      inlined_css = ""
      for css_name in ("stylesheet.css", "paper.css"):
        p = self._find_shared_asset(css_name)
        if p:
          inlined_css += open(p, encoding="utf-8").read() + "\n"
      inlined_js = ""
      js_p = self._find_shared_asset("paper.js")
      if js_p:
        inlined_js = open(js_p, encoding="utf-8").read()
      style_assets = f"  <style>\n{inlined_css}  </style>"
      script_assets = f"  <script>\n{inlined_js}\n  </script>"

    katex_css_url = (
        f"https://cdn.jsdelivr.net/npm/katex@{self.katex_version}"
        "/dist/katex.min.css"
    )
    katex_client_fallback = ""
    if self.katex_cache is None:
      katex_client_fallback = (
          f'\n  <script defer src="{KATEX_CDN_JS}"'
          ' crossorigin="anonymous"></script>\n  <script defer'
          f' src="{KATEX_CDN_AUTORENDER}" crossorigin="anonymous"'
          ' onload="renderMathInElement(document.body, {macros:'
          " {'\\\\sfrac': '{{}^{#1}\\\\!/\\\\!{}_{#2}}',"
          " '\\\\nicefrac':"
          " '{{}^{#1}\\\\!/\\\\!{}_{#2}}'}});\"></script>"
      )

    footer_html = ""
    if self.meta.get("template_credit", True):
      template_url = html.escape(
          str(self.meta.get("template_url", TEMPLATE_REPO_URL))
      )
      footer_html = (
          '\n      <footer class="paper-footer">Built from LaTeX with'
          f' <a href="{template_url}">tex_to_html</a>.</footer>'
      )

    has_lato_css = (
        is_site_mode
        and os.path.isfile(os.path.join(parent_dir, "stylesheet.css"))
    ) or (not is_site_mode and bool(self._find_shared_asset("stylesheet.css")))
    lato_query = (
        "" if has_lato_css else "family=Lato:ital,wght@0,400;0,700;1,400;1,700&"
    )
    mono_font_url = (
        "https://fonts.googleapis.com/css2?"
        f"{lato_query}family=JetBrains+Mono:wght@400;500&display=swap"
    )
    back_href = html.escape(back_cfg["href"])
    back_lbl = html.escape(back_cfg["label"])

    return (
        "<!DOCTYPE html>\n"
        f"<!-- Generated from LaTeX by tex_to_html: {TEMPLATE_REPO_URL} -->\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport"'
        ' content="width=device-width, initial-scale=1">\n'
        f"  <title>{html.escape(title_plain)}</title>\n"
        f"{chr(10).join(meta_tags)}\n"
        f"  {fav_html}\n"
        f"{style_assets}\n"
        '  <link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '  <link rel="preconnect" href="https://fonts.gstatic.com"'
        " crossorigin>\n"
        f'  <link href="{mono_font_url}" rel="stylesheet">\n'
        f'  <link rel="stylesheet" href="{katex_css_url}"'
        f' crossorigin="anonymous">{katex_client_fallback}\n'
        "</head>\n"
        "<body>\n"
        '  <div class="page-layout">\n'
        '    <aside class="toc-sidebar">\n'
        '      <div class="toc-header">Contents</div>\n'
        '      <ul class="toc-list" id="toc-list">\n'
        f"        {toc_html}\n"
        "      </ul>\n"
        "    </aside>\n\n"
        '    <main class="paper-main">\n'
        '      <nav class="paper-nav">\n'
        f'        <a href="{back_href}">{back_lbl}</a>\n'
        '        <div class="paper-nav-links">\n'
        f"          {nav_links_html}\n"
        "        </div>\n"
        "      </nav>\n\n"
        '      <header class="paper-header">\n'
        f'        <h1 class="paper-title">{title_html}</h1>\n'
        f"        {authors_meta_html}\n"
        "      </header>\n\n"
        '      <section class="abstract-box" id="abstract">\n'
        '        <div class="abstract-title">Abstract</div>\n'
        f"        {abstract_html}\n"
        "      </section>\n\n"
        f"      {chr(10).join(body_blocks)}{footer_html}\n"
        "    </main>\n\n"
        '    <div class="layout-spacer" aria-hidden="true"></div>\n'
        "  </div>\n\n"
        '  <div id="hover-popover"></div>\n'
        '  <div id="lightbox-overlay"'
        " onclick=\"this.style.display='none'\">\n"
        '    <img id="lightbox-img" src="" alt="Expanded figure">\n'
        "  </div>\n\n"
        f"{script_assets}\n"
        "</body>\n"
        "</html>\n"
    )


_VOID_HTML_TAGS = frozenset({
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
})
_AUDIT_SKIP_CLASSES = frozenset(
    {"code-listing", "katex", "katex-mathml", "math-inline", "math-display"}
)


class _ProseExtractor(html.parser.HTMLParser):
  """Extracts prose text from HTML while skipping math, code, and scripts."""

  def __init__(self) -> None:
    super().__init__(convert_charrefs=True)
    self._skip_stack: list[bool] = []
    self.chunks: list[str] = []

  def handle_starttag(
      self, tag: str, attrs: list[tuple[str, str | None]]
  ) -> None:
    t = tag.lower()
    if t in _VOID_HTML_TAGS:
      return
    cls_str = dict(attrs).get("class") or ""
    classes = set(cls_str.split())
    should_skip = bool(
        (self._skip_stack and self._skip_stack[-1])
        or t in ("script", "style", "code")
        or (classes & _AUDIT_SKIP_CLASSES)
    )
    self._skip_stack.append(should_skip)

  def handle_endtag(self, tag: str) -> None:
    if tag.lower() not in _VOID_HTML_TAGS and self._skip_stack:
      self._skip_stack.pop()

  def handle_data(self, data: str) -> None:
    if not (self._skip_stack and self._skip_stack[-1]):
      self.chunks.append(data)


def audit_html(html_str: str) -> list[str]:
  """Audits compiled HTML to verify zero unresolved refs or leaked TeX."""
  issues: list[str] = []
  extractor = _ProseExtractor()
  extractor.feed(html_str)
  text_only = " ".join(extractor.chunks)

  if "??" in text_only:
    issues.append("  [html] Unresolved reference or citation '??' found")
  for m in re.finditer(r"\\[a-zA-Z]+", text_only):
    snippet = text_only[
        max(0, m.start() - 30) : min(len(text_only), m.end() + 30)
    ]
    issues.append(
        f"  [html] Unexpanded LaTeX command {m.group(0)} in prose: {snippet!r}"
    )
  if "$" in text_only:
    idx = text_only.index("$")
    snippet = text_only[max(0, idx - 30) : min(len(text_only), idx + 30)]
    issues.append(f"  [html] Raw '$' found in prose: {snippet!r}")
  return issues


def resolve_tex_entry(path: str) -> str:
  """Resolves `path` (file or directory) to the main `.tex` entry file."""
  if os.path.isfile(path):
    return os.path.abspath(path)
  main_cand = os.path.join(path, "main.tex")
  if os.path.isfile(main_cand):
    return os.path.abspath(main_cand)
  for fn in sorted(os.listdir(path)):
    if fn.endswith(".tex"):
      full = os.path.join(path, fn)
      if (
          r"\documentclass" in open(
              full, encoding="utf-8", errors="ignore"
          ).read()
      ):
        return os.path.abspath(full)
  raise FileNotFoundError(f"No main .tex file found in {path}")


def main() -> None:
  """CLI entry point for `tex_to_html.py`."""
  # Support legacy positional call: <tex_dir> <build_dir> <out_html> [img_dir]
  if (
      len(sys.argv) in (4, 5)
      and not any(a.startswith("-") for a in sys.argv[1:])
      and os.path.isdir(sys.argv[2])
  ):
    main_tex = resolve_tex_entry(sys.argv[1])
    build_dir = sys.argv[2]
    out_html = sys.argv[3]
    ext_img_dir = sys.argv[4] if len(sys.argv) == 5 else None
    temp_ctx = None
  else:
    parser = argparse.ArgumentParser(
        description="Compile a LaTeX paper (.tex) into clean HTML."
    )
    parser.add_argument(
        "tex",
        help="Path to main.tex (or directory containing main.tex).",
    )
    parser.add_argument(
        "--out",
        "-o",
        required=True,
        help="Output HTML file (e.g. out/index.html) or directory (e.g. out/).",
    )
    parser.add_argument(
        "--img-dir",
        default=None,
        help=(
            "Relative image folder (e.g. 'img'); omit or pass --standalone to"
            " inline base64."
        ),
    )
    parser.add_argument(
        "--build-dir",
        default=None,
        help="Optional build directory containing pre-built .bbl.",
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        help=(
            "Emit a single self-contained HTML file with inlined CSS/JS/images."
        ),
    )
    args = parser.parse_args()
    main_tex = resolve_tex_entry(args.tex)
    out_ext = os.path.splitext(args.out)[1].lower()
    if (
        args.out.endswith(os.sep)
        or not out_ext
        or (os.path.isdir(args.out) and out_ext not in (".html", ".htm"))
    ):
      os.makedirs(args.out, exist_ok=True)
      out_html = os.path.join(args.out, "index.html")
      ext_img_dir = None if args.standalone else (args.img_dir or "img")
    else:
      out_html = args.out
      ext_img_dir = None if args.standalone else args.img_dir
    if args.build_dir:
      build_dir = args.build_dir
      temp_ctx = None
    else:
      temp_ctx = tempfile.TemporaryDirectory()
      build_dir = temp_ctx.name

  try:
    out_html_abs = os.path.abspath(out_html)
    out_html_dir = os.path.dirname(out_html_abs)
    os.makedirs(out_html_dir, exist_ok=True)
    compiler = LaTeXMLPaperCompiler(
        main_tex,
        build_dir,
        external_img_dir=ext_img_dir,
        out_html_dir=out_html_dir,
    )
    html_doc = compiler.compile()
    issues = audit_html(html_doc)
    if issues:
      print("HTML Compilation Audit Warnings:", file=sys.stderr)
      print("\n".join(issues), file=sys.stderr)
      sys.exit(1)
    with open(out_html_abs, "w", encoding="utf-8") as f:
      f.write(html_doc)
    katex_msg = (
        f"{len(compiler.katex_cache)} pre-rendered KaTeX expressions"
        if compiler.katex_cache is not None
        else "client-side KaTeX auto-render"
    )
    print(
        f"HTML Compilation Audit: PASS ({len(compiler.embedded_images)}"
        f" figures, {katex_msg}, 0 unresolved refs ->"
        f" {os.path.getsize(out_html_abs) / 1024:.0f} KB)"
    )
  finally:
    if temp_ctx is not None:
      temp_ctx.cleanup()


if __name__ == "__main__":
  main()
