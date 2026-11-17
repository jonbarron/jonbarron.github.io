# Agent Guide for `jonbarron.github.io`

This repository powers [jonbarron.info](https://jonbarron.info/), including the
homepage (`index.html` + `stylesheet.css`) and HTML paper/project pages built
with [`tex_to_html/`](tex_to_html/AGENTS.md).

## Core Principles

1.  **Keep it simple and readable**: The footer invites readers to reuse the
    site's source code. Keep HTML, CSS, and minimal vanilla JS clean and
    human-readable — no build bundlers, CSS frameworks, or giant inlined base64
    blobs in `stylesheet.css`.
2.  **Single source of truth (`stylesheet.css`)**: `stylesheet.css` defines all
    `@font-face` rules (`Lato` + `Source Code Pro`, `font-display: block`),
    shared CSS custom properties (`:root` colors & font stacks), and antialiased
    font rendering. Paper pages (`tex_to_html/paper.css`) and interactive demos
    inherit from `../stylesheet.css` rather than loading duplicate Google Fonts
    stylesheets.
3.  **Compile papers from LaTeX**: Never hand-edit generated paper HTML; see
    [`tex_to_html/AGENTS.md`](tex_to_html/AGENTS.md) for compiling `.tex`
    sources via `tex_to_html/tex_to_html.py`.

## Color Policy

*   `#000000` (`--text`): All primary content and metadata (prose, headings,
    authors, emails, affiliations, venues, captions, tables, references, code
    body, and bold Python keywords).
*   `#555555` (`--text-muted`): **Chrome only** — `/` separators, footers,
    sidebar TOC links, margin equation numbers, hover `#` anchors, `Copy`
    buttons, and code/algorithm comments.
*   `#1772d0` (`--accent`) / `#f09228` (`--accent-hover`): **Clickable links and
    active navigation only** (never in code syntax highlighting or non-link UI).
*   `#ffffd0` (`--highlight-bg`): Highlighted homepage paper rows and `:target`
    jump highlights in papers.

## Typography Policy

*   **Homepage (`index.html`)**: `32px` title (`h1`), `22px` section headings
    (`h2`), **`14px` body** with Lato's default `normal` (`~1.20`) line-height
    (preserving the signature compact density beside `160×160` thumbnails), and
    `13px` footer.
*   **Paper pages (`tex_to_html/paper.css`)**:
    *   `32px` title (`h1`), `22px` sections (`h2`), `18px` abstract title &
        subsections (`h3`).
    *   **`15px` regular text** (`14px` on mobile `<= 640px`, `line-height:
        1.55`) for everything that is `\normalsize` in LaTeX: body prose,
        abstract, author names, emails, affiliations, venue, top nav links,
        sidebar TOC, and margin equation numbers `(1)`.
    *   **`13px` small text** *only* for things that are `\small` /
        `\footnotesize` in LaTeX (figure & table captions/subcaptions, tables,
        bibliography, `Source Code Pro` code listings & inline `code`, algorithm
        floats, footnotes) plus small UI chrome (footer, hover popovers, `Copy`
        buttons, and demo widget controls).
    *   **KaTeX math (`1.14em`)**: Scaled to optically match Computer Modern's
        smaller x-height (`0.431em`) to Lato (`0.507em`).
