"""Configuration management - Settings from database."""
from typing import Optional
import json


# Static configuration (not user-configurable)
DATABASE_URL = "sqlite:////data/boat_monitor.db"
SCREENSHOT_DIR = "/data/screenshots"


class Settings:
    """Application settings - loaded from database on startup."""

    def __init__(self):
        # Static settings (not configurable)
        self.database_url = DATABASE_URL
        self.screenshot_dir = SCREENSHOT_DIR

        # Default values (will be overridden from database)
        # Telegram
        self.telegram_bot_token: Optional[str] = None
        self.telegram_chat_id: Optional[str] = None

        # Email
        self.smtp_host: Optional[str] = None
        self.smtp_port: int = 587
        self.smtp_user: Optional[str] = None
        self.smtp_password: Optional[str] = None
        self.smtp_from: str = "Boat Monitor <noreply@example.com>"
        self.smtp_to: Optional[str] = None

        # Application
        self.log_level: str = "INFO"
        self.check_interval_working: str = "*/5 7-17 * * *"
        self.check_interval_off: str = "*/3 0-6,18-23 * * *"
        self.page_timeout_ms: int = 30000
        self.max_retry_attempts: int = 3

        # Screenshot settings
        self.max_screenshots_per_url: int = 50
        self.screenshot_retention_days: int = 30

        # Notification settings
        self.notification_cooldown_minutes: int = 10
        self.max_notification_retries: int = 3

        # HTML Normalization Settings
        self.enable_semantic_comparison: bool = True
        self.track_text_changes: bool = True
        self.track_image_changes: bool = True
        self.track_link_changes: bool = True

    async def load_from_database(self, session):
        """Load settings from database."""
        from sqlalchemy import select
        from backend.database import Setting

        result = await session.execute(select(Setting).where(Setting.key == 'app_settings'))
        setting_record = result.scalar_one_or_none()

        if setting_record:
            data = setting_record.value
            # Update settings from database
            self.telegram_bot_token = data.get('telegram_bot_token')
            self.telegram_chat_id = data.get('telegram_chat_id')
            self.smtp_host = data.get('smtp_host')
            self.smtp_port = data.get('smtp_port', 587)
            self.smtp_user = data.get('smtp_user')
            self.smtp_password = data.get('smtp_password')
            self.smtp_from = data.get('smtp_from', 'Boat Monitor <noreply@example.com>')
            self.smtp_to = data.get('smtp_to')
            self.log_level = data.get('log_level', 'INFO')
            self.check_interval_working = data.get('check_interval_working', '*/5 7-17 * * *')
            self.check_interval_off = data.get('check_interval_off', '*/3 0-6,18-23 * * *')
            self.page_timeout_ms = data.get('page_timeout_ms', 30000)
            self.max_retry_attempts = data.get('max_retry_attempts', 3)
            self.max_screenshots_per_url = data.get('max_screenshots_per_url', 50)
            self.screenshot_retention_days = data.get('screenshot_retention_days', 30)
            self.notification_cooldown_minutes = data.get('notification_cooldown_minutes', 10)
            self.max_notification_retries = data.get('max_notification_retries', 3)
            self.enable_semantic_comparison = data.get('enable_semantic_comparison', True)
            self.track_text_changes = data.get('track_text_changes', True)
            self.track_image_changes = data.get('track_image_changes', True)
            self.track_link_changes = data.get('track_link_changes', True)

    async def save_to_database(self, session, data: dict):
        """Save settings to database."""
        from sqlalchemy import select
        from backend.database import Setting
        from datetime import datetime

        result = await session.execute(select(Setting).where(Setting.key == 'app_settings'))
        setting_record = result.scalar_one_or_none()

        if setting_record:
            setting_record.value = data
            setting_record.updated_at = datetime.utcnow()
        else:
            setting_record = Setting(key='app_settings', value=data)
            session.add(setting_record)

        await session.commit()

        # Reload settings
        await self.load_from_database(session)

    def is_configured(self) -> bool:
        """Check if minimal configuration is set."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    def to_dict(self) -> dict:
        """Export settings as dictionary."""
        return {
            'telegram_bot_token': self.telegram_bot_token,
            'telegram_chat_id': self.telegram_chat_id,
            'smtp_host': self.smtp_host,
            'smtp_port': self.smtp_port,
            'smtp_user': self.smtp_user,
            'smtp_password': self.smtp_password,
            'smtp_from': self.smtp_from,
            'smtp_to': self.smtp_to,
            'log_level': self.log_level,
            'check_interval_working': self.check_interval_working,
            'check_interval_off': self.check_interval_off,
            'page_timeout_ms': self.page_timeout_ms,
            'max_retry_attempts': self.max_retry_attempts,
            'max_screenshots_per_url': self.max_screenshots_per_url,
            'screenshot_retention_days': self.screenshot_retention_days,
            'notification_cooldown_minutes': self.notification_cooldown_minutes,
            'max_notification_retries': self.max_notification_retries,
            'enable_semantic_comparison': self.enable_semantic_comparison,
            'track_text_changes': self.track_text_changes,
            'track_image_changes': self.track_image_changes,
            'track_link_changes': self.track_link_changes,
        }


# Global settings instance
settings = Settings()
