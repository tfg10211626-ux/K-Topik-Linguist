-- 在 Supabase SQL Editor 整段執行一次，再執行 supabase_rls.sql
-- id 若已是 Identity，勿再 SET DEFAULT nextval（會 42601）

-- ========== Member ==========
ALTER TABLE "Member" ADD COLUMN IF NOT EXISTS email text;
CREATE UNIQUE INDEX IF NOT EXISTS member_email_unique
  ON "Member" (email) WHERE email IS NOT NULL;

-- ========== MemberVocabulary：錯誤約束 ==========
ALTER TABLE "MemberVocabulary" DROP CONSTRAINT IF EXISTS "MemberVocabulary_user_id_key";
ALTER TABLE "MemberVocabulary" DROP CONSTRAINT IF EXISTS "MemberVocabulary_vocabulary_key";
ALTER TABLE "MemberVocabulary" DROP CONSTRAINT IF EXISTS "membervocabulary_vocabulary_key";
ALTER TABLE "MemberVocabulary" DROP CONSTRAINT IF EXISTS "MemberVocabulary_pkey";

-- 補齊 id 為 NULL 的列（Identity / sequence 都適用）
DO $backfill$
DECLARE
  r record;
  n bigint;
BEGIN
  SELECT COALESCE(MAX(id), 0) INTO n FROM "MemberVocabulary";
  FOR r IN
    SELECT ctid
    FROM "MemberVocabulary"
    WHERE id IS NULL
    ORDER BY created_at NULLS LAST, ctid
  LOOP
    n := n + 1;
    UPDATE "MemberVocabulary" SET id = n WHERE ctid = r.ctid;
  END LOOP;
END $backfill$;

-- 僅在 id「不是」Identity 時才建立 sequence（Supabase 常已自動設 Identity）
DO $id_default$
DECLARE
  id_identity "char";
BEGIN
  SELECT a.attidentity INTO id_identity
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relname = 'MemberVocabulary'
    AND a.attname = 'id'
    AND NOT a.attisdropped;

  IF COALESCE(id_identity, '') = '' THEN
    CREATE SEQUENCE IF NOT EXISTS "MemberVocabulary_id_seq";
    ALTER TABLE "MemberVocabulary"
      ALTER COLUMN id SET DEFAULT nextval('"MemberVocabulary_id_seq"');
    ALTER SEQUENCE "MemberVocabulary_id_seq" OWNED BY "MemberVocabulary".id;
  END IF;
END $id_default$;

ALTER TABLE "MemberVocabulary" ALTER COLUMN id SET NOT NULL;

DO $pk$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = '"MemberVocabulary"'::regclass
      AND contype = 'p'
  ) THEN
    ALTER TABLE "MemberVocabulary" ADD PRIMARY KEY (id);
  END IF;
END $pk$;

DROP INDEX IF EXISTS member_vocabulary_user_word;
CREATE UNIQUE INDEX member_vocabulary_user_word
  ON "MemberVocabulary" (user_id, vocabulary);
