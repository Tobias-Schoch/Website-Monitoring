import * as cheerio from 'cheerio';
import {
  HTML_NORMALIZATION_CONFIG,
  SemanticContent,
  ImageContent,
  LinkContent,
  SemanticDiff,
  createModuleLogger
} from '@website-monitor/shared';

const logger = createModuleLogger('HtmlNormalizer');

class HtmlNormalizer {
  /**
   * Normalize HTML by removing dynamic attributes and noise
   * This is applied before comparison to reduce false positives
   */
  normalizeAttributes(html: string): string {
    try {
      const $ = cheerio.load(html, { decodeEntities: false });

      // Remove CCM elements if configured
      if (HTML_NORMALIZATION_CONFIG.REMOVE_CCM_ELEMENTS) {
        this.removeCcmElements($);
      }

      // Remove ad elements if configured
      if (HTML_NORMALIZATION_CONFIG.REMOVE_ADS) {
        this.removeAdElements($);
      }

      // Remove noscript tags if configured
      if (HTML_NORMALIZATION_CONFIG.REMOVE_NOSCRIPT) {
        $('noscript').remove();
      }

      // Process all elements to remove dynamic attributes
      $('*').each((_, element) => {
        // Type guard: only process element nodes
        if (element.type !== 'tag') return;

        const $el = $(element);
        const attrs = (element as any).attribs || {};

        // Remove dynamic IDs
        if (HTML_NORMALIZATION_CONFIG.REMOVE_DYNAMIC_IDS && attrs.id) {
          if (this.isDynamicId(attrs.id)) {
            $el.removeAttr('id');
          }
        }

        // Remove dynamic classes
        if (HTML_NORMALIZATION_CONFIG.REMOVE_DYNAMIC_CLASSES && attrs.class) {
          const classes = attrs.class.split(/\s+/).filter((cls: string) => !this.isDynamicClass(cls));
          if (classes.length > 0) {
            $el.attr('class', classes.join(' '));
          } else {
            $el.removeAttr('class');
          }
        }

        // Remove all data-* attributes
        if (HTML_NORMALIZATION_CONFIG.REMOVE_DATA_ATTRIBUTES) {
          Object.keys(attrs).forEach((attr: string) => {
            if (attr.startsWith('data-')) {
              $el.removeAttr(attr);
            }
          });
        }

        // Remove ARIA attributes
        if (HTML_NORMALIZATION_CONFIG.REMOVE_ARIA_ATTRIBUTES) {
          Object.keys(attrs).forEach((attr: string) => {
            if (attr.startsWith('aria-') || attr === 'role' || attr === 'tabindex' || attr === 'inert') {
              $el.removeAttr(attr);
            }
          });
        }

        // Remove style attributes
        if (HTML_NORMALIZATION_CONFIG.REMOVE_STYLE_ATTRIBUTES && attrs.style) {
          $el.removeAttr('style');
        }

        // For links, only keep href attribute
        if ((element as any).name === 'a' && attrs.href) {
          const href = attrs.href;
          Object.keys(attrs).forEach((attr: string) => {
            if (attr !== 'href') {
              $el.removeAttr(attr);
            }
          });
          $el.attr('href', href);
        }
      });

      return $.html();
    } catch (error) {
      logger.error('Error normalizing attributes', { error });
      return html; // Return original on error
    }
  }

  /**
   * Extract semantic content from HTML (text, images, links)
   */
  extractSemanticContent(html: string): SemanticContent {
    try {
      const $ = cheerio.load(html, { decodeEntities: false });

      // Remove script, style, noscript tags for text extraction
      $('script, style, noscript').remove();

      // Extract text content
      const texts: string[] = [];
      $('body *').contents().each((_, node) => {
        if (node.type === 'text') {
          const text = $(node).text().trim();
          if (text.length > 0) {
            texts.push(text);
          }
        }
      });

      // Extract images
      const images: ImageContent[] = [];
      $('img').each((_, element) => {
        const src = $(element).attr('src');
        const alt = $(element).attr('alt') || '';
        if (src) {
          images.push({ src, alt });
        }
      });

      // Extract links
      const links: LinkContent[] = [];
      $('a[href]').each((_, element) => {
        const href = $(element).attr('href');
        if (href) {
          links.push({ href });
        }
      });

      return { texts, images, links };
    } catch (error) {
      logger.error('Error extracting semantic content', { error });
      return { texts: [], images: [], links: [] };
    }
  }

