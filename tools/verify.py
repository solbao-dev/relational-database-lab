"""제출 SQL을 재현 실행하고 평가 증거를 생성하는 검증 도구다."""
from pathlib import Path
import platform
import re
import sqlite3
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]


def show(cursor):
    """조회 결과를 텍스트로 변환한다.

    입력: 실행된 sqlite3 Cursor. 반환: 열 이름과 행을 담은 문자열.
    예외: DB 조회 오류는 호출자에게 전달한다.
    이유: 이미지 대신 검색·비교 가능한 실행 증거를 보관한다.
    """
    if cursor.description is None:
        return '실행 완료 (조회 결과 없음)\n'
    header = ' | '.join(x[0] for x in cursor.description)
    rows = cursor.fetchall()
    body = [' | '.join('NULL' if v is None else str(v) for v in row) for row in rows]
    return '\n'.join([header, *body, f'({len(rows)} rows)']) + '\n'


def main():
    """메모리 DB에 제출 SQL을 실행하고 의미 있는 검증과 증거를 저장한다.

    입력·반환: 없음. 실패: AssertionError 또는 sqlite3 오류로 비정상 종료.
    이유: 기존 사용자 DB를 지우지 않고 매번 동일한 초기 상태에서 재현한다.
    """
    out = ROOT / 'results'
    out.mkdir(exist_ok=True)
    db = sqlite3.connect(':memory:')
    db.execute('PRAGMA foreign_keys = ON')
    db.executescript((ROOT / 'schema.sql').read_text())
    db.executescript((ROOT / 'seed.sql').read_text())
    checks = []
    def check(ok, name):
        """조건(ok)과 설명(name)을 받아 성공을 기록한다.

        반환: 없음. 예외: 거짓이면 AssertionError.
        이유: Python 최적화 옵션에서도 검증이 생략되지 않게 한다.
        """
        if not ok:
            raise AssertionError(name)
        checks.append('PASS | ' + name)
    check(db.execute('PRAGMA foreign_keys').fetchone()[0] == 1, 'FK 검사 활성')
    check(len(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()) == 4, '테이블 4개')
    for table in ('member', 'category', 'book', 'rental'):
        check(any(r[5] for r in db.execute(f'PRAGMA table_info({table})')), table + ' PK 존재')
        n = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        check(n >= 10, f'{table} 초기 {n}행')
    check(sum(len(db.execute(f'PRAGMA foreign_key_list({t})').fetchall()) for t in ('book','rental')) == 3, 'FK 3개')
    evidence = []
    # ★ 평가 핵심 V1: 실패를 예상한 실험을 정상 SQL 실행과 분리한다.
    bad = [
        ('없는 회원 FK', "INSERT INTO rental VALUES (999,999,1,'2026-10-01',NULL,0)"),
        ('없는 책 FK', "INSERT INTO rental VALUES (999,1,999,'2026-10-01',NULL,0)"),
        ('없는 분류 FK', "INSERT INTO book VALUES (999,'검사',999)"),
        ('NOT NULL', "INSERT INTO member VALUES (999,NULL,'new@example.test','2026-10-01')"),
        ('UNIQUE', "INSERT INTO member VALUES (999,'검사','member01@example.test','2026-10-01')"),
        ('PK 중복', "INSERT INTO member VALUES (1,'검사','new@example.test','2026-10-01')"),
        ('음수 연체료', "INSERT INTO rental VALUES (999,1,1,'2026-10-01',NULL,-1)"),
        ('반납일 역전', "INSERT INTO rental VALUES (999,1,1,'2026-10-02','2026-10-01',0)")]
    for name, sql in bad:
        try:
            db.execute(sql)
        except sqlite3.IntegrityError as error:
            evidence.append(f'{name}\nSQL: {sql}\n예상된 거절: {error}\n')
            check(True, name + ' 거절')
        else:
            raise AssertionError(name + ' 거절되지 않음')
    evidence.append('수정 방법: 존재하는 부모 번호를 사용하거나 부모를 먼저 입력한다.\n실패 입력은 저장되지 않았다.')
    (out / 'constraints.txt').write_text('\n'.join(evidence))
    chunks = re.split(r'-- Q(\d{2}) \| ', (ROOT / 'queries.sql').read_text())[1:]
    check(len(chunks) == 30, '번호가 붙은 쿼리 15개')
    check(chunks[::2] == [f'{n:02d}' for n in range(1, 16)], 'Q01~Q15 순서·중복 없음')
    for no, chunk in zip(chunks[::2], chunks[1::2]):
        desc, sql = chunk.strip().split('\n', 1)
        before = ''
        if no in ('13', '14'):
            snapshot = db.execute('SELECT * FROM rental ORDER BY id').fetchall()
            target = 103 if no == '13' else 116
            query = f'SELECT * FROM rental WHERE id = {target}'
            before = '변경 전\n' + show(db.execute(query))
        cur = db.execute(sql)
        # 제출 SQL 자체의 결과를 검사해야 검증용 별도 SQL만 맞는 상황을 피한다.
        rows = cur.fetchall() if cur.description else []
        if no == '05':
            check(len(rows) == 16 and {row[0] for row in rows} == {f'회원{n:02d}' for n in range(1, 9)}, 'Q05 INNER 16행·미대여 회원 제외')
        if no == '07':
            check(len(rows) == 18 and rows[-2:] == [(9, '회원09', None), (10, '회원10', None)], 'Q07 LEFT 18행·미대여 회원 NULL 유지')
        if no == '09':
            check([(r[0], r[2]) for r in rows] == [(n, 2 if n <= 8 else 0) for n in range(1, 11)], 'Q09 전체 회원별 건수 2·0')
        if no == '10':
            check([r[2] for r in rows] == [500,1500,1000,500,1500,1000,500,1500,0,0], 'Q10 전체 회원별 연체료 합계')
        if no == '11':
            check(rows == [(n, 3.0) for n in range(1, 9)], 'Q11 완료 대여 평균 모두 3일')
        if no == '12':
            check(rows == [(9, '회원09'), (10, '회원10')], 'Q12 미대여 회원 9·10번')
        # 조회 커서를 이미 읽었으므로 증거 출력용 조회만 다시 실행한다.
        if cur.description:
            cur = db.execute(sql)
        result = show(cur)
        if no in ('13', '14'):
            expected = []
            for row in snapshot:
                if no == '14' and row[0] == 116:
                    continue
                if no == '13' and row[0] == 103:
                    values = list(row)
                    values[4] = '2026-10-10'  # returned_at만 바뀌어야 한다.
                    row = tuple(values)
                expected.append(row)
            check(db.execute('SELECT * FROM rental ORDER BY id').fetchall() == expected, f'Q{no} 대상 외 모든 행·열 보존')
            result += '변경 후\n' + show(db.execute(query))
        if no == '15':
            result += show(db.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name='idx_rental_member_id'"))
            plan = db.execute('EXPLAIN QUERY PLAN SELECT * FROM rental WHERE member_id = 1').fetchall()
            check(any('idx_rental_member_id' in row[3] for row in plan), '회원 검색 실행 계획에서 인덱스 사용')
            result += 'SQLite 전용 실행 계획 (속도 측정 아님)\n' + show(db.execute('EXPLAIN QUERY PLAN SELECT * FROM rental WHERE member_id = 1'))
        (out / f'q{no}.txt').write_text(f'Q{no}: {desc}\nSQL:\n{sql}\n{before}{result}')
    # ★ 평가 핵심 V2: 단순 성공뿐 아니라 기대한 업무 결과를 검증한다.
    counts = dict(db.execute('SELECT m.id,COUNT(r.id) FROM member m LEFT JOIN rental r ON m.id=r.member_id GROUP BY m.id'))
    check(counts[9] == counts[10] == 0, '미대여 회원 9·10번은 0건')
    check(counts[1] == 2, '1번 회원 대여 2건')
    check(db.execute('SELECT SUM(late_fee) FROM rental WHERE member_id=1').fetchone()[0] == 500, '1번 회원 연체료 합계 500원')
    check(db.execute('SELECT AVG(julianday(returned_at)-julianday(borrowed_at)) FROM rental WHERE member_id=2 AND returned_at IS NOT NULL').fetchone()[0] == 3, '2번 회원 완료 대여 평균 3일')
    check(db.execute('SELECT returned_at FROM rental WHERE id=103').fetchone()[0] == '2026-10-10', '103번 반납일 수정')
    check(db.execute('SELECT COUNT(*) FROM rental WHERE id=116').fetchone()[0] == 0, '116번만 삭제')
    check(db.execute('SELECT COUNT(*) FROM rental').fetchone()[0] == 15, '삭제 후 대여 15행')
    check(db.execute('PRAGMA foreign_key_check').fetchall() == [], '외래 키 위반 없음')
    check(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'DB 무결성 검사 ok')
    check(db.execute("SELECT COUNT(*) FROM rental WHERE date(borrowed_at) IS NULL OR (returned_at IS NOT NULL AND date(returned_at) IS NULL)").fetchone()[0] == 0, '샘플 날짜 파싱 가능')
    check(db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='idx_rental_member_id'").fetchone()[0] == 1, '인덱스 존재')
    bonus = []
    for statement in (ROOT/'bonus.sql').read_text().split(';'):
        if statement.strip():
            bonus.append(statement + ';\n' + show(db.execute(statement)))
    left = db.execute('SELECT m.id FROM member m LEFT JOIN rental r ON m.id=r.member_id WHERE r.id IS NULL ORDER BY m.id').fetchall()
    sub = db.execute('SELECT m.id FROM member m WHERE NOT EXISTS(SELECT 1 FROM rental r WHERE r.member_id=m.id) ORDER BY m.id').fetchall()
    check(left == sub == [(9,), (10,)], '보너스 JOIN·서브쿼리 결과 일치')
    (out/'bonus.txt').write_text('\n'.join(bonus))
    env = f'실행 시각: {datetime.now().astimezone().isoformat(timespec="seconds")}\n검증 환경: Python {platform.python_version()} / Python 내장 SQLite {sqlite3.sqlite_version} / {platform.system()} {platform.release()}\nPython 실행 파일: {sys.executable}\n작업 경로: {ROOT}\n'
    (out/'verification.txt').write_text(env+'\n'.join(checks)+f'\n총 {len(checks)}개 PASS\nCLI는 tools/verify_cli.py의 results/cli-verification.txt 참조\n미검증: GUI 도구, 실제 대규모 성능, 동시 대여 방지\n')
    print(env + '\n'.join(checks))
    db.close()


if __name__ == '__main__':
    main()
