r"""ArangoDB 에 등록된 케이스를 대상으로 이미지 1장 inference 동작 검증 + 설명 출력.

이 스크립트는 `case_service.infer()` 를 호출해서 다음을 한 번에 보여준다.
  - predicted disease top-N (score, supportCases, reason)
  - agent explanation 의 evidence/limitations/warning
  - notable findings (유사 사례 빈도 + 현재 케이스 ROI evidence)
  - similar cases top-N (similarity, disease tags, finding tags)
  - 현재 query 의 ROI severity 분포
  - uncertainty level + reasons
  - heatmap 파일 경로

추가로 `--ground-truth` 가 지정되면 CheXpert valid/train csv 에서 같은 이미지의
라벨을 찾아 prediction 과 자동 비교한다.

사용 예:
  python scripts/smoke_infer.py --image D:\data\chexpert\valid\patient64541\study1\view1_frontal.jpg
  python scripts/smoke_infer.py --image <path> --view AP --top-k 10 --full
  python scripts/smoke_infer.py --image <path> --ground-truth D:\data\chexpert
  python scripts/smoke_infer.py --image <path> --save storage/eval/infer_64541.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


def _setup() -> None:
    for s in ("stdout", "stderr"):
        try:
            getattr(sys, s).reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    here = Path(__file__).resolve()
    if str(here.parent.parent) not in sys.path:
        sys.path.insert(0, str(here.parent.parent))


_setup()

from app.api.dependencies import get_container  # noqa: E402


CHEXPERT_LABEL_MAP = {
    "Enlarged Cardiomediastinum": "enlarged_cardiomediastinum",
    "Cardiomegaly": "cardiomegaly",
    "Lung Opacity": "lung_opacity",
    "Lung Lesion": "lung_lesion",
    "Edema": "edema",
    "Consolidation": "consolidation",
    "Pneumonia": "pneumonia",
    "Atelectasis": "atelectasis",
    "Pneumothorax": "pneumothorax",
    "Pleural Effusion": "pleural_effusion",
    "Pleural Other": "pleural_other",
    "Fracture": "fracture",
}


def _hr(title: str = "") -> None:
    line = "=" * 70
    if title:
        print(f"\n{line}\n  {title}\n{line}")
    else:
        print(line)


def _print_predicted(out: Dict[str, Any], explanation: Dict[str, Any]) -> None:
    _hr("Predicted Diseases (top-5)")
    print(f"{'#':>2}  {'disease':<32} {'score':>7} {'support':>8}  reason")
    pred_block = explanation.get("predictedDiseases") or []
    pred_by_name = {p["name"]: p for p in pred_block}
    for i, d in enumerate(out["predictedDiseases"][:5], 1):
        print(f"{i:>2}  {d['disease']:<32} {d['score']:>7.3f} {d['supportCases']:>8}  {d['reason']}")
        ev = pred_by_name.get(d["disease"], {}).get("evidence") or []
        for line in ev:
            print(f"      - {line}")


def _print_findings(out: Dict[str, Any]) -> None:
    _hr("Notable Findings (top-5)")
    if not out["notableFindings"]:
        print("  (없음 — query 가 모든 ROI severity=low 거나 유사 사례 finding 가 적음)")
        return
    for f in out["notableFindings"][:5]:
        print(f"  - {f['finding']:<35} freq_in_similar={f['frequencyInSimilarCases']:.2f}")
        ev = f.get("currentCaseEvidence") or {}
        if ev:
            print(f"      현재 영상 evidence: {json.dumps(ev, ensure_ascii=False)}")


def _print_similar(out: Dict[str, Any], top: int) -> None:
    _hr(f"Similar Cases (top-{top})")
    rows = out["similarCases"][:top]
    if not rows:
        print("  (DB 에 등록된 케이스가 없거나 view/modelVersion 미일치)")
        return
    for c in rows:
        print(f"  - {c['caseId']}  sim={c['similarity']:.3f}")
        if c.get("diseaseTags"):
            print(f"      diseases: {c['diseaseTags']}")
        if c.get("findingTags"):
            print(f"      findings: {c['findingTags']}")


def _print_roi(out: Dict[str, Any]) -> None:
    _hr("Query ROI Severity / Stats")
    roi_block = out["queryCase"].get("roiStats") or {}
    if not roi_block:
        print("  (roiStats 없음)")
        return
    sev_order = {"high": 0, "medium": 1, "low": 2}
    items = sorted(
        roi_block.items(),
        key=lambda kv: (sev_order.get((kv[1] or {}).get("severity", "low"), 9), -float((kv[1] or {}).get("p95Error", 0))),
    )
    print(f"  {'roi':<22} {'sev':<7} {'mean':>7} {'p95':>7} {'max':>7} {'area%':>7}")
    for roi, st in items:
        st = st or {}
        sev = st.get("severity", "?")
        print(
            f"  {roi:<22} {sev:<7} "
            f"{float(st.get('meanError', 0)):>7.3f} "
            f"{float(st.get('p95Error', 0)):>7.3f} "
            f"{float(st.get('maxError', 0)):>7.3f} "
            f"{float(st.get('areaRatio', 0)) * 100:>6.1f}%"
        )


def _print_uncertainty(out: Dict[str, Any], explanation: Dict[str, Any]) -> None:
    _hr("Uncertainty")
    u = out["uncertainty"]
    print(f"  level: {u['level']}")
    if u.get("reasons"):
        for r in u["reasons"]:
            print(f"  - {r}")
    print(f"  agent confidence: {(explanation.get('predictedDiseases') or [{}])[0].get('confidenceLevel', '?')}")


def _print_explanation_extras(explanation: Dict[str, Any]) -> None:
    _hr("Agent Explanation (요약 + limitations)")
    print(f"  summary: {explanation.get('summary', '')}")
    for line in explanation.get("limitations", []) or []:
        print(f"  - {line}")
    if explanation.get("graphEvidence"):
        ge = explanation["graphEvidence"]
        n_disease = len(ge.get("diseases", [])) if isinstance(ge, dict) else 0
        n_finding = len(ge.get("findings", [])) if isinstance(ge, dict) else 0
        n_roi = len(ge.get("rois", [])) if isinstance(ge, dict) else 0
        print(f"  graphEvidence: diseases={n_disease}, findings={n_finding}, rois={n_roi}")


# ---------- Ground truth (CheXpert csv) 조회 ----------
def _find_chexpert_row(archive: Path, image_path: Path) -> Optional[Dict[str, str]]:
    import csv

    try:
        rel = image_path.resolve().relative_to(archive.resolve())
    except ValueError:
        return None
    rel_str = "/".join(rel.parts)
    candidates = {rel_str, "CheXpert-v1.0-small/" + rel_str, "CheXpert-v1.0/" + rel_str}

    for split in ("valid", "train"):
        csv_file = archive / f"{split}.csv"
        if not csv_file.exists():
            continue
        with open(csv_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                p = row.get("Path", "").replace("\\", "/").strip()
                if p in candidates or p.endswith(rel_str):
                    return row
    return None


def _row_to_disease_set(row: Dict[str, str]) -> Set[str]:
    """uncertainty=ones 정책 (시스템 default) 으로 ground truth 집합 생성."""
    out: Set[str] = set()
    for col, tag in CHEXPERT_LABEL_MAP.items():
        v = (row.get(col) or "").strip()
        if v in ("1.0", "1", "-1.0", "-1"):
            out.add(tag)
    return out


def _print_ground_truth(gt: Set[str], pred_top1: Set[str], pred_top3: Set[str]) -> None:
    _hr("Ground Truth (CheXpert) vs Prediction")
    print(f"  ground_truth: {sorted(gt) or '(No Finding / 라벨 없음)'}")
    print(f"  predicted_top1: {sorted(pred_top1)}")
    print(f"  predicted_top3: {sorted(pred_top3)}")
    if gt:
        top1_match = sorted(pred_top1 & gt)
        top3_match = sorted(pred_top3 & gt)
        print(f"  match@1: {top1_match or '✗ 없음'}")
        print(f"  match@3: {top3_match or '✗ 없음'}")
        missed = sorted(gt - pred_top3)
        if missed:
            print(f"  missed (top-3 안에 없음): {missed}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--image", required=True, help="추론할 X-ray 이미지 경로")
    p.add_argument("--top-k", type=int, default=10, help="similar case top-K (default: 10)")
    p.add_argument("--view", default=None, help="view 힌트 (AP/PA/Lateral)")
    p.add_argument("--full", action="store_true", help="JSON 전체를 추가로 출력")
    p.add_argument("--ground-truth", default=None,
                   help="CheXpert archive 경로. 지정 시 csv 에서 라벨을 찾아 자동 비교")
    p.add_argument("--save", default=None, help="JSON 결과를 저장할 경로")
    args = p.parse_args()

    img_path = Path(args.image)
    if not img_path.exists():
        print(f"[fail] image not found: {img_path}")
        return 2

    container = get_container()
    print(f"[infer] image={img_path}")
    print(f"[infer] view={args.view or '(auto)'}, top_k={args.top_k}")
    res = container.case_service.infer(
        image_bytes=img_path.read_bytes(),
        view=args.view,
        model_version=None,
        mask_version=None,
        top_k=args.top_k,
    )
    out = res.model_dump()
    explanation = out.get("explanation") or {}

    _print_predicted(out, explanation)
    _print_findings(out)
    _print_roi(out)
    _print_similar(out, top=min(5, args.top_k))
    _print_uncertainty(out, explanation)
    _print_explanation_extras(explanation)

    _hr("Heatmap")
    print(f"  {out.get('heatmapPath') or '(없음)'}")

    _hr("Warning")
    print(f"  {out.get('warning', '')}")

    pred_top1: Set[str] = set([d["disease"] for d in out["predictedDiseases"][:1]])
    pred_top3: Set[str] = set([d["disease"] for d in out["predictedDiseases"][:3]])

    if args.ground_truth:
        archive = Path(args.ground_truth)
        if not archive.exists():
            print(f"\n[gt] archive not found: {archive}")
        else:
            row = _find_chexpert_row(archive, img_path)
            if row is None:
                print(f"\n[gt] CheXpert csv 에서 해당 이미지를 찾지 못했습니다 (path 매칭 실패)")
            else:
                gt = _row_to_disease_set(row)
                _print_ground_truth(gt, pred_top1, pred_top3)

    if args.full:
        _hr("Full JSON")
        print(json.dumps(out, ensure_ascii=False, indent=2))

    if args.save:
        save_path = Path(args.save)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[save] {save_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
