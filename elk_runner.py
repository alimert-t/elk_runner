import sys
import argparse
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

def stream_process_output(process, log_file):
    """Print Elk output live and write it to the log file."""
    assert process.stdout is not None

    for line in process.stdout:
        print(line, end="")
        log_file.write(line)
        log_file.flush()

    return process.wait()

def collect_results(
        work_dir: Path, output_dir: Path, save_state: bool = False):
    """Move Elk output files from the run directory into the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    moved_files = []
    copied_files = []

    for pattern in ["*.OUT", "*.INFO"]:
        for f_path in work_dir.glob(pattern):
            dest = output_dir / f_path.name

            if f_path.name == "STATE.OUT" and save_state:
                shutil.copy2(str(f_path), str(dest))
                copied_files.append(f_path.name)
            else:
                shutil.move(str(f_path), str(dest))
                moved_files.append(f_path.name)

    return moved_files, copied_files

def main():
    parser = argparse.ArgumentParser(
        description="Run Elk for input/<input_name>/elk.in, log output, and collect results."
    )

    parser.add_argument(
        "input_name",
        help="Name of the input directory under input/ (example: example_input)",
    )

    parser.add_argument(
        "--elk-exec",
        default="/absolute/path/to/elk.sh",
        help="Absolute path to the ELK executable or shell script",
    )

    parser.add_argument(
        "--save-state",
        action="store_true",
        help="Keep the STATE.OUT in the input dir to use task 1 instead of 0",
    )

    args = parser.parse_args()

    base_dir = Path.cwd()
    input_root = base_dir / "input"
    logs_dir = base_dir / "logs"
    output_root = base_dir / "output"

    run_name = args.input_name
    run_dir = input_root / run_name
    input_file = run_dir / "elk.in"
    elk_exec = Path(args.elk_exec).resolve()

    if not run_dir.exists():
        print(f"Error: input directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    if not input_file.exists():
        print(f"Error: elk.in not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    if not elk_exec.exists():
        print(f"Error: ELK executable/script not found: {elk_exec}", file=sys.stderr)
        sys.exit(1)

    logs_dir.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    run_output_dir = output_root / run_name
    log_file_path = logs_dir / f"{run_name}.log"

    # Remove old result files from the run directory before starting
    # but keep STATE.OUT! 
    for pattern in ["*.OUT", "*.INFO"]:
        for old_file in run_dir.glob(pattern):
            if args.save_state and old_file.name == "STATE.OUT":
                continue
            old_file.unlink()

    start_time = datetime.now()

    with open(log_file_path, "w", encoding="utf-8") as log_file:
        header = (
            f"Run name     : {run_name}\n"
            f"Input file   : {input_file}\n"
            f"ELK exec     : {elk_exec}\n"
            f"Working dir  : {run_dir}\n"
            f"Started at   : {start_time.isoformat()}\n"
            f"{'-'*60}\n"
        )
        print(header, end="")
        log_file.write(header)
        log_file.flush()

        try:
            process = subprocess.Popen(
                [str(elk_exec)],
                cwd=run_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            return_code = stream_process_output(process, log_file)

        except Exception as exc:
            error_msg = f"\nError while running ELK: {exc}\n"
            print(error_msg, file=sys.stderr, end="")
            log_file.write(error_msg)
            log_file.flush()
            sys.exit(1)

        end_time = datetime.now()
        footer = (
            f"\n{'-'*60}\n"
            f"Finished at  : {end_time.isoformat()}\n"
            f"Return code  : {return_code}\n"
        )
        print(footer, end="")
        log_file.write(footer)
        log_file.flush()

    moved_files, copied_files = collect_results(
        run_dir, run_output_dir, save_state=args.save_state
    )

    summary = [
        f"Results directory: {run_output_dir}",
        f"Log file         : {log_file_path}",
    ]

    if moved_files:
        summary.append("Moved files      :")
        summary.extend(f"  - {name}" for name in moved_files)

    if copied_files:
        summary.append("Copied files     :")
        summary.extend(f"  - {name}" for name in copied_files)

    if not moved_files and not copied_files:
        summary.append("Collected files  : none found matching *.OUT or *.INFO")

    print("\n" + "\n".join(summary))
    sys.exit(return_code)


if __name__ == "__main__":
    main()
