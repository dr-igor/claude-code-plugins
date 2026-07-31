# planning

Turns plan mode into something a human can review. Two hooks and a skill:

- A `UserPromptSubmit` hook that, while you're in plan mode, injects a set of conventions telling Claude to write the plan as a design document — target state first, then current state and the delta, then intermediate stages only where they're justified — with every one of those sections anchored by an embedded PlantUML diagram that the prose then walks through.
- A `PreToolUse` hook on `ExitPlanMode` that renders the finished plan Markdown to PDF, diagrams and all, before the plan is presented for approval. If the render fails, the exit is blocked and the errors go back to Claude to fix.
- The `grill-me` skill, which interviews you about a plan until every branch of the design tree is resolved.

## Plan document structure

The conventions live in `contexts/plan-document-conventions.md`, and `plugins/planning/examples/example-plan.md` is a worked example that follows them. In short: fixed section order (`Context`, `Target state`, `Current state`, `Stages`), at least one diagram per structural section, prose discussion after every diagram, and stages presented as end-of-stage snapshots rather than as work items.

Diagrams must be fenced as ` ```plantuml ` — not `puml`, not `uml` — and each block must be a complete `@startuml … @enduml` document. That tag is what the PDF filter matches on; a block tagged anything else renders as a verbatim code listing.

The conventions are injected **once per compaction window**, not on every prompt and not permanently. The hook scans the conversation transcript for the `Contents of <path>:` sentinel and stays quiet if the file is already in context — the same deduplication the language-context plugins in this marketplace use. After a compaction the file is no longer in context, so it is injected again, which is the point.

Nothing happens outside plan mode: the hook reads `permission_mode` from its stdin and exits immediately unless it is `"plan"`.

## Setup

Four pieces have to be present. None of them is bundled with the plugin, and if any is missing the hook exits cleanly and names it rather than blocking — see [Failure behavior](#failure-behavior).

| Piece | What it does | How the hook finds it |
| --- | --- | --- |
| `pandoc` | Markdown to PDF | `PATH`, or `PLANNING_PANDOC_BIN` |
| `pandoc-plantuml` | Turns each ` ```plantuml ` block into an image mid-conversion | `PATH`, or `PLANNING_PLANTUML_FILTER` |
| PlantUML + a JRE | Renders the diagrams | `PLANTUML_BIN`, else `plantuml` on `PATH` |
| A PDF engine | Typesets the result | first of `typst`, `xelatex`, `lualatex`, `pdflatex`, `weasyprint`, `wkhtmltopdf` on `PATH`, or `PLANNING_PDF_ENGINE` |

`graphviz` is a fifth, softer requirement: PlantUML shells out to its `dot` binary for class, component, state and deployment diagrams. Sequence and activity diagrams render without it.

Work through the steps below in order; each ends with a command that confirms it.

### 1. pandoc and graphviz

```bash
brew install pandoc graphviz
pandoc --version        # expect 3.x
dot -V                  # expect "dot - graphviz version ..."
```

### 2. The pandoc filter