  /**
   * Compare semantic content and return differences
   */
  compareSemanticContent(previous: SemanticContent, current: SemanticContent): SemanticDiff {
    // Compare texts
    const prevTextSet = new Set(previous.texts);
    const currTextSet = new Set(current.texts);
    const changedTexts: string[] = [];

    // Find new or changed texts
    current.texts.forEach((text: string) => {
      if (!prevTextSet.has(text)) {
        changedTexts.push(text);
      }
    });

    // Find removed texts
    previous.texts.forEach((text: string) => {
      if (!currTextSet.has(text)) {
        changedTexts.push(`[REMOVED] ${text}`);
      }
    });

    const hasTextChanges = changedTexts.length > 0;

    // Compare images
    const prevImageSrcs = new Set(previous.images.map((img: ImageContent) => img.src));
    const currImageSrcs = new Set(current.images.map((img: ImageContent) => img.src));
    const changedImages: ImageContent[] = [];

    // Find new or changed images
    current.images.forEach((img: ImageContent) => {
      if (!prevImageSrcs.has(img.src)) {
        changedImages.push(img);
      }
    });

    // Find removed images
    previous.images.forEach((img: ImageContent) => {
      if (!currImageSrcs.has(img.src)) {
        changedImages.push({ src: `[REMOVED] ${img.src}`, alt: img.alt });
      }
    });

    const hasImageChanges = changedImages.length > 0;

    // Compare links
    const prevLinkHrefs = new Set(previous.links.map((link: LinkContent) => link.href));
    const currLinkHrefs = new Set(current.links.map((link: LinkContent) => link.href));
    const changedLinks: LinkContent[] = [];

    // Find new or changed links
    current.links.forEach((link: LinkContent) => {
      if (!prevLinkHrefs.has(link.href)) {
        changedLinks.push(link);
      }
    });

    // Find removed links
    previous.links.forEach((link: LinkContent) => {
      if (!currLinkHrefs.has(link.href)) {
        changedLinks.push({ href: `[REMOVED] ${link.href}` });
      }
    });

    const hasLinkChanges = changedLinks.length > 0;

    return {
      hasTextChanges,
      hasImageChanges,
      hasLinkChanges,
      changedTexts,
      changedImages,
      changedLinks,
    };
  }

  /**
   * Generate a human-readable description of changes
   */
  generateChangeDescription(diff: SemanticDiff): string {
    const changes: string[] = [];

    if (diff.hasTextChanges) {
      changes.push('text content');
    }
    if (diff.hasImageChanges) {
      changes.push('images');
    }
    if (diff.hasLinkChanges) {
      changes.push('links');
    }

    if (changes.length === 0) {
      return 'No significant changes detected';
    }

    return `Page ${changes.join(', ')} updated`;
  }

  /**
   * Generate a detailed diff for logging/notification
   */
  generateSemanticDiff(diff: SemanticDiff): string {
    const lines: string[] = [];
    const maxItemsPerCategory = 5;

    if (diff.hasTextChanges && diff.changedTexts.length > 0) {
      lines.push('Text Changes:');
      diff.changedTexts.slice(0, maxItemsPerCategory).forEach((text: string) => {
        lines.push(`  - ${text.substring(0, 100)}${text.length > 100 ? '...' : ''}`);
      });
      if (diff.changedTexts.length > maxItemsPerCategory) {
        lines.push(`  ... and ${diff.changedTexts.length - maxItemsPerCategory} more`);
      }
      lines.push('');
    }

    if (diff.hasImageChanges && diff.changedImages.length > 0) {
      lines.push('Image Changes:');
      diff.changedImages.slice(0, maxItemsPerCategory).forEach((img: ImageContent) => {
        lines.push(`  - ${img.src} (alt: ${img.alt})`);
      });
      if (diff.changedImages.length > maxItemsPerCategory) {
        lines.push(`  ... and ${diff.changedImages.length - maxItemsPerCategory} more`);
      }
      lines.push('');
    }

    if (diff.hasLinkChanges && diff.changedLinks.length > 0) {
      lines.push('Link Changes:');
      diff.changedLinks.slice(0, maxItemsPerCategory).forEach((link: LinkContent) => {
        lines.push(`  - ${link.href}`);
      });
      if (diff.changedLinks.length > maxItemsPerCategory) {
        lines.push(`  ... and ${diff.changedLinks.length - maxItemsPerCategory} more`);
      }
      lines.push('');
    }

    return lines.join('\n');
  }

  /**
   * Check if an ID is dynamic (generated at runtime)
   */
  private isDynamicId(id: string): boolean {
    const dynamicPatterns = [
      /^anker\d+$/i,            // anker12345
      /^id-\d+$/i,              // id-12345
      /^uid-[a-f0-9-]+$/i,      // uid-abc123-def456
      /^\d+$/,                  // pure numbers
      /^[a-f0-9]{8,}$/i,        // hex IDs (8+ chars)
      /-\d{10,}$/,              // ends with timestamp
    ];

    return dynamicPatterns.some(pattern => pattern.test(id));
  }

  /**
   * Check if a CSS class is dynamic or should be ignored
   */
  private isDynamicClass(cls: string): boolean {
    const dynamicPatterns = [
      /^ccm-/i,
      /^cookie-/i,
      /^consent-/i,
      /^gdpr-/i,
      /externerLink$/i,
      /^_[a-f0-9]+$/,           // CSS modules hash
      /^css-[a-f0-9]+$/i,
      /-\d{10,}$/,              // ends with timestamp
    ];

    return dynamicPatterns.some(pattern => pattern.test(cls));
  }

  /**
   * Remove CCM (Cookie Consent Manager) elements
   */
  private removeCcmElements($: ReturnType<typeof cheerio.load>): void {
    const ccmSelectors = [
      '[class*="ccm" i]',
      '[id*="ccm" i]',
      '[class*="cookie" i]',
      '[id*="cookie" i]',
      '[class*="consent" i]',
      '[id*="consent" i]',
      '[class*="gdpr" i]',
      '[id*="gdpr" i]',
    ];

    ccmSelectors.forEach((selector: string) => {
      $(selector).remove();
    });
  }

  /**
   * Remove advertisement elements
   */
  private removeAdElements($: ReturnType<typeof cheerio.load>): void {
    const adSelectors = [
      '[class*="advertisement" i]',
      '[id*="advertisement" i]',
      '[class*="ad-" i]',
      '[id*="ad-" i]',
    ];

    adSelectors.forEach((selector: string) => {
      $(selector).remove();
    });
  }
}

// Export singleton instance
export const htmlNormalizer = new HtmlNormalizer();
