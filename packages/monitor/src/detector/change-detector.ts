import * as Diff from 'diff';
import {
  createModuleLogger,
  CRITICAL_KEYWORDS,
  IMPORTANT_KEYWORDS,
  ChangeType,
  Priority,
  ChangeComparisonResult,
  FormField,
  SemanticDiff,
  HTML_NORMALIZATION_CONFIG
} from '@website-monitor/shared';
import { htmlNormalizer } from '../scraper/html-normalizer';

const logger = createModuleLogger('ChangeDetector');

export class ChangeDetector {
  async detectChanges(
    previousHtmlNormalized: string | null,
    previousHtmlOriginal: string | null,
    currentHtml: string,
    currentNormalizedHtml: string,
    previousHtmlHash: string | null = null,
    currentHtmlHash: string | null = null
  ): Promise<ChangeComparisonResult> {
    // First check - don't trigger critical alerts
    if (!previousHtmlNormalized) {
      return {
        hasChanged: false,
        type: null,
        priority: Priority.INFO,
        confidence: 1.0,
        description: 'Initial check - no previous data'
      };
    }

    // Use hash comparison instead of Levenshtein (prevents memory issues with large HTML)
    const hasHashChange = previousHtmlHash !== currentHtmlHash;

    // If hash hasn't changed, no changes at all
    if (!hasHashChange) {
      return {
        hasChanged: false,
        type: null,
        priority: Priority.INFO,
        confidence: 0,
        description: 'No changes detected'
      };
    }

    // Hash changed - perform SEMANTIC comparison if enabled
    let hasSemanticChange = true;
    let semanticDiff: SemanticDiff | null = null;

    if (HTML_NORMALIZATION_CONFIG.ENABLE_SEMANTIC_COMPARISON) {
      logger.info('Hash change detected, performing semantic comparison...');

      const prevSemantic = htmlNormalizer.extractSemanticContent(previousHtmlNormalized);
      const currSemantic = htmlNormalizer.extractSemanticContent(currentNormalizedHtml);

      semanticDiff = htmlNormalizer.compareSemanticContent(prevSemantic, currSemantic);

      hasSemanticChange =
        (HTML_NORMALIZATION_CONFIG.TRACK_TEXT_CHANGES && semanticDiff?.hasTextChanges) ||
        (HTML_NORMALIZATION_CONFIG.TRACK_IMAGE_CHANGES && semanticDiff?.hasImageChanges) ||
        (HTML_NORMALIZATION_CONFIG.TRACK_LINK_CHANGES && semanticDiff?.hasLinkChanges) ||
        false;

      if (!hasSemanticChange && semanticDiff) {
        logger.info('No semantic changes detected (noise filtered)', {
          textChanges: semanticDiff.hasTextChanges,
          imageChanges: semanticDiff.hasImageChanges,
          linkChanges: semanticDiff.hasLinkChanges
        });
        return {
          hasChanged: false,
          type: null,
          priority: Priority.INFO,
          confidence: 0,
          description: 'No significant changes detected (filtered noise)'
        };
      }

      if (semanticDiff) {
        logger.info('Semantic changes detected', {
          textChanges: semanticDiff.hasTextChanges,
          imageChanges: semanticDiff.hasImageChanges,
          linkChanges: semanticDiff.hasLinkChanges,
          changedTextCount: semanticDiff.changedTexts.length,
          changedImageCount: semanticDiff.changedImages.length,
          changedLinkCount: semanticDiff.changedLinks.length
        });
      }
    }

    // Only check for forms/keywords if there's a semantic content change
    if (hasSemanticChange) {

      // Check for form detection first (highest priority)
      const currentFormDetection = this.detectForms(currentHtml);
      if (currentFormDetection.detected) {
        // Check if form was already present in previous HTML
        const previousFormDetection = this.detectForms(previousHtmlOriginal || previousHtmlNormalized);
        if (!previousFormDetection.detected) {
          // NEW form detected!
          logger.warn('🚨 CRITICAL: NEW Form detected!', { type: currentFormDetection.type });
          const description = currentFormDetection.type === 'PDF'
            ? '📄 PDF form detected! New downloadable form available.'
            : '📝 Online form detected! New submission form is now available.';
          return {
            hasChanged: true,
            type: ChangeType.FORM_DETECTED,
            priority: Priority.CRITICAL,
            confidence: currentFormDetection.confidence,
            description,
            diff: this.generateDiff(previousHtmlOriginal || previousHtmlNormalized, currentHtml)
          };
        }
      }

      // Check for critical keywords
      const currentKeywordMatch = this.detectKeywords(currentNormalizedHtml);
      if (currentKeywordMatch.matched) {
        // Check if same keywords were in previous HTML
        const previousKeywordMatch = this.detectKeywords(previousHtmlNormalized);

        // Find NEW keywords (in current but not in previous)
        const newKeywords = currentKeywordMatch.keywords.filter(
          keyword => !previousKeywordMatch.keywords.includes(keyword)
        );

        if (newKeywords.length > 0) {
          // NEW keywords detected!
          logger.warn('🚨 CRITICAL: NEW Keywords detected!', { newKeywords });
          return {
            hasChanged: true,
            type: ChangeType.KEYWORD_MATCH,
            priority: currentKeywordMatch.priority,
            confidence: currentKeywordMatch.confidence,
            description: currentKeywordMatch.description,
            matchedKeywords: newKeywords,
            diff: this.generateDiff(previousHtmlOriginal || previousHtmlNormalized, currentHtml)
          };
        }
      }
    }

    // If we reach here and there was a semantic change, it's a regular content change
    if (hasSemanticChange) {
      const description = semanticDiff && HTML_NORMALIZATION_CONFIG.ENABLE_SEMANTIC_COMPARISON
        ? `📝 ${htmlNormalizer.generateChangeDescription(semanticDiff)}. Check the screenshot for details.`
        : '📝 Page content updated. Check the screenshot for details.';

      const diff = semanticDiff && HTML_NORMALIZATION_CONFIG.ENABLE_SEMANTIC_COMPARISON
        ? htmlNormalizer.generateSemanticDiff(semanticDiff)
        : this.generateDiff(previousHtmlOriginal || previousHtmlNormalized, currentHtml);

      return {
        hasChanged: true,
        type: ChangeType.CONTENT,
        priority: Priority.INFO,
        confidence: 0.8,
        description,
        diff
      };
    }

    return {
      hasChanged: false,
      type: null,
      priority: Priority.INFO,
      confidence: 0,
      description: 'No significant changes detected'
    };
  }

