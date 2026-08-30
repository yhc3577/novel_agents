from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, bigint_pk_type, jsonb


class Provider(Base):
    """LLM 供应商配置（首启由 config/models.yaml seed）。"""

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)  # deepseek / qwen / glm / kimi / doubao / minimax
    base_url: Mapped[str] = mapped_column(String(255))
    api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet 加密
    models: Mapped[dict] = mapped_column(jsonb())  # {"high","mid","low": model}
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # 同档降级顺序，小者优先
