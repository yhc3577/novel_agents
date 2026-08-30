"""owner 作用域仓储基类。

铁律（US-03）：所有业务查询必须显式带 owner_id 过滤；越权一律返回 None，
由调用方统一映射为 404，不泄露租户存在性。
"""

from sqlalchemy.ext.asyncio import AsyncSession


class OwnerRepo:
    def __init__(self, db: AsyncSession):
        self.db = db
