# Broken plan fixture

## Context

This file exists to test the failure path of the `planning` plugin's PDF conversion. The diagram
below is deliberately invalid PlantUML. Rendering this file must fail: `planning-plan-to-pdf.py`
should exit 2, write PlantUML's error to stderr, and leave no PDF behind.

## Target state

```plantuml
@startuml
Alice -> Bob : hello
>>> this line is not valid PlantUML <<<
@enduml
```

If this ever renders successfully, `-failfast2` is not taking effect and every syntax error in a real
plan will be silently baked into the PDF as an error graphic instead of blocking the exit.
