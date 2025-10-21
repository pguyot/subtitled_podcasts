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
from mistralai import Mistral
import json
import time
import hashlib
import pickle

RSS_FEED_URL = "https://rss.dw.com/xml/DKpodcast_alltagsdeutsch_de"
OUTPUT_FILE = "index.html"
MANUSCRIPTS_DIR = "manuscripts"
CACHE_DIR = "mistral_cache"
MAX_EPISODES = 10

# Load environment variables from .env file if present
def load_env_file():
    """Load environment variables from .env file if it exists"""
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    # Only set if not already in environment
                    if key not in os.environ:
                        os.environ[key] = value

# Load .env file before reading environment variables
load_env_file()

# Mistral API configuration
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY')
MISTRAL_MODEL = "open-mistral-nemo-2407"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Subtitled Podcasts - Alltagsdeutsch</title>

    <!-- Skeleton CSS -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/normalize/8.0.1/normalize.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/skeleton/2.0.4/skeleton.min.css">

    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Helvetica Neue', sans-serif;
            background: #f2f2f7;
            max-width: 428px;
            margin: 0 auto;
            height: 100vh;
            overflow: hidden;
        }}

        /* iOS-style header */
        .app-header {{
            background: rgba(255, 255, 255, 0.8);
            backdrop-filter: blur(20px);
            border-bottom: 0.5px solid rgba(0, 0, 0, 0.1);
            padding: 1rem;
            position: fixed;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 100%;
            max-width: 428px;
            z-index: 100;
        }}

        .app-header h1 {{
            font-size: 1.5rem;
            font-weight: 700;
            text-align: center;
            margin: 0;
        }}

        .back-button {{
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            background: none;
            border: none;
            color: #007AFF;
            font-size: 1rem;
            cursor: pointer;
            display: none;
        }}

        /* Episode list view */
        .episodes-view {{
            margin-top: 60px;
            overflow-y: auto;
            height: calc(100vh - 60px);
            -webkit-overflow-scrolling: touch;
        }}

        .episode-card {{
            background: white;
            margin: 10px;
            border-radius: 10px;
            padding: 1rem;
            cursor: pointer;
            transition: transform 0.2s;
        }}

        .episode-card:active {{
            transform: scale(0.98);
        }}

        .episode-header {{
            display: flex;
            align-items: center;
            margin-bottom: 0.5rem;
        }}

        .episode-number {{
            background: #007AFF;
            color: white;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            margin-right: 0.5rem;
        }}

        .episode-date {{
            color: #8e8e93;
            font-size: 0.75rem;
        }}

        .episode-title {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #000;
        }}

        .episode-description {{
            color: #8e8e93;
            font-size: 0.9rem;
            line-height: 1.4;
        }}

        .chevron {{
            float: right;
            color: #c7c7cc;
            font-size: 1.2rem;
        }}

        /* Episode detail view */
        .episode-detail {{
            display: none;
            margin-top: 60px;
            height: calc(100vh - 60px);
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
            background: white;
        }}

        .episode-detail.active {{
            display: block;
        }}

        .detail-content {{
            padding: 1.5rem;
        }}

        .detail-title {{
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}

        .detail-meta {{
            color: #8e8e93;
            font-size: 0.9rem;
            margin-bottom: 1.5rem;
        }}

        .audio-player {{
            background: #f2f2f7;
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 1.5rem;
        }}

        .audio-player audio {{
            width: 100%;
        }}

        /* Transcript section */
        .transcript-section {{
            border-top: 0.5px solid #c6c6c8;
            padding-top: 1rem;
        }}

        .transcript-toggle {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            margin: 0 -1.5rem;
            background: white;
            border: none;
            width: calc(100% + 3rem);
            cursor: pointer;
            font-size: 1rem;
            font-weight: 600;
        }}

        .transcript-toggle:active {{
            background: #f2f2f7;
        }}

        .transcript-content {{
            display: none;
            padding: 1rem 0;
            line-height: 1.6;
        }}

        .transcript-content.visible {{
            display: block;
        }}

        .toggle-icon {{
            color: #8e8e93;
            transition: transform 0.3s;
        }}

        .toggle-icon.rotated {{
            transform: rotate(180deg);
        }}

        footer {{
            display: none;
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
            background-color: rgba(0, 0, 0, 0.6);
        }}

        .modal-content {{
            background-color: #fefefe;
            margin: 3% auto;
            width: 90%;
            max-width: 900px;
            border-radius: 4px;
            max-height: 90vh;
            display: flex;
            flex-direction: column;
        }}

        .modal-header {{
            padding: 1.5rem;
            border-bottom: 1px solid #e1e1e1;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .modal-header h2 {{
            margin: 0;
        }}

        .close {{
            font-size: 2rem;
            font-weight: bold;
            cursor: pointer;
            background: none;
            border: none;
            color: #999;
        }}

        .close:hover {{
            color: #333;
        }}

        .modal-body {{
            padding: 2rem;
            overflow-y: auto;
            flex: 1;
            position: relative;
        }}

        .modal-body p {{
            line-height: 1.8;
            margin-bottom: 1rem;
        }}

        /* Clickable word styles */
        .word {{
            cursor: pointer;
            padding: 2px 0;
            border-bottom: 1px dotted #33C3F0;
            display: inline-block;
            transition: all 0.2s ease;
        }}

        .word:hover {{
            background-color: #f0f8ff;
            border-bottom: 2px solid #33C3F0;
        }}

        /* Translation popup */
        .translation-popup {{
            display: none;
            position: absolute;
            background: white;
            border: 1px solid #e1e1e1;
            border-radius: 4px;
            padding: 1rem;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            z-index: 10001;
            max-width: 350px;
            min-width: 250px;
        }}

        .translation-popup.visible {{
            display: block;
        }}

        .translation-popup .word-header {{
            font-size: 1.2rem;
            font-weight: bold;
            color: #333;
            margin-bottom: 0.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #e1e1e1;
        }}

        .translation-popup .grammar-info {{
            color: #999;
            font-size: 0.85rem;
            font-style: italic;
            margin-bottom: 0.5rem;
        }}

        .translation-popup .translation {{
            color: #555;
            font-size: 1rem;
            line-height: 1.5;
            margin-top: 0.5rem;
        }}

        .translation-popup .close-popup {{
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            cursor: pointer;
            font-size: 1.5rem;
            color: #999;
            background: none;
            border: none;
        }}

        .translation-popup .close-popup:hover {{
            color: #333;
        }}

        @media (max-width: 768px) {{
            .modal-content {{
                width: 95%;
                margin: 10% auto;
                max-height: 80vh;
            }}

            .modal-body {{
                padding: 1.5rem;
            }}
        }}
    </style>
    <script>
        // Word translation data
        const wordTranslations = {word_translations_data};

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
            // Close translation popup if clicking outside
            const popup = document.getElementById('translation-popup');
            if (popup && !event.target.classList.contains('word') && !popup.contains(event.target)) {{
                popup.classList.remove('visible');
            }}
        }}

        // Close modal on Escape key
        document.addEventListener('keydown', function(event) {{
            if (event.key === 'Escape') {{
                const modals = document.querySelectorAll('.modal');
                modals.forEach(modal => modal.style.display = 'none');
                const popup = document.getElementById('translation-popup');
                if (popup) {{
                    popup.classList.remove('visible');
                }}
            }}
        }});

        // Add click handlers to all word spans
        document.addEventListener('DOMContentLoaded', function() {{
            document.querySelectorAll('.word').forEach(function(wordSpan) {{
                wordSpan.addEventListener('click', function(event) {{
                    showTranslation(event);
                }});
            }});
        }});

        function showTranslation(event) {{
            event.stopPropagation();

            const wordId = event.target.getAttribute('data-word-id');
            if (!wordId) return;

            const wordData = wordTranslations[wordId];
            if (!wordData) return;

            // Find the transcript content container
            const transcriptContent = event.target.closest('.transcript-content');
            if (!transcriptContent) return;

            // Make transcript content position relative for popup positioning
            transcriptContent.style.position = 'relative';

            let popup = document.getElementById('translation-popup');
            if (!popup) {{
                popup = document.createElement('div');
                popup.id = 'translation-popup';
                popup.className = 'translation-popup';
                transcriptContent.appendChild(popup);
            }} else if (popup.parentElement !== transcriptContent) {{
                // Move popup to correct transcript if it's in a different one
                transcriptContent.appendChild(popup);
            }}

            popup.innerHTML = `
                <button class="close-popup" onclick="closeTranslationPopup()">&times;</button>
                <div class="word-header">${{wordData.word}}</div>
                <div class="grammar-info">${{wordData.grammar}}</div>
                <div class="translation">${{wordData.translation}}</div>
            `;

            // Position the popup near the clicked word relative to transcript-content
            const wordRect = event.target.getBoundingClientRect();
            const containerRect = transcriptContent.getBoundingClientRect();

            const popupWidth = 300;
            const popupHeight = 150;

            // Calculate position relative to transcript-content
            let left = wordRect.left - containerRect.left;
            let top = wordRect.bottom - containerRect.top + transcriptContent.scrollTop + 5;

            // Adjust if popup goes off the container's right edge
            if (left + popupWidth > transcriptContent.clientWidth) {{
                left = transcriptContent.clientWidth - popupWidth - 10;
            }}

            // Adjust if popup goes off the container's bottom edge
            if (top + popupHeight > transcriptContent.scrollTop + transcriptContent.clientHeight) {{
                top = wordRect.top - containerRect.top + transcriptContent.scrollTop - popupHeight - 5;
            }}

            // Ensure popup doesn't go off the left edge
            if (left < 0) {{
                left = 10;
            }}

            popup.style.left = left + 'px';
            popup.style.top = top + 'px';
            popup.classList.add('visible');
        }}

        function closeTranslationPopup() {{
            const popup = document.getElementById('translation-popup');
            if (popup) {{
                popup.classList.remove('visible');
            }}
        }}

        // iOS-style navigation
        function showEpisodeDetail(episodeNumber) {{
            // Hide episodes list
            document.getElementById('episodesView').style.display = 'none';

            // Hide all episode details
            document.querySelectorAll('.episode-detail').forEach(detail => {{
                detail.classList.remove('active');
            }});

            // Show selected episode detail
            const detailView = document.getElementById('episode-detail-' + episodeNumber);
            if (detailView) {{
                detailView.classList.add('active');
            }}

            // Show back button
            document.getElementById('backButton').style.display = 'block';

            // Update header title
            document.getElementById('headerTitle').textContent = 'Episode ' + episodeNumber;
        }}

        function showEpisodesList() {{
            // Hide all episode details
            document.querySelectorAll('.episode-detail').forEach(detail => {{
                detail.classList.remove('active');
            }});

            // Show episodes list
            document.getElementById('episodesView').style.display = 'block';

            // Hide back button
            document.getElementById('backButton').style.display = 'none';

            // Reset header title
            document.getElementById('headerTitle').textContent = 'Alltagsdeutsch';
        }}

        function toggleTranscript(episodeNumber) {{
            const content = document.getElementById('transcript-' + episodeNumber);
            const icon = document.getElementById('toggle-icon-' + episodeNumber);

            if (content.classList.contains('visible')) {{
                content.classList.remove('visible');
                icon.classList.remove('rotated');
            }} else {{
                content.classList.add('visible');
                icon.classList.add('rotated');
            }}
        }}
    </script>
