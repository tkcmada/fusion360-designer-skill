#!/usr/bin/env bash
# 公開リポジトリ用 決定論ガード(LLM非依存)。違反で非0終了。
#   使い方: scripts/check_public.sh [staged|tree]
#   - ALLOWLIST: 許可パスのみ(skill 構成ファイル)。それ以外は BLOCK。
#   - 拡張子で binary/artifact(zip/step/stl/png/pdf/pyc…)を BLOCK。
#   - 汎用 secret/provenance パターンを BLOCK(公開に置いて安全な正規表現)。
#   - 非公開語の denylist は LOCAL ファイル($PUBLIC_REPO_DENYLIST or .git/private-denylist)
#     を読む(公開 repo には語を置かない)。無ければ警告のみ。
set -u
MODE="${1:-staged}"
ROOT="$(git rev-parse --show-toplevel)" || exit 2
cd "$ROOT" || exit 2
fail=0
err(){ echo "BLOCK: $*" >&2; fail=1; }

if [ "$MODE" = staged ]; then
  files=$(git diff --cached --name-only --diff-filter=ACMR)
else
  files=$(git ls-files)
fi

allow_re='^(SKILL\.md|README\.md|LICENSE|\.gitignore|reference/[^/]+\.md|examples/[^/]+/[^/]+\.(py|manifest)|scripts/[^/]+\.sh|\.github/workflows/[^/]+\.ya?ml)$'
secret_re='(BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-|claude\.ai/code/session)'

for f in $files; do
  echo "$f" | grep -Eq "$allow_re" || err "non-allowlisted path: $f"
  echo "$f" | grep -Eiq '\.(zip|step|stp|stl|f3d|f3z|png|jpe?g|pdf|pyc|bin)$' && err "artifact/binary: $f"
done

for f in $files; do
  [ -f "$f" ] || continue
  grep -EnI "$secret_re" "$f" >/dev/null 2>&1 && { err "secret/provenance in $f"; grep -EnI "$secret_re" "$f" | head -3 >&2; }
done

DL="${PUBLIC_REPO_DENYLIST:-$ROOT/.git/private-denylist}"
if [ -f "$DL" ]; then
  while IFS= read -r term; do
    [ -z "$term" ] && continue
    case "$term" in \#*) continue;; esac
    for f in $files; do
      [ -f "$f" ] || continue
      grep -nFI "$term" "$f" >/dev/null 2>&1 && err "private term '$term' in $f"
    done
  done < "$DL"
else
  echo "WARN: private denylist not found ($DL) — private-term scan skipped" >&2
fi

if [ "$fail" -eq 0 ]; then echo "check_public($MODE): OK"; else echo "check_public($MODE): BLOCKED" >&2; fi
exit "$fail"
