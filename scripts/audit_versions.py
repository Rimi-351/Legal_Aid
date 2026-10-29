#!/usr/bin/env python3
"""
scripts/audit_versions.py
-------------------------
Audits statutory provisions against legislative metadata, effective dates,
and amendment relationships.

Generates eval/version_audit.csv with schema:
act_id, provision_id, enactment_date, amendment_instrument, effective_date,
relation(amend|repeal|replace|none), consolidated_text(Y/N), source_url,
evidence_type(official|inferred|unknown), review_status(pending|verified), conflict_note
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import os
import csv
import json
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.parser import derive_act_code


def audit_corpus_versions(
    provisions_path: Path = Path("data/processed/provisions.jsonl"),
    manifest_path: Path = Path("data/manifests/processed_manifest.jsonl"),
    output_path: Path = Path("eval/version_audit.csv"),
) -> Dict[str, Any]:
    """Audits corpus provisions and generates version_audit.csv."""
    manifest_info: Dict[str, Dict[str, Any]] = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    fname = item.get("filename") or Path(item.get("filepath", "")).name
                    manifest_info[fname] = item

    provisions: List[Dict[str, Any]] = []
    if provisions_path.exists():
        with open(provisions_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    provisions.append(json.loads(line))

    rows: List[Dict[str, Any]] = []
    evidence_counts = {"official": 0, "inferred": 0, "unknown": 0}
    relation_counts = {"amend": 0, "repeal": 0, "replace": 0, "none": 0}
    missing_enactment_count = 0
    missing_effective_count = 0
    conflicts_count = 0
    verified_count = 0

    for p in provisions:
        # Exclude unparsed or quarantined noise if requested, or keep with notes
        is_quar = p.get("is_quarantined", False)
        pid = p.get("provision_id", "")
        source_file = p.get("source_file", "")
        s_path = Path(source_file)
        act_title = p.get("act_title", "")

        act_id = derive_act_code(act_title, s_path) if act_title else (s_path.stem if source_file else "UNKNOWN")
        enactment_date = (p.get("publication_date") or "").strip()
        effective_date = (p.get("commencement_date") or "").strip()

        # Check relation based on text and title
        heading = (p.get("section_heading") or "").lower()
        text = (p.get("text") or "").lower()
        if "প্রতিস্থাপিত" in text or "replace" in heading or "প্রতিস্থাপন" in heading:
            relation = "replace"
        elif "সংশোধন" in heading or "amend" in heading or "amendment" in act_title.lower() or "সংশোধন" in act_title:
            relation = "amend"
        elif "repeal" in heading or "রহিত" in text or "বাতিল" in text:
            relation = "repeal"
        else:
            relation = "none"

        amendment_instrument = ""
        if relation in ("amend", "replace", "repeal"):
            amendment_instrument = act_id if "A" in act_id else (p.get("act_no") or act_title)

        consolidated_text = "Y" if p.get("is_consolidated") else "N"
        source_url = p.get("source_url") or source_file

        # Evidence type & Review status
        # Per specification: "Fill only from fields present in the corpus/source metadata. Missing = empty, evidence_type=unknown."
        prov_provenance = p.get("provenance")
        m_item = manifest_info.get(s_path.name, {})
        m_provenance = m_item.get("provenance")

        conflict_note = ""
        if is_quar:
            conflict_note = f"Quarantined: {p.get('quarantine_reason', 'Unverified')}"
            conflicts_count += 1

        # Determine evidence_type
        if p.get("evidence_type") in ("official", "inferred", "unknown"):
            evidence_type = p["evidence_type"]
        elif prov_provenance == "official" or m_provenance == "official":
            evidence_type = "official"
        elif prov_provenance == "inferred" or m_provenance == "inferred":
            evidence_type = "inferred"
        else:
            evidence_type = "unknown"

        # Review status: verified requires explicit review_status
        if p.get("review_status") == "verified":
            review_status = "verified"
            verified_count += 1
        else:
            review_status = "pending"

        if not enactment_date:
            missing_enactment_count += 1
        if not effective_date:
            missing_effective_count += 1

        evidence_counts[evidence_type] = evidence_counts.get(evidence_type, 0) + 1
        relation_counts[relation] = relation_counts.get(relation, 0) + 1

        rows.append({
            "act_id": act_id,
            "provision_id": pid,
            "enactment_date": enactment_date,
            "amendment_instrument": amendment_instrument,
            "effective_date": effective_date,
            "relation": relation,
            "consolidated_text": consolidated_text,
            "source_url": source_url,
            "evidence_type": evidence_type,
            "review_status": review_status,
            "conflict_note": conflict_note,
        })

    # Write CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "act_id",
        "provision_id",
        "enactment_date",
        "amendment_instrument",
        "effective_date",
        "relation",
        "consolidated_text",
        "source_url",
        "evidence_type",
        "review_status",
        "conflict_note",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    total_provisions = len(rows)
    verified_coverage_pct = (verified_count / total_provisions * 100.0) if total_provisions > 0 else 0.0

    summary = {
        "total_provisions": total_provisions,
        "evidence_type_counts": evidence_counts,
        "relation_counts": relation_counts,
        "missing_enactment_date": missing_enactment_count,
        "missing_effective_date": missing_effective_count,
        "conflicts": conflicts_count,
        "verified_count": verified_count,
        "verified_coverage_pct": round(verified_coverage_pct, 2),
        "output_path": str(output_path),
    }

    # Print summary
    print("=" * 70)
    print("  Version Audit Summary (eval/version_audit.csv)")
    print("=" * 70)
    print(f"Total provisions audited : {total_provisions}")
    print("Counts per evidence_type :")
    for k, v in evidence_counts.items():
        print(f"  - {k:10s}: {v}")
    print("Counts per relation      :")
    for k, v in relation_counts.items():
        print(f"  - {k:10s}: {v}")
    print(f"Missing enactment date   : {missing_enactment_count}")
    print(f"Missing effective date   : {missing_effective_count}")
    print(f"Conflicts identified     : {conflicts_count}")
    print(f"Verified provisions      : {verified_count}")
    print(f"Verified coverage        : {verified_coverage_pct:.2f}%")
    print("-" * 70)
    print("Verified Subset Analysis:")
    print(f"  - Verified reference set size : {verified_count}")
    if verified_count == 0:
        print("  - Historical-law accuracy     : not computable (no verified reference set exists)")
    else:
        print(f"  - Historical-law accuracy     : {verified_coverage_pct:.2f}%")
    print("=" * 70)

    return summary


if __name__ == "__main__":
    audit_corpus_versions()
