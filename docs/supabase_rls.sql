-- Run in Supabase SQL Editor (可重複執行)

ALTER TABLE "Member" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "MemberVocabulary" ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON "Member" TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON "MemberVocabulary" TO authenticated;

DROP POLICY IF EXISTS "member_select_own" ON "Member";
DROP POLICY IF EXISTS "member_insert_own" ON "Member";
DROP POLICY IF EXISTS "member_update_own" ON "Member";
DROP POLICY IF EXISTS "member_vocabulary_select_own" ON "MemberVocabulary";
DROP POLICY IF EXISTS "member_vocabulary_insert_own" ON "MemberVocabulary";
DROP POLICY IF EXISTS "member_vocabulary_update_own" ON "MemberVocabulary";
DROP POLICY IF EXISTS "member_vocabulary_delete_own" ON "MemberVocabulary";

CREATE POLICY "member_select_own"
  ON "Member" FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "member_insert_own"
  ON "Member" FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "member_update_own"
  ON "Member" FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "member_vocabulary_select_own"
  ON "MemberVocabulary" FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "member_vocabulary_insert_own"
  ON "MemberVocabulary" FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "member_vocabulary_update_own"
  ON "MemberVocabulary" FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "member_vocabulary_delete_own"
  ON "MemberVocabulary" FOR DELETE
  USING (auth.uid() = user_id);

-- 每位使用者每個韓文詞一筆（若 vocabulary 曾被設成「全表唯一」會導致第二筆寫不進去）
CREATE UNIQUE INDEX IF NOT EXISTS member_vocabulary_user_word
  ON "MemberVocabulary" (user_id, vocabulary);
