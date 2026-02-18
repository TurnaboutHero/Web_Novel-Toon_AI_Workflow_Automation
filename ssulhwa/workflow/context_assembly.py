#!/usr/bin/env python3
"""Stage 1: 에피소드 컨텍스트 조립 헬퍼.

사용법: python context_assembly.py EP-05
출력: JSON 형식의 컨텍스트 패키지
"""

import io
import json
import re
import sys
from pathlib import Path

# Windows 환경 UTF-8 출력 보장
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 프로젝트 루트 기준 경로
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
LORE_DIR = SCRIPT_DIR.parent / "lore"
EPISODES_DIR = SCRIPT_DIR.parent / "episodes"

# 키워드 → 세계관 섹션 매핑
WORLD_KEYWORDS = {
    "energy": {
        "keywords": ["전투", "마나", "기운", "폭주", "마법", "에너지", "서클", "공격", "방어", "검"],
        "sections": ["에너지원 체계", "에너지 작용 원리", "안정화 매개체", "마나 운용 메커니즘", "마법 분류 체계", "실전 마법 운용"]
    },
    "geography": {
        "keywords": ["루미나리아", "아스트라", "크론하임", "실바렌", "수도", "도시", "숲", "산맥", "동굴"],
        "sections": ["사회/거점", "지리 개요", "거점/기관 이중 구조"]
    },
    "integration": {
        "keywords": ["또아리", "통합", "조율", "동적", "꼬기", "3에너지", "해체"],
        "sections": ["에너지 통합 이론", "또아리 조율", "동적 조율"]
    },
    "politics": {
        "keywords": ["왕실", "견제파", "심사", "카르마", "정치", "왕가", "맹약"],
        "sections": ["왕가-엔타리스 관계", "왕립 초능력원"]
    },
    "dragon": {
        "keywords": ["드래곤", "코오리", "호노오", "드래고니안", "폴리모프"],
        "sections": ["드래고니안", "드래곤 사회 규칙"]
    },
    "circle": {
        "keywords": [],  # 항상 포함
        "sections": ["서클 체계"]
    }
}

# 캐릭터 이름 → 섹션 헤더 매핑
CHARACTER_NAMES = {
    "사일라즈": "사일라즈 엔타리스",
    "마일스": "마일스 엔타리스",
    "카르마": "카르마 엔타리스",
    "소피아": "소피아",
    "코오리": "츠메타이 코오리",
    "알드릭": "알드릭 아우렐리스",
    "루시안": "루시안 아우렐리스",
}


def parse_ep_number(ep_arg: str) -> int:
    """EP-XX 형식에서 번호 추출."""
    match = re.match(r"EP-?(\d+)", ep_arg, re.IGNORECASE)
    if not match:
        raise ValueError(f"잘못된 에피소드 형식: {ep_arg} (예: EP-05)")
    return int(match.group(1))


def extract_ep_outline(text: str, ep_num: int) -> dict:
    """episode-outline.md에서 해당 EP 아웃라인 + 직전 EP 엔딩 훅 추출."""
    ep_tag = f"EP-{ep_num:02d}"
    prev_tag = f"EP-{ep_num - 1:02d}" if ep_num > 1 else None

    result = {"outline": "", "prev_ending_hook": "", "ep_title": ""}

    # 현재 EP 아웃라인 추출
    pattern = rf"### {ep_tag}:(.+?)(?=\n### EP-|\n---|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        result["outline"] = f"### {ep_tag}:{match.group(1).strip()}"
        # 제목 추출
        title_match = re.search(rf"### {ep_tag}:\s*(.+?)(?:\s*\[|$)", match.group(0).split("\n")[0])
        if title_match:
            result["ep_title"] = title_match.group(1).strip()

    # 직전 EP 엔딩 훅 추출
    if prev_tag:
        prev_pattern = rf"### {prev_tag}:(.+?)(?=\n### EP-|\n---|\Z)"
        prev_match = re.search(prev_pattern, text, re.DOTALL)
        if prev_match:
            hook_match = re.search(r"\*\*엔딩 훅\*\*:\s*(.+?)(?:\n\n|\n-|\Z)", prev_match.group(1), re.DOTALL)
            if hook_match:
                result["prev_ending_hook"] = hook_match.group(1).strip()

    return result


