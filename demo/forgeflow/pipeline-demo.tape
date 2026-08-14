# The pipeline demo, as code (#265).
#
# `vhs demo/forgeflow/pipeline-demo.tape` renders demo/forgeflow/assets/pipeline-demo.gif from
# the commands below — the same offline replay path the README documents and the test suite runs.
# The recording is derived from this file; editing the demo means editing this file, and CI
# re-renders it so the README's recording cannot drift from the commands (.github/workflows/
# demo.yml). Everything runs against the offline profile and the committed recordings: no
# provider, no key, no network.
#
# The hidden epilogue re-runs `trace verify` and writes /tmp/vhs-demo-ok only on success; the
# workflow asserts that file exists, which is what makes this tape a smoke test of the documented
# surface rather than a screenshot of one.
#
# The committed copy is the rendered GIF passed through
# `gifsicle -O3 --colors 32 --lossy=80`, which keeps it under the repository's large-file gate
# without visible cost on terminal text. Regenerate with:
#
#     vhs demo/forgeflow/pipeline-demo.tape
#     gifsicle -O3 --colors 32 --lossy=80 demo/forgeflow/assets/pipeline-demo.gif \
#         -o demo/forgeflow/assets/pipeline-demo.gif

Output demo/forgeflow/assets/pipeline-demo.gif

Set Shell bash
Set FontSize 13
Set Width 1100
Set Height 640
Set TypingSpeed 15ms
Set Padding 10
# 12 frames per second keeps the recording under the repository's large-file gate; the content
# is typed text, and nothing in it moves faster than a keystroke.
Set Framerate 12

Hide
Type `DEMO=$(mktemp -d); trace() { uv run trace --data-root "$DEMO" "$@"; }; rm -f /tmp/vhs-demo-ok; uv run trace >/dev/null 2>&1; clear`
Enter
Sleep 4s
Show

Type "# Trace: the whole pipeline, offline, from the committed ForgeFlow recording"
Enter
Sleep 1.5s

Type "trace assessment create --name 'ForgeFlow Security Review'"
Enter
Sleep 2.5s

Type "trace source add asm-001 demo/forgeflow/input"
Enter
Sleep 4s

Type "trace run asm-001 --model-profile offline-fake --response demo/forgeflow/recorded/extraction"
Enter
Sleep 5s

Type "# The run paused itself: checkpoint 1 is a phase, not an option. Review the context:"
Enter
Sleep 1.5s

Type "trace context show asm-001 | head -24"
Enter
Sleep 5s

Hide
Type `trace context review asm-001 --export "$DEMO/review.yaml" && uv run python -c "import pathlib, yaml; p = pathlib.Path('$DEMO/review.yaml'); d = yaml.safe_load(p.read_text()); [entry.__setitem__('decision', 'approve') for group in ('components', 'actors', 'assets', 'data_flows', 'trust_boundaries', 'claims') for entry in (d.get(group) or [])]; p.write_text(yaml.safe_dump(d, sort_keys=False))" && trace context review asm-001 --reviewer reviewer --apply "$DEMO/review.yaml" >/dev/null && clear`
Enter
Sleep 4s
Show

Type "# Decisions recorded from an exported review file; now approve the baseline:"
Enter
Sleep 1.5s

Type "trace context approve asm-001"
Enter
Sleep 3s

Type "trace resume asm-001 --model-profile offline-fake --response demo/forgeflow/recorded/reasoning"
Enter
Sleep 6s

Type "# Paused again: checkpoint 2. Severity is the reviewer's to assign (DEC-030):"
Enter
Sleep 1.5s

Type "trace findings review asm-001 --severity fnd-001=high --approve fnd-001"
Enter
Sleep 3s

Type "trace findings approve asm-001"
Enter
Sleep 3s

Type "trace resume asm-001 --model-profile offline-fake --response demo/forgeflow/recorded/report"
Enter
Sleep 5s

Type "trace report show asm-001 | head -12"
Enter
Sleep 5s

Type "# And the whole evidence chain re-verifies:"
Enter
Sleep 1.5s

Type "trace verify asm-001"
Enter
Sleep 4s

Hide
Type `trace verify asm-001 >/dev/null 2>&1 && touch /tmp/vhs-demo-ok`
Enter
Sleep 2s
Show
Sleep 2s
