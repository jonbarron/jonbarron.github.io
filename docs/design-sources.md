# Website design sources

The laboratory pages adapt the layout of the [Yale NLP Lab website](https://nlp.cs.yale.edu/), whose [source repository](https://github.com/yale-nlp/yale-nlp.github.io) uses Jekyll, Bootstrap, and the Bootswatch Lumen theme. The existing Yu Qi personal homepage uses its original design and assets.

## Yale NLP layout

The upstream [README](https://github.com/yale-nlp/yale-nlp.github.io/blob/gh-pages/README.md) explicitly permits copying and modification for other purposes and says a link or mention is optional. Its [website documentation](https://github.com/yale-nlp/yale-nlp.github.io/blob/gh-pages/_pages/aboutwebsite.md) also states that the code is released under the MIT License and identifies the [Allan Lab template](https://github.com/mpa139/allanlab) as its source. The Yale repository does not contain a standalone `LICENSE` file.

The layout reference preserves the restrained navigation, centered content area, typography, blue links, and date-based news presentation. Yale's people, publications, text, photographs, logos, analytics settings, and JavaScript are not part of the imported vendor assets. BBIC-specific content is maintained separately.

The homepage News section follows the inline CSS on [Yale NLP's homepage](https://nlp.cs.yale.edu/):
a centered title over a thin horizontal rule, a content region with a maximum
height of 300px and vertical scrolling, 20px side padding, and dated bullet lists
with a 1:6 date-to-event ratio. The entries are maintained in `site-data/lab.json`
using announcements supplied by the laboratory. No Yale news text is copied,
and `yuqi/` remains unchanged.

`assets/lab/vendor/yale-lumen.css` was downloaded from [Yale NLP's compiled stylesheet](https://nlp.cs.yale.edu/css/main.css) on 2026-11-07. The original copyright comments remain in place. Local changes replace the Google Fonts import with local Source Sans Pro files and remove an unused `Open Sans` font declaration whose URLs were upstream placeholders. No other upstream CSS rules were changed.

The stylesheet is loaded only by the laboratory pages. Its global Bootstrap rules must not be added to the personal homepage.

The Students section directly reuses the card markup and active CSS from Yale's
[`_pages/team.html`](https://github.com/yale-nlp/yale-nlp.github.io/blob/gh-pages/_pages/team.html).
The rules in `assets/lab/vendor/yale-team.css` are scoped to Students. The original
150px circular avatars, 45px grid gaps, typography, interest tags, and hover
movement/shadow are preserved. Member names use h3 to sit beneath BBIC's Students
h2. The source page's Bootstrap 3.3.7 inherited font and margins are reproduced
locally. PI content retains its existing layout. The grid shares the PI content
container and its 20px extension on each side so their hover frames align.
It uses four columns on desktop, as requested for BBIC. Smaller screens retain
the source's automatic columns.
The Principal Investigator profile uses the same original hover movement,
shadow, and transition, while keeping its existing photo and text layout.
Profile link icons appear inline to the right of student names, as requested for BBIC.

Student portraits in `assets/lab/students/` use the public GitHub avatars supplied
for [Lei Wang](https://github.com/wanglei3407), [Yao Jia](https://github.com/Jurio0304),
[Yuan Wang](https://github.com/Smullwy), [Jie Yu](https://github.com/zeusyu0927),
and [Xiaoke Yang](https://github.com/Ybekk).
Avatar URLs were obtained from the
GitHub user API and the images are stored locally as PNG files.

`assets/lab/student-placeholder.png` is the unmodified generic
[`dummy_profile.png`](https://github.com/yale-nlp/yale-nlp.github.io/blob/gh-pages/images/teampic/dummy_profile.png)
provided by the Yale repository, reused under its README's permission. No real
Yale member photos or profiles are used. The source Font Awesome 5.15.3 icon CSS
and WOFF2 fonts are self-hosted in `assets/lab/vendor/fontawesome/`; the original
license is retained in that directory.

## Publications

The publications page adapts the live [Yale NLP publications layout](https://nlp.cs.yale.edu/publications/)
and its [Jekyll template](https://github.com/yale-nlp/yale-nlp.github.io/blob/gh-pages/_pages/publications.md).
It uses a single text column, linked bold paper titles, a separate plain author
line, italic venue badges, publication-type toggles, title/author search, and
centered year headings with faded rules. The original typography, 20px item spacing,
and badge geometry are retained. Link and year-rule colors use BBIC's Zhejiang
University blue. These styles are restricted to `.lab-site .publication-page` in
`assets/lab/vendor/yale-publications.css`. Category tags are not fabricated, and
the source page's hidden category and first/last-author controls are not displayed.

The bibliography is limited to 2021 onward. `site-data/publications-sources.json`
records source coverage and date/version differences; individual records carry
their verification URLs. Additions use DBLP records with the correct Yu Qi ORCID
(0000-0002-9789-8907), confirmed collaborators, and publisher or PubMed metadata.
The original 28 thumbnail paths are retained as data, while the lab's publication
page uses Yale's text layout. Complete Google Scholar coverage was not verified
because the profile could not be accessed. The protected personal site's
publication list and files remain unchanged.

## Homepage introduction

The photo and Welcome heading arrangement references the
[Schütze Lab homepage](https://cisnlp.github.io/). Its
[website documentation](https://cisnlp.github.io/aboutwebsite.html) permits copying
and modification and states that the code is released under the MIT License.
The homepage adopts the left photo, surrounding text, 400px photo width, 40px
separation, and 6px photo corners. The transparent BBIC logo sits to the left of
the full laboratory name in a shared title row above the introduction. Smaller
screens stack the photo above the introduction. BBIC's existing typography and
Zhejiang University blue are retained; the wordmark keeps its original proportions.

`assets/lab/lab-group.jpg` is the unmodified group photograph supplied for this
website. The old standalone research screenshot is replaced by this group photo
in the homepage layout; the original personal site's image remains unchanged.

## Featured research video

The homepage's Highlights section appears immediately before News. Paper Reading
has its own page after Publications in the navigation. Highlights links
to the [June 2025 Nature Human Behaviour cover issue](https://www.nature.com/nathumbehav/volumes/9/issues/6).
The user-requested 18:47–22:22 excerpt from
[Fengshows' 我·與腦（三）](https://www.fengshows.com/video/14ddc23a-3da1-4588-87b2-84bfd05ef2bc)
is stored as `assets/lab/videos/recent-research-1080p.mp4`: 1920 × 1080, 25 fps,
3 minutes 35 seconds, with its original visible credits and a stereo audio track.
The poster uses the frame selected by the user. The native video player has
controls, supports inline playback on phones, and starts only when requested;
`preload="none"` avoids downloading the video on the initial page load. The media,
poster, source, and cover-issue URL are configured in `site-data/lab.json` under
`research_highlight`. The broadcaster's video is separate from the template's code
and CSS licensing documented here.

The linked June 2025 cover sits beside the video after the introductory sentence,
with matching image heights and their original proportions. On smaller screens,
the cover appears above the video. The unmodified 827 × 1098 PNG is obtained from
[Springer Nature's official cover image](https://media.springernature.com/full/springer-static/cover-hires/journal/41562/9/6)
and stored at `assets/lab/nature-human-behaviour-june-2025.png` (configured as
`research_highlight.cover`). The issue page credits the image to Yu Qi, Xinyun Zhu,
Yu Han, and Chaoyang Zhao, and the cover design to Bethany Vukomanovic. The cover
artwork is separate from the template licensing. The original personal site's
cover screenshot is unchanged.

## Laboratory accent color

The laboratory overrides the original Lumen link color with Zhejiang University's
official **truth-seeking blue**, RGB (0, 63, 136), or `#003F88`, as specified on the
[university's logo page](https://www.zju.edu.cn/english/2023/0323/c74903a2732011/page.htm).
The color is defined as `--lab-accent` in `assets/lab/lab.css` and used for links and
keyboard/input focus indicators. The footer
acknowledgment remains light gray, and the original personal website is unchanged.

## Laboratory logo

`assets/lab/bbic-logo.png` is the laboratory logo supplied for this website, with
its white background removed to PNG transparency and its edge pixels unmatted.
The original dimensions, proportions, and solid blue/red/black pixels are preserved.
The navigation displays it beside the configurable `nav_name` (`BBIC Lab@ZJU`)
from `site-data/lab.json`.

The browser favicon is cropped from the blue symbol in this supplied logo, with
transparent padding, and exported at 16 × 16 and 32 × 32 pixels plus a multi-size
ICO. The wordmark is omitted in these small icons for legibility. The navigation
continues to use the full logo. The personal site's favicon is unchanged.

## Third-party CSS

Full notices and MIT license texts are retained in [`assets/lab/vendor/LICENSES.txt`](../assets/lab/vendor/LICENSES.txt):

| Component | Version | Upstream license |
| --- | --- | --- |
| Bootstrap | 3.3.7 | [MIT](https://github.com/twbs/bootstrap/blob/v3.3.7/LICENSE) |
| Bootswatch / Lumen | 3.3.7 | [MIT](https://github.com/thomaspark/bootswatch/blob/v3.3.7/LICENSE) |
| normalize.css | 3.0.3 | [MIT](https://github.com/necolas/normalize.css/blob/3.0.3/LICENSE.md) |
| HTML5 Boilerplate print styles | Print-style attribution present in the compiled CSS | [MIT](https://github.com/h5bp/html5-boilerplate/blob/5.3.0/LICENSE.txt) |

## Local fonts

Source Sans Pro is distributed by Adobe under the [SIL Open Font License 1.1](https://github.com/adobe-fonts/source-sans/blob/release/LICENSE.md). Its full license and the original embedded copyright notice are retained in [`assets/lab/vendor/fonts/OFL.txt`](../assets/lab/vendor/fonts/OFL.txt).

The four unmodified TrueType files were downloaded from Google Fonts' `sourcesanspro/v24` distribution and are self-hosted in `assets/lab/vendor/fonts/`:

| File | Weight | Style | Source |
| --- | --- | --- | --- |
| `SourceSansPro-Light.ttf` | 300 | Normal | [Google Fonts](https://fonts.gstatic.com/s/sourcesanspro/v24/6xKydSBYKcSV-LCoeQqfX1RYOo3ik4zwlxdr.ttf) |
| `SourceSansPro-Regular.ttf` | 400 | Normal | [Google Fonts](https://fonts.gstatic.com/s/sourcesanspro/v24/6xK3dSBYKcSV-LCoeQqfX1RYOo3qOK7g.ttf) |
| `SourceSansPro-Bold.ttf` | 700 | Normal | [Google Fonts](https://fonts.gstatic.com/s/sourcesanspro/v24/6xKydSBYKcSV-LCoeQqfX1RYOo3ig4vwlxdr.ttf) |
| `SourceSansPro-Italic.ttf` | 400 | Italic | [Google Fonts](https://fonts.gstatic.com/s/sourcesanspro/v24/6xK1dSBYKcSV-LCoeQqfX1RYOo3qPZ7nsDc.ttf) |

The font faces use `font-display: swap`, with Helvetica Neue, Helvetica, Arial, and generic sans-serif fallbacks. The imported CSS makes no remote font requests.

## Visible acknowledgment

The laboratory footer uses three vertically stacked, full-width paragraphs: copyright, address/contact details, and the acknowledgment. Address and Contact have separate labels and lines; Maps and Directions follow the address. Only the contact email is blue; the remaining footer links inherit their surrounding gray text color. The final acknowledgment line is smaller and light gray: “Website design references GitHub academic homepage projects: Yale NLP Lab”, linking to the Yale source repository. The original Allan template provenance remains documented above. Retain the third-party notices when redistributing the bundled stylesheet and fonts.
