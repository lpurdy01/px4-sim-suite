# Presentations

Marp-based slide decks for px4-sim-suite. Source files are Markdown with
[Marp](https://marp.app/) front matter. Mermaid diagrams are pre-rendered to
SVG for reliable PDF output.

## Prerequisites

**In the devcontainer:** Everything is pre-installed. Just run `npm install`.

**On a fresh system:** Install Node.js (v18+), npm, and Google Chrome:

```bash
# Node.js and npm
sudo apt-get update && sudo apt-get install -y nodejs npm

# Google Chrome (required for PDF export and Mermaid rendering)
wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y /tmp/chrome.deb
```

Then install the project dependencies:

```bash
cd docs/presentations
npm install
```

## Usage

From the `docs/presentations/` directory:

```bash
# Build both HTML and PDF (recommended)
npm run build

# Build HTML only (fast, for preview)
npm run build:html

# Build PDF only (includes Mermaid pre-rendering)
npm run build:pdf

# Live preview in browser
npm run preview

# Pre-render Mermaid diagrams only (without full build)
npm run prerender
```

Output goes to `docs/presentations/dist/`.

## How Mermaid Rendering Works

This pipeline uses a **two-stage approach** for Mermaid diagrams:

1. **HTML preview:** Mermaid.js loads from CDN and renders client-side
2. **PDF export:** Diagrams are pre-rendered to SVG using `@mermaid-js/mermaid-cli`

The pre-rendering step:
- Extracts ```` ```mermaid ```` code blocks from each `.md` file
- Renders each diagram to SVG using `mmdc` (headless Chrome)
- Creates a `.processed.md` file with `![](generated/*.svg)` image references
- PDFs are built from the processed files for pixel-perfect diagrams

This avoids text clipping issues that occur when Chrome captures the page
before Mermaid finishes rendering.

## File Structure

```
docs/presentations/
├── .marp/
│   └── engine.mjs              # Custom Marp engine (CDN mermaid for HTML)
├── .marprc.yml                 # Marp CLI config (slide size, etc.)
├── .gitignore                  # Excludes dist/, node_modules/, generated/
├── package.json                # Build scripts and dependencies
├── puppeteer-config.json       # Chrome flags for containers
├── scripts/
│   └── prerender-mermaid.mjs   # SVG pre-rendering script
├── px4-sim-suite-overview.md   # Main presentation
└── slides/
    ├── agents-md-tree.md
    ├── devcontainer-design.md
    └── uav-stack-coverage.md
```

### Generated files (gitignored)

```
├── dist/                       # Build output (HTML + PDF)
├── generated/                  # Pre-rendered SVGs for root presentations
├── slides/generated/           # Pre-rendered SVGs for slides/
└── *.processed.md              # Intermediate files with SVG references
```

## Adding New Presentations

1. Create a `.md` file anywhere under `docs/presentations/`:

```yaml
---
marp: true
theme: default
paginate: true
---

# My Slide Title

Content here...

---

# Next Slide

More content...
```

2. Add Mermaid diagrams with standard fenced code blocks:

````markdown
```mermaid
graph LR
    A[Start] --> B[Process]
    B --> C[End]
```
````

3. Run `npm run build` to generate HTML and PDF output.

## Configuration

### Slide Size

The default slide size is **2560x1440** (QHD) to provide ample space for
diagrams. Edit `.marprc.yml` to change:

```yaml
size: 1920x1080  # Full HD
size: 1280x720   # Default Marp size
```

### Mermaid Theme

Edit `scripts/prerender-mermaid.mjs` to change the Mermaid theme or config
passed to `mmdc`.

## Troubleshooting

### "No usable sandbox" error

The devcontainer uses `--no-sandbox` for Puppeteer. If running outside the
container, you may need to configure Chrome sandbox permissions or use the
`puppeteer-config.json` approach.

### Mermaid diagrams not rendering in PDF

Run `npm run prerender` separately to check for errors. Common issues:
- Syntax errors in mermaid code blocks
- Missing Chrome/Chromium installation

### Text clipping in diagrams

The pre-rendering approach should fix this. If still occurring:
1. Simplify the diagram (shorter labels)
2. Increase slide size in `.marprc.yml`
3. Check the generated SVG in `generated/` folder
