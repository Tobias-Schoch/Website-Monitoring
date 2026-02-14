"""Change detection logic ported from TypeScript change-detector.ts."""
import logging
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from diff_match_patch import diff_match_patch

from backend.database import ChangeType, Priority
from backend.utils import (
    clean_html,
    extract_semantic_content,
    compare_semantic_content,
    generate_semantic_diff,
    generate_change_description
)
from backend.config import settings


logger = logging.getLogger(__name__)


# Keywords from original TypeScript implementation
CRITICAL_KEYWORDS = [
    'warteliste',
    'anmeldung',
    'registrierung',
    'bewerbung',
    'antrag',
    'formular',
    'bewerben',
    'jetzt anmelden',
    'freie plätze',
    '< 50 personen',
    'verfügbar',
    'öffnung',
    'geöffnet'
]

IMPORTANT_KEYWORDS = [
    'aktualisiert',
    'neu',
    'änderung',
    'information',
    'termin',
    'frist',
    'deadline'
]


@dataclass
class FormDetectionResult:
    """Result of form detection."""
    detected: bool
    form_type: str  # 'HTML', 'PDF', or ''
    confidence: float


@dataclass
class KeywordMatchResult:
    """Result of keyword matching."""
    matched: bool
    priority: Priority
    confidence: float
    description: str
    keywords: List[str]


@dataclass
class ChangeDetectionResult:
    """Result of change detection."""
    has_changed: bool
    change_type: Optional[ChangeType]
    priority: Priority
    confidence: float
    description: str
    diff: Optional[str] = None
    matched_keywords: Optional[List[str]] = None


