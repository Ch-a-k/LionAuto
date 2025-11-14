ALTER TABLE translation 
ADD CONSTRAINT translation_unique 
UNIQUE (field_name, original_value, language);