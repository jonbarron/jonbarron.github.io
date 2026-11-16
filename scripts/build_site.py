#!/usr/bin/env python3
"""Build the lab's static pages. The original personal site is never written."""

from html import escape
from hashlib import sha256
from datetime import date
import json
import re
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
LAB = json.loads((ROOT / "site-data/lab.json").read_text(encoding="utf-8"))
PUBLICATIONS = json.loads((ROOT / "site-data/publications.json").read_text(encoding="utf-8"))
STUDENTS = json.loads((ROOT / "site-data/students.json").read_text(encoding="utf-8"))
NAVIGATION = [("Home", ""), ("Events", "events"), ("Team", "team"), ("Publications", "publications"), ("Paper Reading", "paper-reading"), ("Contact us", "opportunities")]
BUILD_YEAR = date.today().year
VERSION_SOURCES = (
    "scripts/build_site.py",
    "site-data/lab.json",
    "site-data/publications.json",
    "site-data/students.json",
    "assets/lab/lab.css",
    "assets/lab/site.js",
    "assets/lab/vendor/yale-lumen.css",
    "assets/lab/vendor/yale-team.css",
    "assets/lab/vendor/yale-publications.css",
) + tuple(sorted({
    student.get("photo") or "assets/lab/student-placeholder.png" for student in STUDENTS
}))
SITE_VERSION = sha256(
    str(BUILD_YEAR).encode() + b"\0" + b"\0".join((ROOT / path).read_bytes() for path in VERSION_SOURCES)
).hexdigest()[:12]


def e(value):
    return escape(str(value), quote=True)


def asset_url(path, prefix):
    version = sha256((ROOT / path).read_bytes()).hexdigest()[:12]
    return f"{prefix}{path}?v={version}"


def page_url(path, prefix):
    # GitHub Pages caches HTML for ten minutes; use one cache key per build on every lab page.
    return f'{prefix}{path + "/" if path else ""}?v={SITE_VERSION}'


def page(title, active, content, description):
    prefix = "./" if active == "" else "../"
    page_styles = ''
    if active == "team":
        page_styles = f'''  <link rel="stylesheet" href="{prefix}assets/lab/vendor/fontawesome/css/all.min.css">
  <link rel="stylesheet" href="{asset_url('assets/lab/vendor/yale-team.css', prefix)}">
'''
    elif active == "publications":
        page_styles = f'''  <link rel="stylesheet" href="{asset_url('assets/lab/vendor/yale-publications.css', prefix)}">
'''
    destination = LAB["location"] + ", Hangzhou, China"
    map_url = "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": destination})
    directions_url = "https://www.google.com/maps/dir/?" + urlencode({"api": 1, "destination": destination})
    links = []
    for label, path in NAVIGATION:
        current = ' class="active"' if path == active else ""
        aria = ' aria-current="page"' if path == active else ""
        links.append(f'<li{current}><a href="{page_url(path, prefix)}"{aria}>{label}</a></li>')
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{e(description)}">
  <meta name="bbic-site-version" content="{SITE_VERSION}">
  <title>{e(LAB['name'])} — {e(title)}</title>
  <link rel="icon" type="image/x-icon" href="{prefix}assets/lab/favicon.ico">
  <link rel="icon" type="image/png" sizes="16x16" href="{prefix}assets/lab/favicon-16x16.png">
  <link rel="icon" type="image/png" sizes="32x32" href="{prefix}assets/lab/favicon-32x32.png">
  <link rel="stylesheet" href="{prefix}assets/lab/vendor/yale-lumen.css">
  <link rel="stylesheet" href="{asset_url('assets/lab/lab.css', prefix)}">
{page_styles}  <script src="{asset_url('assets/lab/site.js', prefix)}" defer></script>
</head>
<body class="lab-site">
  <a class="skip-link" href="#main">Skip to content</a>
  <header>
    <nav class="navbar navbar-default navbar-fixed-top" aria-label="Main navigation">
      <div class="container-fluid">
        <div class="navbar-header">
          <button class="navbar-toggle collapsed" type="button" aria-controls="lab-navigation" aria-expanded="false" aria-label="Toggle navigation" data-nav-toggle>
            <span class="icon-bar"></span><span class="icon-bar"></span><span class="icon-bar"></span>
          </button>
          <a class="navbar-brand" href="{page_url('', prefix)}">
            <img class="lab-logo" src="{prefix}assets/lab/bbic-logo.png" width="1375" height="809" alt="">
            <span>{e(LAB['nav_name'])}</span>
          </a>
        </div>
        <div class="collapse navbar-collapse" id="lab-navigation">
          <ul class="nav navbar-nav navbar-right">
            {''.join(links)}
          </ul>
        </div>
      </div>
    </nav>
  </header>
  <main class="container-fluid lab-main" id="main">
{content}
  </main>
  <footer class="lab-footer">
    <div class="container-fluid">
      <p>© {BUILD_YEAR} {e(LAB['name'])}.</p>
      <p>Address: Yuquan Campus, <a href="https://www.zju.edu.cn/english/">Zhejiang University</a> | Hangzhou, China
        (<a href="{e(map_url)}" target="_blank" rel="noopener noreferrer">Maps</a>,
        <a href="{e(directions_url)}" target="_blank" rel="noopener noreferrer">Directions</a>)<br>
        Contact: <a href="mailto:{e(LAB['email'])}">{e(LAB['email'])}</a></p>
      <p class="design-credit">Website design references GitHub academic homepage projects:
        <a href="https://github.com/yale-nlp/yale-nlp.github.io">Yale NLP Lab</a></p>
    </div>
  </footer>
