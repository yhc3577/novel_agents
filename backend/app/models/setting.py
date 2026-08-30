from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, bigint_pk_type


class UserSetting(Base, TimestampMixin):
    """用户三档模型选择与默认项目。"""

    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    tier_high: Mapped[str | None] = mapped_column(String(128), nullable=True)  # "provider:model"
    tier_mid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tier_low: Mapped[str | None] = mapped_column(String(128), nullable=True)
    default_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
