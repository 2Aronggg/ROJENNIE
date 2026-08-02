# Supabase pgvector RAG

분석 서버는 `SUPABASE_RAG_ENABLED=true`일 때 로컬 `data/corpus/all.jsonl`을 읽지 않고
Supabase `rag_chunks`의 pgvector RPC에서 근거를 조회합니다. 비활성화하면 기존 로컬
`SearchIndex`를 fallback으로 사용합니다.

## 적용 순서

1. Supabase SQL Editor에서
   `supabase/migrations/20260802_rag_pgvector.sql`을 실행합니다.
2. 임베딩이 포함된 corpus를 준비합니다.
3. 업로드합니다.

```powershell
python -m server.rag.upload_pgvector --input data/corpus/all.jsonl --batch-size 100
```

중간에 네트워크나 파일 오류로 중단되면 마지막 `uploaded` 수가 54100이었다면
다음처럼 재개할 수 있습니다. 이미 올라간 `chunk_id`는 upsert되어 중복되지 않습니다.

```powershell
python -m server.rag.upload_pgvector --input data/corpus/all.jsonl --batch-size 100 --start-line 54101
```

`.env`:

```env
SUPABASE_PERSISTENCE=true
SUPABASE_RAG_ENABLED=true
```

`embedding`이 비어 있는 청크는 업로드하지 않습니다. 새 문서를 추가한 뒤에는 corpus와
임베딩을 다시 생성하고 업로드해야 합니다.
