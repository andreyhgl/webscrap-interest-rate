# scrape_rates.py
#
# A script that fetches Swedbank's mortgage rate page, extracts the rate table,
# and appends today's values to a CSV file — but only when something has
# actually changed since the last saved row.

# ~~ IMPORTS ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #

# Python groups related code into "modules". `import` pulls them in.
# Standard library (ships with Python, no install needed):
import csv                  # helpers for reading/writing CSV files
import re                   # regular expressions — pattern matching on strings
from datetime import date   # `from X import Y` grabs just Y out of module X
from pathlib import Path    # modern, object-oriented way to handle file paths

# Third-party libraries (must be installed via pip):
import requests               # makes HTTP requests (fetches web pages)
from bs4 import BeautifulSoup # parses HTML into a searchable tree structure


# ~~ CONSTANTS ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #

# ALL_CAPS is a Python convention meaning "this is a constant, don't reassign it".
# Python doesn't actually enforce it — it's just a signal to other programmers.
URL = "https://www.swedbank.se/privat/boende-och-bolan/bolanerantor.html"

# Path("rates.csv") creates a Path object. It's smarter than a plain string:
# it has methods like .exists(), .open(), and works across Windows/Mac/Linux.
OUTPUT = Path("swedbank.csv")

# Maps the Swedish binding labels from the website to short, code-friendly keys.
# Any binding NOT in this dict (e.g. "Banklån*") will be skipped during scraping.
BINDING_MAP = {
  "3 månader": "3m",
  "1 år":  "1y",
  "2 år":  "2y",
  "3 år":  "3y",
  "4 år":  "4y",
  "5 år":  "5y",
  "6 år":  "6y",
  "7 år":  "7y",
  "8 år":  "8y",
  "9 år":  "9y",
  "10 år": "10y",
}

# Column order for the CSV. Defined once and used everywhere (writer, duplicate
# check) so there's a single source of truth for what "the columns" are.
# These are the short binding keys in the exact order they'll appear as CSV columns.
RATE_COLUMNS = ["3m", "1y", "2y", "3y", "4y", "5y", "6y", "7y", "8y", "9y", "10y"]

# Full column list including "date" as the first column. List concatenation
# with `+` creates a new list from two others.
FIELDNAMES = ["date"] + RATE_COLUMNS


# ~~ HELPER FUNCTION: parse a rate string into a number ~~~~~~~~~~~~~~~~~~~~~~ #

# `def` defines a function. The `text: str` is a "type hint" — it tells readers
# (and editors) that `text` should be a string. Python doesn't enforce types at
# runtime, but hints help catch bugs and make code self-documenting.
def parse_rate(text: str):
  """Turn '2,69 %' into 2.69, or None if the cell is empty.

  Text inside triple-quotes right after `def` is a "docstring" — Python's
  built-in way to document what a function does. Tools like help() read it.
  """
  # Strip whitespace from both ends, and replace non-breaking spaces (\xa0)
  # with regular spaces. Websites often use \xa0 between number and "%" so
  # the browser doesn't wrap them onto separate lines — but it looks invisible.
  text = text.strip().replace("\xa0", " ")

  # If the cell is empty (e.g. Snittränta for 9 years is blank),
  # return None instead of crashing. None is Python's "nothing" value.
  if not text:
    return None

  # Regex time. `\d+` means "one or more digits". `[,.]` means "a comma or dot".
  # So `\d+[,.]\d+` matches things like "2,69" or "2.69".
  # Parentheses create a "capture group" so we can extract just that part.
  match = re.search(r"(\d+[,.]\d+)", text)
  # The `r"..."` is a "raw string" — backslashes are treated literally.
  # Always use raw strings for regex patterns.

  # If a match was found, get the captured group, swap comma for dot
  # (Python's float() wants dots), and convert to a float.
  # Otherwise return None. This is a "ternary expression":
  # value_if_true if condition else value_if_false.
  return float(match.group(1).replace(",", ".")) if match else None


