# `tex_to_html` — LaTeX Paper to HTML Compiler

A lightweight, single-script compiler that converts a standard LaTeX paper
(`main.tex` + `.bib`/`.bbl`) into a fast, responsive HTML paper matching
[jonbarron.info](https://jonbarron.info/) (for example,
[*A Fix for Softmax and Cross-Entropy*](https://jonbarron.info/softmaxfix/)).

Under the hood, it runs [`latexml`](https://math.nist.gov/~BMiller/LaTeXML/) to
expand all custom LaTeX macros, resolve section/equation/figure/table/algorithm
numbering and `\cite` keys into a semantic XML AST, and pre-renders all math to
static [KaTeX](https://katex.org/) HTML at build time (when `node` or `gjs` is
installed, with an automatic client-side KaTeX fallback otherwise).

## Prerequisites

*   **Python 3.10+** (zero `pip` packages required; installing `Pillow`
    optionally compresses PNG figures).
*   **LaTeXML** (`brew install latexml` on macOS, or `sudo apt install latexml`
    on Ubuntu/Debian).
*   **TeX Live / MacTeX** (`pdflatex` + `bibtex`, only needed if a pre-built
    `main.bbl` is not already next to `main.tex`).
*   Optional: **`node`** (or `gjs`) for build-time static KaTeX math
    pre-rendering (`0ms` client-side math JS).

## Quick Start

From a clone of this repository (or any folder containing `tex_to_html/`):

```bash
# Compile a paper directory into a site subfolder (creates mypaper/index.html + mypaper/img/):
python3 tex_to_html/tex_to_html.py path/to/paper/main.tex --out mypaper/

# Or emit a single self-contained HTML file (inlines CSS, JS, and base64 figures):
python3 tex_to_html/tex_to_html.py path/to/paper/main.tex --out paper.html --standalone
```

## Optional `paper.json` Metadata

Place an optional `paper.json` next to `main.tex` to configure navigation links,
author homepage URLs, mixed affiliations, email display, venue/award banner, and
social-preview cards:

```json
{
  "slug": "softmaxfix",
  "arxiv_id": "2610.31642",
  "bibtex_key": "barron2026softmaxfix",
  "year": 2026,
  "emails": "per_author",
  "affiliation_style": "superscript",
  "favicon_emoji": "🎯",
  "social_image": "img/social_preview.png",
  "social_description": "One-sentence summary for OpenGraph / Twitter cards.",
  "back_link": {"label": "← jonbarron.info", "href": "../"},
  "author_urls": {
    "Jonathan T. Barron": "https://jonbarron.info/",
    "Dan Gnanapragasam": "https://scholar.google.com/citations?user=zNMOfjQAAAAJ&hl=en",
    "Michael Tschannen": "https://mitscha.github.io/"
  },
  "links": [
    {"label": "arXiv", "href": "https://arxiv.org/abs/2610.31642"},
    {"label": "interactive demo", "href": "demo.html"},
    {"label": "tweet", "href": "https://x.com/jon_barron/status/2113707875290042665"}
  ]
}
```

### Supported `paper.json` Options

*   **Authors, Mixed Affiliations & Footnotes:** Extracted automatically from
    `\author{...}` (`\and`, `\And`, `\AND`, `authblk`, and `\thanks{...}`).
    *   Single shared affiliation renders once cleanly below the authors; mixed
        affiliations automatically add numbered superscripts (`1, 2`), or set
        `"affiliation_style": "blocks"` to stack affiliations under each author.
    *   You can also specify `"authors": [{"name": "...", "url": "...", "affil":
        ["Inst A", "Inst B"], "email": "...", "equal": true}]` explicitly in
        `paper.json`.
*   **Emails (`"emails"`):**
    *   `"per_author"` *(default)* — renders each author's email directly under
        their name.
    *   `"grouped"` — collapses shared domains onto one line (e.g.
        `{barron, nanabyte, tschannen}@google.com`).
    *   `"hidden"` — omits email addresses.
*   **Favicon (`"favicon"` / `"favicon_emoji"`):** Place `favicon.png` (and
    optionally `favicon.ico` + `apple-touch-icon.png`) in the paper's `img/`
    folder — or set `"favicon": "img/favicon.png"` in `paper.json` — and
    `tex_to_html` links all available sizes automatically (and inlines a base64
    PNG in `--standalone` mode). Falls back to `"favicon_emoji"` when no custom
    image is present.
*   **Venue / Award (`"venue"`):** Defaults to `arXiv:<arxiv_id>` when
    `"arxiv_id"` is set. Override with e.g.
    `"venue": "CVPR 2026 (Oral Presentation)"`, or `""` to hide.
*   **Supported LaTeX Constructs:** Custom `\newcommand` /
    `\DeclareMathOperator` macros (`macros.tex`), `subcaption` (`subfigure`
    widths & optical margins), `minipage` side-by-side figures, `booktabs`
    tables (`\toprule`, `\cmidrule`, `\midrule`, `\multicolumn`), `listings`
    (`lstlisting` with copy button), `algorithm` + `algpseudocode` /
    `algorithmic` / `algorithm2e` pseudocode floats, theorems/proofs,
    click-to-zoom lightbox, sticky scroll-spy table of contents, and hover
    previews on figure/table/equation/algorithm/citation links.

## Design Policy (Fonts, Colors & Typography)

`../stylesheet.css` is the single source of truth for site-wide `@font-face`
declarations (`Lato` + `Source Code Pro`), CSS color/font tokens, and base
typography rendering. `paper.css` inherits those tokens (with standalone
fallbacks):

*   **Colors:**
    *   `#000000` (`--text`) — all primary content and paper metadata (prose,
        headings, authors, affiliations, venues, emails, captions, tables,
        references, and code body/bold keywords).
    *   `#555555` (`--text-muted`) — **chrome only** (nav `/` separators,
        footers, sidebar TOC, equation numbers, hover `#` anchors, `Copy`
        buttons, and code/algorithm comments). Never use muted gray for primary
        content or paper metadata.
    *   `#1772d0` (`--accent`) — **clickable links and active navigation only**.
        Never use link blue for non-clickable elements or code syntax
        highlighting.
    *   `#f09228` (`--accent-hover`) — hover/focus state for links and
        interactive chrome.
    *   `#ffffd0` (`--highlight-bg`) — highlighted paper rows on the homepage
        and `:target` jump highlights in papers.
    *   `#ffffff` (`--bg`), `#f7f7f5` (`--bg-code`), `#e4e4e0` (`--border`) —
        page surface, code-block fill, and hairline borders.
*   **Fonts:** **Lato** (`400`/`700`, including author emails) for everything
    except inline `code` and `.code-listing`, which use **Source Code Pro**
    (`400`/`700`, monochrome bold keywords + muted `#555555` comments).
*   **Desktop Font Scale:**
    *   **Homepage (`stylesheet.css`):** `32px` (page title `h1`), `22px`
        (section `h2`), `14px` (body text, `normal` ~`1.2` leading), `13px`
        (footer).
    *   **Papers (`paper.css`):** `32px` (page title `h1`), `22px` (section
        `h2`), `18px` (paper abstract title & subsection `h3`), `15px` (all
        `\normalsize` text: prose, authors, emails, affiliations, venue, top
        nav, TOC sidebar, and margin equation numbers; `14px` on mobile), `13px`
        **only** for things that are `\small`/`\footnotesize` in LaTeX (figure &
        table captions/subcaptions, tables, bibliography, code, algorithms,
        footnotes) plus small web chrome (footer, hover popovers, `Copy`
        buttons). KaTeX math uses `1.14em` to match Lato's x-height optically.
