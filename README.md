# Symposium Schedule 

Generate the ORFE Thesis Symposium schedule from a corresponding web site and generate a nicely formatted, paginated PDF or JSON output.

## Features

- Scrapes schedule data from https://symposium.orfe.princeton.edu
- Handles Cloudflare protection using Playwright
- Extracts room information, advisors, graders, and presentation schedules
- Generates paginated PDF with formatted tables
- Optional JSON output for data processing
- Comprehensive unit tests

## Requirements

- Python 3.8+
- Playwright (for browser automation)
- BeautifulSoup4 (for HTML parsing)
- ReportLab (for PDF generation)

## Installation

1. Clone or download the repository
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install Playwright browsers:
   ```bash
   python -m playwright install chromium
   ```

## Usage

### Generate PDF (default)
```bash
python scrape_schedule.py
```
This creates `symposium_schedule.pdf` with the formatted schedule, keeping each room's information together on pages.

### Allow page breaks within rooms
```bash
python scrape_schedule.py --allow-breaks
```
This allows page breaks that might separate room titles from their content (not recommended).

### Show table headers
```bash
python scrape_schedule.py --show-headers
```
Include column headers (Time, Presenter) in the tables.

### Generate JSON output
```bash
python scrape_schedule.py --json
```
This outputs the schedule data as JSON to stdout and saves it to `symposium_schedule.json`.

### Generate PDF without title
```bash
python scrape_schedule.py --no-title
```
Excludes the title header from the PDF output.

### Generate PDF with QR codes
```bash
python scrape_schedule.py --qr-codes
```
Includes QR codes for each room that link to the room's anchor on the webpage.

### Generate landscape grid PDF
```bash
python scrape_schedule.py --grid
```
Creates `symposium_schedule_grid.pdf` with all rooms side by side in a landscape table layout.

### Run tests
```bash
python -m unittest test_scrape.py -v
```

## Output Format

### PDF
- Title page with symposium name
- Separate sections for each room
- Advisor and grader information
- Table with Time and Presenter columns
- Automatic pagination

### JSON
```json
{
  "001": {
    "advisors": "ORFE Advisors: Dr. Smith, Dr. Johnson",
    "graders": "PhD Candidate Graders: Alex Chen",
    "schedule": [
      ["9:00 am – 9:15 am", "John Anderson"],
      ["9:15 am – 9:30 am", "Sarah Mitchell"]
    ]
  }
}
```

## Testing

The project includes unit tests to ensure:
- At least one room is scraped
- Each room has required data structure
- Schedule items are properly formatted
- No regression in parsing logic

Run tests with:
```bash
python -m unittest test_scrape.py
```

## Dependencies

- requests
- beautifulsoup4
- reportlab
- playwright
- pytest (optional, for testing)

## License

This project is for educational purposes. Please respect the website's terms of service and Princeton University's policies.

## GitHub Actions Workflows

### Generate Symposium Schedule
Automatically generates PDF and JSON outputs. Triggers on:
- **Push to main** — regenerates on every commit
- **Scheduled (every 30 minutes)** — polls the source website for changes and regenerates if the schedule content has been updated
- **Manual dispatch** — run from the Actions tab with configurable options:
  - **Show headers**: Include column headers in the PDF table
  - **Allow breaks**: Allow page breaks within room sections
  - **Include title**: Include the title in PDF output
  - **QR codes**: Include QR codes linking to room anchors
  - **Grid PDF**: Generate landscape grid PDF with all rooms side by side
  - **Force generate**: Bypass change detection and regenerate regardless

#### Change Detection
The workflow hashes the scraped schedule data and compares it to a cached hash from the previous run. If no changes are detected, the release step is skipped. Use **Force generate** to bypass this check.

#### Outputs
The workflow produces artifacts and a GitHub Release (`latest` tag) containing:
- `symposium_schedule.pdf` — Formatted PDF with QR codes
- `symposium_schedule_grid.pdf` — Landscape grid PDF with all rooms side by side
- `symposium_schedule.json` — Structured JSON data

### Tests
Runs the full test suite on pushes to main and pull requests. Tests can also be run locally via Docker:
```bash
docker build -f Dockerfile.test -t symposium-test . && docker run --rm symposium-test
```

## Public Displays

The `pages/` directory contains a public display page designed for conference room TVs (1080p and 4K). It is deployed automatically to GitHub Pages.

### Display URLs

Once GitHub Pages is enabled, the display is available at:

| URL | View |
|-----|------|
| `display.html?floor=ground` | Ground floor rooms (001, 003, 008) |
| `display.html?floor=1` | 1st floor rooms (101–125) |
| `display.html?rooms=001,003` | Specific rooms only |
| `display.html` | All rooms |

Add `&highlight=false` to disable current-talk highlighting.

### How it works

- On GitHub Pages, `display.html` fetches the `symposium_schedule.json` that the generate workflow publishes to the `latest` release. The Pages workflow downloads this JSON and deploys it alongside the display page.
- The page refreshes data every 5 minutes. The JSON is updated every 20 minutes by the generate workflow.
- All sizing uses `vw` units so the layout scales identically on 1080p and 4K displays. On smaller screens (laptops), the page scrolls.

### CSS Overrides

For environments that inject CSS on top of the original symposium URL:

- `override-base.css` — core overrides (always required)
- `override-floor-ground.css` — show only ground floor rooms
- `override-floor-1.css` — show only 1st floor rooms

### Local Development

```bash
cd pages
python3 ../serve.py 8000
```

Or serve with any static file server — the page falls back to `/proxy/schedule` when not on GitHub Pages or princeton.edu.