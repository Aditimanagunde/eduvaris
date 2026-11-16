"use client";
/*
  Eduvaris: the whole website in one file (dark theme).

  Sections:
    1. Talking to the backend (API helper, login token)
    2. Small building blocks (tabs, stat tiles, charts, issues table)
    3. Home screen (login + public APAAR check)
    4. AICTE admin screens
    5. Institution screens
    6. App (picks the screen for the logged-in role)
    7. Styles (dark theme)
*/

import { useCallback, useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

// =============================================================================
// 1. TALKING TO THE BACKEND
// =============================================================================
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_KEY = "eduvaris_token";

function getToken() {
  return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
}

function errorText(body, status) {
  if (body && typeof body.detail === "string") return body.detail;
  if (body && Array.isArray(body.detail)) {
    return body.detail.map((d) => `${d.loc?.[d.loc.length - 1] ?? ""}: ${d.msg.replace("Value error, ", "")}`).join("; ");
  }
  return `Something went wrong (${status})`;
}

/** Calls the backend with the login token. Throws an Error with a readable message on failure. */
async function api(path, { method = "GET", json, form } = {}) {
  const headers = {};
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, { method, headers, body });
  } catch {
    throw new Error("Cannot reach the backend. Is it running on port 8000?");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(errorText(data, res.status));
  return data;
}

// =============================================================================
// 2. SMALL BUILDING BLOCKS
// =============================================================================
const COLORS = ["#5b8def", "#3ecf8e", "#f5a524", "#f2555a", "#a78bfa", "#2dd4bf", "#f472b6"];
const AXIS = { tick: { fill: "#9aa4b2", fontSize: 12 }, stroke: "#3a4556" };
const TOOLTIP = {
  contentStyle: { background: "#1a2230", border: "1px solid #2c3646", borderRadius: 8, color: "#e6e9ef" },
  itemStyle: { color: "#e6e9ef" },
  labelStyle: { color: "#9aa4b2" },
  cursor: { fill: "rgba(255,255,255,0.04)" },
};

function Tabs({ tabs, active, onChange }) {
  return (
    <div className="tabs">
      {tabs.map(([key, label]) => (
        <button key={key} className={active === key ? "tab active" : "tab"} onClick={() => onChange(key)}>
          {label}
        </button>
      ))}
    </div>
  );
}

function Tiles({ items }) {
  return (
    <div className="tiles">
      {items.map(([label, value, tone]) => (
        <div key={label} className={`tile ${tone || ""}`}>
          <div className="tile-value">{value}</div>
          <div className="tile-label">{label}</div>
        </div>
      ))}
    </div>
  );
}

function ChartCard({ title, children, height = 280 }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer>{children}</ResponsiveContainer>
      </div>
    </div>
  );
}

function Message({ msg }) {
  if (!msg?.text) return null;
  return <div className={`msg ${msg.type}`}>{msg.text}</div>;
}

const shortName = (name) => (name.length > 22 ? name.slice(0, 20) + "…" : name);

