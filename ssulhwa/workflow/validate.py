#!/usr/bin/env python3
"""Stage 6: 에피소드 최종 검증 스크립트.

사용법: python validate.py <에피소드_파일_경로>
출력: JSON 형식의 검증 결과
"""

import io
import json
import re
import sys
from pathlib import Path

# Windows 환경 UTF-8 출력 보장
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def extract_body(text: str) -> str:
    """본문만 추출 (헤더/IMG/구분자/예고 제외)."""
    lines = text.split("\n")
    body_lines = []
    in_body = False

    for line in lines:
        stripped = line.strip()
        # 헤더 건너뛰기
        if stripped.startswith("# EP-"):
            in_body = True
            continue
        # 한줄요약 건너뛰기 (> 로 시작)
        if stripped.startswith(">") and not in_body:
            continue
        if not in_body:
            # 첫 --- 이후부터 본문
            if stripped == "---":
                in_body = True
            continue
        # 다음 화 예고 이후 제외
        if stripped.startswith("**다음 화 예고**") or stripped.startswith("**다음화 예고**"):
            break
        # [IMG] 마커 제외
        if re.match(r"^\[IMG:[^\]]+\]$", stripped):
            continue
        # 구분자 제외
        if stripped == "---":
            continue
        body_lines.append(line)

    return "\n".join(body_lines)


def check_f1_char_count(text: str) -> dict:
    """F1: 글자 수 검증 (9,000~11,000자)."""
    body = extract_body(text)
    # 공백/줄바꿈 제외한 순수 글자 수
    char_count = len(body.replace("\n", "").replace(" ", ""))
    passed = 9000 <= char_count <= 11000
    return {
        "id": "F1",
        "name": "글자 수",
        "result": "PASS" if passed else "FAIL",
        "value": char_count,
        "criteria": "9,000~11,000자",
        "detail": f"본문 {char_count}자" + ("" if passed else f" ({'부족' if char_count < 9000 else '초과'})")
    }


def check_f2_img_markers(text: str) -> dict:
    """F2: [IMG] 마커 수 검증 (3~5개)."""
    markers = re.findall(r"\[IMG:[^\]]+\]", text)
    count = len(markers)
    passed = 3 <= count <= 5
    return {
        "id": "F2",
        "name": "[IMG] 마커",
        "result": "PASS" if passed else "FAIL",
        "value": count,
        "criteria": "3~5개",
        "detail": f"[IMG] 마커 {count}개" + ("" if passed else f" ({'부족' if count < 3 else '초과'})")
    }


def check_f3_scene_separators(text: str) -> dict:
    """F3: 씬 구분자 수 검증 (3~6개)."""
    lines = text.split("\n")
    count = sum(1 for line in lines if line.strip() == "---")
    passed = 3 <= count <= 6
    return {
        "id": "F3",
        "name": "씬 구분자",
        "result": "PASS" if passed else "FAIL",
        "value": count,
        "criteria": "3~6개",
        "detail": f"--- 구분자 {count}개" + ("" if passed else f" ({'부족' if count < 3 else '초과'})")
    }


def check_f4_markdown_structure(text: str) -> dict:
    """F4: 마크다운 구조 검증 (# EP-XX: 존재)."""
    matches = re.findall(r"^# EP-\d+:", text, re.MULTILINE)
    count = len(matches)
    passed = count == 1
    return {
        "id": "F4",
        "name": "마크다운 구조",
        "result": "PASS" if passed else "FAIL",
        "value": count,
        "criteria": "# EP-XX: 헤더 1개",
        "detail": f"헤더 {count}개 발견" + ("" if passed else " (정확히 1개 필요)")
    }


def check_f5_next_preview(text: str) -> dict:
    """F5: 다음 화 예고 존재 검증."""
    has_preview = bool(re.search(r"\*\*다음\s*화\s*예고\*\*", text))
    return {
        "id": "F5",
        "name": "다음 화 예고",
        "result": "PASS" if has_preview else "FAIL",
        "value": 1 if has_preview else 0,
        "criteria": "**다음 화 예고** 1개",
        "detail": "다음 화 예고 " + ("존재" if has_preview else "없음")
    }


def _has_ssang_siot_batchim(char: str) -> bool:
    """한글 글자의 받침이 ㅆ(쌍시옷)인지 확인."""
    code = ord(char) - 0xAC00
    if code < 0 or code > 11171:
        return False
    return code % 28 == 20  # ㅆ 종성 인덱스


