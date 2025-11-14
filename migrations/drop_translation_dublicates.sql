-- Создаем временную таблицу с уникальными записями
CREATE TEMPORARY TABLE temp_translations AS
SELECT DISTINCT ON (field_name, original_value, language) *
FROM translation
ORDER BY field_name, original_value, language, id;

-- Очищаем оригинальную таблицу
TRUNCATE translation;

-- Вставляем обратно только уникальные записи
INSERT INTO translation
SELECT * FROM temp_translations;

-- Удаляем временную таблицу
DROP TABLE temp_translations;
