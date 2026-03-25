# ELK_RUNNER

`elk_runner` is a small companion script for the all-electron full-potential
augmented-plane-wave code ELK.

The purpose of this runner is to organize ELK inputs, outputs, and logs in a
more structured way, making calculations easier to run, analyse, and reuse.

## Directory structure

The expected directory structure is:

```text
parent_folder/
├── inputs/
│   ├── example_one/
│   │   └── elk.in
│   └── example_two/
│       ├── elk.in
│       └── STATE.OUT
├── outputs/
│   ├── example_one/
│   │   └── *.OUT
│   └── example_two/
│       └── *.OUT
└── logs/
    ├── example_one.log
    └── example_two.log
````

Each calculation lives in its own directory under `inputs/`, and the input file
is always named `elk.in`, as per the Elk design.

Normally, the ELK binary is run directly inside the directory where `elk.in`
lives, and all output files are generated there as well. `elk_runner` keeps
this execution model, but then arranges the generated output files into a
separate `outputs/<input_name>/` directory and writes the terminal output to
`logs/<input_name>.log`.

If `--save-state` is used, `STATE.OUT` is kept in the input directory for reuse
in subsequent runs and is also copied to the corresponding output directory.

## Usage

```bash
python elk_runner.py <input_name>
```

Here, the `<input_name>` is the name of the folder which the respective `elk.in` lives. 

Example:

```bash
python elk_runner.py example_two --save-state
```

By default, the script uses the configured `elk.sh` path, but this can be
overridden:

```bash
python elk_runner.py example_two --elk-exec /path/to/elk.sh
```

or with the Elk binary

```bash
python elk_runner.py example_two --elk-exec /path/to/elk
```

## Notes

* The script assumes that each input directory contains exactly one `elk.in`. Elk will NOT run properly if there exists more than one `elk.in` in a directory.
* ELK is executed in the corresponding input directory.
* Output files such as `*.OUT` and `*.INFO` are collected into the matching
  directory under `outputs/`.
* The full terminal output is both printed live and written to a log file.