</head>
<body>
    <!-- iOS-style App Header -->
    <div class="app-header">
        <button class="back-button" onclick="showEpisodesList()" id="backButton">‹ Zurück</button>
        <h1 id="headerTitle">Alltagsdeutsch</h1>
    </div>

    <!-- Episodes List View -->
    <div class="episodes-view" id="episodesView">
{episodes}
    </div>

    <!-- Episode Details (one for each episode) -->
{episode_details}

    <footer>
        <p>Quelle: DW Deutsch lernen - Alltagsdeutsch</p>
    </footer>
</body>
</html>
"""

EPISODE_CARD_TEMPLATE = """        <div class="episode-card" onclick="showEpisodeDetail({number})">
            {illustration}
            <div class="episode-header">
                <span class="episode-number">{number}</span>
                <span class="episode-date">{date}</span>
                <span class="chevron">›</span>
            </div>
            <h3 class="episode-title">{title}</h3>
            <p class="episode-description">{description}</p>
        </div>
"""

EPISODE_DETAIL_TEMPLATE = """    <div class="episode-detail" id="episode-detail-{number}">
        <div class="detail-content">
            {illustration}
            <h2 class="detail-title">{title}</h2>
            <p class="detail-meta">{date}{duration}</p>

            <div class="audio-player">
                <audio controls preload="metadata">
                    <source src="{audio_url}" type="audio/mpeg">
                    Ihr Browser unterstützt das Audio-Element nicht.
                </audio>
            </div>

            <div class="episode-description" style="margin-bottom: 1.5rem;">
                {description}
            </div>

            {transcript_section}
        </div>
    </div>
