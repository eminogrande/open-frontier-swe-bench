import os, sys, json, random, shutil, tempfile, subprocess

WORK_ST4 = "/tmp/subtasks/st4_bakeoff"
WORK_ST3 = "/tmp/subtasks/st3_gold"
MODELS_JSON = f"{WORK_ST4}/models.json"
V3_SKILL = open("/Users/eminmahrt/Developer/agent-prompt-brevity-bench/prompts/V3_caveman_adhd_winner.md").read()

def check_go_fixtures(wt_path):
    art_p = f"{wt_path}/scripts/fixtures/nuri_delegated_vtxo.json"
    tmpl_p = f"{wt_path}/scripts/fixtures/nuri_renew.json"
    if not (os.path.exists(art_p) and os.path.exists(tmpl_p)):
        return False, "missing fixture files"
    go_code = f'''package template_test
import (
	"os"
	"testing"
	"github.com/arkade-os/executor/pkg/template"
	"github.com/arkade-os/executor/pkg/template/artifact"
	"github.com/stretchr/testify/require"
)
func TestVerifyCandidateFixtures(t *testing.T) {{
	artRaw, err := os.ReadFile({json.dumps(art_p)})
	require.NoError(t, err)
	parsedArt, err := artifact.ParseVersion(artifact.Version1, artRaw)
	require.NoError(t, err)
	require.Len(t, parsedArt.Definition().Functions, 4)
	tmplRaw, err := os.ReadFile({json.dumps(tmpl_p)})
	require.NoError(t, err)
	doc, err := template.Decode(tmplRaw)
	require.NoError(t, err)
	compiled, err := template.CompileDocuments(doc, map[string][]byte{{parsedArt.ID(): artRaw}})
	require.NoError(t, err)
	require.Equal(t, template.Proof, compiled.Type())
}}
'''
    cf = f"/tmp/subtasks/st2_audit/delegatee/pkg/template/cand_verify_{os.getpid()}_test.go"
    open(cf, "w").write(go_code)
    env = os.environ.copy(); env["CGO_ENABLED"] = "0"
    try:
        r = subprocess.run(["go", "test", ".", "-run", "TestVerifyCandidateFixtures"], cwd="/tmp/subtasks/st2_audit/delegatee/pkg/template", env=env, capture_output=True, text=True, timeout=45)
        return r.returncode == 0, (r.stdout + r.stderr)[-300:]
    finally:
        if os.path.exists(cf):
            os.remove(cf)

