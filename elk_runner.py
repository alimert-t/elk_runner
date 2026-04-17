import os
import sys
import argparse
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from .user_config import elk_path

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
        default=elk_path,
        help="Absolute path to the ELK executable or shell script",
    )

    parser.add_argument(
        "--save-state",
        action="store_true",
        help="Keep the STATE.OUT in the input dir to use task 1 instead of 0",
    )

    parser.add_argument(
        "--mpi",
        action="store_true"
        help="Run elk with MPI Hydra. Requires elk binary built for MPI.",
    )

    parser.add_argument(
        "--launcher",
        default="mpiexec.hydra",
        help="MPI launcher command",
    )

    parser.add_argument(
        "--hosts",
        required=True,
        help="Comma-separated host list for MPI, e.g. elk330 or elk330,elk331",
    )

    parser.add_argument(
        "--np",
        type=int,
        required=True,
        help="Total number of MPI ranks",
    )

    parser.add_argument(
        "--ppn",
        type=int,
        default=None,
        help="MPI ranks per node",
    )

    parser.add_argument(
        "--iface",
        default="ib0",
        help="Network interface for MPI (default: ib0)",
    )

    parser.add_argument(
        "--rr",
        action="store_true",
        help="Enable round-robin rank placement",
    )

    parser.add_argument(
        "--omp-threads",
        type=int,
        default=1,
        help="OMP_NUM_THREADS value for each MPI rank",
    )

    parser.add_argument(
        "--omp-stacksize",
        default="512M",
        help="OMP_STACKSIZE value",
    )

    args = parser.parse_args()

    base_dir = Path.cwd()
    input_root = base_dir / "inputs"
    logs_dir = base_dir / "logs"
    output_root = base_dir / "outputs"

    run_name = args.input_name
    run_dir = input_root / run_name
    input_file = run_dir / "elk.in"
    elk_exec = Path(args.elk_exec).resolve()

    host_list = [h.strip() for h in args.hosts.split(",") if h.strip()]
    num_hosts = len(host_list)

    if not run_dir.exists():
        print(f"Error: input directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    if not input_file.exists():
        print(f"Error: elk.in not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    if not elk_exec.exists():
        print(f"Error: ELK executable/script not found: {elk_exec}", file=sys.stderr)
        sys.exit(1)

    if args.ppn is not None and args.np > args.ppn * num_hosts:
        print(
            f"Error: np={args.np} exceeds ppn * host_count = {args.ppn * num_hosts}",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.ppn is not None and args.np % args.ppn != 0:
        print(
            f"Warning: np={args.np} is not divisible by ppn={args.ppn}; "
            "ranks may not be distributed evenly."
        )

    start_time = datetime.now()
    timestamp = start_time.strftime("%Y%m%d_%H-%M-%S")

    logs_dir.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    if args.mpi:
        log_file_path = logs_dir / f"{run_name}_{timestamp}_mpi.log"
        run_output_dir = output_root / run_name / f"{timestamp}_mpi"
    else:
        log_file_path = logs_dir / f"{run_name}_{timestamp}.log"
        run_output_dir = output_root / run_name / f"{timestamp}"


    for host in host_list:
        check = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", host, "hostname"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if check.returncode != 0:
            print(f"Error: passwordless SSH failed for host {host}",
                    file=sys.stderr)
            print(check.stderr, file=sys.stderr)
            sys.exit(1)

    # Remove old result files from the run directory before starting
    # but keep STATE.OUT! 
    for pattern in ["*.OUT", "*.INFO"]:
        for old_file in run_dir.glob(pattern):
            if args.save_state and old_file.name == "STATE.OUT":
                continue
            old_file.unlink()

    if args.mpi:
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = str(args.omp_threads)
        env["OMP_STACKSIZE"] = args.omp_stacksize

        cmd = [
            args.launcher,
            "-bootstrap", "ssh",
            "-hosts", args.hosts,
            "-iface", args.iface,
            "-np", str(args.np),
        ]

        if args.ppn is not None:
            cmd.extend(["-ppn", str(args.ppn)])

        if args.rr:
            cmd.append("-rr")

        cmd.append(str(elk_exec))

        with open(log_file_path, "w", encoding="utf-8") as log_file:
            header = (
                f"Run name     : {run_name}\n"
                f"Input file   : {input_file}\n"
                f"ELK exec     : {elk_exec}\n"
                f"Working dir  : {run_dir}\n"
                f"MPI command  : {' '.join(cmd)}\n"
                f"OMP threads  : {args.omp_threads}\n"
                f"OMP stack    : {args.omp_stacksize}\n"
                f"Hosts        : {', '.join(host_list)}\n"
                f"Host count   : {num_hosts}\n"
                f"Started at   : {start_time.isoformat()}\n"
                f"{'-'*60}\n"
            )
            print(header, end="")
            log_file.write(header)
            log_file.flush()

            try:
                process = subprocess.Popen(
                    cmd,
                    cwd=run_dir,
                    env=env,
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
    else:
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            header = ( f"Run name     : {run_name}\n"
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
