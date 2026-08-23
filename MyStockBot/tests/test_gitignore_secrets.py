"""비밀·산출물 파일이 실수로 커밋되지 않도록 `.gitignore` 를 잠근다.

## 왜 필요한가 (실측으로 발견)
2026-08-23 사용자 저장소의 `git status` 에 이런 줄이 있었다:

    ?? devDogam/.env.local
    ?? devDogam/tsconfig.tsbuildinfo

`git check-ignore` 로 확인하니 **둘 다 무시되지 않았다.** 이 저장소는 프로젝트 여러
개가 든 모노레포인데 루트 `.gitignore` 는 allowlist 방식(`*` 다음에 `!프로젝트/**`)이고,
비밀 관련 규칙은 `**/.env.js` 하나뿐이었다. 하위 프로젝트 중 자기 `.gitignore` 를 가진
것은 일부뿐이라(`devDogam` 은 없음) `git add -A` 한 번으로 `.env.local` 이 커밋될 수
있었다.

한 번 커밋되면 히스토리에서 지우는 것은 어렵고, 그 사이 푸시되면 사실상 유출이다.
그래서 **하위 프로젝트에 `.gitignore` 가 없어도 막히도록** 루트에 규칙을 둔다.

## 이 테스트가 지키는 두 방향
· 비밀·산출물 패턴은 **무시된다** (유출 방지)
· `.env.example` 같은 **템플릿은 무시되지 않는다** (과잉 차단 방지 — 새 개발자가
  받아야 하는 파일이고, 실제로 두 프로젝트가 추적 중이다)
"""
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(_REPO_ROOT), *args],
        capture_output=True, text=True, check=False,
    )


def _is_repo() -> bool:
    if not (_REPO_ROOT / ".git").exists():
        return False
    return _git("rev-parse", "--is-inside-work-tree").returncode == 0


pytestmark = pytest.mark.skipif(
    not _is_repo(), reason="git 저장소가 아님(sdist/배포본에서 실행된 경우)"
)


def _ignored(path: str) -> bool:
    """그 경로가 **패턴상** 무시되는가. 무시되면 exit 0, 아니면 1.

    ★ `--no-index` 가 반드시 필요하다. 기본 동작에서 `git check-ignore` 는 **이미
    추적 중인 파일을 항상 "무시 안 됨"으로 보고**한다(추적 파일은 무시 규칙보다
    우선하므로). 그래서 `--no-index` 없이 `.env.example` 을 검사하면 규칙을
    `**/.env*` 로 넓혀 템플릿까지 잡아도 테스트가 통과한다 — 즉 과잉 차단을 막는
    검사가 **무의미해진다.** 뮤테이션(`**/.env` → `**/.env*`)이 통과하는 것을 보고
    발견했다.
    """
    return _git("check-ignore", "-q", "--no-index", path).returncode == 0


# 하위 프로젝트에 개별 .gitignore 가 없어도 막혀야 하는 것들.
# devDogam 을 대표로 쓴다 — 실제로 .gitignore 가 없고 사고가 여기서 났다.
@pytest.mark.parametrize("path", [
    "devDogam/.env",
    "devDogam/.env.local",
    "devDogam/.env.production.local",
    "devDogam/tsconfig.tsbuildinfo",
    "devDogam/.vercel/project.json",
    # 다른 프로젝트도 같은 보호를 받아야 한다(자기 .gitignore 유무와 무관하게).
    "reviewPickAI/.env.local",
    "focusBear/.env",
    "newsBrew/backend/.env",
    "pharmaTA/.vercel/project.json",
])
def test_secret_and_artifact_paths_are_ignored(path):
    assert _ignored(path), (
        f"{path} 가 무시되지 않는다 — `git add -A` 로 커밋될 수 있다"
    )


@pytest.mark.parametrize("path", [
    "MyStockBot/web/.env.example",
    "newsBrew/backend/.env.example",
])
def test_env_templates_are_not_ignored(path):
    """템플릿은 추적되어야 한다 — 과잉 차단이면 새 개발자가 설정을 못 받는다."""
    assert not _ignored(path), f"{path} 가 무시된다 — 규칙이 너무 넓다"


# 비밀 보호 블록이 쓰는 패턴들. 이 목록이 곧 "내가 넓힌 범위"다.
_SECRET_RULE_PATTERNS = (
    "**/.env",
    "**/.env.local",
    "**/.env.*.local",
    "**/*.tsbuildinfo",
    "**/.vercel/",
)


def test_secret_rules_do_not_capture_tracked_files():
    """**비밀 보호 규칙**이 추적 중인 파일을 잡으면 안 된다.

    잡히면 그 파일은 추적된 상태로 남지만 `git status` 가 변경을 알려주지 않아
    조용히 낡는다. 규칙을 넓힐 때 가장 흔한 사고다.

    검사 범위를 이 블록으로 한정한 이유: 저장소에는 **이 작업과 무관한** 기존
    사례가 이미 있다(예: 루트의 `docs/` 규칙에 걸리는 `multiProfile/docs/**`,
    하위 프로젝트의 `*.json` 규칙). 그것까지 이 테스트가 실패로 잡으면 다른
    프로젝트의 기존 상태에 이 테스트가 인질로 잡힌다. 여기서 답할 질문은
    "내가 추가한 규칙이 무언가를 망가뜨렸나" 다.
    """
    tracked = _git("ls-files").stdout.splitlines()
    assert tracked, "추적 파일 목록이 비었다 — 저장소 상태가 이상하다"
    # -v 는 "<gitignore파일>:<줄>:<패턴>\t<경로>" 형태로 출처를 알려준다.
    result = _git("check-ignore", "-v", "--no-index", *tracked)
    offenders = []
    for line in result.stdout.splitlines():
        if "\t" not in line:
            continue
        source, path = line.split("\t", 1)
        pattern = source.rsplit(":", 1)[-1]
        if pattern in _SECRET_RULE_PATTERNS:
            offenders.append((pattern, path))
    assert offenders == [], f"비밀 보호 규칙이 추적 파일을 잡는다: {offenders[:5]}"