"""

TRANSCRIPT_SECTION_TEMPLATE = """            <div class="transcript-section">
                <button class="transcript-toggle" onclick="toggleTranscript({number})">
                    <span>Manuskript</span>
                    <span class="toggle-icon" id="toggle-icon-{number}">▼</span>
                </button>
                <div class="transcript-content" id="transcript-{number}">
                    {manuscript_content}
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


def get_cache_key(prompt):
    """Generate MD5 hash for cache key"""
    return hashlib.md5(prompt.encode('utf-8')).hexdigest()


def get_from_cache(cache_key):
    """Retrieve result from cache if it exists"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"  ⚠ Error loading cache: {e}")
            return None
    return None


def save_to_cache(cache_key, result):
    """Save result to cache"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(result, f)
    except Exception as e:
        print(f"  ⚠ Error saving cache: {e}")


def translate_paragraph_with_mistral(paragraph_text, context="", max_retries=3):
    """
    Translate difficult words in a paragraph and return HTML with clickable spans
    Returns a tuple: (html_with_spans, word_translations_list)
    """
    if not MISTRAL_API_KEY:
        return paragraph_text, []

    # Extract words while preserving order
    words = re.findall(r'\b\w+\b', paragraph_text)
    if not words:
        return paragraph_text, []

    # Calculate how many difficult words to translate (1/3 of total)
    num_difficult_words = max(1, len(words) // 3)

    client = Mistral(api_key=MISTRAL_API_KEY)

    # Prepare the prompt - simpler approach, just get the words to translate
    prompt = f"""Tu es un assistant de traduction allemand-français spécialisé dans l'analyse grammaticale.

Contexte global : {context if context else "Texte général en allemand"}

Texte à analyser (paragraphe) :
{paragraph_text}

TÂCHE:
Identifie les {num_difficult_words} mots les plus DIFFICILES pour un apprenant de l'allemand (vocabulaire avancé, structures grammaticales complexes, expressions idiomatiques) et fournis pour chacun:
- Le mot exact tel qu'il apparaît dans le texte
- Ses informations grammaticales
- Sa traduction française en contexte

Format de réponse JSON OBLIGATOIRE :
{{
  "translations": [
    {{"word": "mot_exact_1", "grammar": "informations grammaticales", "translation": "traduction en contexte"}},
    {{"word": "mot_exact_2", "grammar": "informations grammaticales", "translation": "traduction en contexte"}}
  ]
}}

RÈGLES:
- Sélectionne EXACTEMENT {num_difficult_words} mots les plus difficiles
- Le champ "word" doit contenir le mot EXACT du texte (même capitalisation)
- Évite les mots faciles (der, die, das, und, aber, ist, hat, etc.)"""

    # Check cache first
    cache_key = get_cache_key(prompt)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        print(f"    ✓ Using cached translation")
        html_with_spans = wrap_words_in_spans(paragraph_text, cached_result)
        return html_with_spans, cached_result

    for attempt in range(max_retries):
        try:
            response = client.chat.complete(
                model=MISTRAL_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
                timeout_ms=60000
            )

            result = json.loads(response.choices[0].message.content)

            if "translations" in result and isinstance(result["translations"], list) and len(result["translations"]) > 0:
                # Save to cache
                save_to_cache(cache_key, result["translations"])

                # Wrap difficult words in spans
                html_with_spans = wrap_words_in_spans(paragraph_text, result["translations"])
                return html_with_spans, result["translations"]
            else:
                print(f"  ⚠ Invalid response format (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2)
                continue

        except Exception as e:
            print(f"  ⚠ Error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                return paragraph_text, []

    return paragraph_text, []


def wrap_words_in_spans(text, translations):
    """
    Wrap words from translations list in span tags
    """
    # Build a list of words to wrap with their translation index
    # Handle duplicate words by tracking which occurrence we're on
    words_to_wrap = {}
    for i, t in enumerate(translations):
        word = t["word"]
        if word not in words_to_wrap:
            words_to_wrap[word] = []
        words_to_wrap[word].append(i)

    # Track which occurrence of each word we've seen
    word_occurrence_counter = {}

    # Split text into parts while preserving everything
    result_parts = []
    current_pos = 0

    # Find all word boundaries
    for match in re.finditer(r'\b(\w+)\b', text):
        word = match.group(0)
        start = match.start()
        end = match.end()

        # Add text before this word
        if start > current_pos:
            result_parts.append(text[current_pos:start])

        # Check if this word should be wrapped
        if word in words_to_wrap:
            # Track which occurrence of this word we're on
            if word not in word_occurrence_counter:
                word_occurrence_counter[word] = 0

            # Get the translation index for this occurrence
            occurrence_idx = word_occurrence_counter[word]
            if occurrence_idx < len(words_to_wrap[word]):
                translation_idx = words_to_wrap[word][occurrence_idx]
                result_parts.append(f'<span class=\'word\' data-word-id=\'{translation_idx}\'>{word}</span>')
                word_occurrence_counter[word] += 1
            else:
                # More occurrences in text than in translations list
                result_parts.append(word)
        else:
            result_parts.append(word)

        current_pos = end

    # Add remaining text
    if current_pos < len(text):
        result_parts.append(text[current_pos:])

    return ''.join(result_parts)


def translate_words_with_mistral(text, context="", episode_id="unknown"):
    """
    Translate difficult German words to French with grammatical information using Mistral API
    Processes text paragraph by paragraph and returns HTML with clickable spans
    Returns a tuple: (html_with_clickable_words, word_translations_dict)
    """
    if not MISTRAL_API_KEY:
        print("  ⚠ Warning: MISTRAL_API_KEY not set. Skipping translations.")
        return text, {}

    # Extract paragraphs from HTML while preserving structure
    # Split by common paragraph tags
    parts = re.split(r'(<p>|</p>|<br\s*/?>|<strong>|</strong>)', text, flags=re.IGNORECASE)

    if not parts:
        return text, {}

    # Get clean text for counting
    clean_text = strip_html_tags(text)
    total_words = len(re.findall(r'\b\w+\b', clean_text))

    # Extract actual paragraphs (non-tag parts with content)
    paragraphs = [p.strip() for p in parts if p.strip() and not re.match(r'^<', p)]

    print(f"  Translating difficult words from {total_words} total words across {len(paragraphs)} paragraphs using Mistral API...")

    all_word_translations = {}
    word_id_counter = 0
    result_parts = []

    for i, part in enumerate(parts):
        # If it's an HTML tag or empty, keep as-is
        if not part.strip() or re.match(r'^<', part):
            result_parts.append(part)
            continue

        para_num = sum(1 for p in parts[:i] if p.strip() and not re.match(r'^<', p)) + 1
        print(f"    Processing paragraph {para_num}/{len(paragraphs)}...")

        # Get HTML with spans and translations for this paragraph
        html_with_spans, translations = translate_paragraph_with_mistral(part, context)

        # Update word IDs to be unique per episode using DW lesson ID
        if translations:
            for translation in translations:
                old_id = str(translations.index(translation))
                # Use DW lesson ID for word ID prefix
                new_id = f"l{episode_id}_w{word_id_counter}"

                # Replace data-word-id in HTML
                html_with_spans = html_with_spans.replace(f"data-word-id='{old_id}'", f"data-word-id='{new_id}'")
                html_with_spans = html_with_spans.replace(f'data-word-id="{old_id}"', f'data-word-id="{new_id}"')

                # Store translation with new ID
                all_word_translations[new_id] = {
                    "word": translation.get("word", ""),
                    "grammar": translation.get("grammar", ""),
                    "translation": translation.get("translation", "")
                }
                word_id_counter += 1

        result_parts.append(html_with_spans)

    final_html = ''.join(result_parts)
    print(f"  ✓ Successfully translated {len(all_word_translations)} difficult words")
    return final_html, all_word_translations


def make_words_clickable(html_content, word_translations):
    """
    Process HTML content to make each word clickable
    Returns modified HTML with clickable words
    """
    if not word_translations:
        return html_content

    word_index = 0

    def replace_text_content(text):
        """Replace words in plain text (not in HTML tags)"""
        nonlocal word_index

        # Split text into words while preserving whitespace and punctuation
        parts = re.split(r'(\s+)', text)
        result_parts = []

        for part in parts:
            # Check if this part is whitespace
            if re.match(r'^\s+$', part):
                result_parts.append(part)
                continue

            # Extract words from this part (may have punctuation)
            # Match word + optional punctuation
            word_match = re.match(r'^(\w+)([\W]*)$', part)
            if word_match:
                word = word_match.group(1)
                punct = word_match.group(2)

                # Check if we have a translation for this word
                if f"word_{word_index}" in word_translations:
                    word_id = f"word_{word_index}"
                    result_parts.append(f'<span class="word" onclick="showTranslation(\'{word_id}\', event)">{word}</span>{punct}')
                    word_index += 1
                else:
                    result_parts.append(part)
            else:
                result_parts.append(part)

        return ''.join(result_parts)

    # Process HTML content - split by tags and process only text between tags
    # This regex splits on HTML tags while keeping the tags
    parts = re.split(r'(<[^>]+>)', html_content)

    result = []
    for part in parts:
        # If it's an HTML tag, keep it as-is
        if part.startswith('<') and part.endswith('>'):
            result.append(part)
        else:
            # It's text content - make words clickable
            result.append(replace_text_content(part))

    return ''.join(result)


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


def get_episode_id(episode_link):
    """
    Extract DW lesson ID from episode link
    Example: https://learngerman.dw.com/de/sportler-im-abseits/l-19262668?maca=...
    Returns: 19262668
    """
    if not episode_link or episode_link == '#':
        return None

    # Extract the lesson ID (format: l-XXXXXXXX)
    import re
    match = re.search(r'/l-(\d+)', episode_link)
    if match:
        return match.group(1)
    return None


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
    Fetch manuscript content and illustration URL from the DW website using Playwright
    Returns a tuple: (manuscript_html, illustration_url) or (None, None) if not found
    """
    if not manuscript_url:
        return None, None

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

                # Fetch illustration URL - look for the poster-container with background-image
                illustration_url = None
                try:
                    # Look for the poster-container div with background-image
                    poster_container = page.locator('[data-testid="poster-container"]').first
                    if poster_container:
                        style = poster_container.get_attribute('style')
                        if style:
                            # Extract URL from background-image: url("...")
                            import re
                            match = re.search(r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style)
                            if match:
                                illustration_url = match.group(1)
                                # Make sure it's an absolute URL
                                if illustration_url.startswith('//'):
                                    illustration_url = 'https:' + illustration_url
                                elif illustration_url.startswith('/'):
                                    illustration_url = 'https://learngerman.dw.com' + illustration_url

                    if illustration_url:
                        print(f"  ✓ Found illustration: {illustration_url}")
                except Exception as e:
                    print(f"  ⚠ Could not fetch illustration: {e}")

                browser.close()

                if manuscript_html:
                    print(f"  ✓ Successfully fetched manuscript for episode {episode_number}")
                    return manuscript_html, illustration_url
                else:
                    print(f"  ✗ Manuscript content not found for episode {episode_number}")
                    return None, None

            except Exception as e:
                print(f"  ✗ Error finding manuscript content: {e}")
                browser.close()
                return None, None

    except Exception as e:
        print(f"  ✗ Error fetching manuscript: {e}")
        return None, None


def generate_episode_html(item, number, fetch_manuscripts=True, word_translations_dict=None):
    """
    Generate HTML for a single episode from XML item
    Returns a tuple: (episode_card_html, episode_detail_html)
    """
    if word_translations_dict is None:
        word_translations_dict = {}

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

    # Keep full description for detail view, but limit for card view
    description_short = description
    if len(description) > 150:
        description_short = description[:147] + "..."

    # Extract link
    link = get_element_text(item, 'link', '#')

    # Extract audio enclosure
    audio_url = ""
    enclosure = item.find('enclosure')
    if enclosure is not None:
        audio_url = enclosure.get('url', '')

    # Extract duration
    duration_html = ""
    duration = get_element_text(item, 'itunes:duration', '')
    if duration:
        formatted_duration = format_duration(duration)
        if formatted_duration:
            duration_html = f' • {formatted_duration}'

    # Fetch manuscript if enabled
    transcript_section = ""
    illustration_html = ""
    illustration_card_html = ""
    if fetch_manuscripts:
        manuscript_url = get_manuscript_url(link)
        if manuscript_url:
            manuscript_content, illustration_url = fetch_manuscript(manuscript_url, number)
            if manuscript_content:
                # Extract DW lesson ID from the episode link
                episode_id = get_episode_id(link) or str(number)  # fallback to number if ID not found

                # Translate difficult words in the manuscript and get HTML with clickable spans
                manuscript_content, word_translations = translate_words_with_mistral(manuscript_content, context=title_text, episode_id=episode_id)

                # Store translations for this episode
                if word_translations:
                    word_translations_dict[f"episode_{number}"] = word_translations

                # Generate transcript section
                transcript_section = TRANSCRIPT_SECTION_TEMPLATE.format(
                    number=number,
                    manuscript_content=manuscript_content
                )

            # Generate illustration HTML if URL was found
            if illustration_url:
                # Full size for detail view
                illustration_html = f'<img src="{illustration_url}" alt="{title}" class="episode-illustration" style="width: 100%; border-radius: 10px; margin-bottom: 1.5rem;">'
                # Smaller version for card view
                illustration_card_html = f'<img src="{illustration_url}" alt="{title}" class="episode-illustration-card" style="width: 100%; border-radius: 8px; margin-bottom: 0.75rem;">'

    # Generate episode card (for list view)
    episode_card = EPISODE_CARD_TEMPLATE.format(
        number=number,
        date=date_str,
        title=title,
        description=description_short,
        illustration=illustration_card_html
    )

    # Generate episode detail (for detail view)
    episode_detail = EPISODE_DETAIL_TEMPLATE.format(
        number=number,
        title=title,
        date=date_str,
        duration=duration_html,
        audio_url=audio_url if audio_url else "",
        description=description,
        illustration=illustration_html,
        transcript_section=transcript_section
    )

    return episode_card, episode_detail


def generate_html(items):
    """Generate complete HTML page from XML items"""
    episode_cards = []
    episode_details = []
    all_word_translations = {}

    # Get the first MAX_EPISODES items
    items_to_process = items[:MAX_EPISODES]

    print("\nGenerating HTML for episodes...")
    for i, item in enumerate(items_to_process, 1):
        print(f"\nProcessing episode {i}...")
        # Fetch manuscript for all episodes
        fetch_manuscripts = True
        episode_card, episode_detail = generate_episode_html(
            item, i,
            fetch_manuscripts=fetch_manuscripts,
            word_translations_dict=all_word_translations
        )
        episode_cards.append(episode_card)
        episode_details.append(episode_detail)

    # Merge all word translations into a single dictionary
    merged_translations = {}
    for episode_key, translations in all_word_translations.items():
        merged_translations.update(translations)

    # Convert translations to JSON
    word_translations_json = json.dumps(merged_translations, ensure_ascii=False)

    # Generate final HTML
    html_content = HTML_TEMPLATE.format(
        episodes="\n".join(episode_cards),
        episode_details="\n".join(episode_details),
        word_translations_data=word_translations_json
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
