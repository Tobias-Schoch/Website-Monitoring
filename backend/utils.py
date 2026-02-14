"""Utility functions for HTML normalization and processing."""
import re
import hashlib
import logging
from typing import Tuple, List, Dict, Set


def clean_html(html: str, aggressive: bool = True) -> str:
    """
    Clean HTML content with configurable aggressiveness.

    Args:
        html: Raw HTML string
        aggressive: If True, removes all attributes and normalizes heavily.
                   If False, does light cleaning for diff display.

    Returns:
        Cleaned HTML string
    """
    if not html:
        return ""

    if not aggressive:
        # Light cleaning for diff display - keeps more content visible
        # Extract body only
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body_match:
            html = body_match.group(1)

        # Remove script tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Remove style tags
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

        # Normalize whitespace a bit (but keep structure)
        html = re.sub(r'\n\s*\n', '\n', html)

        return html.strip()

    # Aggressive cleaning (original clean_html_for_diff behavior)
    return clean_html_for_diff(html)


def clean_html_for_diff(html: str) -> str:
    """
    Clean HTML for diff comparison by removing noise elements.

    Removes:
    - <head> section entirely
    - <style> tags and content
    - <link> tags
    - <script> tags and content
    - CCM19 cookie consent manager elements
    - HTML comments
    - Empty/dynamic attributes
    - Excessive whitespace
    """
    if not html:
        return ""

    # Remove entire <head> section
    html = re.sub(r'<head[^>]*>.*?</head>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove script tags and their content
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove style tags and their content
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove ALL link tags (stylesheets, preload, prefetch, etc.)
    html = re.sub(r'<link\s[^>]*>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<link\s*/>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<link>', '', html, flags=re.IGNORECASE)
    # Also catch malformed/partial link tags
    html = re.sub(r'link\s+rel="[^"]*"[^>]*>', '', html, flags=re.IGNORECASE)

    # Remove noscript tags and their content
    html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove CCM19 cookie consent elements - be very aggressive
    # Remove ANY element with ccm anywhere in class, id, or href
    html = re.sub(r'<[^>]*ccm[^>]*>.*?</[^>]+>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<[^>]*ccm[^>]*/?\s*>', '', html, flags=re.IGNORECASE)
    # Remove ccm URLs
    html = re.sub(r'https?://[^"\'>\s]*ccm[^"\'>\s]*', '', html, flags=re.IGNORECASE)
    # Remove data-ccm attributes
    html = re.sub(r'\s+data-ccm[a-z0-9-]*="[^"]*"', '', html, flags=re.IGNORECASE)
    # Remove ccm script/config blocks
    html = re.sub(r'CCM19\s*[=:]\s*\{[^}]*\}', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'window\.CCM19[^;]*;', '', html, flags=re.IGNORECASE)

    # Remove HTML comments
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

    # Remove meta tags
    html = re.sub(r'<meta[^>]*/?>', '', html, flags=re.IGNORECASE)

    # Remove ALL style attributes (often change dynamically)
    html = re.sub(r'\s+style="[^"]*"', '', html, flags=re.IGNORECASE)

    # Remove ALL class attributes (CSS classes change dynamically)
    html = re.sub(r'\s+class="[^"]*"', '', html, flags=re.IGNORECASE)

    # Remove id attributes (often dynamic)
    html = re.sub(r'\s+id="[^"]*"', '', html, flags=re.IGNORECASE)

    # Remove data-* attributes (often dynamic)
    html = re.sub(r'\s+data-[a-z0-9-]+="[^"]*"', '', html, flags=re.IGNORECASE)

    # Remove other common dynamic attributes
    html = re.sub(r'\s+crossorigin="[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\s+rel="[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\s+aria-[a-z-]+="[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\s+role="[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\s+tabindex="[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\s+onclick="[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\s+onload="[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\s+target="[^"]*"', '', html, flags=re.IGNORECASE)

    # Normalize whitespace (collapse multiple spaces/newlines)
    html = re.sub(r'\s+', ' ', html)

    # Trim
    html = html.strip()

    return html


def normalize_html(html: str) -> str:
    """
    Normalize HTML to reduce false positives in change detection.

    Uses the same aggressive cleaning as clean_html_for_diff, plus
    additional normalization for timestamps/UUIDs.
    """
    if not html:
        return ""

    # First, apply aggressive cleaning to remove noise
    html = clean_html_for_diff(html)

    # Then normalize dynamic content that might still be present

    # Remove common timestamp patterns
    # ISO 8601: 2024-01-15T12:34:56Z
    html = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?', 'TIMESTAMP', html)

    # Date patterns: 15.01.2024, 01/15/2024, etc.
    html = re.sub(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', 'DATE', html)

    # Time patterns: 12:34:56, 12:34
    html = re.sub(r'\d{1,2}:\d{2}(:\d{2})?', 'TIME', html)

    # Remove UUIDs (8-4-4-4-12 format)
    html = re.sub(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        'UUID',
        html,
        flags=re.IGNORECASE
    )

    # Remove session IDs and tokens (common patterns)
    html = re.sub(r'\b[A-Za-z0-9]{32,}\b', 'TOKEN', html)

    # Normalize whitespace again after replacements
    html = re.sub(r'\s+', ' ', html)
    html = html.strip()

    return html


def calculate_hash(content: str) -> str:
    """Calculate SHA-256 hash of content."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def extract_body_text(html: str) -> str:
    """Extract visible text from HTML (strip all tags)."""
    # Remove script and style first
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove all HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def process_html(html: str) -> Tuple[str, str]:
    """
    Process HTML for storage and comparison.

    Returns:
        Tuple of (normalized_html, hash)
    """
    normalized = normalize_html(html)
    html_hash = calculate_hash(normalized)
    return normalized, html_hash


logger = logging.getLogger(__name__)


def extract_semantic_content(html: str) -> Dict[str, List]:
    """
    Extract semantic content from HTML (text, images, links).

    Returns:
        Dict with keys: 'texts', 'images', 'links'
    """
    if not html:
        return {'texts': [], 'images': [], 'links': []}

    try:
        from bs4 import BeautifulSoup

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')

        # Remove script, style, noscript tags
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()

        # Extract text content
        texts = []
        for text in soup.stripped_strings:
            text = text.strip()
            if text and len(text) > 0:
                texts.append(text)

        # Extract images
        images = []
        for img in soup.find_all('img'):
            src = img.get('src', '')
            alt = img.get('alt', '')
            if src:
                images.append({'src': src, 'alt': alt})

        # Extract links
        links = []
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if href:
                links.append({'href': href})

        return {
            'texts': texts,
            'images': images,
            'links': links
        }

    except Exception as e:
        logger.error(f"Error extracting semantic content: {e}")
        return {'texts': [], 'images': [], 'links': []}


def compare_semantic_content(
    previous: Dict[str, List],
    current: Dict[str, List]
) -> Dict[str, any]:
    """
    Compare semantic content and return differences.

    Returns:
        Dict with keys:
        - has_text_changes, has_image_changes, has_link_changes (bool)
        - changed_texts, changed_images, changed_links (lists)
    """
    # Compare texts
    prev_text_set = set(previous.get('texts', []))
    curr_text_set = set(current.get('texts', []))
    changed_texts = []

    # New/changed texts
    for text in curr_text_set:
        if text not in prev_text_set:
            changed_texts.append(text)

    # Removed texts
    for text in prev_text_set:
        if text not in curr_text_set:
            changed_texts.append(f"[REMOVED] {text}")

    has_text_changes = len(changed_texts) > 0

    # Compare images (by src)
    prev_image_srcs = {img['src'] for img in previous.get('images', [])}
    curr_image_srcs = {img['src'] for img in current.get('images', [])}
    changed_images = []

    # New images
    for img in current.get('images', []):
        if img['src'] not in prev_image_srcs:
            changed_images.append(img)

    # Removed images
    for img in previous.get('images', []):
        if img['src'] not in curr_image_srcs:
            changed_images.append({'src': f"[REMOVED] {img['src']}", 'alt': img['alt']})

    has_image_changes = len(changed_images) > 0

    # Compare links (by href)
    prev_link_hrefs = {link['href'] for link in previous.get('links', [])}
    curr_link_hrefs = {link['href'] for link in current.get('links', [])}
    changed_links = []

    # New links
    for link in current.get('links', []):
        if link['href'] not in prev_link_hrefs:
            changed_links.append(link)

    # Removed links
    for link in previous.get('links', []):
        if link['href'] not in curr_link_hrefs:
            changed_links.append({'href': f"[REMOVED] {link['href']}"})

    has_link_changes = len(changed_links) > 0

    return {
        'has_text_changes': has_text_changes,
        'has_image_changes': has_image_changes,
        'has_link_changes': has_link_changes,
        'changed_texts': changed_texts,
        'changed_images': changed_images,
        'changed_links': changed_links
    }


def generate_semantic_diff(diff: Dict[str, any], max_items: int = 5) -> str:
    """
    Generate human-readable diff from semantic comparison.

    Args:
        diff: Result from compare_semantic_content()
        max_items: Max items to show per category

    Returns:
        Formatted string with changes
    """
    lines = []

    if diff['has_text_changes'] and diff['changed_texts']:
        lines.append('Text Changes:')
        for text in diff['changed_texts'][:max_items]:
            # Truncate long texts
            display_text = text[:100] + '...' if len(text) > 100 else text
            lines.append(f"  - {display_text}")
        if len(diff['changed_texts']) > max_items:
            lines.append(f"  ... and {len(diff['changed_texts']) - max_items} more")
        lines.append('')

    if diff['has_image_changes'] and diff['changed_images']:
        lines.append('Image Changes:')
        for img in diff['changed_images'][:max_items]:
            lines.append(f"  - {img['src']} (alt: {img['alt']})")
        if len(diff['changed_images']) > max_items:
            lines.append(f"  ... and {len(diff['changed_images']) - max_items} more")
        lines.append('')

    if diff['has_link_changes'] and diff['changed_links']:
        lines.append('Link Changes:')
        for link in diff['changed_links'][:max_items]:
            lines.append(f"  - {link['href']}")
        if len(diff['changed_links']) > max_items:
            lines.append(f"  ... and {len(diff['changed_links']) - max_items} more")
        lines.append('')

    return '\n'.join(lines)


def generate_change_description(diff: Dict[str, any]) -> str:
    """
    Generate short description of changes.

    Args:
        diff: Result from compare_semantic_content()

    Returns:
        Short description like "Page text, images updated"
    """
    changes = []

    if diff['has_text_changes']:
        changes.append('text content')
    if diff['has_image_changes']:
        changes.append('images')
    if diff['has_link_changes']:
        changes.append('links')

    if not changes:
        return 'No significant changes detected'

    return f"Page {', '.join(changes)} updated"
