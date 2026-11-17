document.addEventListener('DOMContentLoaded', function() {
  initHoverPreviews();
  initLightbox();
  initScrollSpy();
});

/**
 * Copies text to the clipboard with an execCommand fallback for non-HTTPS /
 * local file:// standalone HTML pages.
 * @param {string} text
 * @return {!Promise<void>}
 */
function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text).catch(() => copyTextFallback(text));
  }
  return copyTextFallback(text);
}

/**
 * Fallback clipboard copy via a temporary off-screen textarea.
 * @param {string} text
 * @return {!Promise<void>}
 */
function copyTextFallback(text) {
  return new Promise((resolve, reject) => {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    ta.style.pointerEvents = 'none';
    document.body.appendChild(ta);
    ta.select();
    try {
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      if (ok) resolve();
      else reject(new Error('execCommand copy failed'));
    } catch (err) {
      document.body.removeChild(ta);
      reject(err);
    }
  });
}

/**
 * Copies a code listing's source text to the clipboard.
 * @param {!Element} btn
 */
function copyCodeBlock(btn) {
  const code = btn.getAttribute('data-code') || '';
  copyText(code).then(() => {
    const orig = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => {
      btn.textContent = orig;
    }, 1400);
  }).catch(() => {});
}

let bibtexTimer = null;

/**
 * Copies the paper BibTeX citation to the clipboard.
 * @param {!Element} el
 */
function copyBibtex(el) {
  const bib = el.getAttribute('data-bibtex') || '';
  copyText(bib).then(() => {
    el.classList.add('is-copied');
    clearTimeout(bibtexTimer);
    bibtexTimer = setTimeout(() => {
      el.classList.remove('is-copied');
    }, 1200);
  }).catch(() => {});
}

/** Initializes click-to-zoom lightbox behavior on paper figures. */
function initLightbox() {
  const overlay = document.getElementById('lightbox-overlay');
  const lbImg = document.getElementById('lightbox-img');
  if (!overlay || !lbImg) return;
  function closeLightbox() {
    overlay.style.display = 'none';
    document.body.style.overflow = '';
  }
  document.querySelectorAll('img.zoomable').forEach(img => {
    img.addEventListener('click', () => {
      lbImg.src = img.src;
      lbImg.alt = img.alt || 'Expanded figure';
      overlay.style.display = 'flex';
      document.body.style.overflow = 'hidden';
    });
  });
  overlay.addEventListener('click', closeLightbox);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && overlay.style.display === 'flex') closeLightbox();
  });
}

/** Initializes hover popovers for bibliography citations and cross-refs. */
function initHoverPreviews() {
  if (window.matchMedia &&
      !window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    return;
  }
  const pop = document.getElementById('hover-popover');
  if (!pop) return;
  function showPop(e, contentHtml) {
    if (!contentHtml) return;
    pop.innerHTML = contentHtml;
    pop.style.display = 'block';
    const rect = e.currentTarget.getBoundingClientRect();
    const left = Math.max(
        12, Math.min(rect.left, window.innerWidth - pop.offsetWidth - 12));
    const top = (rect.bottom + pop.offsetHeight + 16 <= window.innerHeight) ?
        rect.bottom + 8 :
        Math.max(12, rect.top - pop.offsetHeight - 8);
    pop.style.left = left + 'px';
    pop.style.top = top + 'px';
  }
  function hidePop() {
    pop.style.display = 'none';
  }
  document.querySelectorAll('a.cite-link').forEach(a => {
    a.addEventListener('mouseenter', e => {
      const bibEl =
          document.getElementById('bib-' + a.getAttribute('data-bib'));
      if (bibEl) showPop(e, bibEl.innerHTML);
    });
    a.addEventListener('mouseleave', hidePop);
  });
  document.querySelectorAll('a.xref').forEach(a => {
    a.addEventListener('mouseenter', e => {
      const refId = a.getAttribute('data-ref');
      if (!refId || refId.startsWith('sec:')) return;
      const target = document.getElementById(refId);
      if (!target || target.matches('h1, h2, h3, h4')) return;
      const figParent = target.closest('figure.paper-figure');
      showPop(e, figParent ? figParent.outerHTML : target.outerHTML);
    });
    a.addEventListener('mouseleave', hidePop);
  });
}

/** Highlights the active section link in the sticky table of contents. */
function initScrollSpy() {
  const links = Array.from(document.querySelectorAll('#toc-list a'));
  if (!links.length) return;
  const sections =
      links.map(a => document.getElementById(a.getAttribute('href').slice(1)))
          .filter(Boolean);
  function updateActive() {
    let cur = sections[0];
    for (const s of sections) {
      if (s.getBoundingClientRect().top <= 120) cur = s;
    }
    links.forEach(a => {
      a.classList.toggle(
          'active', !!(cur && a.getAttribute('href') === '#' + cur.id));
    });
  }
  window.addEventListener('scroll', updateActive, {passive: true});
  updateActive();
}
