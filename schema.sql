-- SQLite 전용: FK 검사는 연결마다 트랜잭션 시작 전에 켠다.
PRAGMA foreign_keys = ON;
-- ★ 평가 핵심 S1: 기본 정보와 반복되는 이력을 분리한다.
CREATE TABLE member (
    id INTEGER PRIMARY KEY, -- PK: 회원 자신의 식별자
    name TEXT NOT NULL, -- 필수값. 빈 문자열 검사까지 의미하지는 않는다.
    email TEXT NOT NULL UNIQUE, -- 필수이면서 회원 간 중복 금지
    joined_at TEXT NOT NULL -- SQLite 날짜는 YYYY-MM-DD 형식 TEXT로 관리
);
CREATE TABLE category (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
-- 한 행은 실제로 대여 가능한 책 한 권이다.
CREATE TABLE book (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    FOREIGN KEY (category_id) REFERENCES category(id)
);
-- ★ 평가 핵심 S2: FK는 참조 대상의 존재를 검사한다.
-- 회원/책 삭제 시 이력을 자동 삭제하지 않고 기본 NO ACTION으로 막는다.
CREATE TABLE rental (
    id INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    borrowed_at TEXT NOT NULL,
    returned_at TEXT, -- NULL이면 아직 반납하지 않은 기록
    late_fee INTEGER NOT NULL DEFAULT 0 CHECK (late_fee >= 0), -- 원 단위 정수
    FOREIGN KEY (member_id) REFERENCES member(id),
    FOREIGN KEY (book_id) REFERENCES book(id),
    CHECK (returned_at IS NULL OR returned_at >= borrowed_at)
);
