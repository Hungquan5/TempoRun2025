#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Dict, Any, Tuple

def fix_top_level_keys(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize common key quirks at the top level (e.g., 'content:' -> 'content').
    """
    fixed = {}
    for k, v in d.items():
        k2 = re.sub(r":+$", "", str(k)).strip()
        fixed[k2] = v
    return fixed

def strip_from_questions(obj: Dict[str, Any]) -> Tuple[int, int]:
    """
    Remove 'correct_answer' and 'explanation' inside obj['questions'] (if present).
    Returns (removed_correct, removed_expl) counts.
    """
    removed_correct = 0
    removed_expl = 0

    questions = obj.get("questions", [])
    if not isinstance(questions, list):
        return removed_correct, removed_expl

    for q in questions:
        if not isinstance(q, dict):
            continue
        # Normalize nested keys that might have trailing colons
        keys_map = {k: re.sub(r":+$", "", str(k)).strip() for k in list(q.keys())}
        # If a normalized key conflicts, prefer normalized
        for old_k, new_k in keys_map.items():
            if new_k != old_k:
                q[new_k] = q.pop(old_k)

        if "correct_answer" in q:
            q.pop("correct_answer", None)
            removed_correct += 1
        if "explanation" in q:
            q.pop("explanation", None)
            removed_expl += 1

    return removed_correct, removed_expl

def process_file(src_path: Path, dst_path: Path) -> Tuple[int, int]:
    data = json.loads(src_path.read_text(encoding="utf-8"))

    # Normalize top-level keys first
    data = fix_top_level_keys(data)

    # Strip fields from questions
    rc, rexp = strip_from_questions(data)

    # Save with pretty, stable formatting
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return rc, rexp

def main():
    ap = argparse.ArgumentParser(
        description="Strip 'correct_answer' and 'explanation' from JSONs in a public/ folder."
    )
    ap.add_argument("--public_dir", type=Path, required=True, help="Path to public/ folder containing .json files.")
    ap.add_argument("--out_dir", type=Path, default=None,
                    help="Output directory for cleaned files. If omitted and --inplace is set, files are overwritten.")
    ap.add_argument("--inplace", action="store_true",
                    help="Edit files in place (requires no out_dir).")
    ap.add_argument("--glob", default="*.json", help="Glob pattern for JSON files (default: *.json)")
    args = ap.parse_args()

    if args.inplace and args.out_dir is not None:
        ap.error("Use either --inplace OR --out_dir, not both.")
    if not args.public_dir.exists():
        ap.error(f"public_dir not found: {args.public_dir}")

    total_files = 0
    total_removed_correct = 0
    total_removed_expl = 0

    for src_path in sorted(args.public_dir.glob(args.glob)):
        if not src_path.is_file():
            continue
        total_files += 1
        dst_path = src_path if args.inplace else (
            (args.out_dir / src_path.name) if args.out_dir else None
        )
        if dst_path is None:
            # Default to a 'public_clean/' sibling if neither flag provided
            dst_path = args.public_dir.parent / "public_clean" / src_path.name

        rc, rexp = process_file(src_path, dst_path)
        total_removed_correct += rc
        total_removed_expl += rexp
        print(f"[OK] {src_path.name} -> {dst_path}  (-correct_answer:{rc}, -explanation:{rexp})")

    print("\nSummary")
    print("-------")
    print(f"Files processed       : {total_files}")
    print(f"correct_answer removed: {total_removed_correct}")
    print(f"explanation removed   : {total_removed_expl}")

if __name__ == "__main__":
    main()
