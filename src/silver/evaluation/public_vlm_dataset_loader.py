"""VLABench public VLM dataset loader for SILVER Track A.

This module discovers and materializes the exact files used for Track A:
input image, visual-prompt image, instruction, GT operation sequence, and
environment config. It never creates replacement samples.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ID = "VLABench/vlm_evaluation_v1.0"
HF_API_ROOT = f"https://huggingface.co/api/datasets/{REPO_ID}/tree/main"
HF_RESOLVE_ROOT = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main"
TRACK_ROOT = Path("silver/results/track_a_vlabench_planning_20260510")

TOP_CATEGORIES = ("CommenSence", "Complex", "M&T", "PhysicsLaw", "Semantic", "Spatial")
REQUIRED_REMOTE_FILES = {
    "input.png": "input/input.png",
    "input_mask.png": "input/input_mask.png",
    "instruction.txt": "input/instruction.txt",
    "operation_sequence.json": "output/operation_sequence.json",
    "env_config.json": "env_config/env_config.json",
}


@dataclass(frozen=True)
class SampleRef:
    category: str
    task: str
    example: str

    @property
    def sample_id(self) -> str:
        return f"{self.category}/{self.task}/{self.example}"

    @property
    def relative_dir(self) -> Path:
        return Path(self.category) / self.task / self.example


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hf_api_json(path: str = "") -> list[dict[str, Any]]:
    suffix = "" if not path else "/" + urllib.parse.quote(path, safe="/")
    url = HF_API_ROOT + suffix
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def hf_download(remote_path: str, local_path: Path, retries: int = 3) -> tuple[bool, str | None]:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if local_path.exists() and local_path.stat().st_size > 0:
        return True, None
    url = HF_RESOLVE_ROOT + "/" + urllib.parse.quote(remote_path, safe="/")
    tmp_path = local_path.with_suffix(local_path.suffix + ".partial")
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=180) as resp, tmp_path.open("wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            if tmp_path.stat().st_size <= 0:
                return False, "empty_download"
            tmp_path.replace(local_path)
            return True, None
        except Exception as exc:  # noqa: BLE001
            if tmp_path.exists():
                tmp_path.unlink()
            if attempt == retries:
                return False, f"download_error:{type(exc).__name__}:{exc}"
            time.sleep(2 * attempt)
    return False, "unknown_download_error"


def natural_example_key(name: str) -> tuple[int, str]:
    if name.startswith("example"):
        suffix = name.replace("example", "", 1)
        if suffix.isdigit():
            return int(suffix), name
    return 10**9, name


def discover_samples() -> tuple[list[SampleRef], dict[str, int]]:
    samples: list[SampleRef] = []
    task_counts: dict[str, int] = {}
    top_entries = hf_api_json()
    categories = sorted([e["path"] for e in top_entries if e.get("type") == "directory"])
    missing_categories = sorted(set(TOP_CATEGORIES) - set(categories))
    if missing_categories:
        raise RuntimeError(f"Missing expected categories from HF tree: {missing_categories}")

    for category in TOP_CATEGORIES:
        task_entries = hf_api_json(category)
        tasks = sorted([Path(e["path"]).name for e in task_entries if e.get("type") == "directory"])
        task_counts[category] = len(tasks)
        for task in tasks:
            example_entries = hf_api_json(f"{category}/{task}")
            examples = sorted(
                [Path(e["path"]).name for e in example_entries if e.get("type") == "directory"],
                key=natural_example_key,
            )
            for example in examples:
                samples.append(SampleRef(category, task, example))
    return samples, task_counts


def write_progress(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = [f"# {title}", "", f"Updated: {now_iso()}", ""]
    content.extend(lines)
    path.write_text("\n".join(content) + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def materialize_one_sample(sample: SampleRef, index: int, data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    local_dir = data_dir / sample.relative_dir
    row: dict[str, Any] = {
        "sample_index": index,
        "sample_id": sample.sample_id,
        "category": sample.category,
        "task": sample.task,
        "example": sample.example,
        "local_dir": str(local_dir),
        "download_ok": True,
        "missing_files": [],
        "file_sha256": {},
    }
    failures: list[dict[str, Any]] = []
    for local_name, remote_suffix in REQUIRED_REMOTE_FILES.items():
        remote_path = f"{sample.sample_id}/{remote_suffix}"
        local_path = local_dir / local_name
        ok, error = hf_download(remote_path, local_path)
        row[local_name] = str(local_path)
        if not ok:
            row["download_ok"] = False
            row["missing_files"].append(local_name)
            failures.append(
                {
                    "stage": "materialize",
                    "sample_id": sample.sample_id,
                    "file": local_name,
                    "remote_path": remote_path,
                    "error": error,
                    "time": now_iso(),
                }
            )
        elif local_path.exists():
            row["file_sha256"][local_name] = sha256_file(local_path)

    if row["download_ok"]:
        instruction = (local_dir / "instruction.txt").read_text(encoding="utf-8-sig").strip()
        gt_text = (local_dir / "operation_sequence.json").read_text(encoding="utf-8-sig")
        row["instruction"] = instruction
        row["instruction_sha256"] = sha256_text(instruction)
        row["gt_sha256"] = sha256_text(gt_text)
        try:
            gt = json.loads(gt_text)
            seq = gt.get("skill_sequence", []) if isinstance(gt, dict) else []
            row["gt_sequence_length"] = len(seq) if isinstance(seq, list) else None
            row["gt_skills"] = [s.get("name") for s in seq if isinstance(s, dict)]
        except json.JSONDecodeError as exc:
            row["download_ok"] = False
            row["gt_parse_error"] = str(exc)
            failures.append(
                {
                    "stage": "gt_parse",
                    "sample_id": sample.sample_id,
                    "file": "operation_sequence.json",
                    "error": str(exc),
                    "time": now_iso(),
                }
            )
    return row, failures


def materialize_dataset(track_root: Path, limit: int | None = None, workers: int = 8) -> list[dict[str, Any]]:
    manifest_dir = track_root / "manifest"
    metrics_dir = track_root / "metrics"
    data_dir = track_root / "data"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    failed_path = metrics_dir / "failed_samples.jsonl"

    samples, task_counts = discover_samples()
    if limit is not None:
        samples = samples[:limit]

    with (manifest_dir / "category_task_counts.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "task_count"])
        writer.writeheader()
        for category, count in task_counts.items():
            writer.writerow({"category": category, "task_count": count})

    rows: list[dict[str, Any]] = []
    manifest_path = manifest_dir / "vlabench_sample_manifest.jsonl"
    if manifest_path.exists():
        manifest_path.unlink()

    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(materialize_one_sample, sample, idx, data_dir): (idx, sample)
            for idx, sample in enumerate(samples, start=1)
        }
        for future in as_completed(futures):
            row, failures = future.result()
            for failure in failures:
                append_jsonl(failed_path, failure)
            append_jsonl(manifest_path, row)
            rows.append(row)
            completed += 1
            if completed % 100 == 0:
                print(f"[materialize] {completed}/{len(samples)}")

    return rows


def preflight(track_root: Path) -> dict[str, Any]:
    samples, task_counts = discover_samples()
    known = SampleRef("M&T", "select_fruit", "example0")
    proof_dir = track_root / "preflight" / known.relative_dir
    proof: dict[str, Any] = {}
    for local_name, remote_suffix in REQUIRED_REMOTE_FILES.items():
        remote_path = f"{known.sample_id}/{remote_suffix}"
        local_path = proof_dir / local_name
        ok, error = hf_download(remote_path, local_path)
        proof[local_name] = {
            "ok": ok,
            "error": error,
            "path": str(local_path),
            "size": local_path.stat().st_size if local_path.exists() else 0,
            "sha256": sha256_file(local_path) if local_path.exists() else None,
        }
    result = {
        "time": now_iso(),
        "repo_id": REPO_ID,
        "top_categories": list(TOP_CATEGORIES),
        "category_task_counts": task_counts,
        "discovered_samples": len(samples),
        "published_rows_expected_from_current_tree": len(samples),
        "published_total_size_note": "Hugging Face UI reports size category and the repository contains 22,503 siblings; current public tree/README expose 45 tasks x 100 episodes = 4,500 samples.",
        "proof_sample": known.sample_id,
        "proof_files": proof,
    }
    out = track_root / "manifest" / "preflight.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    progress_lines = [
        "## Step 0. Preflight",
        "",
        "- Status: completed",
        f"- Dataset: `{REPO_ID}`",
        f"- Discovered samples: {len(samples)}",
        f"- Category task counts: `{task_counts}`",
        f"- Proof sample: `{known.sample_id}`",
        f"- Evidence: `{out}`",
    ]
    write_progress(track_root / "TRACK_A_PROGRESS.md", "Track A Progress", progress_lines)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="VLABench Track A dataset loader.")
    parser.add_argument("command", choices=("preflight", "materialize"))
    parser.add_argument("--track_root", type=Path, default=TRACK_ROOT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    if args.command == "preflight":
        print(json.dumps(preflight(args.track_root), ensure_ascii=False, indent=2))
    elif args.command == "materialize":
        rows = materialize_dataset(args.track_root, args.limit, args.workers)
        ok = sum(1 for r in rows if r.get("download_ok"))
        print(json.dumps({"total": len(rows), "materialized_ok": ok}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
