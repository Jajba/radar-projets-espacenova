from datetime import datetime, timezone
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Text, DateTime, Float, Boolean, UniqueConstraint, select, func
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
metadata = MetaData()

sources = Table('sources', metadata,
    Column('id', Integer, primary_key=True),
    Column('source_code', String(80), unique=True, nullable=False),
    Column('name', String(300), nullable=False),
    Column('structure_type', String(120)),
    Column('department', String(20)),
    Column('url', Text, nullable=False),
    Column('alt_url', Text),
    Column('page_type', String(120)),
    Column('prep_status', String(120)),
    Column('audit_priority', String(30)),
    Column('active', Boolean, default=True),
    Column('notes', Text),
    Column('radar_family', String(120)),
    Column('last_checked_at', DateTime(timezone=True)),
    Column('last_ok_at', DateTime(timezone=True)),
    Column('consecutive_errors', Integer, default=0),
)

documents = Table('documents', metadata,
    Column('id', Integer, primary_key=True),
    Column('source_id', Integer, nullable=False),
    Column('url', Text, nullable=False),
    Column('title', Text),
    Column('content_hash', String(64)),
    Column('content_type', String(120)),
    Column('published_hint', String(80)),
    Column('first_seen_at', DateTime(timezone=True), nullable=False),
    Column('last_seen_at', DateTime(timezone=True), nullable=False),
    Column('processed_at', DateTime(timezone=True)),
    Column('status', String(50)),
    Column('text_chars', Integer, default=0),
    Column('ocr_required', Boolean, default=False),
    Column('error', Text),
    UniqueConstraint('source_id','url', name='uq_document_source_url')
)

leads = Table('leads', metadata,
    Column('id', Integer, primary_key=True),
    Column('lead_code', String(100), unique=True, nullable=False),
    Column('source_id', Integer, nullable=False),
    Column('document_id', Integer),
    Column('detected_at', DateTime(timezone=True), nullable=False),
    Column('company_sci', Text),
    Column('end_user', Text),
    Column('territory', Text),
    Column('commune', Text),
    Column('zone_site', Text),
    Column('signal_family', String(120)),
    Column('signal_type', String(200)),
    Column('project', Text),
    Column('commercial_score', String(1)),
    Column('convergence_score', Float),
    Column('confidence_pct', Float),
    Column('facts', Text),
    Column('deductions', Text),
    Column('unknowns', Text),
    Column('recommended_action', Text),
    Column('evidence_excerpt', Text, nullable=False),
    Column('source_url', Text, nullable=False),
    Column('status', String(50), default='Nouveau'),
)

errors = Table('errors', metadata,
    Column('id', Integer, primary_key=True),
    Column('source_id', Integer),
    Column('occurred_at', DateTime(timezone=True), nullable=False),
    Column('url', Text),
    Column('error_type', String(120)),
    Column('detail', Text),
)

runs = Table('runs', metadata,
    Column('id', Integer, primary_key=True),
    Column('started_at', DateTime(timezone=True), nullable=False),
    Column('finished_at', DateTime(timezone=True)),
    Column('sources_total', Integer, default=0),
    Column('sources_ok', Integer, default=0),
    Column('sources_error', Integer, default=0),
    Column('documents_new', Integer, default=0),
    Column('leads_new', Integer, default=0),
)

def utcnow():
    return datetime.now(timezone.utc)

def init_db():
    metadata.create_all(engine)

def scalar(stmt):
    with engine.begin() as conn:
        return conn.execute(stmt).scalar()