def extract_characters(text: str, outline: str) -> str:
    """characters.md에서 아웃라인에 언급된 캐릭터 섹션만 추출."""
    mentioned = []
    for name, section_header in CHARACTER_NAMES.items():
        if name in outline:
            mentioned.append(section_header)

    if not mentioned:
        # 기본: 사일라즈는 항상 포함
        mentioned = ["사일라즈 엔타리스"]

    extracted = []
    for header in mentioned:
        pattern = rf"## {re.escape(header)}(.+?)(?=\n## |\Z)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            section = f"## {header}{match.group(1)}"
            # 너무 길면 핵심만 (처음 80줄)
            lines = section.split("\n")
            if len(lines) > 80:
                section = "\n".join(lines[:80]) + "\n[... 이하 생략]"
            extracted.append(section)

    return "\n\n".join(extracted)


def extract_world_sections(text: str, outline: str) -> str:
    """world.md에서 키워드 기반 관련 섹션 추출."""
    needed_sections = set()

    # 항상 포함: 서클 체계
    needed_sections.update(WORLD_KEYWORDS["circle"]["sections"])

    # 키워드 기반 매칭
    for category, config in WORLD_KEYWORDS.items():
        for keyword in config["keywords"]:
            if keyword in outline:
                needed_sections.update(config["sections"])
                break

    # 섹션 추출
    extracted = []
    for section_name in needed_sections:
        pattern = rf"### {re.escape(section_name)}(.+?)(?=\n### |\n## |\Z)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            section = f"### {section_name}{match.group(1)}"
            lines = section.split("\n")
            if len(lines) > 60:
                section = "\n".join(lines[:60]) + "\n[... 이하 생략]"
            extracted.append(section)

    return "\n\n".join(extracted)


def get_previous_episode_ending(ep_num: int) -> str:
    """이전 에피소드 파일의 마지막 500자 추출."""
    if ep_num <= 1:
        return ""

    prev_tag = f"EP-{ep_num - 1:02d}"

    # episodes/ 디렉토리에서 이전 EP 파일 검색
    for pattern in [f"{prev_tag}_*.md", f"{prev_tag}*.md"]:
        matches = list(EPISODES_DIR.glob(pattern))
        if matches:
            text = matches[0].read_text(encoding="utf-8")
            return text[-500:] if len(text) > 500 else text

    # pilot/ 디렉토리도 검색
    pilot_dir = EPISODES_DIR / "pilot"
    if pilot_dir.exists():
        for pattern in [f"{prev_tag}_*.md", f"{prev_tag}*.md"]:
            matches = list(pilot_dir.glob(pattern))
            if matches:
                text = matches[0].read_text(encoding="utf-8")
                return text[-500:] if len(text) > 500 else text

    return ""


def assemble_context(ep_arg: str) -> dict:
    """전체 컨텍스트 조립."""
    ep_num = parse_ep_number(ep_arg)
    ep_tag = f"EP-{ep_num:02d}"

    # 로어 파일 읽기
    outline_text = (LORE_DIR / "episode-outline.md").read_text(encoding="utf-8")
    characters_text = (LORE_DIR / "characters.md").read_text(encoding="utf-8")
    world_text = (LORE_DIR / "world.md").read_text(encoding="utf-8")
    style_text = (LORE_DIR / "style-guide.md").read_text(encoding="utf-8")

    # 아웃라인 추출
    ep_data = extract_ep_outline(outline_text, ep_num)

    # 아웃라인 텍스트 기반으로 캐릭터/세계관 추출
    outline_for_matching = ep_data["outline"]

    context = {
        "episode": ep_tag,
        "ep_number": ep_num,
        "ep_title": ep_data["ep_title"],
        "outline": ep_data["outline"],
        "prev_ending_hook": ep_data["prev_ending_hook"],
        "characters": extract_characters(characters_text, outline_for_matching),
        "world": extract_world_sections(world_text, outline_for_matching),
        "style_guide": style_text,
        "previous_ending": get_previous_episode_ending(ep_num),
    }

    # 토큰 추정 (한국어 1자 ≈ 1.5 토큰)
    total_chars = sum(len(str(v)) for v in context.values())
    context["_meta"] = {
        "total_chars": total_chars,
        "estimated_tokens": int(total_chars * 1.5),
        "sections_included": {
            "outline": bool(context["outline"]),
            "prev_ending_hook": bool(context["prev_ending_hook"]),
            "characters": bool(context["characters"]),
            "world": bool(context["world"]),
            "previous_ending": bool(context["previous_ending"]),
        }
    }

    return context


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "사용법: python context_assembly.py EP-05"}, ensure_ascii=False))
        sys.exit(1)

    try:
        result = assemble_context(sys.argv[1])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
