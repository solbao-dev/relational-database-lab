-- 보너스 1: 미대여 회원 찾기를 LEFT JOIN과 서브쿼리로 비교한다.
SELECT m.id FROM member m LEFT JOIN rental r ON m.id = r.member_id WHERE r.id IS NULL ORDER BY m.id;
SELECT m.id FROM member m WHERE NOT EXISTS (SELECT 1 FROM rental r WHERE r.member_id = m.id) ORDER BY m.id;
-- 보너스 3: 월별 대여 건수 / 도서별 인기 순위 / 회원별 연체료 합계.
-- substr은 SQLite에서 사용하는 문자열 함수다. 고정 형식 날짜의 연월을 추출한다.
SELECT substr(borrowed_at, 1, 7) AS month, COUNT(*) AS rentals FROM rental GROUP BY substr(borrowed_at, 1, 7);
SELECT b.id, b.title, COUNT(r.id) AS rentals FROM book b LEFT JOIN rental r ON r.book_id = b.id GROUP BY b.id, b.title ORDER BY rentals DESC, b.id LIMIT 10;
SELECT member_id, SUM(late_fee) AS total_fee FROM rental GROUP BY member_id ORDER BY total_fee DESC, member_id;
