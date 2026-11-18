Implement the server-side slice of Issue #172 (Arkade VTXO offline renewal delegation via official `arkade-os/delegatee` `executord` + `arkade-os/emulator`) in this `nuri-server-musig2-v4-arkade` repository:

### Required Deliverables & Exact Contracts

1. **Nuri 4-Leaf Renewal Artifact & Template Fixtures (`scripts/fixtures/nuri_delegated_vtxo.json` and `scripts/fixtures/nuri_renew.json`)**:
   - `nuri_delegated_vtxo.json`: `contractName: "NuriDelegatedVtxo"` (artifact v1 JSON) with `constructorInputs` (`owner: pubkey`, `clientRecoveryKey: pubkey`, `exitDelay: int`, `clientRecoveryDelay: int`, `renewalWindow: int`, `maxFee: int`), empty `structs: []`, and 4 functions/leaves preserving MuSig2 spends AND delayed client-only recovery:
     - `forfeit` -> leaf `forfeit`: `["<owner>", "OP_CHECKSIGVERIFY", "<SERVER_KEY>", "OP_CHECKSIG"]` (`ownerSig` non-injected `schnorr-64`, `serverSig` `injected: true` `schnorr-64`)
     - `exit` -> leaf `exit`: `["<exitDelay>", "OP_CHECKSEQUENCEVERIFY", "OP_DROP", "<owner>", "OP_CHECKSIG"]` (`ownerSig` `schnorr-64`)
     - `clientRecovery` -> leaf `clientRecovery`: `["<clientRecoveryDelay>", "OP_CHECKSEQUENCEVERIFY", "OP_DROP", "<clientRecoveryKey>", "OP_CHECKSIG"]` (`clientSig` `schnorr-64`)
     - `renew` -> `arkade` covenant checking `OP_PUSHEXPIRY <renewalWindow> OP_SUB OP_CHECKTIME OP_VERIFY`, intent `type == "register"`, `onchain_output_indexes == "[]"`, output value + `<maxFee>` >= input value, and `OP_PUSHCURRENTINPUTINDEX OP_1SUB 5 0 OP_TUNNEL` (preserving scriptPubKey + assets); leaf `renew`: `["<SERVER_KEY>", "OP_CHECKSIGVERIFY", "<EMULATOR_KEY:renew>", "OP_CHECKSIG"]` (both signatures `injected: true` `schnorr-64`).
   - `nuri_renew.json`: `format: "template/v1"`, `type: "proof"`, `variables` (`owner: "pubkey"`, `client_recovery_key: "pubkey"`, `exit_delay: "int"`, `client_recovery_delay: "int"`, `renewal_window: "int"`, `max_fee: "int"`), referencing `nuri_delegated_vtxo.json` by its exact RFC-8785 JCS SHA-256 content `artifact` ID, spending `function: "renew", leaf: "renew"`, single output `renewed` (`value: {"from": "funds"}, locking: {"from": "funds"}, assets: [{"from": "funds"}]`), `fees: {"from": "funds", "max": "<max_fee>"}`, and `delegation: {"schedule": {"funds": {"before_expiry_seconds": "<renewal_window>"}}}`.

