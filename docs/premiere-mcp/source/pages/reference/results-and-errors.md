# Results and errors

## Results

Every tool returns structured content that matches its output schema, and the server checks the report
of the Premiere Pro script against that schema before it returns it. The fields of each tool are in the
[tools reference](tools.md). Times are seconds and paths are absolute.

`premiere_script` returns the script's last value as `answer` and, when `report` names a `.json` path,
the JSON the script wrote as `report`.

## Errors

A failed call is a tool error: `isError` is true, the content is the cause as readable text, and the
structured content has this shape:

```json
{"error": {"version": 1, "code": "INVALID_ARGUMENT", "operation": "premiere_export",
           "outcome": "rejected", "retry_safe": false, "next_action": "inspect_inputs"}}
```

| `code` | `outcome` | `next_action` | When |
|---|---|---|---|
| `INVALID_ARGUMENT` | `rejected` | `inspect_inputs` | An argument is out of range, relative or inconsistent. Nothing was sent to Premiere Pro. |
| `INPUT_NOT_FOUND` | `rejected` | `inspect_inputs` | A file the call needs does not exist. |
| `OUTCOME_UNKNOWN` | `unknown` | `inspect_application_and_outputs` | Anything else: a script that threw, a report that could not be read, a job that could not start. The project may have changed. |

`retry_safe` is always false: the server never claims that repeating a call is harmless. After an
`unknown` outcome, read the project with `premiere_inspect` and check the output files before you call
again.

A script that throws, an unreadable report and a job that cannot start are reported at once; the server
does not wait out the timeout.
