"""설치된 sqlite3 CLI로 제출 파일을 실행하고 Python 내장 DB와 별도 검증한다."""
from datetime import datetime
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run_cli(executable, database, script):
    """SQLite CLI에 스크립트를 전달하고 프로세스 결과를 반환한다.

    매개변수: 실행 파일 경로, DB 경로, CLI 명령과 SQL 문자열.
    반환: 종료 코드·표준 출력·표준 오류를 가진 CompletedProcess.
    예외: 실행 불가 시 OSError, 30초 초과 시 TimeoutExpired.
    이유: 인자를 목록으로 전달해 셸 해석 없이 실제 CLI를 검증한다.
    """
    return subprocess.run(
        [executable, '-batch', '-bail', str(database)], input=script,
        text=True, capture_output=True, cwd=ROOT, timeout=30,
    )


def main():
    """임시 파일 DB에서 CLI 검증을 실행하고 결과 2개를 저장한다.

    매개변수·반환: 없음. 예외: CLI가 없으면 FileNotFoundError,
    결과 불일치 시 AssertionError, 실행 오류는 호출자에게 전달한다.
    이유: 사용자 DB를 건드리지 않고 파일 DB·CLI 실행을 재현한다.
    """
    executable = shutil.which('sqlite3')
    if executable is None:
        raise FileNotFoundError('sqlite3 CLI가 필요합니다. sqlite3 --version을 확인하세요.')
    version = subprocess.run([executable, '--version'], capture_output=True, text=True, check=True).stdout.strip()
    checks = []

    def check(ok, name):
        """조건과 설명을 받아 PASS를 기록한다.

        반환: 없음. 예외: 조건이 거짓이면 AssertionError.
        이유: 예상된 FK 오류와 실제 실행 실패를 구분한다.
        """
        if not ok:
            raise AssertionError(name)
        checks.append('PASS | ' + name)

    # 임시 디렉터리는 이 실행이 만든 DB만 정리하므로 기존 DB를 보존한다.
    with tempfile.TemporaryDirectory(prefix='b61-cli-') as directory:
        database = Path(directory) / 'library.db'
        script = '''.headers on
.mode column
.echo on
.read schema.sql
.read seed.sql
.print === 변경 전 ===
SELECT * FROM rental WHERE id IN (103,116) ORDER BY id;
.read queries.sql
.print === 변경 후 ===
SELECT * FROM rental WHERE id IN (103,116) ORDER BY id;
.read bonus.sql
.echo off
.headers off
.mode list
SELECT 'counts', (SELECT COUNT(*) FROM member), (SELECT COUNT(*) FROM category), (SELECT COUNT(*) FROM book), (SELECT COUNT(*) FROM rental);
SELECT 'returned', returned_at FROM rental WHERE id=103;
SELECT 'deleted', COUNT(*) FROM rental WHERE id=116;
SELECT 'index', name FROM sqlite_master WHERE name='idx_rental_member_id';
SELECT 'fk_enabled', * FROM pragma_foreign_keys;
SELECT 'fk_violations', COUNT(*) FROM pragma_foreign_key_check;
PRAGMA integrity_check;
EXPLAIN QUERY PLAN SELECT * FROM rental WHERE member_id=1;
'''
        run = run_cli(executable, database, script)
        check(run.returncode == 0, 'schema → seed → queries → bonus CLI 실행 성공')
        lines = run.stdout.splitlines()
        for expected, name in [
            ('counts|10|10|12|15', '삭제 후 모든 표 최소 10행'),
            ('returned|2026-10-10', 'Q13 반납일 수정'),
            ('deleted|0', 'Q14 대상 삭제'),
            ('index|idx_rental_member_id', 'Q15 인덱스 생성'),
            ('fk_enabled|1', 'CLI 연결 FK 활성'),
            ('fk_violations|0', 'FK 위반 없음'),
            ('ok', 'DB 무결성 ok'),
        ]:
            check(expected in lines, name)
        check('USING INDEX idx_rental_member_id' in run.stdout, '검색 실행 계획 인덱스 사용')

        # 새 연결에서도 FK를 켜야 한다. 예상 오류는 정상 실행과 분리한다.
        invalid = "PRAGMA foreign_keys=ON;\nINSERT INTO rental VALUES (999,999,1,'2026-10-20',NULL,0);\n"
        rejected = run_cli(executable, database, invalid)
        check(rejected.returncode != 0 and 'FOREIGN KEY constraint failed' in rejected.stderr, '없는 회원 참조 실제 CLI 거절')
        corrected = '''PRAGMA foreign_keys=ON;
BEGIN;
INSERT INTO rental VALUES (999,1,1,'2026-10-20',NULL,0);
SELECT 'corrected', member_id FROM rental WHERE id=999;
ROLLBACK;
SELECT 'restored', COUNT(*) FROM rental;
'''
        fixed = run_cli(executable, database, corrected)
        check(fixed.returncode == 0 and 'corrected|1' in fixed.stdout and 'restored|15' in fixed.stdout, '존재하는 회원으로 수정 성공·ROLLBACK 복원')
        repeated = run_cli(executable, database, '.read schema.sql\n')
        check(repeated.returncode != 0 and 'already exists' in repeated.stderr, '기존 DB 재실행은 덮어쓰지 않고 거절')

    out = ROOT / 'results'
    out.mkdir(exist_ok=True)
    env = f'실행 시각: {datetime.now().astimezone().isoformat(timespec="seconds")}\n환경: {platform.system()} {platform.release()}\nCLI: {executable}\nSQLite CLI 버전: {version}\n작업 경로: {ROOT}\n'
    (out / 'cli-session.txt').write_text(
        env + '=== 실제 CLI 입력 ===\n' + script + '\n=== 표준 출력 ===\n' + run.stdout
        + '\n=== FK 실패 입력 ===\n' + invalid + f'종료 코드: {rejected.returncode}\n' + rejected.stderr
        + '\n=== 수정 입력 ===\n' + corrected + fixed.stdout
        + '\n=== 기존 DB 재실행 거절 ===\n' + repeated.stderr,
        encoding='utf-8',
    )
    report = env + '\n'.join(checks) + f'\n총 {len(checks)}개 PASS\n'
    (out / 'cli-verification.txt').write_text(report, encoding='utf-8')
    print(report)


if __name__ == '__main__':
    main()
