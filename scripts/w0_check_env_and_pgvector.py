#!/usr/bin/env python3
"""
scripts/w0_check_env_and_pgvector.py
------------------------------------
Task 0.3a: Diagnostic script to verify the local Windows environment, Python
toolchain, hardware constraints (16 GB RAM budget), PostgreSQL connection, and
pgvector extension functionality.

Usage:
    python scripts/w0_check_env_and_pgvector.py [--host HOST] [--port PORT]
                                                [--dbname DBNAME] [--user USER]
                                                [--password PASSWORD]
                                                [--skip-db]

Exit codes:
    0: All checks passed (or DB skipped cleanly)
    1: Hardware/OS/Dependency check failed
    2: Database/pgvector check failed
"""

import sys
import os
import platform
import argparse
import random
import time
from typing import Dict, Any, Tuple

# Graceful dependency imports
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Try psycopg3 (psycopg) or psycopg2
PSYCOPG_AVAILABLE = False
PSYCOPG_VERSION = None
try:
    import psycopg
    PSYCOPG_AVAILABLE = True
    PSYCOPG_VERSION = 3
except ImportError:
    try:
        import psycopg2
        PSYCOPG_AVAILABLE = True
        PSYCOPG_VERSION = 2
    except ImportError:
        pass


def check_system_environment() -> Dict[str, Any]:
    """Inspects OS, Python version, CPU cores, system RAM, and disk space."""
    print("=" * 70)
    print("  Legal Aid BD — Week 0: System Environment & Hardware Diagnostic")
    print("=" * 70)

    report = {
        "os_system": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "is_64bit": sys.maxsize > 2**32,
    }

    print(f"[*] Operating System: {report['os_system']} {report['os_release']} ({report['architecture']})")
    print(f"[*] OS Version Build: {report['os_version']}")
    print(f"[*] Python Version:   {report['python_version']} ({'64-bit' if report['is_64bit'] else '32-bit'})")
    print(f"[*] Python Path:      {report['python_executable']}")

    if not PSUTIL_AVAILABLE:
        print("[!] Warning: 'psutil' is not installed. Install via: pip install psutil")
        report["ram_total_gb"] = None
        report["ram_available_gb"] = None
        report["cpu_logical"] = os.cpu_count() or 1
        report["cpu_physical"] = None
        report["disk_free_gb"] = None
        return report

    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(os.getcwd())

    report["ram_total_gb"] = round(vm.total / (1024 ** 3), 2)
    report["ram_available_gb"] = round(vm.available / (1024 ** 3), 2)
    report["ram_percent_used"] = vm.percent
    report["cpu_logical"] = psutil.cpu_count(logical=True)
    report["cpu_physical"] = psutil.cpu_count(logical=False)
    report["disk_free_gb"] = round(disk.free / (1024 ** 3), 2)

    print(f"[*] CPU Cores:        {report['cpu_physical']} physical, {report['cpu_logical']} logical")
    print(f"[*] System RAM:       {report['ram_total_gb']} GB total ({report['ram_available_gb']} GB available, {report['ram_percent_used']}% used)")
    print(f"[*] Workspace Drive:  {report['disk_free_gb']} GB free")

    # Hardware Budget Evaluation
    print("-" * 70)
    if report["ram_total_gb"] >= 15.0:
        print(f"[+] RAM Budget Check: PASSED ({report['ram_total_gb']} GB satisfies ~16 GB research target)")
    else:
        print(f"[!] RAM Budget Warning: Detected {report['ram_total_gb']} GB total RAM (< 15.0 GB).")
        print("    You must strictly enforce single-model sequential execution to avoid Windows page thrashing.")

    if report["ram_available_gb"] < 4.0:
        print(f"[!] Available RAM Alert: Only {report['ram_available_gb']} GB free.")
        print("    Close memory-intensive background applications (browser tabs, Docker, etc.) before running model benchmarks.")
    else:
        print(f"[+] Available Memory Check: PASSED ({report['ram_available_gb']} GB immediately available)")

    return report


def connect_postgres(host: str, port: int, dbname: str, user: str, password: str):
    """Establishes database connection using psycopg3 or psycopg2."""
    if not PSYCOPG_AVAILABLE:
        raise ImportError(
            "Neither 'psycopg' (v3) nor 'psycopg2' is installed.\n"
            "Install psycopg via: pip install \"psycopg[binary]\" or pip install psycopg2-binary"
        )

    conn_params = {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
    }
    if password:
        conn_params["password"] = password

    if PSYCOPG_VERSION == 3:
        return psycopg.connect(**conn_params, autocommit=True)
    else:
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True
        return conn


