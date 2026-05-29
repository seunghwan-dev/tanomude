import datetime as dt

from sqlalchemy import Boolean, Date, DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TripApplication(Base):
    __tablename__ = "trip_application"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dest: Mapped[str] = mapped_column(String(12), nullable=False)
    dept_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    ret_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    proj: Mapped[str] = mapped_column(String(8), nullable=False)
    overseas: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
