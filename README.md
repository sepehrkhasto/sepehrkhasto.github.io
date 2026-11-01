# sepehrkhasto.github.io

Source for my portfolio at <https://sepehrkhasto.github.io> (English) and <https://sepehrkhasto.github.io/fa/> (Persian).

The site is plain HTML, CSS and a small amount of JavaScript, generated from two content files by a Python script that uses only the standard library. GitHub Actions runs the tests and publishes it to GitHub Pages on every push to `main`.

## Running it locally

Requires Python 3.10 or newer. No dependencies.

```bash
python build.py --serve                     # http://localhost:8000
python -m unittest discover -s tests -v
```

## Layout

| Path | Contents |
| --- | --- |
| `content/en.json`, `content/fa.json` | All page copy. Both files keep the same structure; the tests check this. |
| `build.py` | Renders the content into `dist/`: one page per language, plus `404.html`, `sitemap.xml` and `robots.txt`. |
| `static/` | CSS, JavaScript, fonts (IBM Plex, self-hosted), images and the resume PDFs. Copied to `dist/` as is. |
| `assets-src/` | Original screenshots and `images.json`, which records their sizes for the build. |
| `resume/` | HTML sources for the resumes and the script that renders them to PDF. |
| `brand/`, `tools/` | Banner and social preview images, and the scripts that produce them and the WebP screenshots. |
| `tests/` | Build and content checks, run in CI before each deploy. |

## Editing

- **Copy:** edit the same field in both `content/*.json` files, then run the tests.
- **Screenshots:** add a PNG to `assets-src/screenshots/` and run `python tools/process_images.py` (Pillow).
- **Resumes:** edit `resume/en.html` and `resume/fa.html`, then run `python resume/make_pdfs.py` (Playwright with Chromium). `resume/ats-en.html` produces a plain single-column version for job portals; it stays out of the published site.
- **Images:** `python tools/make_brand.py` regenerates the social preview and the LinkedIn and GitHub banners.

## Deployment

In the repository settings, set **Pages → Source** to **GitHub Actions**. After that, every push to `main` is tested and deployed by `.github/workflows/deploy.yml`.
