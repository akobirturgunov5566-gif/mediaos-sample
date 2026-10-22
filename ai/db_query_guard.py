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


_DOLLAR_TAG = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")


def _is_escape_string_start(sql: str, i: int) -> bool:
    """`E'...'` (yoki `e'...'`) — PostgreSQL escape-string literali boshlanishimi.

    Bunday literal ichida `\\'` tirnoqni yopmaydi; oddiy `'...'` ichida esa
    teskari chiziq oddiy belgi (standard_conforming_strings=on).
    """
    if i == 0 or sql[i - 1] not in ("E", "e"):
        return False
    # `E` dan oldin identifikator belgisi bo'lsa — bu prefiks emas (masalan `name'`).
    return i < 2 or not (sql[i - 2].isalnum() or sql[i - 2] == "_")


def _skip_literal(sql: str, i: int, out: list[str] | None) -> int:
    """`sql[i]` ochuvchi tirnoq. Literal yopilgandan KEYINGI indeksni qaytaradi.

    Qamrov: `'...'` (ikkilangan `''` qochirish bilan), `"..."` identifikator,
    `E'...'` (teskari chiziq qochirish bilan). Yopilmagan literal — ValueError.
    `out` berilsa literal o'zgarishsiz unga ko'chiriladi.
    """
    quote = sql[i]
    escapes = quote == "'" and _is_escape_string_start(sql, i)
    n = len(sql)
    j = i + 1
    while j < n:
        ch = sql[j]
        if escapes and ch == "\\" and j + 1 < n:
            j += 2
            continue
        if ch == quote:
            if j + 1 < n and sql[j + 1] == quote:
                # Ikkilangan tirnoq — literal ichidagi qochirish, yopilish EMAS.
                j += 2
                continue
            if out is not None:
                out.append(sql[i : j + 1])
            return j + 1
        j += 1
    # Yopilmagan literal — «tuzatib» yubormaymiz, rad etamiz.
    raise ValueError("Unterminated string literal in SQL")


def _strip_sql_comments(sql: str) -> str:
    """Izohlarni olib tashlaydi, LEKIN satr-literallarga TEGMAYDI.

    Ilgari izoh-kesish butun matn bo'ylab regex bilan yurardi va literal
    ichidagi ikki tireni ham izoh deb kesardi. Ya'ni `WHERE name = 'a--b'`
    so'rovi jimgina `WHERE name = 'a` ga aylanardi: yaxshi holatda sintaksis
    xatosi, yomon holatda BOSHQA natija — va aynan shu o'zgargan matn
    bajarilardi. Endi bir marta yurib, literal holatini kuzatamiz.

    Qamrov: bitta qo'shtirnoqli literal (ikkilangan qochirish bilan),
    `E'...'` escape-literal (teskari chiziq qochirish bilan), qo'shtirnoqli
    identifikator, qatorli izoh, blok izoh.

    Dollar-quoting (`$$...$$`, `$tag$...$tag$`) ATAYLAB rad etiladi: u
    `SELECT` dan KEYIN ham kelishi mumkin, va ichidagi bitta `'` skanerni
    «literal ichidaman» deb aldab, orqasidan kelgan `; DELETE ...` ni
    yashirar edi. Noma'lum qismni «xavfsiz» deb ko'rsatgandan ko'ra rad
    etish yaxshi.
    """
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in ("'", '"'):
            i = _skip_literal(sql, i, out)
            continue
        if ch == "$" and _DOLLAR_TAG.match(sql, i):
            raise ValueError("Dollar-quoted strings are not allowed")
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
    return "".join(out)


def _has_statement_separator(sql: str) -> bool:
    """Literaldan TASHQARIDA nuqtali vergul bormi.

    `SELECT ';' AS x` haqli so'rov — sodda tekshiruv uni «Only ONE statement»
    deb rad etardi (soxta rad). Literal-skaner `_strip_sql_comments` bilan
    BIR XIL (`_skip_literal`) — ikki skaner bir-biridan farq qilsa, biri
    «ichkarida» deb o'ylagan joyni ikkinchisi «tashqarida» deb o'qiydi.
    """
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in ("'", '"'):
            i = _skip_literal(sql, i, None)
            continue
        if ch == ";":
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
