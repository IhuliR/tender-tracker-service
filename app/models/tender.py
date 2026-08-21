from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TenderStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    WON = "won"
    LOST = "lost"


tender_status_enum = SqlEnum(
    TenderStatus,
    name="tender_status",
    values_callable=lambda enum_class: [status.value for status in enum_class],
    metadata=Base.metadata,
)


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TenderStatus] = mapped_column(
        tender_status_enum,
        default=TenderStatus.DRAFT,
        server_default=TenderStatus.DRAFT.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    status_history: Mapped[list["TenderStatusHistory"]] = relationship(
        back_populates="tender"
    )


class TenderStatusHistory(Base):
    __tablename__ = "tender_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id"),
        index=True,
        nullable=False,
    )
    old_status: Mapped[TenderStatus] = mapped_column(
        tender_status_enum,
        nullable=False,
    )
    new_status: Mapped[TenderStatus] = mapped_column(
        tender_status_enum,
        nullable=False,
    )
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    tender: Mapped[Tender] = relationship(back_populates="status_history")
