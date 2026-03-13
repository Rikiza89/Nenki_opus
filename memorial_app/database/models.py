"""SQLAlchemy ORM models for memorial anniversary management."""

import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Index, create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, Session

Base = declarative_base()


class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    death_date = Column(String(10), nullable=False, index=True)  # ISO format YYYY-MM-DD
    source_file_path = Column(Text, nullable=True)  # Original Excel file path
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    attributes = relationship("Attribute", back_populates="person", cascade="all, delete-orphan")

    @property
    def death_date_obj(self) -> datetime.date:
        return datetime.date.fromisoformat(self.death_date)

    def __repr__(self):
        return f"<Person(id={self.id}, name='{self.name}', death_date='{self.death_date}')>"


class Attribute(Base):
    __tablename__ = "attributes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True)
    column_name = Column(String(200), nullable=False)
    value = Column(Text, nullable=True)

    person = relationship("Person", back_populates="attributes")

    __table_args__ = (
        Index("ix_attributes_person_column", "person_id", "column_name"),
    )

    def __repr__(self):
        return f"<Attribute(person_id={self.person_id}, '{self.column_name}'='{self.value}')>"
