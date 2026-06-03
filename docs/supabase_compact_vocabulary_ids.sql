-- 全表 id 連號 1,2,3…（新單字 = MAX(id)+1）
-- 刪除後遞補由後端呼叫 compact（勿用 ALTER TABLE，否則 DELETE 會失敗）
-- Supabase SQL Editor 整段執行（可重複執行）

CREATE OR REPLACE FUNCTION public.compact_member_vocabulary_ids()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  max_id bigint;
  seq_name text;
BEGIN
  WITH ordered AS (
    SELECT id AS old_id,
           row_number() OVER (ORDER BY created_at NULLS LAST, id)::bigint AS new_id
    FROM "MemberVocabulary"
  )
  UPDATE "MemberVocabulary" mv
  SET id = -o.new_id
  FROM ordered o
  WHERE mv.id = o.old_id AND mv.id IS DISTINCT FROM o.new_id;

  UPDATE "MemberVocabulary" SET id = -id WHERE id < 0;

  SELECT COALESCE(MAX(id), 0) INTO max_id FROM "MemberVocabulary";

  seq_name := pg_get_serial_sequence('"MemberVocabulary"', 'id');
  IF seq_name IS NOT NULL AND max_id > 0 THEN
    PERFORM setval(seq_name::regclass, max_id, true);
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.assign_member_vocabulary_id()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.id IS NULL THEN
    SELECT COALESCE(MAX(id), 0) + 1 INTO NEW.id FROM "MemberVocabulary";
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS member_vocabulary_compact_ids ON "MemberVocabulary";
DROP FUNCTION IF EXISTS public.compact_member_vocabulary_ids_trigger();

DROP TRIGGER IF EXISTS member_vocabulary_assign_id ON "MemberVocabulary";
CREATE TRIGGER member_vocabulary_assign_id
  BEFORE INSERT ON "MemberVocabulary"
  FOR EACH ROW
  EXECUTE FUNCTION public.assign_member_vocabulary_id();

REVOKE ALL ON FUNCTION public.compact_member_vocabulary_ids() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.compact_member_vocabulary_ids() TO authenticated;
GRANT EXECUTE ON FUNCTION public.compact_member_vocabulary_ids() TO service_role;

SELECT public.compact_member_vocabulary_ids();