LIVE_HTTP_SECURITY_HARNESS = r"""
import crypto from "node:crypto";
import http from "node:http";
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const cwd = process.cwd();
const rpId = "127.0.0.1";
const origin = "http://127.0.0.1";
const templateId = "c6d690e1a4fa1f89becfbbe904ea7239c7ce3cc3b0e6ecb41a053bc8cddd59eb";

function makeWallet(label, skByte) {
  const passkey = crypto.generateKeyPairSync("ec", { namedCurve: "prime256v1" });
  const credPubkeyB64u = passkey.publicKey.export({ type: "spki", format: "der" }).toString("base64url");
  const ecdh = crypto.createECDH("secp256k1");
  ecdh.setPrivateKey(Buffer.alloc(32, skByte));
  const clientPk33 = ecdh.getPublicKey("hex", "compressed").toLowerCase();
  return { credId: `cred_${label}`, passkey, credPubkeyB64u, clientPk33 };
}

const walletA = makeWallet("alice", 0x21);
const walletB = makeWallet("bob", 0x22);

const storedById = new Map();
let nextId = 1;
const upstreamCalls = [];

const stub = http.createServer((req, res) => {
  const u = new URL(req.url, "http://127.0.0.1");
  let raw = "";
  req.on("data", (c) => { raw += c; });
  req.on("end", () => {
    upstreamCalls.push({ method: req.method, path: u.pathname, query: u.search, body: raw ? JSON.parse(raw) : null });
    if (req.method === "POST" && u.pathname === "/v1/delegation") {
      const b = JSON.parse(raw || "{}");
      const id = nextId++;
      const del = {
        id,
        fingerprint: "ff".repeat(32),
        address: `tark1qdelegated${id}`,
        template_id: b.template_id ?? b.templateId,
        templateId: b.template_id ?? b.templateId,
        variables: b.variables || {},
        inputs: [{ name: "funds", onchain: false, script: "5120" + "aa".repeat(32), tapscripts: [], locktime: 0 }],
        stream_id: 0,
        expires_at: Number(b.expires_at ?? b.expiresAt ?? 0),
        status: "active",
        created_at: 1700000000,
        updated_at: 1700000000,
      };
      storedById.set(String(id), del);
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ delegation: del }));
      return;
    }
    if (req.method === "GET" && u.pathname === "/v1/delegation") {
      const id = u.searchParams.get("id");
      const addr = u.searchParams.get("address");
      let found = id ? storedById.get(String(id)) : null;
      if (!found && addr) {
        for (const v of storedById.values()) if (v.address === addr) found = v;
      }
      if (!found) {
        res.writeHead(404, { "content-type": "application/json" });
        res.end(JSON.stringify({ code: 5, message: "not found" }));
        return;
      }
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ delegation: found, coins: [{ outpoint: "11".repeat(32) + ":0", input: 0, amount: 100000, status: "present" }] }));
      return;
    }
    res.writeHead(404); res.end();
  });
});

await new Promise((r) => stub.listen(0, "127.0.0.1", r));
const stubUrl = `http://127.0.0.1:${stub.address().port}`;
const dataDir = mkdtempSync(path.join(tmpdir(), "gate-sec-"));
const port = Math.floor(25000 + Math.random() * 20000);
const baseUrl = `http://127.0.0.1:${port}`;

const child = spawn(process.execPath, ["src/ArkadeServer.js"], {
  cwd,
  env: {
    ...process.env,
    NODE_ENV: "test",
    ARKADE_ENV_V4: "local",
    HOST_V4: "127.0.0.1",
    PORT_V4: String(port),
    RP_ID_V4: rpId,
    ORIGIN_V4: origin,
    ALLOW_ANDROID_ORIGIN_V4: "false",
    PASSKEY_PUBKEY_POLICY_V4: "hard",
    TOKEN_SEED_V4: "00".repeat(32),
    COSIGNER_SEED_V4: "11".repeat(32),
    COSIGNER_NURI_SERVER_CSV_TYPE_V4: "seconds",
    COSIGNER_NURI_SERVER_CSV_VALUE_V4: "6674432",
    ARKADE_DATABASE_PATH_V4: path.join(dataDir, "arkade.sqlite"),
    RECOVERY_STORE_PATH_V4: path.join(dataDir, "rec.json"),
    LNURL_STORE_PATH_V4: path.join(dataDir, "lnurl.json"),
    LNURL_BASE_URL_V4: baseUrl,
    LNURL_DOMAIN_V4: "127.0.0.1",
    ARKADE_NODE_URL_V4: "http://127.0.0.1:1",
    BOARDING_ESPLORA_API_URL_V4: "http://127.0.0.1:1",
    BOARDING_ESPLORA_FALLBACK_API_URL_V4: "off",
    DELEGATE_WORKER_ENABLED_V4: "false",
    ARKADE_EXECUTOR_URL_V4: stubUrl,
    ARKADE_EXECUTOR_TEMPLATE_ID_V4: templateId,
    ARKADE_EXECUTOR_TIMEOUT_MS_V4: "2000",
  },
  stdio: ["ignore", "pipe", "pipe"],
});

async function reqJson(pathname, body = null) {
  const r = await fetch(`${baseUrl}${pathname}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "content-type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: r.status, body: await r.json().catch(() => null) };
}

function signAssertion(wallet, token, challenge) {
  const clientData = Buffer.from(JSON.stringify({ type: "webauthn.get", challenge, origin, crossOrigin: false }));
  const authData = Buffer.concat([crypto.createHash("sha256").update(rpId).digest(), Buffer.from([0x05]), Buffer.from([0,0,0,1])]);
  const signed = Buffer.concat([authData, crypto.createHash("sha256").update(clientData).digest()]);
  return {
    token,
    client_data_b64u: clientData.toString("base64url"),
    auth_data_b64u: authData.toString("base64url"),
    sig_b64u: crypto.sign("sha256", signed, wallet.passkey.privateKey).toString("base64url"),
  };
}

async function freshAuth(wallet) {
  const a = await reqJson("/arkade/auth", {
    cred_id_b64u: wallet.credId,
    cred_pubkey_b64u: wallet.credPubkeyB64u,
    client_signer_pubkey: wallet.clientPk33,
  });
  if (a.status !== 200) throw new Error("auth failed " + a.status);
  return signAssertion(wallet, a.body.token, a.body.challenge);
}

try {
  const deadline = Date.now() + 12000;
  let healthy = false;
  while (Date.now() < deadline) {
    try {
      const h = await reqJson("/health");
      if (h.status === 200 && h.body?.ok) { healthy = true; break; }
    } catch {}
    await new Promise((r) => setTimeout(r, 80));
  }
  if (!healthy) throw new Error("server failed to boot");

  const validHexPayload = {
    variables: {
      exit_delay: "010040",
      client_recovery_delay: "ec3240",
      renewal_window: "100e",
      max_fee: "f401",
    },
  };
  const validStructuredPayload = {
    exit_delay: { type: "seconds", value: 512 },
    client_recovery_delay: { type: "seconds", value: 6674432 },
    renewal_window: 3600,
    max_fee: 500,
  };

  // 1. Unauthenticated must fail 401
  const rUnauth = await reqJson("/arkade/executor/delegation/register", validHexPayload);
  if (rUnauth.status !== 401) throw new Error(`expected 401 unauth, got ${rUnauth.status}`);

  // 2. Purpose-scoped bootstrap token must fail 401
  const boot = await reqJson("/arkade/lnurl/register-bootstrap/auth", {
    username: "alicegate",
    cred_id_b64u: walletA.credId,
    cred_pubkey_b64u: walletA.credPubkeyB64u,
  });
  if (boot.status === 200 && boot.body?.token) {
    const rPurpose = await reqJson("/arkade/executor/delegation/register", {
      ...signAssertion(walletA, boot.body.token, boot.body.challenge),
      ...validHexPayload,
    });
    if (rPurpose.status !== 401) throw new Error(`expected 401 purpose token, got ${rPurpose.status}`);
  }

  // 3. Cross-wallet spoofing of client_recovery_key or owner must fail 403
  let rSpoof = await reqJson("/arkade/executor/delegation/register", {
    ...(await freshAuth(walletA)),
    client_recovery_key: walletB.clientPk33,
    variables: { ...validHexPayload.variables, client_recovery_key: walletB.clientPk33 },
  });
  if (rSpoof.status === 400) {
    rSpoof = await reqJson("/arkade/executor/delegation/register", {
      ...(await freshAuth(walletA)),
      ...validStructuredPayload,
      client_recovery_key: walletB.clientPk33,
    });
  }
  if (rSpoof.status !== 403) throw new Error(`expected 403 spoof, got ${rSpoof.status}`);

  // 4. Valid authenticated Wallet A registration -> 200 (accept canonical hex variables OR structured timelocks)
  let rReg = await reqJson("/arkade/executor/delegation/register", {
    ...(await freshAuth(walletA)),
    ...validHexPayload,
  });
  if (rReg.status === 400) {
    rReg = await reqJson("/arkade/executor/delegation/register", {
      ...(await freshAuth(walletA)),
      ...validStructuredPayload,
    });
  }
  if (rReg.status !== 200) throw new Error(`expected 200 register, got ${rReg.status}: ${JSON.stringify(rReg.body)}`);
  const delObj = rReg.body?.delegation || rReg.body;
  const delId = delObj?.id;
  if (!delId) throw new Error("missing delegation id");
  const upVars = upstreamCalls[upstreamCalls.length - 1]?.body?.variables || {};
  if (upVars.client_recovery_key !== walletA.clientPk33) {
    throw new Error("bound client_recovery_key mismatch");
  }
  for (const [k, v] of Object.entries(upVars)) {
    if (typeof v !== "string" || !/^[0-9a-f]*$/.test(v) || v.length % 2 !== 0) {
      throw new Error(`upstream variable ${k} is not valid even-length lowercase hex: ${v}`);
    }
  }
  if (upVars.exit_delay !== "010040" || upVars.client_recovery_delay !== "ec3240") {
    throw new Error(`upstream BIP-68 CSV hex mismatch: exit=${upVars.exit_delay} rec=${upVars.client_recovery_delay}`);
  }

  // 5. Valid Wallet A status -> 200
  const rStatA = await reqJson("/arkade/executor/delegation/status", {
    ...(await freshAuth(walletA)),
    id: delId,
  });
  if (rStatA.status !== 200) throw new Error(`expected 200 status A, got ${rStatA.status}`);

  // 6. Cross-wallet IDOR: Wallet B querying Wallet A's delegation id -> 403!
  const rIdorB = await reqJson("/arkade/executor/delegation/status", {
    ...(await freshAuth(walletB)),
    id: delId,
  });
  if (rIdorB.status !== 403) throw new Error(`IDOR VULN! expected 403 for Wallet B status on Wallet A id, got ${rIdorB.status}`);

  console.log("LIVE_HTTP_SEC_OK");
} finally {
  child.kill();
  stub.close();
  rmSync(dataDir, { recursive: true, force: true });
}
"""