class ChangeDetector:
    """Detects and analyzes changes in HTML content."""

    def __init__(self):
        self.dmp = diff_match_patch()

    async def detect_changes(
        self,
        previous_html_normalized: Optional[str],
        previous_html_original: Optional[str],
        current_html: str,
        current_normalized_html: str,
        previous_html_hash: Optional[str] = None,
        current_html_hash: Optional[str] = None
    ) -> ChangeDetectionResult:
        """
        Detect changes between previous and current HTML.

        This is a direct port of the TypeScript detectChanges method.
        """
        # First check - don't trigger critical alerts
        if not previous_html_normalized:
            return ChangeDetectionResult(
                has_changed=False,
                change_type=None,
                priority=Priority.INFO,
                confidence=1.0,
                description='Initial check - no previous data'
            )

        # Use hash comparison (prevents memory issues with large HTML)
        has_hash_change = previous_html_hash != current_html_hash

        # If hash unchanged, no changes at all
        if not has_hash_change:
            return ChangeDetectionResult(
                has_changed=False,
                change_type=None,
                priority=Priority.INFO,
                confidence=0,
                description='No changes detected'
            )

        # Hash changed - perform SEMANTIC comparison if enabled
        has_semantic_change = True
        semantic_diff = None

        if settings.enable_semantic_comparison:
            logger.info('Hash change detected, performing semantic comparison...')

            prev_semantic = extract_semantic_content(previous_html_normalized)
            curr_semantic = extract_semantic_content(current_normalized_html)

            semantic_diff = compare_semantic_content(prev_semantic, curr_semantic)

            has_semantic_change = (
                (settings.track_text_changes and semantic_diff['has_text_changes']) or
                (settings.track_image_changes and semantic_diff['has_image_changes']) or
                (settings.track_link_changes and semantic_diff['has_link_changes'])
            )

            if not has_semantic_change:
                logger.info('No semantic changes detected (noise filtered)', extra={
                    'text_changes': semantic_diff['has_text_changes'],
                    'image_changes': semantic_diff['has_image_changes'],
                    'link_changes': semantic_diff['has_link_changes']
                })
                return ChangeDetectionResult(
                    has_changed=False,
                    change_type=None,
                    priority=Priority.INFO,
                    confidence=0,
                    description='No significant changes detected (filtered noise)'
                )

            logger.info('Semantic changes detected', extra={
                'text_changes': semantic_diff['has_text_changes'],
                'image_changes': semantic_diff['has_image_changes'],
                'link_changes': semantic_diff['has_link_changes'],
                'changed_text_count': len(semantic_diff['changed_texts']),
                'changed_image_count': len(semantic_diff['changed_images']),
                'changed_link_count': len(semantic_diff['changed_links'])
            })

        # Only check for forms/keywords if there's a semantic content change
        if has_semantic_change:
            # Check for form detection first (highest priority)
            current_form_detection = self.detect_forms(current_html)
            if current_form_detection.detected:
                # Check if form was already present in previous HTML
                previous_form_detection = self.detect_forms(
                    previous_html_original or previous_html_normalized
                )
                if not previous_form_detection.detected:
                    # NEW form detected!
                    logger.warning(
                        f'🚨 CRITICAL: NEW Form detected! Type: {current_form_detection.form_type}'
                    )
                    description = (
                        'PDF-Antragsformular gefunden! Download jetzt möglich.'
                        if current_form_detection.form_type == 'PDF'
                        else 'Online-Anmeldeformular entdeckt! Du kannst dich jetzt bewerben.'
                    )
                    return ChangeDetectionResult(
                        has_changed=True,
                        change_type=ChangeType.FORM,
                        priority=Priority.CRITICAL,
                        confidence=current_form_detection.confidence,
                        description=description,
                        diff=self.generate_diff(
                            previous_html_original or previous_html_normalized,
                            current_html
                        )
                    )

            # Check for critical keywords
            current_keyword_match = self.detect_keywords(current_normalized_html)
            if current_keyword_match.matched:
                # Check if same keywords were in previous HTML
                previous_keyword_match = self.detect_keywords(previous_html_normalized)

                # Find NEW keywords (in current but not in previous)
                new_keywords = [
                    kw for kw in current_keyword_match.keywords
                    if kw not in previous_keyword_match.keywords
                ]

                if new_keywords:
                    # NEW keywords detected!
                    logger.warning(f'🚨 CRITICAL: NEW Keywords detected! {new_keywords}')
                    return ChangeDetectionResult(
                        has_changed=True,
                        change_type=ChangeType.KEYWORD,
                        priority=current_keyword_match.priority,
                        confidence=current_keyword_match.confidence,
                        description=current_keyword_match.description,
                        matched_keywords=new_keywords,
                        diff=self.generate_diff(
                            previous_html_original or previous_html_normalized,
                            current_html
                        )
                    )

        # If we reach here and there was a semantic change, it's a regular content change
        if has_semantic_change:
            description = '📝 Page content updated. Check the screenshot for details.'
            diff_text = None

            if semantic_diff and settings.enable_semantic_comparison:
                description = f"📝 {generate_change_description(semantic_diff)}. Check the screenshot for details."
                diff_text = generate_semantic_diff(semantic_diff)
            else:
                diff_text = self.generate_diff(
                    previous_html_original or previous_html_normalized,
                    current_html
                )

            return ChangeDetectionResult(
                has_changed=True,
                change_type=ChangeType.CONTENT,
                priority=Priority.INFO,
                confidence=0.8,
                description=description,
                diff=diff_text
            )

        return ChangeDetectionResult(
            has_changed=False,
            change_type=None,
            priority=Priority.INFO,
            confidence=0,
            description='No significant changes detected'
        )

    def detect_forms(self, html: str) -> FormDetectionResult:
        """
        Detect forms in HTML content.

        Port of TypeScript detectForms method.
        """
        html_lower = html.lower()

        # Check for HTML forms
        has_form_tag = bool(re.search(r'<form[^>]*>', html, re.IGNORECASE))
        has_input_fields = bool(re.search(r'<input[^>]*>', html, re.IGNORECASE))
        has_submit_button = bool(
            re.search(r'<button[^>]*type=["\']?submit["\']?[^>]*>', html, re.IGNORECASE) or
            re.search(r'<input[^>]*type=["\']?submit["\']?[^>]*>', html, re.IGNORECASE)
        )

        if has_form_tag and has_input_fields and has_submit_button:
            # Check for application-related form fields
            has_name_field = bool(re.search(r'name.*input|input.*name', html, re.IGNORECASE))
            has_email_field = bool(re.search(r'email.*input|input.*email', html, re.IGNORECASE))
            has_address_field = bool(re.search(r'address|adresse', html, re.IGNORECASE))

            if has_name_field or has_email_field or has_address_field:
                return FormDetectionResult(detected=True, form_type='HTML', confidence=0.95)
            return FormDetectionResult(detected=True, form_type='HTML', confidence=0.7)

        # Check for PDF forms
        has_pdf_link = bool(re.search(r'\.pdf["\'\s>]', html, re.IGNORECASE))
        has_form_keywords = bool(
            re.search(r'(antrag|formular|application|form).*\.pdf', html, re.IGNORECASE)
        )

        if has_pdf_link and has_form_keywords:
            return FormDetectionResult(detected=True, form_type='PDF', confidence=0.85)

        # Check for online application links
        has_online_application = bool(
            re.search(r'(online.*antrag|onlineantrag|apply.*online)', html, re.IGNORECASE)
        )
        has_application_url = bool(
            re.search(r'/antrag|/application|/bewerbung', html, re.IGNORECASE)
        )

        if has_online_application or has_application_url:
            return FormDetectionResult(detected=True, form_type='HTML', confidence=0.8)

        return FormDetectionResult(detected=False, form_type='', confidence=0)

    def _match_keywords(self, html: str, keywords: list) -> list:
        """Find matching keywords in HTML content."""
        html_lower = html.lower()
        return [kw for kw in keywords if kw.lower() in html_lower]

    def detect_keywords(self, normalized_html: str) -> KeywordMatchResult:
        """
        Detect keywords in normalized HTML.

        Port of TypeScript detectKeywords method.
        """
        matched_critical = self._match_keywords(normalized_html, CRITICAL_KEYWORDS)
        matched_important = self._match_keywords(normalized_html, IMPORTANT_KEYWORDS)

        if matched_critical:
            # More user-friendly descriptions based on keywords
            description = 'Wichtige Änderung auf der Seite!'
            if any(k in ['warteliste', 'anmeldung'] for k in matched_critical):
                description = 'Die Warteliste könnte bald öffnen! Neue Informationen zur Anmeldung gefunden.'
            elif any(k in ['formular', 'antrag'] for k in matched_critical):
                description = 'Anmeldeformular wurde gefunden! Jetzt könnte eine Bewerbung möglich sein.'

            return KeywordMatchResult(
                matched=True,
                priority=Priority.CRITICAL,
                confidence=min(0.9 + (len(matched_critical) * 0.02), 1.0),
                description=description,
                keywords=matched_critical
            )

        if matched_important:
            description = 'Relevante Änderung auf der Seite gefunden.'
            if any(k in ['verfügbar', 'available'] for k in matched_important):
                description = 'Neue Verfügbarkeits-Informationen wurden veröffentlicht.'
            elif any(k in ['termin', 'öffnung'] for k in matched_important):
                description = 'Neue Informationen zu Terminen oder Öffnungszeiten.'

            return KeywordMatchResult(
                matched=True,
                priority=Priority.IMPORTANT,
                confidence=min(0.7 + (len(matched_important) * 0.05), 0.9),
                description=description,
                keywords=matched_important
            )

        return KeywordMatchResult(
            matched=False,
            priority=Priority.INFO,
            confidence=0,
            description='',
            keywords=[]
        )

    def generate_diff(self, old_content: str, new_content: str, max_length: int = 5000, context_lines: int = 2) -> str:
        """Generate human-readable diff between old and new content.

        Shows the actual differences with context lines before and after,
        so users can see exactly what changed.

        Args:
            old_content: Previous HTML content
            new_content: Current HTML content
            max_length: Maximum length of the diff output
            context_lines: Number of unchanged lines to show before/after each change
        """
        try:
            # Light cleaning only - remove head/script/style but keep body content
            old_cleaned = self._light_clean_for_diff(old_content)
            new_cleaned = self._light_clean_for_diff(new_content)

            # Split into lines for line-based diff with context
            old_lines = old_cleaned.split('\n')
            new_lines = new_cleaned.split('\n')

            # Use difflib for unified diff with context
            import difflib
            differ = difflib.unified_diff(
                old_lines,
                new_lines,
                lineterm='',
                n=context_lines  # Context lines before/after
            )

            # Build human-readable diff
            output_lines = []
            for line in differ:
                # Skip the diff headers (---, +++, @@)
                if line.startswith('---') or line.startswith('+++'):
                    continue
                if line.startswith('@@'):
                    # Add separator between hunks
                    if output_lines:
                        output_lines.append('···')
                    continue

                # Truncate very long lines
                display_line = line[:500] + '...' if len(line) > 500 else line

                # Normalize tabs for display
                display_line = display_line.replace('\t', '→')

                if line.startswith('-'):
                    output_lines.append(f"- {display_line[1:]}")
                elif line.startswith('+'):
                    output_lines.append(f"+ {display_line[1:]}")
                elif line.startswith(' '):
                    output_lines.append(f"  {display_line[1:]}")
                else:
                    output_lines.append(f"  {display_line}")

            result = '\n'.join(output_lines)

            # Truncate if too long
            if len(result) > max_length:
                result = result[:max_length] + '\n\n... (gekürzt)'

            return result if result else '(keine Unterschiede nach Bereinigung)'
        except Exception as e:
            logger.error(f'Failed to generate diff: {e}')
            return f'Diff-Fehler: {str(e)}'

    def _light_clean_for_diff(self, html: str) -> str:
        """Light cleaning for diff display - keeps more content visible."""
        return clean_html(html, aggressive=False)

    def extract_form_fields(self, html: str) -> List[Dict[str, Any]]:
        """Extract form fields from HTML."""
        fields: List[Dict[str, Any]] = []

        try:
            # Extract input fields
            input_regex = re.compile(r'<input[^>]*>', re.IGNORECASE)
            inputs = input_regex.findall(html)

            for input_tag in inputs:
                name_match = re.search(r'name=["\']([^"\']+)["\']', input_tag, re.IGNORECASE)
                type_match = re.search(r'type=["\']([^"\']+)["\']', input_tag, re.IGNORECASE)
                placeholder_match = re.search(
                    r'placeholder=["\']([^"\']+)["\']',
                    input_tag,
                    re.IGNORECASE
                )
                required_match = re.search(r'\brequired\b', input_tag, re.IGNORECASE)

                if name_match:
                    fields.append({
                        'name': name_match.group(1),
                        'type': type_match.group(1) if type_match else 'text',
                        'required': bool(required_match),
                        'placeholder': placeholder_match.group(1) if placeholder_match else None
                    })

            # Extract textareas
            textarea_regex = re.compile(r'<textarea[^>]*>', re.IGNORECASE)
            textareas = textarea_regex.findall(html)

            for textarea_tag in textareas:
                name_match = re.search(r'name=["\']([^"\']+)["\']', textarea_tag, re.IGNORECASE)
                required_match = re.search(r'\brequired\b', textarea_tag, re.IGNORECASE)

                if name_match:
                    fields.append({
                        'name': name_match.group(1),
                        'type': 'textarea',
                        'required': bool(required_match)
                    })

        except Exception as e:
            logger.error(f'Failed to extract form fields: {e}')

        return fields


# Global instance
change_detector = ChangeDetector()
