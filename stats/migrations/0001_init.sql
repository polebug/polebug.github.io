-- Running totals per page ("blog:/2024/05/01/foo/", "home:/") and for the whole site ("site").
CREATE TABLE counts (
  key TEXT PRIMARY KEY,
  views INTEGER NOT NULL DEFAULT 0,
  visitors INTEGER NOT NULL DEFAULT 0
);

-- Who has been counted today: a salted hash of IP and browser, never the IP itself. Pruned daily.
CREATE TABLE seen (
  day TEXT NOT NULL,
  key TEXT NOT NULL,
  visitor TEXT NOT NULL,
  PRIMARY KEY (day, key, visitor)
) WITHOUT ROWID;