  private detectForms(html: string): { detected: boolean; type: string; confidence: number } {
    const htmlLower = html.toLowerCase();

    // Check for HTML forms
    const hasFormTag = /<form[^>]*>/i.test(html);
    const hasInputFields = /<input[^>]*>/i.test(html);
    const hasSubmitButton = /<button[^>]*type=["']?submit["']?[^>]*>/i.test(html) ||
                           /<input[^>]*type=["']?submit["']?[^>]*>/i.test(html);

    if (hasFormTag && hasInputFields && hasSubmitButton) {
      // Check for application-related form fields
      const hasNameField = /name.*input|input.*name/i.test(html);
      const hasEmailField = /email.*input|input.*email/i.test(html);
      const hasAddressField = /address|adresse/i.test(html);

      if (hasNameField || hasEmailField || hasAddressField) {
        return { detected: true, type: 'HTML', confidence: 0.95 };
      }
      return { detected: true, type: 'HTML', confidence: 0.7 };
    }

    // Check for PDF forms
    const hasPdfLink = /\.pdf["'\s>]/i.test(html);
    const hasFormKeywords = /(application|form).*\.pdf/i.test(html);

    if (hasPdfLink && hasFormKeywords) {
      return { detected: true, type: 'PDF', confidence: 0.85 };
    }

    // Check for online application links
    const hasOnlineApplication = /(apply.*online|online.*application)/i.test(html);
    const hasApplicationUrl = /\/application|\/apply/i.test(html);

    if (hasOnlineApplication || hasApplicationUrl) {
      return { detected: true, type: 'HTML', confidence: 0.8 };
    }

    return { detected: false, type: '', confidence: 0 };
  }

  private detectKeywords(normalizedHtml: string): {
    matched: boolean;
    priority: Priority;
    confidence: number;
    description: string;
    keywords: string[];
  } {
    const htmlLower = normalizedHtml.toLowerCase();
    const matchedCritical: string[] = [];
    const matchedImportant: string[] = [];

    // Check critical keywords
    for (const keyword of CRITICAL_KEYWORDS) {
      if (htmlLower.includes(keyword.toLowerCase())) {
        matchedCritical.push(keyword);
      }
    }

    // Check important keywords
    for (const keyword of IMPORTANT_KEYWORDS) {
      if (htmlLower.includes(keyword.toLowerCase())) {
        matchedImportant.push(keyword);
      }
    }

    if (matchedCritical.length > 0) {
      // More user-friendly descriptions based on keywords
      let description = '🚨 Critical keywords detected on page!';
      if (matchedCritical.some(k => k.toLowerCase().includes('registration') || k.toLowerCase().includes('apply'))) {
        description = '⚠️ Registration or application keywords found! Important update detected.';
      } else if (matchedCritical.some(k => k.toLowerCase().includes('form') || k.toLowerCase().includes('submit'))) {
        description = '📝 Form-related keywords detected! New submission options may be available.';
      }

      return {
        matched: true,
        priority: Priority.CRITICAL,
        confidence: Math.min(0.9 + (matchedCritical.length * 0.02), 1.0),
        description,
        keywords: matchedCritical
      };
    }

    if (matchedImportant.length > 0) {
      let description = 'ℹ️ Important keywords detected on page.';
      if (matchedImportant.some(k => k.toLowerCase().includes('available') || k.toLowerCase().includes('updated'))) {
        description = '✅ New availability or update information published.';
      } else if (matchedImportant.some(k => k.toLowerCase().includes('deadline') || k.toLowerCase().includes('announcement'))) {
        description = '📅 New deadline or announcement information available.';
      }

      return {
        matched: true,
        priority: Priority.IMPORTANT,
        confidence: Math.min(0.7 + (matchedImportant.length * 0.05), 0.9),
        description,
        keywords: matchedImportant
      };
    }

    return {
      matched: false,
      priority: Priority.INFO,
      confidence: 0,
      description: '',
      keywords: []
    };
  }

  private generateDiff(oldContent: string, newContent: string): string {
    try {
      const diffResult = Diff.createPatch('content', oldContent, newContent, 'Old', 'New');
      return diffResult;
    } catch (error) {
      logger.error('Failed to generate diff', { error });
      return 'Diff generation failed';
    }
  }

  extractFormFields(html: string): FormField[] {
    const fields: FormField[] = [];

    try {
      // Simple regex-based extraction (could be improved with proper HTML parsing)
      const inputRegex = /<input[^>]*>/gi;
      const inputs = html.match(inputRegex) || [];

      for (const input of inputs) {
        const nameMatch = input.match(/name=["']([^"']+)["']/i);
        const typeMatch = input.match(/type=["']([^"']+)["']/i);
        const placeholderMatch = input.match(/placeholder=["']([^"']+)["']/i);
        const requiredMatch = /required/i.test(input);

        if (nameMatch) {
          fields.push({
            name: nameMatch[1],
            type: typeMatch ? typeMatch[1] : 'text',
            required: requiredMatch,
            placeholder: placeholderMatch ? placeholderMatch[1] : undefined
          });
        }
      }

      // Extract textareas
      const textareaRegex = /<textarea[^>]*>/gi;
      const textareas = html.match(textareaRegex) || [];

      for (const textarea of textareas) {
        const nameMatch = textarea.match(/name=["']([^"']+)["']/i);
        const requiredMatch = /required/i.test(textarea);

        if (nameMatch) {
          fields.push({
            name: nameMatch[1],
            type: 'textarea',
            required: requiredMatch
          });
        }
      }
    } catch (error) {
      logger.error('Failed to extract form fields', { error });
    }

    return fields;
  }
}

export const changeDetector = new ChangeDetector();
