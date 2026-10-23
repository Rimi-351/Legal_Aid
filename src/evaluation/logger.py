"""
src/evaluation/logger.py
------------------------
Reproducible experiment logger tracking model parameters, execution latency,
memory utilization, git revision, and retrieval results in append-only JSONL format.
"""

import os
import sys
import json
import time
import uuid
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


def get_current_git_commit() -> str:
    """Retrieves current Git commit hash or returns uncommitted/unknown indicator."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except Exception:
        return "untracked_or_no_git"


def get_process_memory_mb() -> float:
    """Returns current process Resident Set Size (RSS) in MB."""
    if not PSUTIL_AVAILABLE:
        return 0.0
    try:
        proc = psutil.Process(os.getpid())
        return round(proc.memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return 0.0


class ExperimentLogger:
    """
    Append-only experiment tracker saving detailed execution metadata to JSONL.
    """

    def __init__(self, log_dir: str = "experiments/runs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "experiments.jsonl"
        self.summary_md = self.log_dir / "experiment_summary.md"

    def log_run(self,
                experiment_name: str,
                retrieval_method: str,
                model_name: Optional[str],
                corpus_manifest: str,
                num_provisions: int,
                query_records: List[Dict[str, Any]],
                config_params: Dict[str, Any],
                overall_metrics: Optional[Dict[str, float]] = None,
                total_duration_sec: float = 0.0,
                warnings: Optional[List[str]] = None) -> str:
        """
        Logs a completed retrieval experiment run to experiments.jsonl and updates summary.
        """
        exp_id = f"EXP_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        git_hash = get_current_git_commit()
        rss_mb = get_process_memory_mb()

        entry = {
            "experiment_id": exp_id,
            "experiment_name": experiment_name,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "git_commit": git_hash,
            "retrieval_method": retrieval_method,
            "model_name": model_name or "none",
            "corpus_manifest": corpus_manifest,
            "num_provisions_indexed": num_provisions,
            "num_queries_evaluated": len(query_records),
            "config_parameters": config_params,
            "overall_metrics": overall_metrics or {},
            "execution_time_sec": round(total_duration_sec, 3),
            "process_rss_mb": rss_mb,
            "python_version": sys.version.split()[0],
            "warnings": warnings or [],
            "query_evaluations": query_records
        }

        # Append to JSONL log
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Update markdown summary table
        self._append_to_summary_markdown(entry)

        return exp_id

    def _append_to_summary_markdown(self, entry: Dict[str, Any]):
        """Maintains a human-readable Markdown summary of all executed runs."""
        headers = (
            "| Experiment ID | Timestamp (UTC) | Method | Model | Queries | Duration | Peak RSS | Reciprocal Rank | Status |\n"
            "|---|---|---|---|---|---|---|---|---|\n"
        )
        if not self.summary_md.exists():
            content = "# Legal Aid BD — Retrieval Experiment Tracking Summary\n\n" + headers
            self.summary_md.write_text(content, encoding="utf-8")

        mrr = entry.get("overall_metrics", {}).get("mean_reciprocal_rank", "N/A")
        if isinstance(mrr, float):
            mrr_str = f"{mrr:.4f}"
        else:
            mrr_str = str(mrr)

        row = (
            f"| `{entry['experiment_id']}` | {entry['timestamp_utc']} | "
            f"`{entry['retrieval_method']}` | `{entry['model_name']}` | "
            f"{entry['num_queries_evaluated']} | {entry['execution_time_sec']:.2f} s | "
            f"{entry['process_rss_mb']:.1f} MB | {mrr_str} | "
            f"{'Warning' if entry['warnings'] else 'Completed'} |\n"
        )

        with open(self.summary_md, "a", encoding="utf-8") as f:
            f.write(row)