def test_pgvector_suite(conn, dimensions=(768, 1024)) -> bool:
    """Tests pgvector extension creation, table creation, insertion, and HNSW cosine search."""
    table_name = "w0_pgvector_diagnostic_temp"
    cursor = conn.cursor()

    try:
        print("\n" + "=" * 70)
        print("  PostgreSQL & pgvector Extension Verification")
        print("=" * 70)

        # 1. Verify Extension
        print("[*] Testing pgvector extension installation (`CREATE EXTENSION IF NOT EXISTS vector;`)...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
        ext_row = cursor.fetchone()
        if not ext_row:
            print("[X] Error: pgvector extension is not registered in PostgreSQL.")
            return False
        print(f"[+] pgvector extension is ACTIVE (Version: {ext_row[0]})")

        # 2. Test Multiple Dimensions (768 for E5-base, 1024 for BGE-M3)
        for dim in dimensions:
            print(f"\n[*] Testing vector dimension: {dim}d ...")
            test_tbl = f"{table_name}_{dim}"
            cursor.execute(f"DROP TABLE IF EXISTS {test_tbl};")
            cursor.execute(f"""
                CREATE TABLE {test_tbl} (
                    id SERIAL PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    embedding vector({dim})
                );
            """)
            print(f"    [+] Created temporary table `{test_tbl}` with vector({dim})")

            # Generate and insert 10 synthetic vectors
            records = []
            for i in range(10):
                vec = [round(random.uniform(-1.0, 1.0), 6) for _ in range(dim)]
                vec_str = "[" + ",".join(map(str, vec)) + "]"
                records.append((f"doc_{i}", vec_str))

            for doc_id, vec_str in records:
                cursor.execute(f"INSERT INTO {test_tbl} (doc_id, embedding) VALUES (%s, %s);", (doc_id, vec_str))
            print(f"    [+] Inserted 10 synthetic {dim}d vectors")

            # Build HNSW index with cosine distance
            print(f"    [*] Creating HNSW index (m=16, ef_construction=64, vector_cosine_ops)...")
            start_idx = time.perf_counter()
            cursor.execute(f"""
                CREATE INDEX ON {test_tbl} 
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """)
            idx_dur_ms = (time.perf_counter() - start_idx) * 1000
            print(f"    [+] HNSW index created successfully in {idx_dur_ms:.2f} ms")

            # Run Cosine Distance Query
            query_vec = "[" + ",".join(str(round(random.uniform(-1.0, 1.0), 6)) for _ in range(dim)) + "]"
            start_query = time.perf_counter()
            cursor.execute(f"""
                SELECT doc_id, embedding <=> %s AS cosine_distance
                FROM {test_tbl}
                ORDER BY embedding <=> %s
                LIMIT 3;
            """, (query_vec, query_vec))
            results = cursor.fetchall()
            query_dur_ms = (time.perf_counter() - start_query) * 1000

            print(f"    [+] Top-3 Cosine Similarity query returned in {query_dur_ms:.2f} ms:")
            for rank, (doc_id, dist) in enumerate(results, 1):
                print(f"        Rank {rank}: {doc_id} -> Cosine Distance: {float(dist):.4f}")

            # Cleanup dimension table
            cursor.execute(f"DROP TABLE IF EXISTS {test_tbl};")
            print(f"    [+] Cleaned up temporary table `{test_tbl}`")

        print("\n[+] All pgvector dimensional and indexing checks PASSED.")
        return True

    except Exception as e:
        print(f"\n[X] pgvector test encountered an error:\n    {type(e).__name__}: {e}")
        return False
    finally:
        cursor.close()


def main():
    parser = argparse.ArgumentParser(description="Week 0: Environment & pgvector Diagnostic Script for Legal Aid BD")
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"), help="PostgreSQL host (default: localhost)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5432")), help="PostgreSQL port (default: 5432)")
    parser.add_argument("--dbname", default=os.getenv("PGDATABASE", "postgres"), help="PostgreSQL DB name (default: postgres)")
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"), help="PostgreSQL user (default: postgres)")
    parser.add_argument("--password", default=os.getenv("PGPASSWORD", ""), help="PostgreSQL password")
    parser.add_argument("--skip-db", action="store_true", help="Skip PostgreSQL & pgvector test (check system hardware only)")

    args = parser.parse_args()

    # Step 1: System Environment Check
    env_report = check_system_environment()

    if args.skip_db:
        print("\n[*] PostgreSQL & pgvector test was skipped (--skip-db specified).")
        sys.exit(0)

    # Step 2: Database Check
    print("\n[*] Attempting connection to PostgreSQL...")
    print(f"    Target: {args.user}@{args.host}:{args.port}/{args.dbname}")

    try:
        conn = connect_postgres(args.host, args.port, args.dbname, args.user, args.password)
        print("[+] Successfully connected to PostgreSQL server.")
    except Exception as e:
        print(f"[X] Database Connection Failed: {e}")
        print("\n--- Troubleshooting Guidance ---")
        print("1. Ensure PostgreSQL service is running on Windows (Services -> postgresql-x64-XX).")
        print("2. Ensure pgvector extension binaries are copied into the PostgreSQL `lib/` and `share/extension/` folders.")
        print("   Download pre-compiled Windows pgvector from: https://github.com/pgvector/pgvector/releases")
        print("3. Check credentials or set PGUSER, PGPASSWORD, PGHOST, PGPORT, PGDATABASE.")
        print("4. To verify hardware environment without connecting to DB right now, run:")
        print("   python scripts/w0_check_env_and_pgvector.py --skip-db")
        sys.exit(2)

    try:
        success = test_pgvector_suite(conn, dimensions=(768, 1024))
        if success:
            print("\n" + "=" * 70)
            print("  WEEK 0 TASK 0.3a: ENVIRONMENT & PGVECTOR STATUS: READY [GO]")
            print("=" * 70)
            sys.exit(0)
        else:
            print("\n" + "=" * 70)
            print("  WEEK 0 TASK 0.3a: PGVECTOR TEST FAILED [NO-GO]")
            print("=" * 70)
            sys.exit(2)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
