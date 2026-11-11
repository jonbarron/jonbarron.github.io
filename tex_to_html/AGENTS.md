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
