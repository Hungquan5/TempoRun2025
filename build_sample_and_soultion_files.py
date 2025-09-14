#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

VALID_CHOICES = {"A", "B", "C", "D"}

def load_json_fix_keys(path: Path) -> Dict:
    """
    Load JSON and normalize a few common key quirks:
      - strip trailing ':' in keys (e.g., 'content:' -> 'content')
    """
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    fixed = {}
    for k, v in data.items():
        k2 = re.sub(r":+$", "", k.strip())  # remove any trailing colons
        fixed[k2] = v
    return fixed

def iter_qas_from_json(j: Dict) -> Iterable[Tuple[str, Dict]]:
    """
    Yield (question_text, qa_dict) for each question entry.
    Expects a 'questions' list with dicts that include:
      - 'question'
      - 'choices' (dict with A/B/C/D)
      - 'correct_answer' (training/solution only)
    """
    questions = j.get("questions", []) or []
    for qa in questions:
        # normalize nested keys (rare colon-edge)
        qa_fixed = {re.sub(r":+$", "", str(k)).strip(): v for k, v in qa.items()}
        yield str(qa_fixed.get("question", "")).strip(), qa_fixed

def make_row_id(stem: str, q_index: int) -> str:
    """
    Build a unique row_id. Using file stem + 1-based question index keeps it stable and human-decodable.
    Example: '0a3e4a42__q1'
    """
    return f"{stem}__q{q_index}"

def extract_rows_from_dir(data_dir: Path, usage_value: str) -> List[Dict]:
    """
    Walk a directory of JSON files and extract rows:
      - row_id
      - answer (ground truth)
      - Usage (Public/Private)
    """
    rows: List[Dict] = []
    for path in sorted(data_dir.glob("*.json")):
        j = load_json_fix_keys(path)
        stem = path.stem
        for i, (_, qa) in enumerate(iter_qas_from_json(j), start=1):
            # Ground truth must be present for solution building
            correct = qa.get("correct_answer", None)
            if correct is None:
                raise ValueError(
                    f"Missing 'correct_answer' in {path.name} (q#{i}). "
                    "Solution building requires ground-truth labels."
                )
            label = str(correct).strip().upper()
            if label not in VALID_CHOICES:
                raise ValueError(
                    f"Invalid correct_answer='{correct}' in {path.name} (q#{i}). "
                    f"Expected one of {sorted(VALID_CHOICES)}."
                )
            row = {
                "row_id": make_row_id(stem, i),
                "answer": label,
                "Usage": usage_value,
            }
            rows.append(row)
    return rows

def main(
    public_dir: Path,
    out_solution: Path,
    out_sample_sub: Path,
    private_dir: Optional[Path] = None,
):
    if not public_dir.exists():
        raise FileNotFoundError(f"Public dir not found: {public_dir}")

    # Build rows for Public
    public_rows = extract_rows_from_dir(public_dir, usage_value="Public")

    # Optionally add Private
    private_rows: List[Dict] = []
    if private_dir:
        if not private_dir.exists():
            raise FileNotFoundError(f"Private dir not found: {private_dir}")
        private_rows = extract_rows_from_dir(private_dir, usage_value="Private")

    rows = public_rows + private_rows
    if not rows:
        raise RuntimeError("No rows extracted. Are the folders empty?")

    df_solution = pd.DataFrame(rows)

    # Validate unique IDs
    dup = df_solution["row_id"].duplicated(keep=False)
    if dup.any():
        dups = df_solution.loc[dup, "row_id"].value_counts()
        raise ValueError(
            "Duplicate row_id detected in solution file. First few:\n"
            + dups.head(10).to_string()
        )

    # Optional: sort for determinism
    df_solution = df_solution.sort_values(["Usage", "row_id"]).reset_index(drop=True)

    # Save solution.csv
    out_solution.parent.mkdir(parents=True, exist_ok=True)
    df_solution.to_csv(out_solution, index=False, encoding="utf-8")
    print(f"✔ Wrote solution file: {out_solution}  (rows={len(df_solution)})")
    print(df_solution["Usage"].value_counts())

    # Build sample_submission.csv: same IDs, blank/placeholder answers
    df_sample = df_solution[["row_id"]].copy()
    df_sample["answer"] = "A"  # harmless default; competitors will overwrite
    df_sample.to_csv(out_sample_sub, index=False, encoding="utf-8")
    print(f"✔ Wrote sample submission: {out_sample_sub}  (rows={len(df_sample)})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build Kaggle solution.csv and sample_submission.csv from public/ (and optional private/) JSON QA files."
    )
    parser.add_argument("--public_dir", type=Path, required=True, help="Path to the public test folder containing JSON files.")
    parser.add_argument("--private_dir", type=Path, default=None, help="Path to the private test folder containing JSON files (optional).")
    parser.add_argument("--out_solution", type=Path, default=Path("solution.csv"), help="Output path for solution.csv")
    parser.add_argument("--out_sample", type=Path, default=Path("sample_submission.csv"), help="Output path for sample_submission.csv")
    args = parser.parse_args()

    main(
        public_dir=args.public_dir,
        out_solution=args.out_solution,
        out_sample_sub=args.out_sample,
        private_dir=args.private_dir,
    )
