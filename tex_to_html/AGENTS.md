# Agent Guide for `tex_to_html`

This directory contains a self-contained LaTeX-to-HTML academic paper compiler
used on [jonbarron.info](https://jonbarron.info/). Do **not** hand-write HTML or
one-off conversion scripts for individual papers; always compile from the
paper's `.tex` source using `tex_to_html.py`.

## Files in This Directory

*   `tex_to_html.py` — Main CLI compiler (`Python 3.10+`, zero required `pip`
    packages; `Pillow` optional for 256-color PNG compression).
*   `paper_latexml.ltxml` — Preloaded LaTeXML bindings (`subcaption`,
    `algorithm` + `algpseudocode`/`algorithmic`, `\htmlwidget`, conference style
    helpers).
*   `paper.css` & `paper.js` — Shared responsive paper stylesheet and client-side
    interactivity (sticky scroll-spy TOC, figure/equation/citation hover
    popovers, click-to-zoom lightbox, code/BibTeX copy buttons).
*   `README.md` — Human quick-start and `paper.json` reference.

## Standard Workflow for Compiling a Paper

1.  **Verify `latexml` is installed** (`which latexml`; install via
    `brew install latexml` on macOS or `sudo apt install latexml` on
    Ubuntu/Debian). Ensure `node` (or `gjs`) is on `PATH` if you want static
    build-time KaTeX math pre-rendering (`KATEX_JS=/path/to/katex.min.js`
    overrides automatic bundle caching when offline).
2.  **Add an optional `paper.json` next to `main.tex`** to supply metadata not
    present in LaTeX (homepage URLs, top-bar links, social cards, favicon):
    *   `"slug"`: URL folder name (e.g. `"softmaxfix"`).
    *   `"arxiv_id"`: e.g. `"2610.31642"` (populates default `"venue"` and BibTeX).
    *   `"author_urls"`: `{"Author Name": "https://..."}` map, or explicit
        `"authors"` list when overriding `\author{...}`.
    *   `"emails"`: `"per_author"` (default), `"grouped"`, or `"hidden"`.
    *   `"affiliation_style"`: `"superscript"` (default for mixed affiliations)
        or `"blocks"`.
    *   `"venue"`: Optional string (e.g. `"CVPR 2026 (Oral Presentation)"`, or
        `""` to hide).
    *   `"links"`: List of `{"label": "...", "href": "..."}` buttons in the top
        right nav bar (`copy bibtex` is appended automatically).
    *   `"back_link"`: `{"label": "← jonbarron.info", "href": "../"}`.
    *   `"favicon_emoji"`, `"social_image"`, `"social_description"`,
        `"quantize_png"` (`true` by default; set `false` only if photographic
        `.png` figures show palette banding).
3.  **Run the compiler**:
    ```bash
    # Site mode — outputs <slug>/index.html + <slug>/img/* and links ../tex_to_html/paper.{css,js}:
    python3 tex_to_html/tex_to_html.py path/to/main.tex --out <slug>/

    # Standalone mode — outputs a single self-contained HTML file with inlined CSS/JS/images:
    python3 tex_to_html/tex_to_html.py path/to/main.tex --out paper.html --standalone
    ```
4.  **Check the built-in audit**: `tex_to_html.py` automatically fails with a
    non-zero exit code if any unresolved cross-reference (`??`), unexpanded TeX
    command (`\foo`), or raw `$` leaks into visible prose.

## Handling LaTeX Edge Cases Without Altering PDF Output

*   **PDF-only TeX hacks**: Wrap low-level TeX primitives that LaTeXML should
    ignore in `\ifx\isLaTeXML\undefined ... \fi` inside `macros.tex` or
    `main.tex` (this preserves byte-identical `pdflatex` output).
*   **Section-leading floats**: `[t]` / `[b]` floats placed immediately after
    `\section{...}` for PDF page layout are automatically deferred in HTML to
    the paragraph that first `\ref`s them; use `[h]` if a float must stay
    immediately under the heading.
*   **Interactive HTML widgets**: Use `\htmlwidget[height=520px]{demo.html}` (or
    `[height=520px,replace]` inside a `figure` environment to replace static PDF
    subfigures with an interactive `<iframe>` in HTML while keeping the PDF
    unchanged).
*   **Adding a paper to the `jonbarron.info` homepage (`index.html`)**: Prepend
    an `<article class="paper">` (or `<article class="paper highlighted">`) in
    `<section class="papers">` with `width="160"` media, `<span class="author">`
    around any unlinked co-author names (never insert `<br>` in
    `.paper-authors`), and UTF-8 accents.

## Site-Wide Design & Typography Conventions

`../stylesheet.css` is the single source of truth for `@font-face` declarations
(`Lato` + `Source Code Pro`, `font-display: block`), color variables, and
font-smoothing (`-webkit-font-smoothing: antialiased`). Do not add duplicate
Google Fonts `<link>` tags to individual pages when `stylesheet.css` is loaded.

### Colors
*   `#000000` (`--text`): All primary content and paper metadata (prose,
    headings, authors, emails, affiliations, venues, captions, tables,
    references, code body, and bold Python keywords).
*   `#555555` (`--text-muted`): **Chrome only** — `/` nav/link separators,
    footers, sidebar TOC links, margin equation numbers, hover `#` anchors,
    `Copy` buttons, and code/algorithm comments. Never use muted gray for
    primary content or author/venue metadata.
*   `#1772d0` (`--accent`) / `#f09228` (`--accent-hover`): **Clickable links and
    active navigation only**. Never use link blue for non-clickable elements or
    code syntax highlighting.
*   `#ffffd0` (`--highlight-bg`): Highlighted homepage paper rows and `:target`
    jump highlights in papers.

### Typography & Font Sizes
*   **Homepage (`stylesheet.css`)**: Keep the classic dense `14px` body size
    with Lato's default `normal` (`~1.20`) line-height so paper entries stay
    compact next to `160×160` thumbnails (`32px` `h1`, `22px` `h2`, `13px`
    footer).
*   **Papers (`paper.css`)**:
    *   `32px` title (`h1`), `22px` sections (`h2`), `18px` abstract title &
        subsections (`h3`).
    *   `15px` (`14px` on mobile `<= 640px`, `line-height: 1.55`) for **all
        LaTeX `\normalsize` equivalents**: body prose, abstract, author names,
        emails, affiliations, venue, top nav links, sidebar TOC, and margin
        equation numbers `(1)`.
    *   `13px` **only** for things that would be `\small` / `\footnotesize` in
        LaTeX (figure & table captions/subcaptions, booktabs tables,
        bibliography/references, `Source Code Pro` code listings & inline
        `code`, algorithm floats, and `\thanks` footnotes), plus small web UI
        chrome (footer, hover preview popovers, `Copy` buttons/tooltips, and
        interactive demo controls).
    *   **KaTeX math (`1.14em`)**: Computer Modern (`KaTeX_Main`, x-height
        `0.431em`) is scaled to `1.14em` (`1.02em` for display math on mobile)
        to optically match Lato (`x-height 0.507em`).
