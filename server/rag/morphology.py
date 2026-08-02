from __future__ import annotations

from functools import lru_cache

# Korean is agglutinative: "연장했더니"(extended, so...)와 "연장시"(at extension)는
# 같은 명사 어간 "연장"을 공유하지만, 순수 정규식 토크나이저(retrieval._tokens)는
# 조사·어미가 붙은 전체 형태를 통째로 하나의 토큰으로 다뤄서 이 둘을 다른 단어로
# 취급한다. kiwipiepy로 내용형태소(명사/용언 어간)만 뽑아내면 이 불일치를 없앨 수
# 있는데, 전체 코퍼스(6만5천+ 청크)에 걸면 청크당 ~23ms로 25분이 걸려 매 서버
# 기동·테스트마다 다시 돌릴 수 없다. 그래서 embeddings.jsonl과 같은 패턴으로
# cases/products/guides 청크(약 1,000개)에 대해서만 오프라인으로 한 번 계산해
# stems.jsonl에 저장하고(server/rag/stem_corpus.py), 질의 쪽만 매 요청마다
# 실시간으로 형태소 분석한다(문장 하나라 수 ms 수준).
CONTENT_POS_PREFIXES = ("NN", "VV", "VA", "XR", "SL", "SH", "SN")


@lru_cache(maxsize=1)
def _kiwi():
    from kiwipiepy import Kiwi

    return Kiwi()


def extract_stems(text: str) -> list[str]:
    """Content-word morpheme stems (nouns, verb/adjective roots) from `text`.

    Drops particles (조사) and endings (어미) so conjugated/declined forms of the
    same word collapse to one token. Returns [] if kiwipiepy isn't installed or
    the text is empty - callers must treat that as "no stem signal available",
    not as an error, since regulations chunks intentionally have none.
    """
    if not text or not text.strip():
        return []
    try:
        kiwi = _kiwi()
    except ImportError:
        return []
    stems: list[str] = []
    for token in kiwi.tokenize(text):
        if token.tag.startswith(CONTENT_POS_PREFIXES) and len(token.form) >= 2:
            stems.append(token.form.lower())
    return stems