def ensure_trailing_newline():
  """Make sure the CSV file ends with a newline before we append to it.

  Why this matters: if the file's last byte isn't a newline character,
  opening in "a" (append) mode starts writing right at the end — which
  means our new row gets glued onto the end of the previous row, producing
  garbage like:
      2026-04-16,3.94,3.58,...,4.292026-05-02,3.94,3.48,...,4.29
  instead of two separate lines. This can happen if:
    - someone edited the file by hand and their editor stripped the final newline
    - a different tool wrote the file without a trailing newline
    - git or a merge tool mangled the line ending

  We open in "rb+" (read-binary-update) so we can seek to the last byte and
  check it. Binary mode ("b") is important because text mode on Windows
  translates \\r\\n to \\n on read, which would give us a false positive.
  "r+" means read-and-write on an existing file (vs "a" which only appends).
  """
  if not OUTPUT.exists():
    return  # nothing to fix if the file doesn't exist yet

  with OUTPUT.open("rb+") as f:
    # seek(offset, whence) moves the file cursor. whence=2 means "from the end".
    # So seek(-1, 2) positions us at the very last byte in the file.
    f.seek(-1, 2)
    # f.read(1) reads one byte from that position. In binary mode it
    # returns a bytes object like b'\n', not a string.
    last_byte = f.read(1)
    if last_byte != b"\n":
      # The file doesn't end with a newline — write one at the end.
      # Since we just read the last byte, the cursor is already at the end.
      f.write(b"\n")


# ~~ MAIN SCRAPING FUNCTION ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #

def scrape():
  """Fetch the page and return today's rates as a single flat dict.

  Returns a dict like:
    {"date": "2026-04-16", "3m_snitt": 2.69, "3m_list": 3.94, ...}
  One dict = one full snapshot for one day.
  """

  # requests.get() sends an HTTP GET request and returns a Response object.
  # We pass custom headers because some sites block the default User-Agent
  # that `requests` sends (it contains "python-requests"). Pretending to be
  # a browser is a common, harmless workaround for simple scrapes.
  # timeout=30 means: give up if no response in 30 seconds (prevents hangs).
  resp = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
  
  # Raises an exception if the server returned an error status (404, 500, etc).
  # Better to crash loudly than silently parse an error page.    
  resp.raise_for_status()

  # Feed the HTML text into BeautifulSoup. "html.parser" is Python's built-in
  # HTML parser — no extra install needed. The result is a tree we can search.
  soup = BeautifulSoup(resp.text, "html.parser")

  # ---- Find the right table ----
  # The page may contain many <table> elements. We want the one with a header
  # row mentioning "Bindningstid" (the Swedish word for "binding period").
  # Searching by content is more robust than searching by CSS class — classes
  # often change when sites redesign, but the Swedish word won't.
  table = None  # start with "nothing found yet"
  for t in soup.find_all("table"):
    # find_all returns a list; find() returns the first match or None.
    # get_text() returns all text inside the tag, stripped of HTML.
    if t.find("th") and "Bindningstid" in t.get_text():
      table = t
      break  # stop looping as soon as we find it

  # If we never found a matching table, something is wrong.
  # `raise` throws an exception, which stops the script with an error message.
  # We use RuntimeError for "something unexpected happened at runtime".
  if table is None:
    raise RuntimeError("Rate table not found — page structure may have changed")

  # Start with just the date. We add rate columns to this dict as we go.
  row = {"date": date.today().isoformat()}

  # HTML tables have <thead> (header) and <tbody> (body). We only want body rows.
  # tr = "table row", td = "table data" (cell).
  for tr in table.find("tbody").find_all("tr"):
    # List comprehension: a compact way to build a list.
    # "give me td.get_text(strip=True) for each td in all tds of this row".
    # strip=True trims whitespace from each cell's text.
    cells = [td.get_text(strip=True) for td in tr.find_all("td")]

    # Skip malformed rows with fewer than 3 cells. Defensive programming:
    # don't assume the page is perfectly structured.
    if len(cells) < 3:
      continue
      
    # "Tuple unpacking" — assign multiple variables from a list in one line.
    binding, snitt, list_rate = cells[0], cells[1], cells[2]

    # Translate Swedish label to short form; None means "skip this row"
    # (that's how "Banklån*" gets filtered out).
    short = BINDING_MAP.get(binding)
    if short is None:
      continue

    row[short] = parse_rate(list_rate)

  return row