[`pandoc-plantuml-filter`](https://github.com/timofurrer/pandoc-plantuml-filter) is a Python package whose only dependency is `pandocfilters`. `uv tool install` is the tidiest route — it puts the executable on your `PATH` without adding anything to a project environment.

```bash
uv tool install pandoc-plantuml-filter    # or: pipx install / pip install --user
which pandoc-plantuml                     # expect ~/.local/bin/pandoc-plantuml
```

### 3. PlantUML

Two routes. **Prefer the jar** if you already have a JDK installed — `brew install plantuml` pulls in its own `openjdk` formula, so you end up maintaining a second JVM purely for diagram rendering.

**Route A — standalone jar against a JDK you already have.** Note that `/usr/bin/java` on macOS is a stub that reports "Unable to locate a Java Runtime" unless a JDK is on the system path; point at the JDK's own `java` binary explicitly rather than relying on it.

```bash
# Find your JDK
ls /Library/Java/JavaVirtualMachines/
# e.g. zulu-21.jdk -> /Library/Java/JavaVirtualMachines/zulu-21.jdk/Contents/Home/bin/java
/Library/Java/JavaVirtualMachines/zulu-21.jdk/Contents/Home/bin/java -version

# Fetch the jar somewhere user-global, not per-project
mkdir -p ~/.claude/planning
curl -fL -o ~/.claude/planning/plantuml.jar \
  https://github.com/plantuml/plantuml/releases/download/v1.2026.6/plantuml-1.2026.6.jar

/Library/Java/JavaVirtualMachines/zulu-21.jdk/Contents/Home/bin/java \
  -jar ~/.claude/planning/plantuml.jar -version
```

Then tell the plugin about it by setting `PLANTUML_BIN` to the **whole command**. The hook splits it on whitespace and appends its own flags, so a `java -jar …` form works as-is. Put it in `~/.claude/settings.json` so it applies to every project and doesn't depend on your shell's rc files:

```json
{
  "env": {
    "PLANTUML_BIN": "/Library/Java/JavaVirtualMachines/zulu-21.jdk/Contents/Home/bin/java -jar /Users/<you>/.claude/planning/plantuml.jar"
  }
}
```

Restart Claude Code afterwards — `env` is read at startup.

**Route B — global install.** Simpler if you don't already have a JDK, at the cost of a second JVM. No `PLANTUML_BIN` needed; the hook finds `plantuml` on `PATH`.

```bash
brew install plantuml
plantuml -version
```

### 4. A PDF engine

If you have MacTeX, you already have one — `xelatex` is detected automatically and there is nothing to install:

```bash
which xelatex
```

Otherwise install `typst`, which is a single fast binary with no LaTeX tree and better Unicode tolerance:

```bash
brew install typst
typst --version
```

### 5. Confirm `-failfast2`

The plugin appends `-failfast2` to the PlantUML command so a syntax error fails the build instead of being drawn into the image. Confirm your build knows the flag:

```bash
plantuml -help 2>&1 | grep failfast
# jar route:
java -jar ~/.claude/planning/plantuml.jar -help 2>&1 | grep failfast
```

Expect both `-failfast` and `-failfast2` to be listed. If only `-failfast` is there, the plugin still works — it retries without the flag — but broken diagrams will silently render as error graphics.

### 6. Confirm the whole pipeline

Run the two fixture conversions in [Testing the conversion](#testing-the-conversion) below. The happy path must exit 0 and produce a PDF with real diagrams; the broken fixture must exit 2. If both behave, the toolchain is correct.

## Testing the conversion

`scripts/planning-plan-to-pdf.py` runs standalone with a file argument, which is the fastest way to check your toolchain without going through a real planning session. Two fixtures ship with the plugin for exactly this. Run these from the root of this repo.

Happy path — should exit 0 and print the output path:

```bash
plugins/planning/scripts/planning-plan-to-pdf.py \
  plugins/planning/examples/example-plan.md -o ./.tmp/example.pdf
```

Open `./.tmp/example.pdf` and check three things: the diagrams appear as images rather than as code listings, none of them is a PlantUML error graphic, and no `plantuml-images/` directory was left behind in the repo (the hook renders inside a temp directory and discards it).

Failure path — should exit 2, print PlantUML's error, and write no PDF:

```bash
plugins/planning/scripts/planning-plan-to-pdf.py \
  plugins/planning/examples/broken-plan.md -o ./.tmp/broken.pdf
```

If that command _succeeds_, your PlantUML build is ignoring `-failfast2`, and syntax errors will be baked into real plans as error graphics instead of blocking the exit. Check with `plantuml -help`.

Missing-toolchain path — should exit 0 with an install hint rather than an error:

```bash
PLANNING_PANDOC_BIN=/nonexistent plugins/planning/scripts/planning-plan-to-pdf.py \
  plugins/planning/examples/example-plan.md -o ./.tmp/example.pdf
```

To test the hooks as hooks, feed them the JSON they'd get on stdin:

```bash
echo '{"permission_mode":"plan","transcript_path":"","cwd":"'"$PWD"'"}' \
  | plugins/planning/scripts/planning-plan-conventions.py

echo '{"tool_name":"ExitPlanMode","cwd":"'"$PWD"'","tool_input":{"planFilePath":"'"$PWD"'/plugins/planning/examples/example-plan.md"}}' \
  | plugins/planning/scripts/planning-plan-to-pdf.py
```

The first prints JSON containing `additionalContext`; swap `"plan"` for `"default"` and it prints nothing. The second writes `example-plan.pdf` next to the fixture and prints a `systemMessage`.

## Where the PDF lands

Next to the plan Markdown, same filename with a `.pdf` extension — so in practice `.claude/plans-local/<plan>.pdf`. Override the directory with `PLANNING_PDF_OUTPUT_DIR`.

## Environment overrides

- `PLANNING_PDF_DISABLE=1` — skip PDF rendering entirely. The escape hatch if a plan will not render and you want to approve it anyway.
- `PLANNING_PDF_OUTPUT_DIR` — where the PDF is written (default: alongside the plan file).
- `PLANNING_PANDOC_BIN` — path to `pandoc` (default: found on `PATH`).
- `PLANNING_PLANTUML_FILTER` — path to `pandoc-plantuml` (default: found on `PATH`).
- `PLANNING_PDF_ENGINE` — force a specific engine instead of autodetecting.
- `PLANTUML_BIN` — the filter's own variable, honored here too. Set it to a full command such as `java -jar /opt/plantuml.jar`; the hook appends `-failfast2 -Sdpi=200` to whatever you set.

## Failure behavior

The two failure classes are treated differently on purpose.

| What went wrong | Exit | Effect |
| --- | --- | --- |
| PlantUML rejected a diagram, or the PDF engine rejected the document | 2 | `ExitPlanMode` is blocked and the diagnostics go to Claude, which fixes the plan file and retries |
| pandoc, `pandoc-plantuml`, PlantUML, or every PDF engine is missing | 0 | The plan is approved as normal; a system message names the missing tool and its install command |
| Anything unexpected | 0 | The plan is approved as normal |

The distinction is the whole design. A plan can be edited to fix a broken diagram, so blocking there is useful. A plan cannot be edited to install pandoc, so blocking there would trap the session in a retry loop it could never escape.

`-failfast2` is appended to the PlantUML command for the same reason. By default PlantUML draws a syntax error _into the image_ and exits 0, which would put an error graphic in the PDF and report success. With the flag it exits non-zero, the filter's `subprocess.check_call` raises, pandoc fails, and the error reaches Claude. If your PlantUML build doesn't recognize the flag, the hook detects that from pandoc's stderr and retries once without it — you get a PDF, but broken diagrams stop being caught.

No partial PDF is left behind on failure, so a stale file never passes for a current one.

Note that `plan-review`, if you have it enabled, also hooks `PreToolUse(ExitPlanMode)`. The two run independently and either can block.
