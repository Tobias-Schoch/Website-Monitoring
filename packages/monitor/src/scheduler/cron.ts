import { checkQueue } from './queue';
import { MonitoredUrlsRepository } from '@website-monitor/database';
import { createModuleLogger } from '@website-monitor/shared';
import { settingsService } from '../services/settings-service';
import * as cron from 'node-cron';

const logger = createModuleLogger('Cron');
const urlsRepo = new MonitoredUrlsRepository();

let currentCronJob: cron.ScheduledTask | null = null;

export async function scheduleCronJobs(): Promise<void> {
  try {
    // Get check interval from settings (default: 5 minutes)
    const checkIntervalMinutes = await getCheckInterval();

    logger.info(`Scheduling checks every ${checkIntervalMinutes} minute(s)`);

    // Schedule the cron job with configurable interval
    await scheduleCronWithInterval(checkIntervalMinutes);

    // Trigger initial check immediately
    await triggerCheckAll();
  } catch (error) {
    logger.error('Failed to schedule cron jobs', { error });
    throw error;
  }
}

async function getCheckInterval(): Promise<number> {
  try {
    const intervalSetting = await settingsService.get('check_interval_minutes');
    const interval = intervalSetting ? parseInt(intervalSetting) : 5;

    // Validate interval (min: 1 minute, max: 1440 minutes = 24 hours)
    if (interval < 1 || interval > 1440 || isNaN(interval)) {
      logger.warn(`Invalid check interval: ${interval}, using default: 5 minutes`);
      return 5;
    }

    return interval;
  } catch (error) {
    logger.warn('Failed to get check interval from settings, using default: 5 minutes', { error });
    return 5;
  }
}

async function scheduleCronWithInterval(intervalMinutes: number): Promise<void> {
  // Stop existing cron job if any
  if (currentCronJob) {
    currentCronJob.stop();
    logger.info('Stopped existing cron job');
  }

  // Create cron expression based on interval
  const cronExpression = getCronExpression(intervalMinutes);

  logger.info(`Using cron expression: ${cronExpression}`);

  currentCronJob = cron.schedule(cronExpression, async () => {
    await triggerCheckAll();
  });
}

function getCronExpression(intervalMinutes: number): string {
  // For intervals that divide 60 evenly (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)
  if (60 % intervalMinutes === 0) {
    return `*/${intervalMinutes} * * * *`;
  }

  // For other intervals, check every minute and handle in the job
  // This is a fallback - for production, consider using a different scheduling approach
  logger.warn(`Interval ${intervalMinutes} does not divide 60 evenly. Using best-effort scheduling.`);
  return `*/${intervalMinutes} * * * *`;
}

export async function updateCronInterval(newIntervalMinutes: number): Promise<void> {
  logger.info(`Updating check interval to ${newIntervalMinutes} minute(s)`);
  await scheduleCronWithInterval(newIntervalMinutes);
}

export async function triggerCheckAll(): Promise<void> {
  try {
    const enabledUrls = await urlsRepo.findEnabled();

    if (enabledUrls.length === 0) {
      logger.info('No enabled URLs to check');
      return;
    }

    logger.info(`Queuing checks for ${enabledUrls.length} URL(s)`);

    // Add all checks to queue sequentially
    for (const url of enabledUrls) {
      await checkQueue.add(
        'check-url',
        {
          urlId: url.id,
          url: url.url
        },
        {
          attempts: 3,
          backoff: {
            type: 'exponential',
            delay: 2000
          }
        }
      );
    }

    logger.info(`Successfully queued ${enabledUrls.length} check(s)`);
  } catch (error) {
    logger.error('Failed to trigger check all', { error });
    throw error;
  }
}