def _classify_ending(sentence: str) -> str:
    """문장 종결어미를 분류.

    Returns:
        'PAST': 과거 서술형 (~았다/었다/였다/했다/갔다/왔다 등 ㅆ받침+다)
        'OTHER_DA': 기타 ~다 종결 (현재형 ~ㄴ다, 피동 ~된다 등 - 변주로 인정)
        'NON_DA': ~다로 끝나지 않음 (명사형, 연결형, 대사 등)
    """
    clean = sentence.rstrip(".!? \t")
    if len(clean) >= 2 and clean[-1] == "다":
        prev = clean[-2]
        if _has_ssang_siot_batchim(prev):
            # 있다(상태/존재), 겠다(추측/미래)는 과거형이 아님
            if prev in ("있", "겠"):
                return "OTHER_DA"
            return "PAST"
        return "OTHER_DA"
    return "NON_DA"


def check_f6_sentence_endings(text: str) -> dict:
    """F6: 과거형 문미 연속 체크.

    과거 서술형(~았다/었다/였다/했다 등 ㅆ받침+다)이 3개 이상 연속되면 FAIL.
    현재형(~ㄴ다/한다), 피동형(~된다/진다) 등은 다른 패턴으로 분류하여
    과거형 연속을 끊는 것으로 처리한다.
    대사(따옴표), 짧은 파편(10자 미만)은 제외한다.
    """
    body = extract_body(text)

    raw_lines = body.split("\n")
    sentences = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        parts = re.split(r'(?<=[.!?])\s+', line)
        sentences.extend(p.strip() for p in parts if p.strip())

    categories = []
    sentence_texts = []
    for s in sentences:
        if len(s) < 10:
            continue
        stripped = s.strip()
        # 대사 건너뛰기
        if stripped[0] in ('"', '\u201c', '\u300c'):
            continue
        if stripped.startswith("'") and stripped.endswith("'"):
            continue

        sentence_texts.append(stripped)
        categories.append(_classify_ending(stripped))

    # 연속 과거형(PAST) 3개 이상 탐지
    violation_groups = []
    start = -1
    consecutive = 0
    for i, cat in enumerate(categories):
        if cat == "PAST":
            if consecutive == 0:
                start = i
            consecutive += 1
        else:
            if consecutive >= 3:
                violation_groups.append({
                    "start": start,
                    "length": consecutive,
                    "samples": [sentence_texts[j][-30:] for j in range(start, start + min(consecutive, 3))]
                })
            consecutive = 0
            start = -1
    if consecutive >= 3:
        violation_groups.append({
            "start": start,
            "length": consecutive,
            "samples": [sentence_texts[j][-30:] for j in range(start, start + min(consecutive, 3))]
        })

    count = len(violation_groups)
    passed = count == 0
    detail_parts = [f"과거형 문미 연속 위반 {count}개소"]
    if not passed:
        for g in violation_groups[:3]:
            detail_parts.append(f"  [{g['length']}연속] ...{' / ...'.join(g['samples'])}")

    return {
        "id": "F6",
        "name": "문미 연속",
        "result": "PASS" if passed else "FAIL",
        "value": count,
        "criteria": "과거형(~았/었/였/했다) 3연속 0개소",
        "detail": "\n".join(detail_parts)
    }


def validate(filepath: str) -> dict:
    """전체 검증 실행."""
    path = Path(filepath)
    if not path.exists():
        return {"error": f"파일을 찾을 수 없음: {filepath}", "overall": "ERROR"}

    text = path.read_text(encoding="utf-8")

    results = [
        check_f1_char_count(text),
        check_f2_img_markers(text),
        check_f3_scene_separators(text),
        check_f4_markdown_structure(text),
        check_f5_next_preview(text),
        check_f6_sentence_endings(text),
    ]

    fail_items = [r["id"] for r in results if r["result"] == "FAIL"]
    overall = "FAIL" if fail_items else "PASS"

    return {
        "file": str(path),
        "results": results,
        "overall": overall,
        "fail_items": fail_items,
        "summary": {r["id"]: r["result"] for r in results}
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "사용법: python validate.py <파일경로>", "overall": "ERROR"}, ensure_ascii=False))
        sys.exit(1)

    result = validate(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["overall"] == "PASS" else 1)