2. **Thin Executor Client & Encoding Helpers (`src/ArkadeExecutorClient.js`)**:
   - Export `encodeScriptNumHex(n)` (minimal CScriptNum little-endian lowercase hex: `0n -> ""`, positive/negative minimal sign-bit encoding matching Bitcoin Script / `arkade.BigNum`) and `encodeCsvSequenceHex(timelock)` (`{ type: "blocks" | "seconds", value }` -> BIP-68 sequence integer encoded via `encodeScriptNumHex`; reject seconds not divisible by 512 or out-of-range 16-bit masked values).
   - Export `computeJcsSha256Hex(doc)` (RFC-8785 canonical JSON SHA-256 hex) so artifact/template content IDs can be verified locally without trusting remote state.
   - Export `createArkadeExecutorClient({ cfg, fetchImpl = fetch })`:
     - Configured via `ARKADE_EXECUTOR_URL_V4`, `ARKADE_EXECUTOR_TEMPLATE_ID_V4`, `ARKADE_EXECUTOR_TIMEOUT_MS_V4` (default 10000ms) in `src/ArkadeConfig.js` (default disabled when URL/template unset; never enable `DELEGATE_WORKER_ENABLED_V4` or restore `/v1/delegate`).
     - Talks ONLY to `executord`'s public `ExecutorService` JSON gateway (`/v1/info`, `POST /v1/delegation`, `GET /v1/delegation?id=...` or `?address=...`). NEVER expose or call `/v1/admin/*`, port `7081`, or `/v1/artifact` / `/v1/template` mutation routes from user requests.
     - `registerDelegation({ templateId, variables, expiresAt = 0 })`: validates all variable values are lowercase hex, enforces `AbortController` timeout, classifies network/timeout/5xx errors on `POST /v1/delegation` as explicit uncertain state (`error.code = "EXECUTOR_OUTCOME_UNKNOWN"`, `error.outcomeUnknown = true`) vs deterministic 4xx (`400`/`409` `ErrBlocked` when cancelled), and ensures idempotent re-registration returns the active delegation.
     - `getDelegation({ id, address })` and `getInfo()`.
     - Redact/refuse any secret/token/seed fields so sensitive material never enters logs or error messages.

3. **Authenticated Wallet-Bound Server Routes (`src/ArkadeServer.js`, `src/ArkadeConfig.js`, `ENDPOINTS.md`)**:
   - Add narrowly scoped passkey-authenticated (`verifyRequestAuth(body, cfg)`) routes:
     - `POST /arkade/executor/delegation/register`
     - `POST /arkade/executor/delegation/status`
   - **Strict Wallet Ownership Binding (Critical Security Invariant)**:
     - Extract `clientPk33` from the verified WebAuthn auth token (`getClientSignerFromToken(token)`), derive the server's cosigner pubkey (`getDerivedServerPublicKey(cfg, clientPk33)`), and compute the wallet's exact `owner = deriveAggregatedPk33(clientPk33, derived.pub33)` and `client_recovery_key = clientPk33`.
     - NEVER trust a caller-supplied `owner` or `client_recovery_key` for another wallet: if provided in body and mismatched, reject with `403`; always bind `variables.owner` and `variables.client_recovery_key` to the authenticated wallet's derived keys!
     - On `status` lookup (by `id` or `address`, or default by computing/querying the caller's delegation), verify the returned delegation's `template_id` matches `cfg.ARKADE_EXECUTOR_TEMPLATE_ID_V4` AND `delegation.variables.owner === expectedAggregatePk33` and `delegation.variables.client_recovery_key === clientPk33` before returning it (preventing cross-user IDOR enumeration of another user's delegation ID or address!).
     - Return `503` when executor is not configured, `504`/`502` with `outcome_unknown: true` when registration outcome is uncertain, and never leak tokens/keys in logs.
   - Document the new routes and trust/security boundaries concisely in `ENDPOINTS.md`.

4. **Comprehensive Unit + Live HTTP Route Integration Tests (`src/ArkadeExecutorClient.test.js`)**:
   - Runnable via `node --test src/ArkadeExecutorClient.test.js`.
   - Test `encodeScriptNumHex`, `encodeCsvSequenceHex` (including BIP-68 seconds multiple-of-512 trap!), fixture JCS SHA-256 integrity (`nuri_renew.json` references exact `nuri_delegated_vtxo.json` ID, all 4 leaves present), idempotent registration, timeout -> `outcomeUnknown: true`, cancelled `ErrBlocked` handling, secret redaction, and live HTTP server route tests (`startArkadeServer` or HTTP harness) proving:
     - unauthenticated / purpose-scoped token rejection (`401`)
     - cross-wallet `owner` / `client_recovery_key` spoofing rejection (`403`)
     - cross-wallet `status` IDOR lookup (`id` belonging to another `owner`) rejection (`403`)
     - valid authenticated wallet registration + status roundtrip against a stub `executord` gateway.
