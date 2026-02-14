import { NotificationChannel, Priority } from '../types/notification.types';

export const APP_CONFIG = {
  CHECK_INTERVAL_MINUTES: parseInt(process.env.CHECK_INTERVAL_MINUTES || '5', 10),
  SCREENSHOT_DIR: process.env.SCREENSHOT_DIR || './data/screenshots',
  LOG_LEVEL: process.env.LOG_LEVEL || 'info',
  MAX_RETRY_ATTEMPTS: 3,
  RETRY_DELAY_MS: 2000,
  PAGE_TIMEOUT_MS: 30000,
  SCREENSHOT_QUALITY: 90,
  MAX_SCREENSHOT_WIDTH: 1920,
  MAX_SCREENSHOT_HEIGHT: 1080
} as const;

export const HTML_NORMALIZATION_CONFIG = {
  // Enable/disable semantic comparison (vs. just hash)
  ENABLE_SEMANTIC_COMPARISON: true,

  // Attribute patterns to remove
  REMOVE_DYNAMIC_IDS: true,
  REMOVE_DYNAMIC_CLASSES: true,
  REMOVE_DATA_ATTRIBUTES: true,
  REMOVE_ARIA_ATTRIBUTES: true,
  REMOVE_STYLE_ATTRIBUTES: true,

  // Element removal patterns
  REMOVE_CCM_ELEMENTS: true,
  REMOVE_NOSCRIPT: true,
  REMOVE_ADS: true,

  // What to track
  TRACK_TEXT_CHANGES: true,
  TRACK_IMAGE_CHANGES: true,
  TRACK_LINK_CHANGES: true,
} as const;

export const NOTIFICATION_CONFIG = {
  CHANNELS: [
    {
      channel: NotificationChannel.TELEGRAM,
      enabled: !!process.env.TELEGRAM_BOT_TOKEN,
      priority: [Priority.INFO, Priority.IMPORTANT, Priority.CRITICAL],
      rateLimit: {
        maxNotifications: 10,
        windowMs: 60000 // 1 minute
      }
    },
    {
      channel: NotificationChannel.EMAIL,
      enabled: !!process.env.SMTP_HOST,
      priority: [Priority.IMPORTANT, Priority.CRITICAL],
      rateLimit: {
        maxNotifications: 5,
        windowMs: 300000 // 5 minutes
      }
    }
  ],
  MAX_RETRY_ATTEMPTS: 5,
  RETRY_BACKOFF_MS: 5000,
  DEDUPLICATION_WINDOW_MS: 300000 // 5 minutes
} as const;

export const DATABASE_CONFIG = {
  URL: process.env.DATABASE_URL || 'postgresql://boat_monitor:password@localhost:5432/boat_monitor',
  POOL_SIZE: 10,
  CONNECTION_TIMEOUT_MS: 5000
} as const;

export const REDIS_CONFIG = {
  HOST: process.env.REDIS_HOST || 'localhost',
  PORT: parseInt(process.env.REDIS_PORT || '6379', 10),
  PASSWORD: process.env.REDIS_PASSWORD || undefined,
  DB: 0
} as const;