</body>
</html>
'''


def home():
    areas = "".join(f"<li>{e(area)}</li>" for area in LAB["research_areas"])
    highlight = LAB["research_highlight"]
    news_by_month = {}
    for item in LAB["news"]:
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", e(item["text"]))
        link = f' <a href="{e(item["link"])}">[{e(item["link_label"])}]</a>' if item.get("link") else ''
        news_by_month.setdefault(item["date"], []).append(f'<li>{text}{link}</li>')
    news = [f'''          <div class="news-entry">
            <dt>{e(month)}</dt>
            <dd><ul>{''.join(entries)}</ul></dd>
          </div>''' for month, entries in news_by_month.items()]
    news_html = "\n".join(news)
    return f'''    <section class="home-intro" aria-labelledby="lab-title">
      <header class="home-heading">
        <img class="home-heading-logo" src="assets/lab/bbic-logo.png" width="1375" height="809" alt="BBIC Lab logo">
        <h1 id="lab-title">Brain and Brain-Inspired Computing (BBIC) Lab</h1>
      </header>
      <div class="home-intro-content">
        <figure class="home-photo">
          <img src="{e(LAB['home_photo'])}" width="1352" height="1080" alt="BBIC Lab group photo">
        </figure>
        <h2 class="welcome-title">Welcome!</h2>
        <p>We are a research group at the
          <a href="http://www.bbmi.zju.edu.cn/">Center for Brain and Brain-Machine Integration Frontiers</a>,
          <a href="https://www.zju.edu.cn/english/">Zhejiang University</a>,
          under the supervision of <a href="yuqi/">Yu Qi (祁玉)</a>.</p>
        <p>Our current research interests include:</p>
        <ul class="research-areas">{areas}</ul>
        <p class="home-recruitment">We welcome students and researchers interested in these directions. <a href="{page_url('opportunities', './')}">Contact us</a> for more information.</p>
      </div>
    </section>
    <section class="research-feature" aria-labelledby="research-feature-title">
      <h2 class="line-through-title" id="research-feature-title"><span>{e(highlight['title'])}</span></h2>
      <p class="research-feature-intro">Our research on the neural encoding of handwriting was featured on the
        <a href="{e(highlight['publication_url'])}">June 2025 cover of <em>Nature Human Behaviour</em></a>.</p>
      <div class="research-media">
      <figure class="research-cover">
        <a href="{e(highlight['publication_url'])}" aria-label="View the June 2025 Nature Human Behaviour cover issue">
          <img src="{asset_url(highlight['cover'], '')}" width="827" height="1098" loading="lazy"
            alt="Nature Human Behaviour, June 2025 cover: Handwriting in the brain">
        </a>
        <figcaption><a href="{e(highlight['publication_url'])}">June 2025 cover issue</a></figcaption>
      </figure>
      <figure class="research-video">
        <video controls playsinline preload="none" width="1920" height="1080"
          poster="{asset_url(highlight['poster'], '')}" aria-label="BBIC Lab research video">
          <source src="{e(highlight['video'])}" type="video/mp4">
          Your browser does not support embedded video. <a href="{e(highlight['video'])}">Download the video</a>.
        </video>
        <figcaption>Video: <a href="{e(highlight['source_url'])}">Fengshows</a></figcaption>
      </figure>
      </div>
      <p class="research-more">More research: <a href="{page_url('publications', './')}">Publications</a>.</p>
    </section>
    <section class="news-block" aria-labelledby="news-title">
      <h2 class="line-through-title" id="news-title"><span>News</span></h2>
      <div class="news-scroll" role="region" aria-label="Lab news" tabindex="0">
        <dl class="news-list">
{news_html}
        </dl>
      </div>
    </section>'''


def paper_reading():
    sharing_by_year = {}
    for item in LAB["paper_sharing"]:
        presentation_links = []
        preview = item.get("slides_preview")
        if item["slides_format"].upper() == "PDF":
            preview = preview or item["slides"]
        if preview:
            presentation_links.append(f'<a href="../{e(preview)}" target="_blank" rel="noopener">Preview (PDF)</a>')
        if item["slides_format"].upper() != "PDF":
            presentation_links.append(f'<a href="../{e(item["slides"])}" download>Download ({e(item["slides_format"])})</a>')
        sharing_by_year.setdefault(item["year"], []).append(f'''        <div class="sharing-entry">
          <dt>{e(item['date'])}</dt>
          <dd>
            <p>Presenter and topic:</p>
            <p><span lang="zh-CN">{e(item['presenter'])}</span>: {e(item['title'])}</p>
            <p>{' · '.join(presentation_links)} ·
              <a href="{e(item['paper_url'])}">Original paper</a></p>
          </dd>
        </div>''')
    year_sections = []
    for year in sorted(sharing_by_year, reverse=True):
        sharing_html = "\n".join(sharing_by_year[year])
        year_sections.append(f'''      <section class="reading-year" aria-labelledby="reading-year-{e(year)}">
        <h2 class="reading-year-heading" id="reading-year-{e(year)}">{e(year)}</h2>
        <dl class="sharing-list">
{sharing_html}
        </dl>
      </section>''')
    sections_html = "\n".join(year_sections)
    return f'''    <section class="page-copy paper-reading-page" aria-labelledby="paper-reading-title">
      <h1 id="paper-reading-title">Paper Reading</h1>
{sections_html}
    </section>'''


def team():
    students = []
    for student in STUDENTS:
        name = student.get("name") or "To be added"
        photo = student.get("photo") or "assets/lab/student-placeholder.png"
        photo_alt = name if student.get("photo") else ""
        details = []
        if student.get("role"):
            details.append(f'<p>{e(student["role"])}</p>')
        if not student.get("name"):
            details.append('<p>Profile coming soon</p>')
        icons = []
        for field, icon, label in [("homepage", "fas fa-home", "Personal homepage"),
                                   ("github", "fab fa-github", "GitHub"),
                                   ("csdn", "fas fa-blog", "CSDN")]:
            if student.get(field):
                icons.append(f'<a href="{e(student[field])}" aria-label="{e(name)}: {label}" title="{label}" target="_blank" rel="noopener noreferrer"><i class="{icon} icon" style="color: black;" aria-hidden="true"></i></a>')
        if student.get("email"):
            icons.append(f'<a href="mailto:{e(student["email"])}" aria-label="{e(name)}: Email" title="{e(student["email"])}"><i class="fas fa-envelope icon" style="color: black;" aria-hidden="true"></i></a>')
        name_links = f'<span class="student-name-links">{"".join(icons)}</span>' if icons else ''
        interests = student.get("interests") or []
        if isinstance(interests, str):
            interests = [interests]
        interests_html = ''
        if interests:
            tags = ''.join(f'<li class="interest-item" title="{e(interest)}">{e(interest)}</li>' for interest in interests[:3])
            interests_html = f'              <div class="interests-box"><ul class="interests-list">{tags}</ul></div>\n'
        students.append(f'''          <div class="card">
            <figure>
              <div class="avatar">
                <img src="{e(asset_url(photo, '../'))}" alt="{e(photo_alt)}" width="150" height="150" loading="lazy">
              </div>
            </figure>
            <div class="card-body">
              <h3>{e(name)}{name_links}</h3>
              {''.join(details)}
{interests_html}            </div>
          </div>''')
    student_profiles = "\n".join(students)
    return f'''    <section class="team-page" aria-labelledby="team-title">
      <div class="page-copy">
      <h1 id="team-title">Team</h1>
      <h2>Principal Investigator</h2>
      <article class="faculty-profile">
        <a class="faculty-photo" href="../yuqi/" aria-label="Visit Yu Qi’s homepage">
          <img src="../yuqi/images/qiyu.png" alt="Yu Qi" width="220" height="250">
        </a>
        <div>
          <h3><a href="../yuqi/">Yu Qi (祁玉)</a></h3>
          <p>Researcher / Doctoral Supervisor</p>
          <p>School of Medicine, Zhejiang University<br>
            Center for Brain and Brain-Machine Integration Frontiers</p>
          <p>Research interests: artificial intelligence, brain-computer interfaces,
            neural information pattern recognition, and brain-inspired computing.</p>
          <p><a href="../yuqi/">Personal homepage</a> ·
            <a href="https://scholar.google.com/citations?user=LJ9ClwoAAAAJ&amp;hl=en">Google Scholar</a> ·
            <a href="mailto:qiyu@zju.edu.cn">Email</a></p>
        </div>
      </article>
      </div>
      <section class="students-section" aria-labelledby="students-title">
        <div class="page-copy">
          <h2 id="students-title">Students</h2>
          <div class="team-grid">
{student_profiles}
          </div>
        </div>
      </section>
      <div class="page-copy"><p class="join-note">Interested in working with us? <a href="{page_url('opportunities', '../')}">Contact us</a>.</p></div>
    </section>'''


def publications():
    recent_papers = [p for p in PUBLICATIONS if p["year"] is not None and p["year"] >= 2021]
    years = sorted({p["year"] for p in recent_papers}, reverse=True)
    sections = []
    for year in years:
        entries = []
        for paper in (p for p in recent_papers if p["year"] == year):
            kind = paper["type"]
            primary_label = next((label for label in ("paper", "preprint", "scholar", "DBLP") if paper["links"].get(label)), next(iter(paper["links"])))
            primary_url = paper["links"][primary_label]
            additional_links = []
            for label, url in paper["links"].items():
                if label == primary_label or not url:
                    continue
                text = {"code": "Code", "scholar": "Scholar", "preprint": "Preprint"}.get(label.lower(), label)
                additional_links.append(f'<span class="separator" aria-hidden="true">|</span><a class="publication-code-link" href="{e(url)}">{e(text)}</a>')
            search = " ".join([paper["title"], paper["authors"]])
            entries.append(f'''          <li class="publication-item" data-publication data-type="{e(kind)}" data-search="{e(search)}">
            <div class="publication-title-container">
              <a class="publication-title" href="{e(primary_url)}">&quot;{e(paper['title'])}&quot;</a>
            </div>
            <span class="publication-authors">{e(paper['authors'])}</span>
            <div class="publication-venue-categories">
              <span class="publication-venue publication-venue-{e(kind)}">{e(paper['conference'])}</span>{''.join(additional_links)}
            </div>
          </li>''')
        sections.append(f'''      <section class="publication-year" data-year="{year}" aria-labelledby="year-{year}">
        <h2 class="line-through-title" id="year-{year}"><span>{year}</span></h2>
        <ul class="publication-list">{''.join(entries)}</ul>
      </section>''')
    type_controls = ''.join(f'''          <input class="publication-type-checkbox" type="checkbox" id="type-{kind}" value="{kind}" data-publication-type checked>
          <label class="publication-type-label publication-type-label-{kind}" for="type-{kind}">{label}</label>
