#!/usr/bin/env python3
"""
scripts/run_ingestion.py
------------------------
CLI runner for the section-aware document ingestion pipeline.
Parses raw legal files into structured provision records with stable identifiers.

Usage:
    python scripts/run_ingestion.py [--input-dir data/raw/sample_audit_files]
                                    [--output data/processed/provisions.jsonl]
                                    [--manifest data/manifests/processed_manifest.jsonl]
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import argparse
from pathlib import Path

# Add project root to sys.path so 'src' can be imported cleanly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.parser import LegalDocumentParser


def main():
    parser = argparse.ArgumentParser(description="Legal Aid BD: Document Ingestion Pipeline")
    parser.add_argument("--input-dir", default="data/raw/sample_audit_files", help="Input directory of raw legal files")
    parser.add_argument("--output", default="data/processed/provisions.jsonl", help="Output JSONL path for extracted provisions")
    parser.add_argument("--manifest", default="data/manifests/processed_manifest.jsonl", help="Output JSONL manifest path")

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_file = Path(args.output)
    manifest_file = Path(args.manifest)

    print("=" * 70)
    print("  Legal Aid BD — Section-Aware Legal Document Ingestion Pipeline")
    print("=" * 70)
    print(f"[*] Input Directory:   {input_dir.resolve()}")
    print(f"[*] Output Provisions: {output_file.resolve()}")
    print(f"[*] Output Manifest:   {manifest_file.resolve()}\n")

    if not input_dir.exists():
        print(f"[X] Error: Input directory '{input_dir}' does not exist.")
        sys.exit(1)

    doc_parser = LegalDocumentParser()
    stats = doc_parser.parse_directory(input_dir, output_file, manifest_file)

    print("[+] Ingestion Summary:")
    print(f"    - Total Source Files:        {stats['total_source_files']}")
    print(f"    - Valid Documents Ingested:  {stats['valid_files']}")
    print(f"    - Quarantined Documents:     {stats['quarantined_files']}")
    print(f"    - Total Provisions Extracted: {stats['total_extracted_provisions']}")
    print(f"    - Valid Evaluatable Provisions: {stats['valid_provisions_count']}")
    print(f"\n[+] Extracted provisions written to: {output_file}")
    print(f"[+] Provenance manifest written to:  {manifest_file}")


if __name__ == "__main__":
    main()