def run_deterministic_gates(wt_path):
    gates = {}
    test_f = f"{wt_path}/src/ArkadeExecutorClient.test.js"
    if os.path.exists(test_f):
        r_own = subprocess.run(["node", "--test", "src/ArkadeExecutorClient.test.js"], cwd=wt_path, capture_output=True, text=True, timeout=75)
        gates["G1_own_tests"] = (r_own.returncode == 0)
    else:
        gates["G1_own_tests"] = False

    go_ok, _ = check_go_fixtures(wt_path)
    gates["G2_go_compiler_fixtures"] = go_ok

    probe_js = """
import assert from 'node:assert/strict';
import * as mod from './src/ArkadeExecutorClient.js';
assert.equal(mod.encodeScriptNumHex(0), '');
assert.equal(mod.encodeScriptNumHex(144), '9000');
assert.equal(mod.encodeScriptNumHex(288), '2001');
assert.equal(mod.encodeScriptNumHex(500), 'f401');
assert.equal(mod.encodeScriptNumHex(3600), '100e');
assert.equal(mod.encodeScriptNumHex(-1), '81');
assert.equal(mod.encodeCsvSequenceHex({ type: 'blocks', value: 144 }), '9000');
assert.equal(mod.encodeCsvSequenceHex({ type: 'seconds', value: 512 }), '010040');
assert.throws(() => mod.encodeCsvSequenceHex({ type: 'seconds', value: 86400 }));
const art = JSON.parse((await import('node:fs')).readFileSync('./scripts/fixtures/nuri_delegated_vtxo.json', 'utf8'));
const tmpl = JSON.parse((await import('node:fs')).readFileSync('./scripts/fixtures/nuri_renew.json', 'utf8'));
assert.equal(mod.computeJcsSha256Hex(art), tmpl.inputs[0].contract.definition.artifact);
console.log('PROBE_OK');
"""
    r_probe = subprocess.run(["node", "--input-type=module", "-e", probe_js], cwd=wt_path, capture_output=True, text=True, timeout=20)
    gates["G3_encoding_and_jcs_invariants"] = (r_probe.returncode == 0 and "PROBE_OK" in r_probe.stdout)

    client_js = """
import assert from 'node:assert/strict';
import { createArkadeExecutorClient } from './src/ArkadeExecutorClient.js';
const client = createArkadeExecutorClient({
  cfg: { ARKADE_EXECUTOR_URL_V4: 'http://127.0.0.1:17080', ARKADE_EXECUTOR_TEMPLATE_ID_V4: 'aa'.repeat(32), ARKADE_EXECUTOR_TIMEOUT_MS_V4: 50 },
  fetchImpl: async () => new Promise((_, rej) => setTimeout(() => { const e = new Error('aborted'); e.name = 'AbortError'; rej(e); }, 10))
});
let caught = null;
try {
  await client.registerDelegation({ templateId: 'aa'.repeat(32), variables: { owner: '02' + '11'.repeat(32) }, expiresAt: 0 });
} catch (err) { caught = err; }
assert.ok(caught && (caught.outcomeUnknown === true || caught.code === 'EXECUTOR_OUTCOME_UNKNOWN'));
console.log('CLIENT_OK');
"""
    r_cli = subprocess.run(["node", "--input-type=module", "-e", client_js], cwd=wt_path, capture_output=True, text=True, timeout=20)
    gates["G4_uncertain_outcome_handling"] = (r_cli.returncode == 0 and "CLIENT_OK" in r_cli.stdout)

    r_sec = subprocess.run(["node", "--input-type=module", "-e", LIVE_HTTP_SECURITY_HARNESS], cwd=wt_path, capture_output=True, text=True, timeout=45)
    gates["G5_live_http_auth_idor_security"] = (r_sec.returncode == 0 and "LIVE_HTTP_SEC_OK" in r_sec.stdout)
    gates["G5_sec_detail"] = (r_sec.stdout + r_sec.stderr).strip()[-240:]

    r_reg = subprocess.run(["node", "scripts/notifications-bind-proof.mjs"], cwd=wt_path, capture_output=True, text=True, timeout=45)
    gates["G6_existing_server_regression"] = (r_reg.returncode == 0)

    ep_txt = open(f"{wt_path}/ENDPOINTS.md").read()
    srv_txt = open(f"{wt_path}/src/ArkadeServer.js").read()
    gates["G7_docs_and_no_admin_leak"] = (
        "/arkade/executor/delegation/register" in ep_txt and
        "/arkade/executor/delegation/status" in ep_txt and
        "/v1/admin" not in srv_txt and
        "7081" not in srv_txt
    )

    bool_gates = [v for k, v in gates.items() if k.startswith("G") and isinstance(v, bool)]
    gates["gates_passed"] = sum(1 for v in bool_gates if v is True)
    gates["gates_total"] = len(bool_gates)
    return gates

