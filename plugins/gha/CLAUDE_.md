# GitHub Actions Workflow Guidelines

## Workflow Structure

- Use descriptive, human-readable names: `name: "Run Tests and Deploy"`
- Organize workflows by purpose: separate CI, CD, scheduled tasks, and release workflows
- Use appropriate triggers: `push`, `pull_request`, `workflow_dispatch`, `schedule`, `release`
- Filter triggers with paths, branches, and types to minimize unnecessary runs
- Document workflow purpose with comments at the top of the file

## Security Best Practices

- Pin actions to full commit SHAs, not tags: `actions/checkout@a12b3c4d...` (not `@v3`)
- Set minimum required permissions: use `permissions:` block at workflow or job level
- Never log or expose secrets, use `::add-mask::` if handling sensitive output
- Use GitHub secrets for credentials: `${{ secrets.SECRET_NAME }}`
- Use OpenID Connect (OIDC) for cloud authentication instead of long-lived credentials
- Use environments for deployment protection rules and environment-specific secrets
- Review third-party actions before use, prefer verified creators or official actions

## Job Configuration

- Use `runs-on: ubuntu-latest` for Linux, `macos-latest` or `windows-latest` as needed
- Set `timeout-minutes` on jobs to prevent runaway workflows (default 360 is often too long)
- Use `needs:` to define job dependencies and create sequential/parallel execution
- Use `if:` conditions to control job execution: `if: github.ref == 'refs/heads/main'`
- Use `continue-on-error: true` sparingly, only for non-critical jobs
- Use `strategy.matrix` for testing multiple versions, platforms, or configurations

## Steps & Actions

- Use meaningful step names that describe the action being performed
- Checkout code first: `uses: actions/checkout@<sha>`
- Use `actions/cache@<sha>` for dependencies, node_modules, build artifacts
- Use `actions/upload-artifact@<sha>` and `actions/download-artifact@<sha>` for job data sharing
- Use `actions/setup-*` actions for language runtimes (node, python, java, go, etc.)
- Use `if: always()` for cleanup steps that must run regardless of previous step failures
- Use `if: failure()` or `if: success()` to conditionally run steps based on prior results

## Environment Variables & Outputs

- Define env vars at workflow, job, or step level for appropriate scope
- Use `$GITHUB_ENV` to set env vars for subsequent steps: `echo "VAR=value" >> $GITHUB_ENV`
- Use `$GITHUB_OUTPUT` for step outputs: `echo "result=success" >> $GITHUB_OUTPUT`
- Reference step outputs: `${{ steps.step-id.outputs.result }}`
- Use GitHub context variables: `${{ github.sha }}`, `${{ github.ref }}`, `${{ github.actor }}`
- Use secrets context for sensitive data: `${{ secrets.SECRET_NAME }}`

## Reusability

- Create composite actions for reusable step sequences in `.github/actions/`
- Create reusable workflows in `.github/workflows/` and call with `uses:` at job level
- Use workflow inputs with `workflow_call` trigger for parameterized reusable workflows
- Use `workflow_dispatch` inputs for manual triggers with parameters
- Share common logic across repositories with separate action repositories

## Performance Optimization

- Use `actions/cache` for package managers: npm, pip, cargo, maven, gradle
- Use matrix strategies to run tests in parallel across versions/platforms
- Use `concurrency` groups to cancel in-progress runs on new commits to same PR/branch
- Use `paths` and `paths-ignore` filters to skip workflows when irrelevant files change
- Use sparse checkout or shallow clone when full history isn't needed
- Use self-hosted runners for faster builds or specialized hardware requirements

## Conditional Execution

- Skip workflows on specific conditions: `if: "!contains(github.event.head_commit.message, '[skip ci]')"`
- Run jobs only on specific branches: `if: github.ref == 'refs/heads/main'`
- Run jobs only for PRs: `if: github.event_name == 'pull_request'`
- Use matrix include/exclude to customize matrix combinations
- Use outputs from previous jobs to control downstream job execution

## Debugging & Troubleshooting

- Enable debug logging: set `ACTIONS_STEP_DEBUG` secret to `true` in repo settings
- Use `ACTIONS_RUNNER_DEBUG` secret for runner diagnostic logs
- Add debug steps: `run: env | sort` to inspect environment, `run: cat $GITHUB_ENV`
- Use `tmate` action for interactive SSH debugging sessions in failing workflows
- Check runner logs and timing information in workflow run summary
- Use `set -x` in shell scripts for command tracing

## Best Practices

- Keep workflows DRY: use reusable workflows and composite actions
- Version control workflow changes carefully, test in feature branches first
- Use `workflow_dispatch` for manual testing during development
- Document complex workflows with README in `.github/workflows/` directory
- Use YAML anchors and aliases to reduce duplication (limited GitHub Actions support)
- Set clear job and step names for readability in the UI
- Use status checks in branch protection rules to enforce quality gates

## Common Patterns

- Install dependencies: `npm ci`, `pip install -r requirements.txt`, `go mod download`
- Run tests: `npm test`, `pytest`, `cargo test`, `go test ./...`
- Build artifacts: `npm run build`, `cargo build --release`, `go build`
- Upload coverage: use `codecov/codecov-action` or `coverallsapp/github-action`
- Semantic versioning: use `semantic-release` or similar for automated releases
- Docker build and push: use `docker/build-push-action` with layer caching

## Matrix Strategy Examples

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    node: [18, 20, 22]
    exclude:
      - os: macos-latest
        node: 18
runs-on: ${{ matrix.os }}
```

## Dynamic Matrix from JSON

```yaml
jobs:
  prepare:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.set-matrix.outputs.matrix }}
    steps:
      - id: set-matrix
        run: echo "matrix={\"include\":[{\"name\":\"test1\"},{\"name\":\"test2\"}]}" >> $GITHUB_OUTPUT

  run:
    needs: prepare
    strategy:
      matrix: ${{ fromJSON(needs.prepare.outputs.matrix) }}
```
