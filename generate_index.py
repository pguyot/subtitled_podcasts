#!/usr/bin/env python3
"""
Generate index.html from DW Alltagsdeutsch RSS feed
"""

import xml.etree.ElementTree as ET
import html
from datetime import datetime
from urllib.request import urlopen
import re
import os
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

RSS_FEED_URL = "https://rss.dw.com/xml/DKpodcast_alltagsdeutsch_de"
OUTPUT_FILE = "index.html"
MANUSCRIPTS_DIR = "manuscripts"
MAX_EPISODES = 10

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Subtitled Podcasts - Alltagsdeutsch</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}

        header {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}

        h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
        }}

        .subtitle {{
            font-size: 1.1rem;
            opacity: 0.9;
        }}

        .content {{
            padding: 40px;
        }}

        .intro {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin-bottom: 30px;
            border-radius: 5px;
        }}

        .episodes-list {{
            display: grid;
            gap: 20px;
        }}

        .episode {{
            background: #fff;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 25px;
            transition: all 0.3s ease;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
        }}

        .episode:hover {{
            transform: translateY(-3px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            border-color: #667eea;
        }}

        .episode-number {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: bold;
            margin-bottom: 10px;
        }}

        .episode-title {{
            font-size: 1.5rem;
            color: #1e3c72;
            margin: 10px 0;
            font-weight: 600;
        }}

        .episode-date {{
            color: #888;
            font-size: 0.9rem;
            margin-bottom: 10px;
        }}

        .episode-description {{
            color: #666;
            margin: 15px 0;
            line-height: 1.7;
        }}

        .episode-meta {{
            display: flex;
            gap: 15px;
            margin-top: 15px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .episode-link {{
            display: inline-block;
            padding: 8px 16px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 0.9rem;
            transition: background 0.3s ease;
        }}

        .episode-link:hover {{
            background: #5568d3;
        }}

        .audio-link {{
            background: #28a745;
        }}

        .audio-link:hover {{
            background: #218838;
        }}

        .level-badge {{
            background: #ffc107;
            color: #333;
            padding: 5px 12px;
            border-radius: 5px;
            font-size: 0.85rem;
            font-weight: 600;
        }}

        .duration {{
            color: #666;
            font-size: 0.85rem;
            padding: 5px 12px;
            background: #f0f0f0;
            border-radius: 5px;
        }}

        footer {{
            background: #f8f9fa;
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.9rem;
        }}

        footer a {{
            color: #667eea;
            text-decoration: none;
        }}

        footer a:hover {{
            text-decoration: underline;
        }}

        .last-updated {{
            margin-top: 10px;
            font-size: 0.85rem;
            color: #888;
        }}

        .manuscript-link {{
            background: #ff6b6b;
        }}

        .manuscript-link:hover {{
            background: #ee5a5a;
        }}

        /* Modal styles */
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            overflow: auto;
            background-color: rgba(0, 0, 0, 0.7);
        }}

        .modal-content {{
            background-color: #fefefe;
            margin: 5% auto;
            padding: 0;
            border: 1px solid #888;
            width: 90%;
            max-width: 900px;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            max-height: 85vh;
            display: flex;
            flex-direction: column;
        }}

        .modal-header {{
            padding: 20px;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            border-radius: 10px 10px 0 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .modal-header h2 {{
            margin: 0;
            font-size: 1.5rem;
        }}

        .close {{
            color: white;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            background: none;
            border: none;
            padding: 0;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.2s;
        }}

        .close:hover,
        .close:focus {{
            transform: scale(1.2);
        }}

        .modal-body {{
            padding: 30px;
            overflow-y: auto;
            flex: 1;
        }}

        .modal-body h3 {{
            color: #1e3c72;
            margin-top: 20px;
            margin-bottom: 10px;
        }}

        .modal-body p {{
            line-height: 1.8;
            margin-bottom: 15px;
        }}

        @media (max-width: 768px) {{
            h1 {{
                font-size: 2rem;
            }}

            .content {{
                padding: 20px;
            }}

            header {{
                padding: 30px 20px;
            }}

            .modal-content {{
                width: 95%;
                margin: 10% auto;
                max-height: 80vh;
            }}

            .modal-body {{
                padding: 20px;
            }}
        }}
    </style>
    <script>
        function showManuscript(episodeNumber) {{
            const modal = document.getElementById('manuscript-modal-' + episodeNumber);
            modal.style.display = 'block';
        }}

        function closeManuscript(episodeNumber) {{
            const modal = document.getElementById('manuscript-modal-' + episodeNumber);
            modal.style.display = 'none';
        }}

        // Close modal when clicking outside of it
        window.onclick = function(event) {{
            if (event.target.classList.contains('modal')) {{
                event.target.style.display = 'none';
            }}
        }}

        // Close modal on Escape key
        document.addEventListener('keydown', function(event) {{
            if (event.key === 'Escape') {{
                const modals = document.querySelectorAll('.modal');
                modals.forEach(modal => modal.style.display = 'none');
            }}
        }});
    </script>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎧 Subtitled Podcasts</h1>
            <p class="subtitle">Alltagsdeutsch - Deutsche im Alltag</p>
        </header>

        <div class="content">
            <div class="intro">
                <h2>Willkommen!</h2>
                <p>Hier finden Sie die neuesten Alltagsdeutsch-Podcastfolgen von DW Deutsch lernen. Diese Podcasts sind für fortgeschrittene Deutschlernende (C1-Niveau) konzipiert und behandeln verschiedene Themen aus dem deutschen Alltag.</p>
            </div>

            <div class="episodes-list">
{episodes}
            </div>
        </div>

        <footer>
            <p>
                Quelle: <a href="https://learngerman.dw.com/de/alltagsdeutsch/s-56744441" target="_blank">DW Deutsch lernen - Alltagsdeutsch</a>
            </p>
            <p>
                RSS Feed: <a href="{rss_url}" target="_blank">{rss_url}</a>
            </p>
            <p class="last-updated">
                Zuletzt aktualisiert: {last_updated}
            </p>
        </footer>
    </div>
</body>
</html>
"""

EPISODE_TEMPLATE = """                <!-- Episode {number} -->
                <div class="episode">
                    <span class="episode-number">Episode {number}</span>
                    <h3 class="episode-title">{title}</h3>
                    <p class="episode-date">{date}</p>
                    <p class="episode-description">
                        {description}
                    </p>
                    <div class="episode-meta">
                        <span class="level-badge">C1 Niveau</span>
{duration}
                        <a href="{link}" class="episode-link" target="_blank">Zur Episode →</a>
{audio_link}
{manuscript_button}
                    </div>
                </div>
{manuscript_modal}
"""

MANUSCRIPT_MODAL_TEMPLATE = """                <!-- Manuscript Modal for Episode {number} -->
                <div id="manuscript-modal-{number}" class="modal">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2>📄 Manuskript - {title}</h2>
                            <button class="close" onclick="closeManuscript({number})">&times;</button>
                        </div>
                        <div class="modal-body">
                            {manuscript_content}
                        </div>
                    </div>
                </div>
"""


def format_duration(duration_str):
    """Format duration string to readable format"""
    if not duration_str:
        return ""

    try:
        # Handle different duration formats (HH:MM:SS, MM:SS, or seconds)
        if ':' in str(duration_str):
            parts = str(duration_str).split(':')
            if len(parts) == 3:  # HH:MM:SS
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])
                if hours > 0:
                    return f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    return f"{minutes}:{seconds:02d}"
            elif len(parts) == 2:  # MM:SS
                return duration_str
        else:
            # Assume seconds
            seconds = int(duration_str)
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}:{secs:02d}"
    except (ValueError, TypeError):
        return duration_str

    return ""


def strip_html_tags(text):
    """Remove HTML tags from text"""
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub('<.*?>', '', text)
    return clean.strip()


def parse_feed():
    """Parse RSS feed and extract episodes"""
    print(f"Fetching RSS feed from {RSS_FEED_URL}...")

    try:
        from urllib.request import Request
        # Add User-Agent to avoid 403 errors
        req = Request(RSS_FEED_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req) as response:
            xml_data = response.read()
    except Exception as e:
        raise Exception(f"Failed to fetch RSS feed: {e}")

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        raise Exception(f"Failed to parse RSS feed XML: {e}")

    # Find all item elements
    # RSS feeds use the 'item' tag within 'channel'
    items = root.findall('.//item')

    if not items:
        raise Exception("No episodes found in RSS feed")

    print(f"Found {len(items)} episodes in feed")
    return items


def get_element_text(element, tag, default=''):
    """Safely extract text from XML element"""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text
    # Try with namespace for iTunes tags
    if 'itunes:' in tag:
        ns_tag = tag.replace('itunes:', '{http://www.itunes.com/dtds/podcast-1.0.dtd}')
        child = element.find(ns_tag)
        if child is not None and child.text:
            return child.text
    return default


def get_manuscript_url(episode_link):
    """
    Extract manuscript URL from episode link
    Example: https://learngerman.dw.com/de/sportler-im-abseits/l-19262668?maca=...
    Returns: https://learngerman.dw.com/de/sportler-im-abseits/l-19262668/lm
    """
    if not episode_link or episode_link == '#':
        return None

    # Remove query string
    base_url = episode_link.split('?')[0]

    # Add /lm to get the manuscript page
    manuscript_url = f"{base_url}/lm"

    return manuscript_url


def fetch_manuscript(manuscript_url, episode_number):
    """
    Fetch manuscript content from the DW website using Playwright
    Returns the manuscript HTML content or None if not found
    """
    if not manuscript_url:
        return None

    print(f"  Fetching manuscript from {manuscript_url}...")

    try:
        with sync_playwright() as p:
            # Launch browser in headless mode
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Navigate to the manuscript page
            page.goto(manuscript_url, wait_until='networkidle', timeout=30000)

            # Wait for the page to load and JavaScript to render
            page.wait_for_timeout(2000)

            # Find the div containing "Manuskript"
            # Then find the next richtext-content-container div
            try:
                # Look for the section with Manuskript heading
                manuscript_section = page.locator('div.richtext-content-container').all()

                manuscript_html = None
                for section in manuscript_section:
                    # Get the HTML content
                    content = section.inner_html()
                    # Check if this section appears after "Manuskript" heading
                    # We'll take the content if it looks substantial
                    if content and len(content.strip()) > 100:
                        manuscript_html = content
                        break

                browser.close()

                if manuscript_html:
                    print(f"  ✓ Successfully fetched manuscript for episode {episode_number}")
                    return manuscript_html
                else:
                    print(f"  ✗ Manuscript content not found for episode {episode_number}")
                    return None

            except Exception as e:
                print(f"  ✗ Error finding manuscript content: {e}")
                browser.close()
                return None

    except Exception as e:
        print(f"  ✗ Error fetching manuscript: {e}")
        return None


def generate_episode_html(item, number, fetch_manuscripts=True):
    """Generate HTML for a single episode from XML item"""
    # Extract title
    title_text = get_element_text(item, 'title', 'Untitled')
    title = html.escape(title_text)

    # Extract and format date
    date_str = "Datum unbekannt"
    pub_date = get_element_text(item, 'pubDate', '')
    if pub_date:
        try:
            # Parse RFC 822 date format (e.g., "Mon, 15 Jan 2024 12:00:00 +0000")
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(pub_date)
            # Format to German date
            months_de = ['', 'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
                        'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
            date_str = f"{dt.day}. {months_de[dt.month]} {dt.year}"
        except:
            date_str = pub_date

    # Extract description/summary
    description_text = get_element_text(item, 'description',
                                       get_element_text(item, 'itunes:summary',
                                                       'Keine Beschreibung verfügbar.'))
    # Clean HTML tags from description
    description = strip_html_tags(description_text)
    description = html.escape(description)
    # Limit description length
    if len(description) > 300:
        description = description[:297] + "..."

    # Extract link
    link = get_element_text(item, 'link', '#')

    # Extract audio enclosure
    audio_link_html = ""
    enclosure = item.find('enclosure')
    if enclosure is not None:
        audio_url = enclosure.get('url', '')
        if audio_url:
            audio_link_html = f'                        <a href="{audio_url}" class="episode-link audio-link" target="_blank">🎵 Audio abspielen</a>'

    # Extract duration
    duration_html = ""
    duration = get_element_text(item, 'itunes:duration', '')
    if duration:
        formatted_duration = format_duration(duration)
        if formatted_duration:
            duration_html = f'                        <span class="duration">⏱️ {formatted_duration}</span>'

    # Fetch manuscript if enabled
    manuscript_button = ""
    manuscript_modal = ""
    if fetch_manuscripts:
        manuscript_url = get_manuscript_url(link)
        if manuscript_url:
            manuscript_content = fetch_manuscript(manuscript_url, number)
            if manuscript_content:
                # Create button
                manuscript_button = f'                        <button class="episode-link manuscript-link" onclick="showManuscript({number})">📄 Manuskript</button>'
                # Create modal
                manuscript_modal = MANUSCRIPT_MODAL_TEMPLATE.format(
                    number=number,
                    title=title,
                    manuscript_content=manuscript_content
                )

    return EPISODE_TEMPLATE.format(
        number=number,
        title=title,
        date=date_str,
        description=description,
        link=link,
        audio_link=audio_link_html,
        duration=duration_html,
        manuscript_button=manuscript_button,
        manuscript_modal=manuscript_modal
    )


def generate_html(items):
    """Generate complete HTML page from XML items"""
    episodes_html = []

    # Get the first MAX_EPISODES items
    items_to_process = items[:MAX_EPISODES]

    print("\nGenerating HTML for episodes...")
    for i, item in enumerate(items_to_process, 1):
        print(f"\nProcessing episode {i}...")
        # Only fetch manuscript for the first episode
        fetch_manuscripts = (i == 1)
        episode_html = generate_episode_html(item, i, fetch_manuscripts=fetch_manuscripts)
        episodes_html.append(episode_html)

    # Get current timestamp
    last_updated = datetime.now().strftime('%d.%m.%Y %H:%M:%S UTC')

    # Generate final HTML
    html_content = HTML_TEMPLATE.format(
        episodes="\n".join(episodes_html),
        rss_url=RSS_FEED_URL,
        last_updated=last_updated
    )

    return html_content


def main():
    """Main function"""
    try:
        # Parse feed
        items = parse_feed()

        # Generate HTML
        html_content = generate_html(items)

        # Write to file
        print(f"Writing HTML to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✓ Successfully generated {OUTPUT_FILE} with {min(len(items), MAX_EPISODES)} episodes")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