cids = ["C1_solo_k3_max", "C2_homo_k3_4stage", "C3_hetero_k3_ds_glm", "C4_hetero_glm_kimi_k3", "C5_hetero_nem_ds_k3", "C6_solo_deepseek_v4_1"]
gate_results = {}
gate_results["GOLD_carbon_fable"] = run_deterministic_gates(f"{WORK_ST3}/gold-wt")
for cid in cids:
    gate_results[cid] = run_deterministic_gates(f"{WORK_ST4}/wt_{cid}")

rng = random.Random(20261118)
shuffled = list(cids)
rng.shuffle(shuffled)
anon_map = {f"CANDIDATE_{chr(65+i)}": cid for i, cid in enumerate(shuffled)}
json.dump(anon_map, open(f"{WORK_ST4}/blind_key_mapping.json", "w"), indent=2)

gold_patch = open(f"{WORK_ST3}/gold_final.patch").read()
task_spec = open(f"{WORK_ST3}/TASK_PROMPT.md").read()

bundle_parts = []
for anon_id in sorted(anon_map.keys()):
    cid = anon_map[anon_id]
    patch = open(f"{WORK_ST4}/{cid}.patch").read()
    g = gate_results[cid]
    g_clean = {k: v for k, v in g.items() if k.startswith("G") and isinstance(v, bool)}
    bundle_parts.append(
        f"## {anon_id}\n"
        f"Deterministic Gate Pass Summary: {g['gates_passed']}/{g['gates_total']} ({json.dumps(g_clean)})\n"
        f"```diff\n{patch[:24000] if patch.strip() else '(EMPTY DIFF — pipeline produced 0 file edits before timeout)'}\n```\n"
    )

