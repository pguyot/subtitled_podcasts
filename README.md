# Subtitled Podcasts - Alltagsdeutsch

This project automatically generates and publishes a podcast index page for DW's Alltagsdeutsch (Everyday German) podcast series on GitHub Pages.

## Features

- **Automated RSS Feed Parsing**: Fetches the latest episodes from DW's RSS feed
- **Dynamic HTML Generation**: Creates a beautiful, responsive index page
- **GitHub Actions Deployment**: Automatically updates the page when changes are pushed
- **No External Dependencies**: Uses only Python standard library

## Project Structure

```
.
├── .github/
│   └── workflows/
│       └── deploy-pages.yml    # GitHub Actions workflow for deployment
├── generate_index.py            # Python script to parse RSS and generate HTML
├── requirements.txt             # Python dependencies (currently none)
├── index.html                   # Generated podcast index page (auto-generated)
└── README.md                    # This file
```

## How It Works

1. **RSS Feed Parsing**: The `generate_index.py` script fetches the RSS feed from:
   ```
   https://rss.dw.com/xml/DKpodcast_alltagsdeutsch_de
   ```

2. **HTML Generation**: The script extracts the first 10 episodes and generates an HTML page with:
   - Episode titles
   - Publication dates
   - Descriptions
   - Audio links
   - Duration information

3. **Automatic Deployment**: On every push to `main` or `master` branch, GitHub Actions:
   - Runs the Python script to regenerate the index
   - Deploys the updated page to GitHub Pages

## Local Development

### Generate the Index Page Locally

```bash
python3 generate_index.py
```

This will create/update the `index.html` file with the latest episodes from the RSS feed.

### Requirements

- Python 3.x (uses standard library only, no pip install needed)

## GitHub Pages Setup

To enable GitHub Pages for this repository:

1. Go to **Repository Settings** → **Pages**
2. Under "Build and deployment" → **Source**, select **GitHub Actions**
3. The workflow will automatically deploy on the next push to main/master

Your site will be available at:
```
https://<username>.github.io/subtitled_podcasts/
```

## RSS Feed Source

Episodes are sourced from **DW Deutsch lernen - Alltagsdeutsch**:
- Website: https://learngerman.dw.com/de/alltagsdeutsch/s-56744441
- RSS Feed: https://rss.dw.com/xml/DKpodcast_alltagsdeutsch_de
- Level: C1 (Advanced German)

## Customization

### Change Number of Episodes

Edit `generate_index.py` and modify:
```python
MAX_EPISODES = 10  # Change to desired number
```

### Modify Styling

The HTML template in `generate_index.py` contains embedded CSS. Edit the `HTML_TEMPLATE` variable to customize the appearance.

### Use Different RSS Feed

Change the `RSS_FEED_URL` variable in `generate_index.py`:
```python
RSS_FEED_URL = "your-rss-feed-url"
```

## License

This project is for educational purposes. Podcast content is copyright Deutsche Welle.