''' for kind, label in [("preprint", "Preprint"), ("journal", "Journal"), ("conference", "Conference"), ("workshop", "Workshop")])
    year_options = ''.join(f'<option value="{year}">{year}</option>' for year in years)
    return f'''    <section class="publication-page" aria-labelledby="publications-title">
      <h1 class="sr-only" id="publications-title">Publications, 2021 onward</h1>
      <form class="publication-filters" role="search" aria-label="Filter publications" data-publication-filters hidden>
        <div id="publication-type-filter" role="group" aria-labelledby="publication-type-label">
          <h5 id="publication-type-label">Filter by publication type:</h5>
{type_controls}        </div>
        <div id="search-filter">
          <div class="publication-filter-field publication-search-field">
            <h5><label for="publication-search">Search:</label></h5>
            <input id="publication-search" type="search" placeholder="Filter by title or author" autocomplete="off">
          </div>
          <div class="publication-filter-field">
            <h5><label for="publication-year">Year:</label></h5>
            <select id="publication-year">
              <option value="all">All years</option>{year_options}
            </select>
          </div>
        </div>
      </form>
      <p class="sr-only" role="status" aria-live="polite" aria-atomic="true" data-publication-count>{len(recent_papers)} publications</p>
      <p class="empty-results" data-empty-results hidden>No publications match your search. Try another term or year.</p>
{''.join(sections)}
    </section>'''


def events():
    return '''    <section class="page-copy events-page" aria-labelledby="events-title">
      <h1 id="events-title">Events</h1>
      <p>Lab events and activities will be announced here.</p>
    </section>'''


def opportunities():
    return f'''    <section class="page-copy opportunities-page" aria-labelledby="contact-title">
      <h1 id="contact-title">Contact us</h1>
      <p>We welcome motivated PhD and master’s students, postdoctoral researchers, and research assistants
        interested in neural signal processing, machine learning, and brain-inspired intelligence.</p>
      <h2>Research with us</h2>
      <p>Our interests span brain-computer interfaces, robust neural decoding, neural representations,
        and brain-inspired computing. Students with backgrounds in Computer Science and Technology
        or Biomedical Engineering are encouraged to get in touch.</p>
      <h2>Get in touch</h2>
      <p>Please contact <a href="mailto:{e(LAB['email'])}">{e(LAB['email'])}</a> to discuss your interests and potential opportunities.
        A short introduction to your background, research interests, and relevant work would be helpful.</p>
      <p>You can learn more about our work through our <a href="{page_url('publications', '../')}">publications</a>
        and <a href="../yuqi/">Yu Qi’s homepage</a>.</p>
      <h2>Location</h2>
      <p>Yuquan Campus, <a href="https://www.zju.edu.cn/english/">Zhejiang University</a>, Hangzhou, China.</p>
    </section>'''


def main():
    pages = [
        ("index.html", "Home", "", home(), "BBIC Lab: brain-computer interfaces, neural decoding, and brain-inspired intelligence."),
        ("events/index.html", "Events", "events", events(), "Events and activities at BBIC Lab."),
        ("team/index.html", "Team", "team", team(), "Faculty and students at BBIC Lab."),
        ("publications/index.html", "Publications", "publications", publications(), "Research publications by Yu Qi and collaborators, grouped by year from 2021 onward."),
        ("paper-reading/index.html", "Paper Reading", "paper-reading", paper_reading(), "Paper-reading sessions and presentation materials at BBIC Lab."),
        ("opportunities/index.html", "Contact Us", "opportunities", opportunities(), "Contact BBIC Lab about research opportunities and collaborations."),
    ]
    for path, title, active, content, description in pages:
        destination = ROOT / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(page(title, active, content, description), encoding="utf-8")
        print(f"Built {path}")


if __name__ == "__main__":
    main()