blind_prompt = f"""You are a double-blind software-engineering evaluation judge (`Fable`).
Six anonymized open-model engineering pipelines (`CANDIDATE_A` through `CANDIDATE_F` — model identities and whether single-agent or multi-agent are hidden and randomized) attempted the exact same task on `nuri-server-musig2-v4-arkade` at frozen commit `136a54fa`.

Grade each candidate strictly against the Task Specification, the 7 Deterministic Gate results, and the Gold-Standard Reference PR on 4 axes (0-25 points each, total 0-100):
- `correctness_25`: Protocol accuracy (4-leaf `NuriDelegatedVtxo` artifact, RFC-8785 JCS SHA-256 ID in `nuri_renew.json`, minimal CScriptNum + BIP-68 CSV `seconds % 512 === 0`, executor REST contract)
- `security_25`: Strict passkey->MuSig2 wallet ownership binding (`deriveAggregatedPk33`, `clientPk33`), cross-user IDOR prevention on `register` & `status`, purpose-scoped token rejection, `outcome_unknown: true` classification, zero admin-port or secret leaks
- `craft_brevity_25`: Reuse of existing `ArkadeServer.js` helpers, minimal clean code without bloat/abstractions, zero regressions
- `tests_docs_25`: Depth/realism of `ArkadeExecutorClient.test.js` (including live HTTP auth/IDOR tests) and crisp `ENDPOINTS.md` docs

### Task Specification
{task_spec}

### Gold-Standard Reference Diff (Anchor = 98/100, passed 7/7 deterministic gates)
```diff
{gold_patch[:20000]}
```

### Anonymized Candidate Submissions
{"".join(bundle_parts)}

Return ONLY valid JSON with exact structure:
{{
  "scores": {{
    "CANDIDATE_A": {{"correctness_25": int, "security_25": int, "craft_brevity_25": int, "tests_docs_25": int, "total_100": int, "key_strengths": string, "flaws_found": string}},
    "CANDIDATE_B": ...,
    "CANDIDATE_C": ...,
    "CANDIDATE_D": ...,
    "CANDIDATE_E": ...,
    "CANDIDATE_F": ...
  }},
  "ranking": ["CANDIDATE_...", ...]
}}
"""

