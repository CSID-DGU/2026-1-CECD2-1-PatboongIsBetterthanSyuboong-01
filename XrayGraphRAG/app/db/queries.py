"""AQL 쿼리 모음. vector index가 없는 환경을 위한 fallback 쿼리도 포함."""
from __future__ import annotations

# 메모: APPROX_NEAR_COSINE은 ArangoDB 3.12+ 의 experimental vector function이다.
# 사용 불가 시 fallback에서 직접 코사인 유사도를 계산한다.

VECTOR_SEARCH_AQL = """
FOR c IN xray_cases
  FILTER (@view == null OR c.view == @view)
  FILTER (@modelVersion == null OR c.modelVersion == @modelVersion)
  FILTER (@maskVersion == null OR c.maskVersion == @maskVersion)
  FILTER c[@field] != null
  LET similarity = APPROX_NEAR_COSINE(
    c[@field],
    @queryEmbedding,
    { nProbe: @nProbe }
  )
  SORT similarity DESC
  LIMIT @topK
  RETURN {
    caseId: c._key,
    similarity: similarity,
    diseaseTags: c.diseaseTags,
    findingTags: c.findingTags,
    roiStats: c.roiStats,
    imagePath: c.imagePath,
    heatmapPath: c.heatmapPath
  }
"""

VECTOR_SEARCH_FALLBACK_AQL = """
LET q = @queryEmbedding
LET qn = SQRT(SUM(FOR x IN q RETURN x*x))
FOR c IN xray_cases
  FILTER (@view == null OR c.view == @view)
  FILTER (@modelVersion == null OR c.modelVersion == @modelVersion)
  FILTER (@maskVersion == null OR c.maskVersion == @maskVersion)
  FILTER c[@field] != null
  LET v = c[@field]
  LET dot = SUM(FOR i IN 0..LENGTH(v)-1 RETURN v[i]*q[i])
  LET vn = SQRT(SUM(FOR x IN v RETURN x*x))
  LET denom = (vn * qn)
  LET similarity = denom == 0 ? 0 : dot / denom
  SORT similarity DESC
  LIMIT @topK
  RETURN {
    caseId: c._key,
    similarity: similarity,
    diseaseTags: c.diseaseTags,
    findingTags: c.findingTags,
    roiStats: c.roiStats,
    imagePath: c.imagePath,
    heatmapPath: c.heatmapPath
  }
"""


GRAPH_TRAVERSAL_AQL = """
LET caseIds = @similarCaseIds
FOR cid IN caseIds
  LET startNode = CONCAT('xray_cases/', cid)
  FOR v, e, p IN 1..2 OUTBOUND startNode
    GRAPH @graphName
    OPTIONS { uniqueVertices: 'global', bfs: true }
    RETURN { caseId: cid, vertex: v, edge: e, depth: LENGTH(p.edges) }
"""
