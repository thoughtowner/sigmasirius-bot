import asyncio
import logging
import os
import re
from pathlib import Path

from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError

from src.model import meta
from src.storage.db import engine


async def _apply_sql_file(conn, path: Path):
    if not path.exists():
        logging.warning('SQL file not found: %s', path)
        return
    sql = path.read_text()
    try:
        # exec_driver_sql can't prepare multiple statements at once when
        # using asyncpg (error: "cannot insert multiple commands into a
        # prepared statement"). Split the file into top-level statements
        # and execute them one-by-one. This splitter understands single
        # and double quotes, dollar-quoted blocks, and SQL comments.
        def _split_statements(s: str):
            stmts = []
            cur = []
            i = 0
            n = len(s)
            in_sq = False
            in_dq = False
            in_dollar = None
            in_line_comment = False
            in_block_comment = False

            while i < n:
                ch = s[i]

                # handle line comments
                if not in_sq and not in_dq and not in_dollar and not in_block_comment:
                    if s.startswith('--', i):
                        in_line_comment = True
                        cur.append(ch)
                        i += 1
                        # will advance normally; skip handling here
                    elif s.startswith('/*', i):
                        in_block_comment = True
                        cur.append(ch)
                        i += 1
                        i += 0

                if in_line_comment:
                    cur.append(ch)
                    if ch == '\n':
                        in_line_comment = False
                    i += 1
                    continue

                if in_block_comment:
                    cur.append(ch)
                    if s.startswith('*/', i):
                        cur.append(s[i+1])
                        i += 2
                        in_block_comment = False
                    else:
                        i += 1
                    continue

                # dollar-quote start/end: $tag$ ... $tag$
                if not in_sq and not in_dq:
                    if in_dollar is None and ch == '$':
                        # try to read tag
                        j = i + 1
                        tag = ''
                        while j < n and s[j] != '$' and s[j] != '\n' and s[j] != '\r':
                            tag += s[j]
                            j += 1
                        if j < n and s[j] == '$':
                            in_dollar = '$' + tag + '$'
                            # append the opener
                            cur.append(in_dollar)
                            i = j + 1
                            continue
                    elif in_dollar is not None and s.startswith(in_dollar, i):
                        cur.append(in_dollar)
                        i += len(in_dollar)
                        in_dollar = None
                        continue

                if in_dollar is not None:
                    cur.append(ch)
                    i += 1
                    continue

                # quotes
                if ch == "'" and not in_dq:
                    cur.append(ch)
                    in_sq = not in_sq
                    i += 1
                    continue
                if ch == '"' and not in_sq:
                    cur.append(ch)
                    in_dq = not in_dq
                    i += 1
                    continue

                # split on semicolon at top level
                if ch == ';' and not in_sq and not in_dq and in_dollar is None:
                    cur.append(ch)
                    stmt = ''.join(cur).strip()
                    if stmt:
                        stmts.append(stmt)
                    cur = []
                    i += 1
                    continue

                cur.append(ch)
                i += 1

            tail = ''.join(cur).strip()
            if tail:
                stmts.append(tail)
            return stmts

        statements = _split_statements(sql)
        for stmt in statements:
            if not stmt:
                continue
            # remove SQL comments to detect comment-only statements
            clean = re.sub(r"(--.*?$)|(/\*.*?\*/)", "", stmt, flags=re.MULTILINE | re.DOTALL)
            if not clean.strip():
                continue
            try:
                await conn.exec_driver_sql(stmt)
            except Exception:
                logging.exception('Failed to exec statement (continuing): %s', stmt[:200])
                continue
        logging.info('Applied SQL: %s', path)
    except Exception:
        logging.exception('Failed to apply SQL file: %s', path)


async def migrate():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(meta.metadata.create_all)

            # Apply production triggers (always)
            base = Path(__file__).resolve().parents[1]
            prod_sql = base / 'sql' / 'triggers' / 'reservation_triggers.sql'
            await _apply_sql_file(conn, prod_sql)

            # # Optionally apply test-only triggers when env var is set
            # if os.getenv('APPLY_TEST_TRIGGERS') == '1':
            #     test_sql = base / 'sql' / 'triggers' / 'reservation_test_triggers.sql'
            #     await _apply_sql_file(conn, test_sql)
            #     # Invalidate prepared statement plans in other connections/pools
            #     # (asyncpg raises InvalidCachedStatementError when schema/config changes).
            #     try:
            #         await engine.dispose()
            #         logging.info('Disposed engine after applying test triggers')
            #     except Exception:
            #         logging.exception('Failed to dispose engine after applying test triggers')

    except IntegrityError:
        logging.exception('Already exists')


if __name__ == '__main__':
    asyncio.run(migrate())
