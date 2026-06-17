from __future__ import annotations

import argparse
from pprint import pprint
from typing import Any

from src.agent import graph
from src.database import BigQueryExecutor
from src.tools import list_dataset_tables


SESSION_CONFIG = {"configurable": {"thread_id": "ecommerce_analysis_session_1"}}


def _divider(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def _prompt_runtime_value(label: str) -> str:
    value = input(f"{label}: ").strip()
    while not value:
        print(f"{label} is required.")
        value = input(f"{label}: ").strip()
    return value


def _print_previous_state() -> None:
    _divider("PREVIOUS SESSION STATE")
    previous_state = graph.get_state(SESSION_CONFIG)
    if previous_state is None:
        print("No previous state found for this thread.")
        return

    pprint(previous_state.values)


def _print_update(node_name: str, state_update: dict[str, Any]) -> None:
    node_name = str(node_name)

    if node_name == "planner":
        print("[PLANNER NODE COMPLETED] Generated Schema Context:")
        print(state_update.get("schema_context", ""))
        selected_tables = state_update.get("selected_tables", [])
        if selected_tables:
            print(f"Selected Tables: {', '.join(selected_tables)}")
        return

    if node_name == "engineer":
        print("[ENGINEER NODE COMPLETED] Generated SQL Code:")
        print(state_update.get("generated_sql", ""))
        if state_update.get("execution_error"):
            print(f"Current iteration_count: {state_update.get('iteration_count', 0)}")
        return

    if node_name == "validator":
        print("[VALIDATOR NODE COMPLETED] Running dry-run validation...")
        print(f"Current iteration_count: {state_update.get('iteration_count', 0)}")
        execution_error = state_update.get("execution_error")
        if execution_error:
            print(
                "⚠️ CRITICAL: Database Engine Error Detected! Streaming traceback back to the Engineer node for self-healing..."
            )
            print(execution_error)
        else:
            print("Validation passed. Query results captured.")
            pprint(state_update.get("query_results", []))
        return

    print(f"[{node_name.upper()} NODE COMPLETED]")
    pprint(state_update)


def _stream_workflow(initial_state: dict[str, Any]) -> dict[str, Any]:
    latest_result: dict[str, Any] = {}

    _divider("LIVE EXECUTION STREAM")
    print(f"User question: {initial_state.get('user_query', '')}")
    print(f"Project ID: {initial_state.get('project_id', '')}")
    print(f"Dataset ID: {initial_state.get('dataset_id', '')}")

    for chunk in graph.stream(initial_state, config=SESSION_CONFIG, stream_mode="updates"):
        if not isinstance(chunk, dict):
            continue

        for node_name, state_update in chunk.items():
            if isinstance(state_update, dict):
                latest_result.update(state_update)
                _print_update(str(node_name), state_update)

    final_state = graph.get_state(SESSION_CONFIG)
    if final_state is not None:
        latest_result.update(final_state.values)

    return latest_result


def _print_final_summary(result: dict[str, Any]) -> None:
    _divider("FINAL EXECUTION SUMMARY")
    print(f"Current iteration_count: {result.get('iteration_count', 0)}")
    print(f"Bytes scanned: {result.get('bytes_scanned')}")
    print(f"Execution error: {result.get('execution_error')}")
    print("Query results:")
    pprint(result.get("query_results"))


def _snapshot_node_name(snapshot: Any) -> str:
    metadata = snapshot.metadata if hasattr(snapshot, "metadata") else {}
    writes = metadata.get("writes") if isinstance(metadata, dict) else {}
    if not isinstance(writes, dict) or not writes:
        return "Unknown"

    node_name = next(iter(writes.keys()))
    return str(node_name).replace("_", " ").title()


def _snapshot_status(snapshot: Any, previous_failed: bool) -> str:
    values = snapshot.values if hasattr(snapshot, "values") else {}
    if not isinstance(values, dict):
        return ""

    execution_error = values.get("execution_error")
    query_results = values.get("query_results")

    if execution_error:
        return "(Failed)"
    if query_results is not None:
        if previous_failed and _snapshot_node_name(snapshot) == "Engineer":
            return "(Self-Healed)"
        return "(Passed)"
    return ""


def _collect_latest_run_chain(history: list[Any], stop_checkpoint_id: str | None = None) -> list[Any]:
    if not history:
        return []

    by_checkpoint_id: dict[str, Any] = {}
    for snapshot in history:
        config = snapshot.config if hasattr(snapshot, "config") else {}
        if not isinstance(config, dict):
            continue

        configurable = config.get("configurable") if isinstance(config.get("configurable"), dict) else {}
        checkpoint_id = configurable.get("checkpoint_id")
        if isinstance(checkpoint_id, str):
            by_checkpoint_id[checkpoint_id] = snapshot

    latest_snapshot = history[0]
    chain: list[Any] = [latest_snapshot]
    current_snapshot = latest_snapshot

    while True:
        parent_config = current_snapshot.parent_config if hasattr(current_snapshot, "parent_config") else None
        if not isinstance(parent_config, dict):
            break

        configurable = parent_config.get("configurable") if isinstance(parent_config.get("configurable"), dict) else {}
        parent_checkpoint_id = configurable.get("checkpoint_id")
        if not isinstance(parent_checkpoint_id, str):
            break

        if stop_checkpoint_id is not None and parent_checkpoint_id == stop_checkpoint_id:
            break

        parent_snapshot = by_checkpoint_id.get(parent_checkpoint_id)
        if parent_snapshot is None:
            break

        chain.append(parent_snapshot)
        current_snapshot = parent_snapshot

    return list(reversed(chain))


def _print_audit_trail(stop_checkpoint_id: str | None = None) -> None:
    _divider("SESSION AUDIT TRAIL")
    history = list(graph.get_state_history(SESSION_CONFIG))

    if not history:
        print("No checkpoint history available yet.")
        return

    latest_run = _collect_latest_run_chain(history, stop_checkpoint_id=stop_checkpoint_id)
    if not latest_run:
        print("No historical steps found.")
        return

    had_failure = any(
        isinstance(snapshot.values, dict) and snapshot.values.get("execution_error")
        for snapshot in latest_run
    )

    timeline: list[str] = []
    for index, snapshot in enumerate(latest_run, start=1):
        node_name = _snapshot_node_name(snapshot)
        status = _snapshot_status(snapshot, had_failure)
        timeline.append(f"Step {index}: {node_name} {status}".rstrip())

    final_values = latest_run[-1].values if hasattr(latest_run[-1], "values") else {}
    final_error = final_values.get("execution_error") if isinstance(final_values, dict) else None
    timeline.append("Failure" if final_error else "Success")

    print(" -> ".join(timeline))


def run_dashboard(project_id: str, dataset_id: str, user_query: str) -> int:
    previous_state = graph.get_state(SESSION_CONFIG)
    previous_checkpoint_id = None
    if previous_state is not None and hasattr(previous_state, "config"):
        configurable = previous_state.config.get("configurable") if isinstance(previous_state.config, dict) else {}
        if isinstance(configurable, dict):
            checkpoint_id = configurable.get("checkpoint_id")
            if isinstance(checkpoint_id, str):
                previous_checkpoint_id = checkpoint_id

    _print_previous_state()

    initial_state = {
        "user_query": user_query,
        "project_id": project_id,
        "dataset_id": dataset_id,
        "iteration_count": 0,
        "selected_tables": [],
    }
    result = _stream_workflow(initial_state)
    _print_final_summary(result)
    _print_audit_trail(stop_checkpoint_id=previous_checkpoint_id)
    return 0 if result.get("execution_error") is None else 1


def run_verification(project_id: str, dataset_id: str) -> int:
    executor = BigQueryExecutor()
    tables = list_dataset_tables(project_id, dataset_id)
    sample_table = tables[0] if tables else None

    broken_sql = "SELECT FROM"
    dry_run_sql = f"SELECT * FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.TABLES` LIMIT 5"
    valid_sql = (
        f"SELECT COUNT(*) AS row_count FROM `{project_id}.{dataset_id}.{sample_table}`"
        if sample_table
        else f"SELECT table_name FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.TABLES` LIMIT 1"
    )

    _divider("SMOKE VERIFICATION")
    print("=== Dry-run syntax validation ===")
    pprint(executor.validate_and_analyze_query(broken_sql))

    print("\n=== Dry-run bytes estimate ===")
    pprint(executor.validate_and_analyze_query(dry_run_sql))

    print("\n=== Query execution ===")
    pprint(executor.execute_query(valid_sql))

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BigQuery LangGraph agent CLI")
    parser.add_argument("--verify", action="store_true", help="Run BigQuery smoke verification")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.verify:
        project_id = _prompt_runtime_value("Target GCP Project ID")
        dataset_id = _prompt_runtime_value("Target Dataset ID")
        return run_verification(project_id, dataset_id)

    project_id = _prompt_runtime_value("Target GCP Project ID")
    dataset_id = _prompt_runtime_value("Target Dataset ID")
    user_query = _prompt_runtime_value("Natural Language Query")

    return run_dashboard(project_id, dataset_id, user_query)


if __name__ == "__main__":
    raise SystemExit(main())
