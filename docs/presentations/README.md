# Presentations

Marp-based slide decks for px4-sim-suite. Source files are Markdown with
[Marp](https://marp.app/) front matter; Mermaid diagrams are supported via a
custom engine that loads Mermaid from CDN.

## Prerequisites

Install Node.js (LTS), npm, and Google Chrome:

```bash
# Node.js and npm
sudo apt-get update && sudo apt-get install -y nodejs npm

# Google Chrome (required for PDF export and Mermaid rendering in PDFs)
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
# Build all slides to HTML
npm run build:html

# Build all slides to PDF
npm run build:pdf

# Build both HTML and PDF
npm run build

# Live preview (opens in browser)
npm run preview
```

Output goes to `docs/presentations/dist/`.

## File structure

```
docs/presentations/
├── .marp/
│   └── engine.mjs          # Custom Marp engine (adds Mermaid support)
├── .marprc.yml              # Marp CLI configuration
├── package.json             # npm scripts and dependencies
├── px4-sim-suite-overview.md
└── slides/
    ├── agents-md-tree.md
    └── uav-stack-coverage.md
```

## Adding new presentations

Create a `.md` file anywhere under `docs/presentations/` with Marp front matter:

```yaml
---
marp: true
theme: default
paginate: true
---
```

Mermaid diagrams work with standard fenced code blocks:

````markdown
```mermaid
graph LR
    A --> B
```
````

Run `npm run build` to generate HTML and PDF output.