ag = tempfile.mkdtemp(prefix="pi-judge-")
shutil.copy(MODELS_JSON, f"{ag}/models.json")
open(f"{ag}/settings.json", "w").write("{}")
open(f"{ag}/trust.json", "w").write("{}")
open(f"{ag}/APPEND_SYSTEM.md", "w").write(V3_SKILL)
env = os.environ.copy(); env["PI_CODING_AGENT_DIR"] = ag
proc = subprocess.run(
    ["pi", "-p", "--mode", "json", "--no-session", "--no-context-files", "--no-extensions", "--no-mcp", "--no-skills", "--no-tools",
     "--provider", "nous", "--model", "anthropic/claude-fable-5.2", "--thinking", "max", "--", blind_prompt],
    env=env, capture_output=True, text=True, timeout=360
)
shutil.rmtree(ag, ignore_errors=True)

judge_txt = ""
for l in proc.stdout.splitlines():
    if l.strip().startswith("{"):
        ev = json.loads(l)
        if ev.get("type") == "turn_end":
            txts = [c.get("text", "") for c in ev.get("message", {}).get("content", []) if c.get("type") == "text"]
            if txts:
                judge_txt = "\n".join(txts)

open(f"{WORK_ST4}/fable_blind_judgment_raw.txt", "w").write(judge_txt)
json.dump({"gates": gate_results, "anon_map": anon_map, "fable_raw": judge_txt}, open(f"{WORK_ST4}/final_blind_evaluation.json", "w"), indent=2)
print("BLIND EVALUATION COMPLETE!")
