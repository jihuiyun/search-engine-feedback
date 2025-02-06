
--------------------------------
-- 查找重复的记录数
WITH duplicates AS (
    SELECT id, keyword, title, url, last_updated,
           ROW_NUMBER() OVER (
               PARTITION BY keyword, title, url 
               ORDER BY last_updated ASC
           ) as row_num
    FROM results
)
SELECT COUNT(*) as duplicate_count
FROM duplicates 
WHERE row_num > 1;

--------------------------------
-- 1. 先找出要保留的记录
WITH keep_records AS (
    SELECT MIN(id) as id
    FROM results
    GROUP BY keyword, title, url
)
-- 2. 删除不在保留列表中的记录
DELETE FROM results 
WHERE id NOT IN (SELECT id FROM keep_records);

--------------------------------

-- 1. 创建临时表，保留每组中最早的完整记录
CREATE TABLE results_temp AS
SELECT r.*
FROM results r
         INNER JOIN (
    SELECT MIN(id) as min_id
    FROM results
    GROUP BY keyword, title, url
) m ON r.id = m.min_id;

-- 2. 删除原表
DROP TABLE results;

-- 3. 创建新表
CREATE TABLE results (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         keyword TEXT NOT NULL,
                         title TEXT NOT NULL,
                         url TEXT NOT NULL,
                         search_engine TEXT NOT NULL,
                         is_expired BOOLEAN NOT NULL,
                         last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 从临时表导入数据，让 SQLite 自动生成新的 id
INSERT INTO results (keyword, title, url, search_engine, is_expired, last_updated)
SELECT keyword, title, url, search_engine, is_expired, last_updated
FROM results_temp;

-- 5. 删除临时表
DROP TABLE results_temp;



