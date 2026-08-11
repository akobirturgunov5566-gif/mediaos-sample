"""AI layer — guarded read-only window over live operational state.

[Excerpt from the private MediaOS `mcp-bridge` server. Authentication, OAuth,
rate-limiting and file-bridge layers are removed for this public sample —
what remains is the core principle: the AI assistant NEVER gets raw database
access. Every query passes a strict SQL guard (single read-only statement,
comment-stripping that respects string literals, response size caps) before
touching the production database through a dedicated read-only DB role.]

Principle: deterministic core + AI on top. The ERP state machine decides;
the AI layer only *reads* live state (slots, tasks, KPIs) and explains it —
"nima bo'lyapti, nega, endi nima qilish kerak" — via MCP tools.
"""
from __future__ import annotations

import re

MAX_QUERY_ROWS = 500
MAX_RESPONSE_CHARS = 100_000

_SQL_OK = re.compile(r"^(select|with)\b", re.IGNORECASE)


def _strip_sql_comments(sql: str) -> str:
    """Izohlarni olib tashlaydi, LEKIN satr-literallarga TEGMAYDI.

    Ilgari izoh-kesish butun matn bo'ylab regex bilan yurardi va literal
    ichidagi ikki tireni ham izoh deb kesardi. Ya'ni `WHERE name = 'a--b'`
    so'rovi jimgina `WHERE name = 'a` ga aylanardi: yaxshi holatda sintaksis
    xatosi, yomon holatda BOSHQA natija — va aynan shu o'zgargan matn
    bajarilardi. Endi bir marta yurib, literal holatini kuzatamiz.

    Qamrov: bitta qo'shtirnoqli literal (ikkilangan qochirish bilan),
    qo'shtirnoqli identifikator, qatorli izoh, blok izoh. Dollar-quoting
    (`$$...$$`) `_SQL_OK` filtridan o'tmaydi (faqat SELECT/WITH), shuning
    uchun bu yerda ataylab qo'llanmaydi — noma'lum qismni «xavfsiz» deb
    ko'rsatgandan ko'ra rad etish yaxshi.
    """
    out: list[str] = []
    i, n = 0, len(sql)
    quote: str | None = None
    while i < n:
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == quote:
                # Ikkilangan tirnoq — literal ichidagi qochirish, yopilish EMAS.
                if i + 1 < n and sql[i + 1] == quote:
                    out.append(sql[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "-" and sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j == -1 else j
            out.append(" ")
            continue
        if ch == "/" and sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
            out.append(" ")
            continue
        out.append(ch)
        i += 1
    if quote:
        # Yopilmagan literal — «tuzatib» yubormaymiz, rad etamiz.
        raise ValueError("Unterminated string literal in SQL")
    return "".join(out)


def _has_statement_separator(sql: str) -> bool:
    """Literaldan TASHQARIDA nuqtali vergul bormi.

    `SELECT ';' AS x` haqli so'rov — sodda tekshiruv uni «Only ONE statement»
    deb rad etardi (soxta rad).
    """
    quote: str | None = None
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if quote:
            if ch == quote:
                if i + 1 < n and sql[i + 1] == quote:
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == ";":
            return True
        i += 1
    return False


def guard_sql(sql: str) -> str:
    """Yagona kirish nuqtasi: AI yuborgan SQL faqat shu darvozadan o'tadi."""
    s = _strip_sql_comments(sql).strip()
    # Oxiridagi nuqtali vergul(lar) — odatiy odat, ruxsat.
    while s.endswith(";"):
        s = s[:-1].strip()
    if not _SQL_OK.match(s):
        raise ValueError("Only a single SELECT/WITH statement is allowed")
    if _has_statement_separator(s):
        raise ValueError("Only ONE statement per call")
    return s


def guard_response_size(payload: str) -> str:
    """Bitta juda keng qator ham har qanday row-limitdan oshib ketishi mumkin."""
    if len(payload) > MAX_RESPONSE_CHARS:
        raise ValueError(
            f"Result too large ({len(payload)} chars). Narrow the columns or "
            f"lower max_rows (limit {MAX_RESPONSE_CHARS})."
        )
    return payload


# ── Representative read-only MCP tools built on the guard ────────────────────
# (`_pg_rows` in the real server executes through a read-only PostgreSQL role
#  with statement timeouts; connection details live only in server env files.)
#
# @mcp.tool()
# def query_db(sql: str, max_rows: int = 200) -> str:
#     """Run a read-only SQL query (single SELECT/WITH) against the prod DB."""
#     safe = guard_sql(sql)
#     return _pg_rows(safe, (), max_rows=min(int(max_rows), MAX_QUERY_ROWS))
#
# @mcp.tool()
# def get_slots(sana: str | None = None, limit: int = 100) -> str:
#     """Content-plan slots for one day — the AI reads live pipeline state
#     and explains delays/bottlenecks to leadership in plain language."""
#     ...