function IssuesTable({ issues, showInstitution }) {
  const [type, setType] = useState("");
  const types = [...new Set(issues.map((i) => i.label))];
  const shown = type ? issues.filter((i) => i.label === type) : issues;
  return (
    <div className="card">
      <div className="row space">
        <h3>Problems found automatically ({shown.length})</h3>
        <select value={type} onChange={(e) => setType(e.target.value)} style={{ maxWidth: 320 }}>
          <option value="">All problem types</option>
          {types.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      {shown.length === 0 ? (
        <p className="muted">No problems found. The data looks clean.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Severity</th><th>Problem</th>{showInstitution && <th>Institution</th>}
                <th>Program</th><th>Student</th><th>Details</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((i, n) => (
                <tr key={n}>
                  <td><span className={`badge ${i.severity}`}>{i.severity}</span></td>
                  <td>{i.label}</td>
                  {showInstitution && <td>{i.institution_name}</td>}
                  <td>{i.program || "-"}</td>
                  <td>{i.student_name ? <>{i.student_name}<div className="muted mono">{i.apaar_id}</div></> : "-"}</td>
                  <td>{i.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function IssuesChart({ data }) {
  return (
    <ChartCard title="Problems found, by type">
      <BarChart data={data} layout="vertical" margin={{ left: 20, right: 20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2c3646" />
        <XAxis type="number" allowDecimals={false} {...AXIS} />
        <YAxis type="category" dataKey="label" width={200} {...AXIS} />
        <Tooltip {...TOOLTIP} />
        <Bar dataKey="count" name="Problems" fill="#f2555a" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ChartCard>
  );
}

function CategoryChart({ data }) {
  return (
    <ChartCard title="Admission category">
      <PieChart>
        <Pie data={data} dataKey="count" nameKey="label" outerRadius={95} innerRadius={50} paddingAngle={2}
             stroke="#0f141c" label={{ fill: "#e6e9ef", fontSize: 12 }}>
          {data.map((d, n) => <Cell key={d.label} fill={COLORS[n % COLORS.length]} />)}
        </Pie>
        <Tooltip {...TOOLTIP} />
        <Legend wrapperStyle={{ color: "#9aa4b2" }} />
      </PieChart>
    </ChartCard>
  );
}

function SpecialCategoriesChart({ totals }) {
  const data = [
    { label: "NRI", count: totals.nri },
    { label: "OCI", count: totals.oci },
    { label: "Foreign National", count: totals.foreign_nationals },
    { label: "Supernumerary", count: totals.enrolled_supernumerary },
  ];
  return (
    <ChartCard title="NRI / OCI / Foreign National / Supernumerary students">
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2c3646" />
        <XAxis dataKey="label" {...AXIS} />
        <YAxis allowDecimals={false} {...AXIS} />
        <Tooltip {...TOOLTIP} />
        <Bar dataKey="count" name="Students" radius={[4, 4, 0, 0]}>
          {data.map((d, n) => <Cell key={d.label} fill={COLORS[(n + 1) % COLORS.length]} />)}
        </Bar>
      </BarChart>
    </ChartCard>
  );
}

// =============================================================================
// 3. HOME SCREEN: login + public APAAR check
// =============================================================================
function HomeScreen({ onLoggedIn }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [busy, setBusy] = useState(false);
  const [apaar, setApaar] = useState("");
  const [result, setResult] = useState(null);
  const [checkError, setCheckError] = useState("");

  async function login(e) {
    e.preventDefault();
    setBusy(true);
    setLoginError("");
    try {
      const data = await api("/api/auth/token", { method: "POST", form: new URLSearchParams({ username: email, password }) });
      localStorage.setItem(TOKEN_KEY, data.access_token);
      onLoggedIn();
    } catch (err) {
      setLoginError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function verify(e) {
    e.preventDefault();
    setResult(null);
    setCheckError("");
    try {
      setResult(await api(`/api/verify/${encodeURIComponent(apaar.replace(/[\s-]/g, ""))}`));
    } catch (err) {
      setCheckError(err.message);
    }
  }

  return (
    <>
      <section className="hero">
        <h1>Eduvaris</h1>
        <p>
          APAAR ID-based student data management and verification for AICTE-approved institutions.
          Institutions submit student records, the platform checks them automatically, and AICTE monitors
          everything in real time.
        </p>
        <div className="features">
          <div><strong>Submit</strong><span>Form, Excel/CSV upload, or API</span></div>
          <div><strong>Validate</strong><span>Duplicates, invalid APAAR IDs, intake limits</span></div>
          <div><strong>Monitor</strong><span>Live dashboards for AICTE and institutions</span></div>
        </div>
      </section>

      <div className="grid2">
        <div className="card">
          <h3>Log in</h3>
          <p className="muted">For AICTE administrators and institutions.</p>
          <form onSubmit={login}>
            <label>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
            <label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
            <button type="submit" disabled={busy} className="mt">{busy ? "Logging in…" : "Log in"}</button>
          </form>
          {loginError && <div className="msg error">{loginError}</div>}
        </div>

        <div className="card">
          <h3>Verify an APAAR ID</h3>
          <p className="muted">Check whether a student is enrolled at an AICTE-approved institution.</p>
          <form onSubmit={verify}>
            <label>APAAR ID (12 digits)</label>
            <input value={apaar} onChange={(e) => setApaar(e.target.value)} placeholder="1234 5678 9012" required />
            <button type="submit" className="mt">Verify</button>
          </form>
          {checkError && <div className="msg error">{checkError}</div>}
          {result && (
            <div className="verify-result">
              <div><span className="badge ok">Enrolled</span> <strong>{result.student_name_masked}</strong></div>
              {result.enrolments.map((e, n) => (
                <div key={n} className="muted">
                  {e.program} ({e.academic_year}), year {e.year_of_study} · {e.institution} [{e.aicte_id}]
                </div>
              ))}
              {result.multiple_institutions && (
                <div className="msg warn">This APAAR ID is enrolled at more than one institution.</div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// =============================================================================
// 4. AICTE ADMIN SCREENS
// =============================================================================
function AdminScreen() {
  const [tab, setTab] = useState("dashboard");
  const [overview, setOverview] = useState(null);
  const [issues, setIssues] = useState([]);
  const [error, setError] = useState("");

  const reload = useCallback(() => {
    api("/api/admin/overview").then(setOverview).catch((e) => setError(e.message));
    api("/api/admin/issues").then(setIssues).catch((e) => setError(e.message));
  }, []);
  useEffect(() => { reload(); }, [reload]);

  return (
    <>
      <h2>AICTE Dashboard</h2>
      <Tabs active={tab} onChange={setTab} tabs={[
        ["dashboard", "Dashboard"], ["issues", `Problems (${issues.length})`],
        ["institutions", "Institutions"], ["students", "Search students"],
      ]} />
      {error && <div className="msg error">{error}</div>}
      {tab === "dashboard" && <AdminDashboard overview={overview} />}
      {tab === "issues" && <IssuesTable issues={issues} showInstitution />}
      {tab === "institutions" && <InstitutionsManager onChange={reload} />}
      {tab === "students" && <StudentSearch />}
    </>
  );
}

function AdminDashboard({ overview }) {
  if (!overview) return <p className="muted">Loading…</p>;
  const t = overview.totals;
  const rows = overview.rows.map((r) => ({ ...r, short: shortName(r.name) }));
  return (
    <>
      <Tiles items={[
        ["Institutions", t.institutions], ["Programs", t.programs], ["Approved intake", t.approved_intake],
        ["Students enrolled", t.enrolled], ["Supernumerary used / seats", `${t.enrolled_supernumerary} / ${t.supernumerary_seats}`],
        ["NRI · OCI · Foreign", `${t.nri} · ${t.oci} · ${t.foreign_nationals}`],
        ["Problems found", t.issues, t.issues ? "bad" : "good"],
        ["Rows rejected (bad APAAR)", `${t.rows_rejected} (${t.rows_rejected_apaar})`, t.rows_rejected ? "warn" : ""],
      ]} />
      <div className="grid2">
        <ChartCard title="Approved intake vs actual enrolment">
          <BarChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2c3646" />
            <XAxis dataKey="short" {...AXIS} interval={0} angle={-15} textAnchor="end" height={60} />
            <YAxis allowDecimals={false} {...AXIS} />
            <Tooltip {...TOOLTIP} />
            <Legend wrapperStyle={{ color: "#9aa4b2" }} />
            <Bar dataKey="approved_intake" name="Approved intake" fill="#5b8def" radius={[4, 4, 0, 0]} />
            <Bar dataKey="enrolled" name="Enrolled" fill="#3ecf8e" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>
        <IssuesChart data={overview.issues_by_type} />
        <CategoryChart data={overview.by_category} />
        <SpecialCategoriesChart totals={t} />
      </div>
      <div className="card">
        <h3>Institutions at a glance</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Institution</th><th>AICTE ID</th><th>State</th><th>Approved intake</th><th>Enrolled</th><th>Utilisation</th><th>Problems</th></tr></thead>
            <tbody>
              {overview.rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.name}</td><td className="mono">{r.aicte_id}</td><td>{r.state}</td>
                  <td>{r.approved_intake}</td><td>{r.enrolled}</td>
                  <td>{r.approved_intake ? `${Math.round((r.enrolled / r.approved_intake) * 100)}%` : "-"}</td>
                  <td>{r.issues ? <span className="badge high">{r.issues}</span> : <span className="badge ok">0</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

const NEW_INSTITUTION = { name: "", aicte_id: "", state: "", city: "", login_email: "", login_password: "" };

function InstitutionsManager({ onChange }) {
  const [list, setList] = useState([]);
  const [form, setForm] = useState(NEW_INSTITUTION);
  const [msg, setMsg] = useState(null);
  const load = useCallback(() => { api("/api/admin/institutions").then(setList).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function add(e) {
    e.preventDefault();
    try {
      await api("/api/admin/institutions", { method: "POST", json: form });
      setMsg({ type: "success", text: `${form.name} added. They can now log in with ${form.login_email}.` });
      setForm(NEW_INSTITUTION);
      load();
      onChange();
    } catch (err) {
      setMsg({ type: "error", text: err.message });
    }
  }

  return (
    <div className="grid2 wide-right">
      <div className="card">
        <h3>Add AICTE-approved institution</h3>
        <form onSubmit={add}>
          <label>Institution name</label><input value={form.name} onChange={set("name")} required minLength={3} />
          <label>AICTE permanent ID</label><input value={form.aicte_id} onChange={set("aicte_id")} required minLength={3} />
          <div className="grid2 tight">
            <div><label>State</label><input value={form.state} onChange={set("state")} required /></div>
            <div><label>City</label><input value={form.city} onChange={set("city")} required /></div>
          </div>
          <label>Login email for the institution</label><input type="email" value={form.login_email} onChange={set("login_email")} required />
          <label>Login password</label><input type="password" value={form.login_password} onChange={set("login_password")} required minLength={6} />
          <button type="submit" className="mt">Add institution</button>
        </form>
        <Message msg={msg} />
      </div>
      <div className="card">
        <h3>Registered institutions ({list.length})</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>AICTE ID</th><th>Location</th><th>Login</th></tr></thead>
            <tbody>
              {list.map((i) => (
                <tr key={i.id}><td>{i.name}</td><td className="mono">{i.aicte_id}</td><td>{i.city}, {i.state}</td><td>{i.login_email}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StudentSearch() {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");

  async function run(e) {
    e.preventDefault();
    try {
      setResults(await api(`/api/admin/students?search=${encodeURIComponent(search)}`));
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="card">
      <h3>Search students across all institutions</h3>
      <form onSubmit={run} className="row">
        <input placeholder="APAAR ID or name" value={search} onChange={(e) => setSearch(e.target.value)} style={{ flex: 1 }} />
        <button type="submit">Search</button>
      </form>
      {error && <div className="msg error">{error}</div>}
      {results && <StudentsTable students={results} showInstitution />}
    </div>
  );
}

function flags(s) {
  return [s.is_nri && "NRI", s.is_oci && "OCI", s.is_foreign_national && "FN", s.seat_type === "Supernumerary" && "Supernumerary"]
    .filter(Boolean).join(", ") || "-";
}

function StudentsTable({ students, showInstitution, onEdit, onDelete }) {
  if (students.length === 0) return <p className="muted mt">No students found.</p>;
  return (
    <div className="table-wrap mt">
      <table>
        <thead>
          <tr>
            <th>APAAR ID</th><th>Name</th>{showInstitution && <th>Institution</th>}<th>Program</th><th>Year</th>
            <th>Category</th><th>Special</th><th>Nationality</th><th>Source</th>{onEdit && <th />}
          </tr>
        </thead>
        <tbody>
          {students.map((s) => (
            <tr key={s.id}>
              <td className="mono">{s.apaar_id}</td><td>{s.full_name}</td>
              {showInstitution && <td>{s.institution}</td>}
              <td>{s.program}</td><td>{s.year_of_study}</td><td>{s.admission_category}</td>
              <td>{flags(s)}</td><td>{s.nationality}</td><td><span className="badge neutral">{s.source}</span></td>
              {onEdit && (
                <td className="nowrap">
                  <button className="small secondary" onClick={() => onEdit(s)}>Edit</button>{" "}
                  <button className="small danger" onClick={() => onDelete(s)}>Delete</button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// 5. INSTITUTION SCREENS
// =============================================================================
function InstitutionScreen({ user }) {
  const [tab, setTab] = useState("dashboard");
  const [overview, setOverview] = useState(null);
  const [issues, setIssues] = useState([]);
  const [programs, setPrograms] = useState([]);

  const reload = useCallback(() => {
    api("/api/institution/overview").then(setOverview).catch(() => {});
    api("/api/institution/issues").then(setIssues).catch(() => {});
    api("/api/programs").then(setPrograms).catch(() => {});
  }, []);
  useEffect(() => { reload(); }, [reload]);

  return (
    <>
      <h2>{user.institution.name} <span className="muted small-text">AICTE ID {user.institution.aicte_id}</span></h2>
      <Tabs active={tab} onChange={setTab} tabs={[
        ["dashboard", "Dashboard"], ["programs", "Programs & intake"], ["students", "Students"],
        ["upload", "Upload Excel/CSV"], ["issues", `Problems (${issues.length})`], ["api", "API access"],
      ]} />
      {tab === "dashboard" && <InstitutionDashboard overview={overview} />}
      {tab === "programs" && <ProgramsManager programs={programs} onChange={reload} />}
      {tab === "students" && <StudentsManager programs={programs} onChange={reload} />}
      {tab === "upload" && <UploadPanel onChange={reload} />}
      {tab === "issues" && <IssuesTable issues={issues} />}
      {tab === "api" && <ApiAccess />}
    </>
  );
}

function InstitutionDashboard({ overview }) {
  if (!overview) return <p className="muted">Loading…</p>;
  const t = overview.totals;
  const rows = overview.rows.map((r) => ({ ...r, short: shortName(r.name) }));
  return (
    <>
      <Tiles items={[
        ["Programs", t.programs], ["Approved intake", t.approved_intake], ["Students enrolled", t.enrolled],
        ["Supernumerary used / seats", `${t.enrolled_supernumerary} / ${t.supernumerary_seats}`],
        ["NRI · OCI · Foreign", `${t.nri} · ${t.oci} · ${t.foreign_nationals}`],
        ["Problems to fix", t.issues, t.issues ? "bad" : "good"],
        ["Rows rejected (bad APAAR)", `${t.rows_rejected} (${t.rows_rejected_apaar})`, t.rows_rejected ? "warn" : ""],
      ]} />
      <div className="grid2">
        <ChartCard title="Approved intake vs regular admissions, by program">
          <BarChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2c3646" />
            <XAxis dataKey="short" {...AXIS} interval={0} angle={-15} textAnchor="end" height={60} />
            <YAxis allowDecimals={false} {...AXIS} />
            <Tooltip {...TOOLTIP} />
            <Legend wrapperStyle={{ color: "#9aa4b2" }} />
            <Bar dataKey="approved_intake" name="Approved intake" fill="#5b8def" radius={[4, 4, 0, 0]} />
            <Bar dataKey="enrolled_regular" name="Regular admissions" fill="#3ecf8e" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>
        {overview.issues_by_type.length > 0
          ? <IssuesChart data={overview.issues_by_type} />
          : <div className="card"><h3>Problems found, by type</h3><p className="muted">No problems. 🎉</p></div>}
        <CategoryChart data={overview.by_category} />
        <SpecialCategoriesChart totals={t} />
      </div>
    </>
  );
}

const NEW_PROGRAM = { name: "", level: "UG", academic_year: "2025-26", approved_intake: 60, supernumerary_seats: 0 };

function ProgramsManager({ programs, onChange }) {
  const [form, setForm] = useState(NEW_PROGRAM);
  const [editingId, setEditingId] = useState(null);
  const [msg, setMsg] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function save(e) {
    e.preventDefault();
    const json = { ...form, approved_intake: Number(form.approved_intake), supernumerary_seats: Number(form.supernumerary_seats) };
    try {
      if (editingId) await api(`/api/programs/${editingId}`, { method: "PUT", json });
      else await api("/api/programs", { method: "POST", json });
      setMsg({ type: "success", text: editingId ? "Program updated." : "Program added." });
      setForm(NEW_PROGRAM);
      setEditingId(null);
      onChange();
    } catch (err) {
      setMsg({ type: "error", text: err.message });
    }
  }

  async function remove(p) {
    if (!window.confirm(`Delete ${p.name} (${p.academic_year})?`)) return;
    try {
      await api(`/api/programs/${p.id}`, { method: "DELETE" });
      onChange();
    } catch (err) {
      setMsg({ type: "error", text: err.message });
    }
  }

  return (
    <div className="grid2 wide-right">
      <div className="card">
        <h3>{editingId ? "Edit program" : "Add program"}</h3>
        <form onSubmit={save}>
          <label>Program name</label><input value={form.name} onChange={set("name")} required placeholder="e.g. B.Tech Computer Science" />
          <div className="grid2 tight">
            <div>
              <label>Level</label>
              <select value={form.level} onChange={set("level")}>
                <option>UG</option><option>PG</option><option>Diploma</option>
              </select>
            </div>
            <div><label>Academic year</label><input value={form.academic_year} onChange={set("academic_year")} required pattern="\d{4}-\d{2}" title="Like 2025-26" /></div>
            <div><label>Approved intake</label><input type="number" min={1} value={form.approved_intake} onChange={set("approved_intake")} required /></div>
            <div><label>Supernumerary seats</label><input type="number" min={0} value={form.supernumerary_seats} onChange={set("supernumerary_seats")} required /></div>
          </div>
          <div className="row mt">
            <button type="submit">{editingId ? "Save changes" : "Add program"}</button>
            {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm(NEW_PROGRAM); }}>Cancel</button>}
          </div>
        </form>
        <Message msg={msg} />
      </div>
      <div className="card">
        <h3>Your programs ({programs.length})</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Program</th><th>Level</th><th>Year</th><th>Approved intake</th><th>Supernumerary</th><th /></tr></thead>
            <tbody>
              {programs.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td><td>{p.level}</td><td>{p.academic_year}</td><td>{p.approved_intake}</td><td>{p.supernumerary_seats}</td>
                  <td className="nowrap">
                    <button className="small secondary" onClick={() => { setEditingId(p.id); setForm({ ...p }); }}>Edit</button>{" "}
                    <button className="small danger" onClick={() => remove(p)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const NEW_STUDENT = {
  apaar_id: "", full_name: "", gender: "Female", date_of_birth: "", program_id: "", year_of_study: 1,
  admission_category: "General", seat_type: "Regular", is_nri: false, is_oci: false, is_foreign_national: false,
  nationality: "Indian", email: "", mobile: "",
};

function StudentsManager({ programs, onChange }) {
  const [students, setStudents] = useState([]);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState(NEW_STUDENT);
  const [editingId, setEditingId] = useState(null);
  const [msg, setMsg] = useState(null);
  const [warnings, setWarnings] = useState([]);

  const load = useCallback(() => {
    api(`/api/students?search=${encodeURIComponent(search)}`).then(setStudents).catch(() => {});
  }, [search]);
  useEffect(() => { load(); }, [load]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  async function save(e) {
    e.preventDefault();
    const json = { ...form, program_id: Number(form.program_id), year_of_study: Number(form.year_of_study) };
    try {
      const res = editingId
        ? await api(`/api/students/${editingId}`, { method: "PUT", json })
        : await api("/api/students", { method: "POST", json });
      setMsg({ type: "success", text: `${res.student.full_name} ${editingId ? "updated" : "added"}.` });
      setWarnings(res.warnings);
      setForm(NEW_STUDENT);
      setEditingId(null);
      load();
      onChange();
    } catch (err) {
      setMsg({ type: "error", text: err.message });
      setWarnings([]);
    }
  }

  function edit(s) {
    setEditingId(s.id);
    setForm({ ...NEW_STUDENT, ...s, email: s.email || "", mobile: s.mobile || "" });
    setMsg(null);
    setWarnings([]);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function remove(s) {
    if (!window.confirm(`Delete ${s.full_name} (${s.apaar_id})?`)) return;
    try {
      await api(`/api/students/${s.id}`, { method: "DELETE" });
      load();
      onChange();
    } catch (err) {
      setMsg({ type: "error", text: err.message });
    }
  }

  return (
    <>
      <div className="card">
        <h3>{editingId ? "Edit student" : "Add one student"}</h3>
        {programs.length === 0 && <div className="msg warn">Add a program first (Programs & intake tab).</div>}
        <form onSubmit={save}>
          <div className="grid3">
            <div><label>APAAR ID</label><input value={form.apaar_id} onChange={set("apaar_id")} required placeholder="12 digits" inputMode="numeric" /></div>
            <div><label>Full name</label><input value={form.full_name} onChange={set("full_name")} required minLength={2} /></div>
            <div>
              <label>Gender</label>
              <select value={form.gender} onChange={set("gender")}><option>Female</option><option>Male</option><option>Other</option></select>
            </div>
            <div><label>Date of birth</label><input type="date" value={form.date_of_birth} onChange={set("date_of_birth")} required /></div>
            <div>
              <label>Program</label>
              <select value={form.program_id} onChange={set("program_id")} required>
                <option value="">Select program</option>
                {programs.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.academic_year})</option>)}
              </select>
            </div>
            <div><label>Year of study</label><input type="number" min={1} max={6} value={form.year_of_study} onChange={set("year_of_study")} required /></div>
            <div>
              <label>Admission category</label>
              <select value={form.admission_category} onChange={set("admission_category")}>
                <option>General</option><option>OBC</option><option>SC</option><option>ST</option><option>EWS</option>
              </select>
            </div>
            <div>
              <label>Seat type</label>
              <select value={form.seat_type} onChange={set("seat_type")}><option>Regular</option><option>Supernumerary</option></select>
            </div>
            <div><label>Nationality</label><input value={form.nationality} onChange={set("nationality")} required /></div>
            <div><label>Email (optional)</label><input type="email" value={form.email} onChange={set("email")} /></div>
            <div><label>Mobile (optional)</label><input value={form.mobile} onChange={set("mobile")} placeholder="10 digits" inputMode="numeric" /></div>
            <div className="checks">
              <label className="check"><input type="checkbox" checked={form.is_nri} onChange={set("is_nri")} /> NRI</label>
              <label className="check"><input type="checkbox" checked={form.is_oci} onChange={set("is_oci")} /> OCI</label>
              <label className="check"><input type="checkbox" checked={form.is_foreign_national} onChange={set("is_foreign_national")} /> Foreign National</label>
            </div>
          </div>
          <div className="row mt">
            <button type="submit" disabled={programs.length === 0}>{editingId ? "Save changes" : "Add student"}</button>
            {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm(NEW_STUDENT); }}>Cancel</button>}
          </div>
        </form>
        <Message msg={msg} />
        {warnings.length > 0 && (
          <div className="msg warn">
            <strong>Saved, but please check:</strong>
            <ul>{warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          </div>
        )}
      </div>

      <div className="card">
        <div className="row space">
          <h3>Your students ({students.length})</h3>
          <input placeholder="Search APAAR ID or name" value={search} onChange={(e) => setSearch(e.target.value)} style={{ maxWidth: 300 }} />
        </div>
        <StudentsTable students={students} onEdit={edit} onDelete={remove} />
      </div>
    </>
  );
}

function UploadPanel({ onChange }) {
  const [file, setFile] = useState(null);
  const [report, setReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadHistory = useCallback(() => { api("/api/students/uploads").then(setHistory).catch(() => {}); }, []);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  async function upload(e) {
    e.preventDefault();
    if (!file) return;
    const formEl = e.currentTarget;
    const data = new FormData();
    data.append("file", file);
    setBusy(true);
    setMsg(null);
    try {
      setReport(await api("/api/students/upload", { method: "POST", form: data }));
      setFile(null);
      formEl.reset();
      loadHistory();
      onChange();
    } catch (err) {
      setMsg({ type: "error", text: err.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="card">
        <h3>Upload many students at once</h3>
        <ol className="steps">
          <li>Download the template and fill one student per row (keep the column names).</li>
          <li>The program name and academic year must match a program you added.</li>
          <li>Save it as Excel (.xlsx) or CSV, then upload it here.</li>
        </ol>
        <a className="btn secondary" href={`${API_URL}/api/students/template.csv`}>Download template</a>
        <form onSubmit={upload} className="row mt">
          <input type="file" accept=".xlsx,.csv" onChange={(e) => setFile(e.target.files[0])} required style={{ maxWidth: 360 }} />
          <button type="submit" disabled={busy}>{busy ? "Checking…" : "Upload & check"}</button>
        </form>
        <Message msg={msg} />
      </div>

      {report && (
        <div className="card">
          <h3>Result: {report.filename}</h3>
          <Tiles items={[
            ["Rows in file", report.total_rows], ["New students", report.created, "good"], ["Updated", report.updated],
            ["Rejected rows", report.failed, report.failed ? "bad" : "good"], ["Problems now flagged", report.issues_now, report.issues_now ? "warn" : ""],
          ]} />
          {report.errors.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Row</th><th>APAAR ID</th><th>Why it was rejected</th></tr></thead>
                <tbody>
                  {report.errors.map((e) => (
                    <tr key={e.row}><td>{e.row}</td><td className="mono">{e.apaar_id}</td><td>{e.errors.join("; ")}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h3>Upload history</h3>
        {history.length === 0 ? <p className="muted">No uploads yet.</p> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>File</th><th>When</th><th>Rows</th><th>New</th><th>Updated</th><th>Rejected</th></tr></thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id}>
                    <td>{h.filename}</td><td>{new Date(h.uploaded_at).toLocaleString()}</td>
                    <td>{h.total_rows}</td><td>{h.created}</td><td>{h.updated}</td><td>{h.failed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function ApiAccess() {
  const [key, setKey] = useState("");
  const [show, setShow] = useState(false);
  const [msg, setMsg] = useState(null);
  useEffect(() => { api("/api/institution/api-key").then((d) => setKey(d.api_key)).catch(() => {}); }, []);

  async function regenerate() {
    if (!window.confirm("Make a new key? Software using the old key will stop working.")) return;
    try {
      setKey((await api("/api/institution/api-key", { method: "POST" })).api_key);
      setShow(true);
      setMsg({ type: "success", text: "New key created. Update it in your software." });
    } catch (err) {
      setMsg({ type: "error", text: err.message });
    }
  }

  return (
    <div className="card">
      <h3>API access for your own software (ERP)</h3>
      <p className="muted">
        If your institution already manages students in its own software, that software can send data to
        Eduvaris automatically, with no manual uploads. It uses this secret key.
      </p>
      <label>Your API key</label>
      <div className="row">
        <input readOnly className="mono" value={show ? key : key.replace(/./g, "•")} style={{ flex: 1 }} />
        <button type="button" className="secondary" onClick={() => setShow(!show)}>{show ? "Hide" : "Show"}</button>
        <button type="button" className="danger" onClick={regenerate}>Regenerate</button>
      </div>
      <Message msg={msg} />
      <label className="mt">Example: add a student from any program</label>
      <pre className="code">{`POST ${API_URL}/api/students
X-API-Key: <your key>
Content-Type: application/json

{
  "apaar_id": "123456789012", "full_name": "Priya Sharma", "gender": "Female",
  "date_of_birth": "2005-08-21", "program_id": 1, "year_of_study": 1,
  "admission_category": "General", "seat_type": "Regular", "nationality": "Indian"
}`}</pre>
      <p className="muted">Full list of endpoints: <a href={`${API_URL}/docs`} target="_blank" rel="noreferrer">{API_URL}/docs</a></p>
    </div>
  );
}

// =============================================================================
// 6. APP: loads the logged-in user and shows the right screen
// =============================================================================
export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api("/api/auth/me"));
    } catch {
      localStorage.removeItem(TOKEN_KEY); // expired or invalid login
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { loadUser(); }, [loadUser]);

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }

  let screen;
  if (loading) screen = <p className="muted">Loading…</p>;
  else if (!user) screen = <HomeScreen onLoggedIn={loadUser} />;
  else if (user.role === "aicte_admin") screen = <AdminScreen />;
  else screen = <InstitutionScreen user={user} />;

  return (
    <>
      <style>{STYLES}</style>
      <header className="topbar">
        <div className="brand"><span className="logo">E</span> Eduvaris</div>
        {user && (
          <div className="row">
            <span className="muted">{user.full_name} · {user.role === "aicte_admin" ? "AICTE Admin" : "Institution"}</span>
            <button className="small secondary" onClick={logout}>Log out</button>
          </div>
        )}
      </header>
      <main className="container">{screen}</main>
    </>
  );
}

// =============================================================================
// 7. STYLES (dark theme)
// =============================================================================
const STYLES = `
:root {
  --bg: #0f141c; --card: #161d28; --card2: #1c2533; --border: #2c3646; --text: #e6e9ef; --muted: #9aa4b2;
  --primary: #5b8def; --primary-dark: #4473d6; --ok: #3ecf8e; --warn: #f5a524; --bad: #f2555a;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; overflow-x: hidden; }
a { color: var(--primary); }
.topbar { position: sticky; top: 0; z-index: 10; display: flex; justify-content: space-between; align-items: center; gap: 16px;
  padding: 12px 24px; background: rgba(15,20,28,0.92); border-bottom: 1px solid var(--border); backdrop-filter: blur(6px); }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.15rem; }
.logo { display: inline-grid; place-items: center; width: 30px; height: 30px; border-radius: 8px; background: var(--primary); color: #fff; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px 16px 60px; }
h2 { font-size: 1.5rem; margin: 0 0 16px; }
h3 { font-size: 1.05rem; margin: 0 0 12px; }
.small-text { font-size: 0.9rem; font-weight: 400; }
.hero { padding: 28px 0 20px; }
.hero h1 { font-size: 2.4rem; margin: 0 0 10px; }
.hero p { color: var(--muted); max-width: 760px; line-height: 1.6; margin: 0 0 20px; }
.features { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.features div { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px; display: grid; gap: 4px; }
.features span { color: var(--muted); font-size: 0.9rem; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; min-width: 0; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 0 20px; }
.grid2.wide-right { grid-template-columns: minmax(300px, 1fr) minmax(340px, 2fr); }
.grid2.tight { grid-template-columns: 1fr 1fr; gap: 0 12px; }
.grid3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0 16px; }
@media (max-width: 760px) { .grid2.wide-right { grid-template-columns: 1fr; } }
label { display: block; font-size: 0.85rem; font-weight: 600; color: var(--muted); margin: 12px 0 5px; }
input, select { width: 100%; padding: 9px 11px; background: var(--card2); color: var(--text); border: 1px solid var(--border);
  border-radius: 8px; font: inherit; }
input:focus, select:focus { outline: 2px solid var(--primary); outline-offset: -1px; }
input[type="checkbox"] { width: auto; margin: 0 6px 0 0; accent-color: var(--primary); }
input[type="file"] { padding: 6px; }
.checks { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; padding-bottom: 8px; }
.check { display: flex; align-items: center; margin: 0; color: var(--text); font-weight: 500; }
button, .btn { display: inline-block; padding: 9px 16px; border: 0; border-radius: 8px; cursor: pointer; background: var(--primary);
  color: #fff; font: inherit; font-weight: 600; text-decoration: none; }
button:hover, .btn:hover { background: var(--primary-dark); }
button:disabled { opacity: 0.55; cursor: not-allowed; }
button.secondary, .btn.secondary { background: var(--card2); color: var(--text); border: 1px solid var(--border); }
button.secondary:hover, .btn.secondary:hover { background: #253043; }
button.danger { background: transparent; color: var(--bad); border: 1px solid #5a2a2e; }
button.danger:hover { background: #2a1517; }
button.small { padding: 5px 10px; font-size: 0.85rem; }
.mt { margin-top: 14px; }
.row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.row.space { justify-content: space-between; margin-bottom: 8px; }
.row.space h3 { margin: 0; }
.muted { color: var(--muted); font-size: 0.9rem; }
.mono { font-family: ui-monospace, Consolas, monospace; }
.nowrap { white-space: nowrap; }
.tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 20px; border-bottom: 1px solid var(--border); }
.tab { background: transparent; color: var(--muted); border-radius: 8px 8px 0 0; border-bottom: 2px solid transparent; }
.tab:hover { background: var(--card); color: var(--text); }
.tab.active { color: var(--text); border-bottom-color: var(--primary); background: var(--card); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
.tile { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; }
.tile-value { font-size: 1.6rem; font-weight: 700; }
.tile-label { color: var(--muted); font-size: 0.82rem; margin-top: 4px; }
.tile.good .tile-value { color: var(--ok); }
.tile.warn .tile-value { color: var(--warn); }
.tile.bad .tile-value { color: var(--bad); }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th { text-align: left; color: var(--muted); font-weight: 600; padding: 9px 8px; border-bottom: 1px solid var(--border); white-space: nowrap; }
td { padding: 9px 8px; border-bottom: 1px solid #222b38; vertical-align: top; }
tbody tr:hover { background: rgba(255,255,255,0.02); }
.badge { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
.badge.high { background: rgba(242,85,90,0.15); color: var(--bad); }
.badge.medium { background: rgba(245,165,36,0.15); color: var(--warn); }
.badge.ok { background: rgba(62,207,142,0.15); color: var(--ok); }
.badge.neutral { background: var(--card2); color: var(--muted); }
.msg { margin-top: 12px; padding: 10px 12px; border-radius: 8px; font-size: 0.9rem; }
.msg.error { background: rgba(242,85,90,0.12); color: #ff9a9d; border: 1px solid #5a2a2e; }
.msg.success { background: rgba(62,207,142,0.12); color: #7ee2b3; border: 1px solid #1f5a40; }
.msg.warn { background: rgba(245,165,36,0.12); color: #f8c46b; border: 1px solid #5c4314; }
.msg ul { margin: 6px 0 0; padding-left: 20px; }
.verify-result { margin-top: 14px; display: grid; gap: 6px; }
.steps { color: var(--muted); line-height: 1.7; padding-left: 20px; margin: 0 0 14px; }
.code { background: #0b1018; border: 1px solid var(--border); border-radius: 8px; padding: 12px; overflow-x: auto; font-size: 0.85rem; color: #c9d4e3; }
`;
