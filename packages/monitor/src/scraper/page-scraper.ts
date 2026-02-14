import { Page } from 'playwright';
import fs from 'fs/promises';
import path from 'path';
import { playwrightManager } from './playwright-manager';
import { retry, createModuleLogger, APP_CONFIG, hashContent } from '@website-monitor/shared';
import { htmlNormalizer } from './html-normalizer';

const logger = createModuleLogger('PageScraper');

export interface ScrapeResult {
  html: string;
  htmlHash: string;
  normalizedHtml: string;
  screenshotPath: string;
  responseTime: number;
  statusCode: number;
  success: boolean;
  error?: string;
}

export class PageScraper {
  async scrape(url: string): Promise<ScrapeResult> {
    const startTime = Date.now();
    let page: Page | null = null;

    try {
      const result = await retry(
        async () => {
          page = await playwrightManager.newPage();
          return await this.performScrape(page, url);
        },
        {
          maxAttempts: APP_CONFIG.MAX_RETRY_ATTEMPTS,
          delayMs: APP_CONFIG.RETRY_DELAY_MS,
          onRetry: (error, attempt) => {
            logger.warn(`Scrape attempt ${attempt} failed`, { url, error: error.message });
          }
        }
      );

      const responseTime = Date.now() - startTime;

      return {
        ...result,
        responseTime,
        success: true
      };
    } catch (error) {
      const responseTime = Date.now() - startTime;
      logger.error('Page scrape failed', { url, error, responseTime });

      return {
        html: '',
        htmlHash: '',
        normalizedHtml: '',
        screenshotPath: '',
        responseTime,
        statusCode: 0,
        success: false,
        error: error instanceof Error ? error.message : String(error)
      };
    } finally {
      if (page !== null) {
        await (page as Page).close().catch((err: unknown) => {
          logger.warn('Failed to close page', { error: err });
        });
      }
    }
  }

  private async performScrape(page: Page, url: string): Promise<Omit<ScrapeResult, 'responseTime' | 'success'>> {
    // Navigate to page
    const response = await page.goto(url, {
      waitUntil: 'networkidle',
      timeout: APP_CONFIG.PAGE_TIMEOUT_MS
    });

    if (!response) {
      throw new Error('No response received');
    }

    const statusCode = response.status();

    // Wait for page to be fully loaded
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000); // Additional wait for dynamic content

    // Extract HTML content
    const html = await page.content();
    const htmlHash = hashContent(html);

    // Normalize HTML for comparison
    const normalizedHtml = await this.normalizeHtml(page);

    // Take screenshot
    const screenshotPath = await this.takeScreenshot(page, url);

    return {
      html,
      htmlHash,
      normalizedHtml,
      screenshotPath,
      statusCode
    };
  }

  private async normalizeHtml(page: Page): Promise<string> {
    // Remove dynamic elements before extracting HTML
    // Note: This function runs in browser context where DOM APIs are available
    await page.evaluate(() => {
      // Remove scripts and styles
      // @ts-expect-error - Running in browser context where document is available
      document.querySelectorAll('script, style, noscript').forEach(el => el.remove());

      // Remove cookie banners, consent dialogs, and CCM elements
      const ccmSelectors = [
        '[class*="ccm" i]',
        '[id*="ccm" i]',
        '[class*="cookie" i]',
        '[id*="cookie" i]',
        '[class*="consent" i]',
        '[id*="consent" i]',
        '[class*="gdpr" i]',
        '[id*="gdpr" i]'
      ];
      ccmSelectors.forEach(selector => {
        // @ts-expect-error - Running in browser context
        document.querySelectorAll(selector).forEach(el => el.remove());
      });

      // Remove advertisement elements
      const adSelectors = [
        '[class*="advertisement" i]',
        '[id*="advertisement" i]',
        '[class*="ad-" i]',
        '[id*="ad-" i]'
      ];
      adSelectors.forEach(selector => {
        // @ts-expect-error - Running in browser context
        document.querySelectorAll(selector).forEach(el => el.remove());
      });

      // Remove tracking pixels and analytics
      // @ts-expect-error - Running in browser context
      document.querySelectorAll('img[width="1"][height="1"]').forEach(el => el.remove());
      // @ts-expect-error - Running in browser context
      document.querySelectorAll('iframe[style*="display: none"]').forEach(el => el.remove());
    });

    // Get cleaned HTML
    const cleanedHtml = await page.content();

    // Additional normalization (timestamps, session IDs, etc.)
    return this.normalizeHtmlString(cleanedHtml);
  }

  private normalizeHtmlString(html: string): string {
    let normalized = html;

    // Remove timestamps
    normalized = normalized.replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?/g, 'TIMESTAMP');
    normalized = normalized.replace(/\d{2}\.\d{2}\.\d{4}/g, 'DATE');
    normalized = normalized.replace(/\d{1,2}:\d{2}(:\d{2})?/g, 'TIME');

    // Remove session IDs and tokens
    normalized = normalized.replace(/sessionid=[a-zA-Z0-9_-]+/gi, 'sessionid=SESSION');
    normalized = normalized.replace(/csrf[_-]?token=[a-zA-Z0-9_-]+/gi, 'csrf_token=TOKEN');
    normalized = normalized.replace(/token=[a-zA-Z0-9_-]+/gi, 'token=TOKEN');

    // Remove UUIDs
    normalized = normalized.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, 'UUID');

    // Apply aggressive attribute normalization to remove dynamic IDs, classes, data-*, aria-*, etc.
    normalized = htmlNormalizer.normalizeAttributes(normalized);

    // Aggressive whitespace normalization to handle formatting differences
    // 1. Remove whitespace between tags (handles formatted vs. minified HTML)
    normalized = normalized.replace(/>\s+</g, '><');
    // 2. Replace all remaining whitespace (including newlines) with single space
    normalized = normalized.replace(/\s+/g, ' ');
    // 3. Trim leading/trailing whitespace
    normalized = normalized.trim();

    return normalized;
  }

  private async takeScreenshot(page: Page, url: string): Promise<string> {
    try {
      // Create screenshot directory if it doesn't exist
      const screenshotDir = APP_CONFIG.SCREENSHOT_DIR;
      await fs.mkdir(screenshotDir, { recursive: true });

      // Generate filename
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const urlHash = hashContent(url).substring(0, 8);
      const filename = `screenshot-${urlHash}-${timestamp}.png`;
      const filePath = path.join(screenshotDir, filename);

      // Take full-page screenshot
      await page.screenshot({
        path: filePath,
        fullPage: true,
        type: 'png'
      });

      // Return absolute path so it can be accessed from other packages
      const absolutePath = path.resolve(filePath);
      return absolutePath;
    } catch (error) {
      logger.error('Failed to take screenshot', { error });
      throw error;
    }
  }
}

export const pageScraper = new PageScraper();
