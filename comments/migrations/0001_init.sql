-- Immutable document IDs survive URL/title changes. Revisions identify the text an anchor saw.
CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  canonical_path TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  current_revision_id TEXT,
  comments_enabled INTEGER NOT NULL DEFAULT 1 CHECK(comments_enabled IN (0,1)),
  created_at TEXT NOT NULL,
  FOREIGN KEY(current_revision_id, id) REFERENCES document_revisions(id, document_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE document_aliases (
  path TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id)
);
CREATE TABLE document_revisions (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id),
  text_sha256 TEXT NOT NULL,
  text_content TEXT NOT NULL,
  normalization TEXT NOT NULL DEFAULT 'article-text-v1',
  created_at TEXT NOT NULL,
  UNIQUE(document_id, text_sha256),
  UNIQUE(id, document_id)
);
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('github','guest','imported')),
  display_name TEXT NOT NULL CHECK(length(display_name) BETWEEN 1 AND 80),
  blocked INTEGER NOT NULL DEFAULT 0 CHECK(blocked IN (0,1)),
  created_at TEXT NOT NULL
);
CREATE TABLE identities (
  provider TEXT NOT NULL,
  subject TEXT NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id),
  PRIMARY KEY(provider, subject),
  UNIQUE(provider, user_id)
);
CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  csrf TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE INDEX sessions_expiry ON sessions(expires_at);
CREATE TABLE oauth_states (
  state_hash TEXT PRIMARY KEY,
  verifier TEXT NOT NULL,
  return_path TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);
-- A quote is immutable evidence, not an editable DOM selector or pixel coordinate.
-- Offsets are Unicode code points in the stored normalized text, end exclusive.
CREATE TABLE anchors (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  revision_id TEXT NOT NULL,
  selector_version INTEGER NOT NULL DEFAULT 1 CHECK(selector_version = 1),
  exact TEXT NOT NULL CHECK(length(exact) BETWEEN 1 AND 5000),
  prefix TEXT NOT NULL DEFAULT '',
  suffix TEXT NOT NULL DEFAULT '',
  start_offset INTEGER NOT NULL CHECK(start_offset >= 0),
  end_offset INTEGER NOT NULL CHECK(end_offset > start_offset),
  created_at TEXT NOT NULL,
  FOREIGN KEY(revision_id, document_id) REFERENCES document_revisions(id, document_id),
  UNIQUE(id, document_id)
);
CREATE TABLE anchor_resolutions (
  anchor_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  revision_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('exact','relocated','ambiguous','orphaned')),
  start_offset INTEGER,
  end_offset INTEGER,
  resolved_at TEXT NOT NULL,
  PRIMARY KEY(anchor_id, revision_id),
  FOREIGN KEY(anchor_id, document_id) REFERENCES anchors(id, document_id),
  FOREIGN KEY(revision_id, document_id) REFERENCES document_revisions(id, document_id),
  CHECK((status IN ('ambiguous','orphaned') AND start_offset IS NULL AND end_offset IS NULL)
    OR (status IN ('exact','relocated') AND start_offset >= 0 AND end_offset > start_offset))
);
CREATE TABLE threads (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id),
  anchor_id TEXT,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','locked','hidden')),
  created_at TEXT NOT NULL,
  FOREIGN KEY(anchor_id, document_id) REFERENCES anchors(id, document_id)
);
CREATE UNIQUE INDEX one_page_thread ON threads(document_id) WHERE anchor_id IS NULL;
CREATE INDEX threads_document ON threads(document_id, anchor_id);
CREATE TABLE comments (
  id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL REFERENCES threads(id),
  parent_id TEXT,
  author_id TEXT NOT NULL REFERENCES users(id),
  author_name TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','published','hidden','deleted')),
  source TEXT NOT NULL DEFAULT 'native' CHECK(source IN ('native','github')),
  external_id TEXT UNIQUE,
  source_url TEXT,
  request_key TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  published_at TEXT,
  UNIQUE(id, thread_id),
  UNIQUE(author_id, request_key),
  FOREIGN KEY(parent_id, thread_id) REFERENCES comments(id, thread_id),
  CHECK(parent_id IS NULL OR parent_id <> id)
);
CREATE INDEX comment_feed ON comments(thread_id, created_at, id);
CREATE INDEX comment_moderation ON comments(status, created_at, id);
CREATE TABLE moderation_events (
  id TEXT PRIMARY KEY,
  comment_id TEXT NOT NULL REFERENCES comments(id),
  actor_id TEXT NOT NULL REFERENCES users(id),
  action TEXT NOT NULL,
  previous_status TEXT NOT NULL,
  next_status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE rate_limits (
  key TEXT NOT NULL,
  window INTEGER NOT NULL,
  count INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  PRIMARY KEY(key, window)
);
CREATE INDEX rate_expiry ON rate_limits(expires_at);
