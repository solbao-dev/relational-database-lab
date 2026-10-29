-- schema.sql → seed.sql → queries.sql 순서로 새 DB에서 한 번 실행한다.
PRAGMA foreign_keys = ON;

-- Q01 | 기본 조회: 회원 전체를 식별자 순서로 확인한다.
SELECT id, name, email FROM member ORDER BY id;

-- Q02 | 기본 조회: 1번 분류의 책을 검색한다.
SELECT id, title FROM book WHERE category_id = 1 ORDER BY id;

-- Q03 | 기본 조회: 가입일 최신순으로 회원을 조회한다.
SELECT id, name, joined_at FROM member ORDER BY joined_at DESC, id DESC;

-- Q04 | 기본 조회: 최근 대여 5건만 조회한다. LIMIT는 선택한 SQLite에서 지원하는 문법이다.
SELECT id, borrowed_at FROM rental ORDER BY borrowed_at DESC, id DESC LIMIT 5;

-- Q05 | INNER JOIN: 회원번호가 일치하는 대여와 회원 이름을 연결한다.
SELECT m.name, r.id AS rental_id FROM member AS m INNER JOIN rental AS r ON m.id = r.member_id ORDER BY r.id;

-- Q06 | INNER JOIN: 책의 분류명을 연결한다.
SELECT b.id, b.title, c.name AS category_name FROM book AS b INNER JOIN category AS c ON b.category_id = c.id ORDER BY b.id;

-- Q07 | ★ 평가 핵심 Q07 LEFT JOIN: 미대여 회원도 남긴다. NULL은 연결된 대여가 없다는 뜻이다.
SELECT m.id, m.name, r.id AS rental_id FROM member AS m LEFT JOIN rental AS r ON m.id = r.member_id ORDER BY m.id, r.id;

-- Q08 | 조인: 회원·대여·책을 연결해 누가 무엇을 빌렸는지 확인한다.
SELECT r.id, m.name, b.title, r.borrowed_at FROM rental AS r INNER JOIN member AS m ON r.member_id = m.id INNER JOIN book AS b ON r.book_id = b.id ORDER BY r.id;

-- Q09 | ★ 평가 핵심 Q09 집계: 회원별 대여 건수. COUNT(r.id)는 NULL을 제외해 미대여 회원을 0으로 센다.
SELECT m.id, m.name, COUNT(r.id) AS rental_count FROM member AS m LEFT JOIN rental AS r ON m.id = r.member_id GROUP BY m.id, m.name ORDER BY rental_count DESC, m.id;

-- Q10 | 집계: 회원별 연체료 합계. COALESCE는 대여가 없어 합계가 NULL인 경우 0으로 표시한다.
SELECT m.id, m.name, COALESCE(SUM(r.late_fee), 0) AS total_fee FROM member AS m LEFT JOIN rental AS r ON m.id = r.member_id GROUP BY m.id, m.name ORDER BY m.id;

-- Q11 | 집계: 반납 완료 기록의 회원별 평균 대여일수. julianday는 SQLite 날짜 함수다.
SELECT member_id, AVG(julianday(returned_at) - julianday(borrowed_at)) AS avg_days FROM rental WHERE returned_at IS NOT NULL GROUP BY member_id ORDER BY member_id;

-- Q12 | ★ 평가 핵심 Q12 서브쿼리: 대여 이력이 전혀 없는 회원을 찾는다. SELECT 1은 존재 확인용이다.
SELECT m.id, m.name FROM member AS m WHERE NOT EXISTS (SELECT 1 FROM rental AS r WHERE r.member_id = m.id) ORDER BY m.id;

-- Q13 | ★ 평가 핵심 Q13 수정: 103번 대여를 반납 처리한다. WHERE로 대상 하나를 지정한다.
UPDATE rental SET returned_at = '2026-10-10' WHERE id = 103;

-- Q14 | ★ 평가 핵심 Q14 삭제: 지정한 가상 대여 기록만 삭제한다. 표 자체는 유지된다.
DELETE FROM rental WHERE id = 116;

-- Q15 | ★ 평가 핵심 Q15 인덱스: 회원별 대여 검색과 조인에 사용하는 member_id를 대상으로 한다. 쓰기 비용·공간이 추가되며 속도 향상을 단정하지 않는다.
CREATE INDEX idx_rental_member_id ON rental(member_id);
