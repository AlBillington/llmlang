# llmlang Flow — Format Spec (draft)

Status: draft syntax for a second, non-canonical flow artifact. Flow files are readable execution maps for externally meaningful entry points. They do not replace `.llm`, do not define code ownership, and do not participate in the lockfile yet.

For canonical `.llm` syntax and behavior specs, see [llmlang-format.md](llmlang-format.md). For the manual drafting checklist, see [onboarding-spec.md](onboarding-spec.md) Part C.

## 1. Purpose

A flow file explains how an entry point runs end to end. It is optimized for following execution and data movement across function calls and external boundaries.

The key invariant is: **arrows are the complete call map for the covered flow**. A reader should be able to trust that a missing arrow means no call happens at that point in the covered path.

## 2. Line Types

### Entry Point

An entry point starts with the externally meaningful trigger and a short description:

```text
main: runs the nightly import job
GET /users/{id}: returns one user
```

Use one entry point per externally triggered path, such as a job `main`, exposed API/RPC handler, queue consumer, CLI command, or UI journey. Do not create flow entries for every helper function.

### Internal Calls

Internal function or method calls use `-> call` followed by the canonical `.llm` entry name:

```text
-> call ImportJob.fetch_pending_records
	- builds the pending-record query
<- return records ready to import
```

The call line names the target only. Put the reason, effect, or important local context in nested dash bullets below the call.

### External Calls

External HTTP, gRPC, SDK, database, queue, logging, or storage boundaries also use `-> call`, with `via` naming the integration boundary:

```text
-> call fetch records via Partner Records API
	- finds records updated since the last import
<- return matching partner records
```

Keep the operation conceptual. Include the service, method, endpoint, or boundary only as far as needed to identify what leaves the codebase.

### Returns

Returns use `<- return` at the same indentation level as the matching call:

```text
-> call UserService.find_user
	- looks up the user for the submitted identifier
<- return matching user, or no user
```

Return lines are optional. Include them when they clarify data flow. Return text should be conceptual, not local variable names.

### Local Behavior

Dash bullets describe behavior happening in the current function scope:

```text
- sorts deduplicated records by creation time
- keeps only valid records
```

Dash bullets must not hide calls. If the behavior is performed by an internal function or external service, use an arrow line.

## 3. Flow Control

Flow control uses normal dash bullets and nested dash bullets. Arrows remain reserved for calls.

```text
- checks whether any records were fetched:
	- if no, exits early
	- if yes, continues processing

- for update case:
	- writes the changed fields
	-> call RecordService.update_record
		- applies changes to the existing record
	<- return write outcome
```

Use `if yes` / `if no` for if/then logic. Use `for X case:` for routing by request type, mode, status, enum, or state.

## 4. Indentation

Indentation shows the current execution context:

- Lines nested under `-> call ...` explain what happens inside that called entry.
- Lines nested under `- ` control bullets explain that control block's body.
- `<- return ...` appears at the same indentation level as the matching `-> call ...`.
- Behavior/control bullets with children end with `:`.
- Call arrows do not need `:` even when they have explanation bullets.

## 5. Completeness Rules

- Every internal call in the covered flow is represented as `-> call CanonicalEntryName`.
- Every external boundary call in the covered flow is represented as `-> call operation via ExternalServiceOrEndpoint`.
- Calls are never intentionally omitted.
- Plain dash bullets never summarize work done by an omitted call.
- If the flow becomes too noisy, narrow the flow scope or improve the real code abstraction; do not curate calls out of the flow file.

## 6. Worked Example

```text
import_job.py:

main: runs the nightly import job
	-> call ImportJob.create
		- creates the import job with configured clients
		-> call load configuration via Config Store
			- loads service configuration
		<- return import configuration
		-> call open connection via Database
			- connects to the import database
		<- return database connection
	<- return configured import job

	-> call ImportJob.fetch_pending_records
		- builds the pending-record query
		-> call fetch records via Partner Records API
			- finds records updated since the last import
		<- return partner records
		- filters out records that were already imported
		-> call ImportJob.parse_record
			- parses one partner record into an import record
		<- return parsed import record
	<- return import records ready to process

	-> call ImportJob.process_records
		- repeats processing for each import record:
			-> call ImportJob.validate_record
				- validates required fields
			<- return validation result
			- checks whether the record is valid:
				- if no, records a validation failure
				- if yes, continues processing
			-> call ImportJob.write_record
				- writes the valid record
			<- return write outcome
	<- return import summary
```