# ---- READ THE LAST SAVED SNAPSHOT ----
def read_last_row():
  """Return the last row of the CSV as a dict, or None if file is empty/missing.

  We read the whole file because csv has no built-in "jump to end" — the file
  format doesn't support random access. For a file that grows by one row per
  day, this is a non-issue; it'd still be tiny after decades.
  """
  # If the file doesn't exist yet (first ever run), there's nothing to read.
  if not OUTPUT.exists():
    return None

  # Mode "r" = read. `with ... as f:` is a "context manager" — it guarantees
  # the file is properly closed when the block ends, even if an error occurs.
  with OUTPUT.open("r", encoding="utf-8") as f:
    # DictReader turns each CSV row into a dict keyed by the header names.
    # list() exhausts the reader into a list of row-dicts so we can index it.
    rows = list(csv.DictReader(f))

  # rows[-1] is the last row (negative indices count from the end).
  # If the file only had a header (no data rows), `rows` is empty — return None.
  # This is a ternary expression again: value_if_true if condition else value_if_false.
  return rows[-1] if rows else None


# ---- CHECK IF TODAY'S SNAPSHOT DIFFERS FROM THE LAST SAVED ONE ----
def is_duplicate(new_row, last_row):
  """Return True if new_row has the same rate values as last_row.

  We compare values in their string form — that's how they'll look once
  written to the CSV, so both sides are apples-to-apples. We only check
  the rate columns; the date is irrelevant for 'has anything changed?'.
  """
  # No previous snapshot means nothing to compare against → definitely not a duplicate.
  if last_row is None:
    return False

  # Loop through each rate column and compare old vs new values.
  for col in RATE_COLUMNS:
    # Format the new value the same way the CSV writer would store it.
    # (None → "", floats → their str() form, e.g. 3.94 → "3.94".)
    new_value = "" if new_row.get(col) is None else str(new_row[col])
    
    # last_row came straight from DictReader, so its values are already strings.
    # .get(col, "") returns "" if the column is missing from the old row —
    # defensive in case the CSV structure ever changed between runs.
    old_value = last_row.get(col, "")
    
    if new_value != old_value:
      # Found a column that differs. No need to check the rest —
      # we already know it's NOT a duplicate. This is called "short-circuiting":
      # return as soon as the answer is known.
      return False

  # Got through every column without finding a difference → it's a duplicate.
  return True


# ---- APPEND A NEW SNAPSHOT TO THE CSV ----
def append_row(row):
  """Append a single snapshot to the CSV, creating it with a header if new."""
  new_file = not OUTPUT.exists()

  # Guard against a missing trailing newline before appending.
  if not new_file:
    ensure_trailing_newline()

  with OUTPUT.open("a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    
    if new_file:
      writer.writeheader()
    
    writer.writerow(row)


# ~~ ENTRY POINT ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #

# This `if` block is a Python idiom. When you run `python scrape_rates.py`,
# Python sets the special variable __name__ to "__main__". But if another
# file *imports* this one, __name__ is set to "scrape_rates" instead.
# This check means "only run the code below when this file is executed directly,
# not when it's imported". It's good practice so your helpers stay reusable.
if __name__ == "__main__":
  # 1. Scrape today's rates from the website.
  row = scrape()

  # 2. Load the last saved snapshot (or None if this is the first run).
  last_row = read_last_row()

  # 3. Decide whether to save. Only append if rates actually changed.
  if is_duplicate(row, last_row):
    print(f"No changes since last run — nothing to save ({OUTPUT})")
  else:
    # ---- Verbose output: show what changed ----
    print(f"Changes detected in {OUTPUT}")
    print(f"Date: {row['date']}")
    print("")

    if last_row is None:
      # First ever run — no previous data to compare against.
      print("First run — all values are new:")
      for col in RATE_COLUMNS:
        value = row.get(col)
        # Format None as "-" so it's obvious in the log rather than
        # printing the word "None" which could be confused with a bug.
        display = "-" if value is None else value
        print(f"  {col:>4}: {display}")
    
    else:
      # Show each column: old value → new value, with a marker for changes.
      print(f"  {'':>4}  {'old':>8}  {'new':>8}")
      print(f"  {'':>4}  {'---':>8}  {'---':>8}")
      for col in RATE_COLUMNS:
        new_value = "" if row.get(col) is None else str(row[col])
        old_value = last_row.get(col, "")
        # Build a marker: "*" if this column changed, " " if unchanged.
        # Makes it easy to scan a long list for the one thing that moved.
        marker = "*" if new_value != old_value else " "
        # Format for display: show "-" instead of empty strings.
        old_display = old_value if old_value else "-"
        new_display = new_value if new_value else "-"
        print(f"  {col:>4}: {old_display:>8} → {new_display:>8} {marker}")

    print("")
    append_row(row)
    print(f"Saved snapshot to {OUTPUT}")