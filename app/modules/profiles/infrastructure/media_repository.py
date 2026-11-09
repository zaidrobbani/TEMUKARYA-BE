from datetime import datetime

from sqlalchemy import Boolean, CHAR, ForeignKey, String, delete, select, text, update
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base
from app.modules.profiles.domain.media import PortfolioMedia
from app.modules.profiles.infrastructure.models import PortfolioModel
from app.modules.profiles.infrastructure.repositories import SqlAlchemyPortfolioRepository


class PortfolioMediaModel(Base):
    __tablename__ = "portfolio_media"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("portfolios.id", ondelete="CASCADE"))
    storage_key: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True))
    uploaded_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)"))
    sort_order: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), server_default="0")
    is_cover: Mapped[bool] = mapped_column(Boolean, server_default="0")


class SqlAlchemyMediaRepository:
    def __init__(self, session: Session):
        self.session = session

    def owns(self, portfolio_id, owner, lock=True):
        query = select(PortfolioModel.id).where(
            PortfolioModel.id == portfolio_id, PortfolioModel.freelancer_id == owner,
        )
        if lock:
            query = query.with_for_update()
        return self.session.scalar(query) is not None

    def list(self, portfolio_id):
        # Current/locking read also avoids a stale REPEATABLE READ snapshot after upload authorization.
        rows = self.session.scalars(select(PortfolioMediaModel).where(
            PortfolioMediaModel.portfolio_id == portfolio_id,
        ).order_by(PortfolioMediaModel.sort_order, PortfolioMediaModel.id)
            .with_for_update().execution_options(populate_existing=True)).all()
        return [self._entity(row) for row in rows]

    def add(self, media):
        row = PortfolioMediaModel(**{key: value for key, value in vars(media).items() if key != "uploaded_at"})
        self.session.add(row)
        self.session.flush()
        self.session.refresh(row)
        return self._entity(row)

    def arrange(self, portfolio_id, ids, cover_id):
        for order, media_id in enumerate(ids):
            self.session.execute(update(PortfolioMediaModel).where(
                PortfolioMediaModel.portfolio_id == portfolio_id, PortfolioMediaModel.id == media_id,
            ).values(sort_order=order, is_cover=(media_id == cover_id)))

    def delete(self, portfolio_id, media_id):
        self.session.execute(delete(PortfolioMediaModel).where(
            PortfolioMediaModel.portfolio_id == portfolio_id, PortfolioMediaModel.id == media_id,
        ))

    def delete_portfolio(self, portfolio_id, owner):
        # Explicit metadata removal also supports isolated SQLite tests without FK enforcement.
        self.session.execute(delete(PortfolioMediaModel).where(PortfolioMediaModel.portfolio_id == portfolio_id))
        SqlAlchemyPortfolioRepository(self.session).delete(portfolio_id, owner)

    @staticmethod
    def _entity(row):
        return PortfolioMedia(**{field: getattr(row, field) for field in PortfolioMedia.__dataclass_fields__})
