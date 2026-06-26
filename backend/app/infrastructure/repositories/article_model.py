import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, SmallInteger, Integer, Text, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ArticleModel(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_origin: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    preprocessed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_preprocessed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    preprocessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationship to sentences
    sentences: Mapped[list["ArticleSentenceModel"]] = relationship(
        "ArticleSentenceModel", 
        back_populates="article", 
        cascade="all, delete-orphan"
    )


class ArticleSentenceModel(Base):
    __tablename__ = "article_sentences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sentence_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sentence_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # NLP & Annotation
    sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    initial_sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    annotation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_manual_annotated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    validation_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    annotator_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    dataset_version: Mapped[str | None] = mapped_column(Text, nullable=True)

    preprocessed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_preprocessed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    preprocessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationship to parent article
    article: Mapped["ArticleModel"] = relationship("ArticleModel", back_populates="sentences")


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    action: Mapped[str] = mapped_column(Text, nullable=False) # e.g., 'upload_csv', 'annotate_sentence', 'run_preprocessing'
    entity_id: Mapped[str | None] = mapped_column(Text, nullable=True) # e.g., article_id, sentence_id, or batch_id
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
