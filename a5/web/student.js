// Talaba sahifasi: server holatini har 2 soniyada oladi va faqat o'zgargan qismlarni qayta chizadi.
let META = {amis: {}, types: {}};
let TOKEN = null, openName = null, cache = {}, toastT;
let doneSeen = null, lastScore = null, seenIds = null, seenItems = new Set(), seenLog = null, lastIp = {};
try { TOKEN = localStorage.getItem("a5_token"); } catch (e) {}

const BUSY = ["pending", "stopping", "rebooting", "shutting-down", "CREATING", "DELETING"];
const SEC = {ec2: ["server", "1-qism · EC2 virtual mashina"], ddb: ["db", "2-qism · DynamoDB jadvallar"], fin: ["check", "Yakun"]};
const rich = (t) => t.split("**").map((p, i) => i % 2 ? h("b", null, p) : p);
const badge = (st) => h("span", {class: "badge " + st + (BUSY.includes(st) ? " busy" : "")}, st);
const empty = (ic, text) => h("div", {class: "empty"}, icon(ic), text);

function changed(k, v) { const s = JSON.stringify(v); if (cache[k] === s) return false; cache[k] = s; return true; }
function toast(msg, ok) {
  const t = $("toast");
  t.replaceChildren(icon(ok ? "check" : "info"), msg);
  t.className = "show " + (ok ? "ok" : "bad");
  clearTimeout(toastT); toastT = setTimeout(() => t.className = "", 3500);
}
async function api(path, body) {
  try {
    const r = await fetch(path, body ? {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {cache: "no-store"});
    const j = await r.json();
    if (r.status === 401) logout();
    return j;
  } catch (e) { return {ok: false, msg: "Server bilan aloqa yo'q"}; }
}
async function act(op, args, btn) {
  if (btn) btn.disabled = true;
  const j = await api("/api/do", Object.assign({token: TOKEN, op}, args || {}));
  if (btn) btn.disabled = false;
  toast(j.msg || "Xato", j.ok);
  if (j.state) render(j.state);
  return j;
}
function logout() {
  TOKEN = null; try { localStorage.removeItem("a5_token"); } catch (e) {}
  $("app").hidden = true; $("login").hidden = false;
}
async function refresh() {
  if (!TOKEN) return;
  const j = await api("/api/state?token=" + encodeURIComponent(TOKEN));
  if (j.ok) { $("login").hidden = true; $("app").hidden = false; render(j.state); }
}

// ---------------------------------------------------------------- umumiy chizish
function render(st) {
  $("who").textContent = st.name + (st.group ? " · " + st.group : "");
  $("score").textContent = st.score; $("total").textContent = st.total;
  $("bar").style.width = (100 * st.score / st.total) + "%";
  if (lastScore !== null && st.score > lastScore) bump($("scorebox"));
  lastScore = st.score;

  const fresh = [];
  for (const t of st.tasks) if (t.state === "done" && doneSeen && !doneSeen.includes(t.id)) fresh.push(t.id);
  if (fresh.length) toast("Bajarildi: " + st.tasks.find(t => t.id === fresh[0]).title + " (+10 ball)", true);
  doneSeen = st.tasks.filter(t => t.state === "done").map(t => t.id);

  if (changed("tasks", st.tasks)) renderTasks(st, fresh);
  if (changed("inst", st.instances)) renderInstances(st.instances);
  if (changed("tables", [openName, st.tables.map(t => [t.name, t.status, t.pk, t.sk, t.items.length])])) renderTables(st.tables);
  renderOpen(st);
  if (changed("log", st.log)) renderLog(st.log);
}
function bump(el) { el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump"); }

function renderTasks(st, fresh) {
  const box = $("tasks"); box.replaceChildren();
  if (st.score === st.total) box.append(h("div", {class: "finish"}, icon("trophy"), "Tabriklaymiz! Hamma topshiriqlar bajarildi."));
  let sec = null;
  st.tasks.forEach((t, n) => {
    if (t.sec !== sec) { sec = t.sec; box.append(h("div", {class: "sec"}, icon(SEC[sec][0]), SEC[sec][1])); }
    const num = t.state === "done" ? icon("check") : t.state === "locked" ? icon("lock") : n + 1;
    box.append(h("div", {class: "task " + t.state + (fresh.includes(t.id) ? " pop" : "")},
      h("div", {class: "num"}, num),
      h("div", null, h("div", {class: "tt"}, t.title), h("div", {class: "tx"}, rich(t.text)))));
  });
}

// ---------------------------------------------------------------- EC2
const FLOW = [["pending", "running", "stopping", "stopped"], ["running", "rebooting", "running"], ["shutting-down", "terminated"]];
function renderFlow(list) {
  const alive = list.filter(i => i.state !== "terminated");
  const cur = (alive.filter(i => i.name === "web-server").pop() || alive.pop() || list[list.length - 1] || {}).state;
  const box = $("flow"); box.replaceChildren(h("b", null, "Hayot sikli:"));
  FLOW.forEach((row, r) => {
    if (r) box.append(h("span", null, " · "));
    row.forEach((s, n) => { if (n) box.append("→"); box.append(h("span", {class: "st" + (s === cur ? " on" : "")}, s)); });
  });
}

function renderInstances(list) {
  renderFlow(list);
  const box = $("instances");
  if (!list.length) { seenIds = new Set(); return box.replaceChildren(empty("server", "Hozircha namuna yo'q. Yuqoridagi shakl orqali birinchi virtual mashinani ishga tushiring.")); }
  const btn = (i, ic, label, op, cls, ask) => h("button", {class: "btn sm " + (cls || ""), onclick: (e) => {
    if (ask && !confirm(ask)) return; act(op, {id: i.id}, e.currentTarget); }}, icon(ic), label);

  const cards = list.slice().reverse().map(i => {
    const busy = BUSY.includes(i.state);
    const acts = h("div", {class: "acts"});
    const kill = btn(i, "trash", "O'chirish", "ec2.terminate", "danger", "«" + i.name + "» butunlay o'chiriladi (terminate). Davom etasizmi?");
    if (i.state === "running") acts.append(btn(i, "stop", "To'xtatish", "ec2.stop"), btn(i, "reboot", "Qayta yuklash", "ec2.reboot"), kill);
    else if (i.state === "stopped") {
      const sel = h("select", {class: "sm", "aria-label": "Yangi tur"}, Object.keys(META.types).map(k => h("option", {value: k}, k)));
      sel.value = i.type;
      acts.append(btn(i, "play", "Ishga tushirish", "ec2.start", "primary"), sel,
        h("button", {class: "btn sm", onclick: (e) => act("ec2.modify", {id: i.id, type: sel.value}, e.currentTarget)}, icon("cpu"), "Turini o'zgartirish"), kill);
    } else acts.append(h("span", {class: "muted small"}, i.state === "terminated" ? "Namuna o'chirilgan" : "Kuting, holat o'zgarmoqda…"));

    const ipChanged = i.public_ip && lastIp[i.id] !== undefined && lastIp[i.id] !== i.public_ip;
    lastIp[i.id] = i.public_ip;
    const fact = (ic, label, value, cls) => h("div", {class: "fact"}, h("span", null, icon(ic), label), h("b", {class: cls || ""}, value));
    return h("div", {class: "res s-" + i.state + (busy ? " busy" : "") + (i.state === "terminated" ? " dead" : "") + (seenIds && !seenIds.has(i.id) ? " new" : "")},
      h("div", {class: "head"},
        h("div", {class: "avatar"}, icon("server")),
        h("div", {class: "grow"}, h("div", {class: "name"}, i.name), h("div", {class: "muted mono small"}, i.id)),
        badge(i.state)),
      h("div", {class: "facts"},
        fact("cpu", i.type, META.types[i.type]),
        fact("globe", "Public IP", i.public_ip || "—", "mono" + (ipChanged ? " flash" : "")),
        fact("home", "Private IP", i.private_ip, "mono")),
      h("div", {class: "muted small"}, "AMI: " + i.ami_name + " (" + i.ami + ")"),
      acts);
  });
  seenIds = new Set(list.map(i => i.id));
  box.replaceChildren(h("div", {class: "cards"}, cards));
}

// ---------------------------------------------------------------- DynamoDB
const typeName = (t) => t === "N" ? "Number" : "String";
const keyChips = (t) => h("div", {class: "acts"},
  h("span", {class: "chip"}, icon("key"), "PK: " + t.pk + " (" + typeName(t.pkt) + ")"),
  t.sk ? h("span", {class: "chip"}, icon("key"), "SK: " + t.sk + " (" + typeName(t.skt) + ")") : null);

let seenTables = null;
function renderTables(list) {
  const box = $("tables");
  if (!list.length) { seenTables = new Set(); return box.replaceChildren(empty("db", "Hozircha jadval yo'q. Yuqorida birinchi jadvalni yarating.")); }
  const cards = list.map(t => h("div", {class: "res s-" + t.status + (BUSY.includes(t.status) ? " busy" : "") + (t.name === openName ? " open" : "") + (seenTables && !seenTables.has(t.name) ? " new" : "")},
    h("div", {class: "head"},
      h("div", {class: "avatar"}, icon("db")),
      h("div", {class: "grow"}, h("div", {class: "name"}, t.name), h("div", {class: "muted small"}, t.items.length + " ta element")),
      badge(t.status)),
    keyChips(t),
    h("div", {class: "acts"},
      t.status === "ACTIVE" ? h("button", {class: "btn sm primary", onclick: (e) => openTable(t.name, e.currentTarget)}, icon("open"), "Ochish") : null,
      t.status !== "DELETING" ? h("button", {class: "btn sm danger", onclick: (e) => {
        if (confirm("«" + t.name + "» jadvali va undagi hamma elementlar o'chiriladi. Davom etasizmi?")) act("ddb.delete_table", {table: t.name}, e.currentTarget);
      }}, icon("trash"), "O'chirish") : h("span", {class: "muted small"}, "O'chirilmoqda…"))));
  seenTables = new Set(list.map(t => t.name));
  box.replaceChildren(h("div", {class: "cards"}, cards));
}

async function openTable(name, btn) {
  openName = name; delete cache.schema; delete cache.items; delete cache.tables;
  await act("ddb.scan", {table: name}, btn);
  $("tview").scrollIntoView({behavior: "smooth", block: "start"});
}

function keyInputs(t) {
  const inputs = {}, labels = [];
  for (const [a, ty, role] of [[t.pk, t.pkt, "partition key"], [t.sk, t.skt, "sort key"]]) if (a) {
    inputs[a] = h("input", {maxlength: "200", placeholder: ty === "N" ? "raqam" : "matn"});
    labels.push(h("label", null, "🔑 " + a + " — " + role + " (" + typeName(ty) + ")", inputs[a]));
  }
  return [labels, inputs];
}
const vals = (inputs) => Object.fromEntries(Object.entries(inputs).map(([k, v]) => [k, v.value]));
const ddbJson = (item) => JSON.stringify(Object.fromEntries(Object.entries(item).map(([k, [t, v]]) => [k, {[t]: v}])), null, 2);

function renderOpen(st) {
  const t = st.tables.find(x => x.name === openName && x.status === "ACTIVE");
  if (!t) { $("tview").hidden = true; delete cache.schema; delete cache.items; return; }
  $("tview").hidden = false;
  if (changed("schema", [t.name, t.pk, t.pkt, t.sk, t.skt])) buildView(t);
  if (changed("items", [t.name, t.items])) renderItems(t);
}

function buildView(t) {
  $("tvtitle").textContent = "Jadval: " + t.name;
  $("tvkeys").replaceChildren(keyChips(t));
  seenItems = null;
  const [pl, pin] = keyInputs(t);
  const extra = h("textarea", {rows: "3", placeholder: "ism = Ali Valiyev\nguruh = 101"});
  $("tvput").replaceChildren(...pl,
    h("label", {class: "wide"}, "Boshqa atributlar — har qatorda: nom = qiymat (raqam bo'lsa Number bo'ladi)", extra),
    h("button", {class: "btn primary", onclick: async (e) => {
      const j = await act("ddb.put", {table: t.name, item: vals(pin), extra: extra.value}, e.currentTarget);
      if (j.ok) { Object.values(pin).forEach(i => i.value = ""); extra.value = ""; Object.values(pin)[0].focus(); }
    }}, icon("plus"), "Element qo'shish"));
  const [gl, gin] = keyInputs(t);
  $("tvres").replaceChildren();
  $("tvget").replaceChildren(...gl, h("button", {class: "btn", onclick: async (e) => {
    const j = await act("ddb.get", {table: t.name, key: vals(gin)}, e.currentTarget);
    $("tvres").replaceChildren(j.ok ? (j.item ? h("pre", {class: "new"}, ddbJson(j.item)) : h("p", {class: "muted"}, "Natija: bo'sh (bunday Item yo'q)")) : "");
  }}, icon("search"), "Olish (GetItem)"));
}

function renderItems(t) {
  $("tvcount").textContent = t.items.length + " ta element";
  if (!t.items.length) { seenItems = new Set(); return $("items").replaceChildren(empty("list", "Jadval bo'sh. Yuqorida element qo'shing.")); }
  const keys = [t.pk].concat(t.sk ? [t.sk] : []), cols = keys.slice();
  for (const it of t.items) for (const k of Object.keys(it)) if (!cols.includes(k)) cols.push(k);
  const kid = (it) => keys.map(k => it[k][1]).join("\u0000");
  const rows = t.items.slice().sort((a, b) => kid(a).localeCompare(kid(b), undefined, {numeric: true}));
  $("items").replaceChildren(h("div", {class: "scroll"}, h("table", null,
    h("thead", null, h("tr", null, cols.map(c => h("th", null, (keys.includes(c) ? "🔑 " : "") + c)), h("th", null, ""))),
    h("tbody", null, rows.map(it => h("tr", {class: seenItems && !seenItems.has(kid(it)) ? "new" : ""},
      cols.map(c => h("td", null, it[c] ? (keys.includes(c) ? h("b", null, it[c][1]) : it[c][1]) : h("span", {class: "muted"}, "—"))),
      h("td", null, h("button", {class: "btn sm danger", title: "O'chirish (DeleteItem)", onclick: (e) =>
        act("ddb.delete_item", {table: t.name, key: Object.fromEntries(keys.map(k => [k, it[k][1]]))}, e.currentTarget)}, icon("trash")))))))));
  seenItems = new Set(t.items.map(kid));
}

// ---------------------------------------------------------------- CLI jurnali
function renderLog(log) {
  if (!log.length) { seenLog = 0; return $("log").replaceChildren(empty("terminal", "Har bir amalingizning AWS CLI dagi buyrug'i shu yerda chiqadi.")); }
  const last = log[log.length - 1].t;
  $("log").replaceChildren(...log.slice().reverse().map(e => h("div", {class: "entry" + (seenLog !== null && e.t > seenLog ? " new" : "")},
    h("div", null, h("span", {class: "muted mono small"}, new Date(e.t * 1000).toLocaleTimeString()), "  ", e.msg),
    h("pre", null, "$ " + e.cli))));
  seenLog = last;
}

// ---------------------------------------------------------------- boshlash
async function init() {
  applyIcons();
  try { META = await (await fetch("/api/meta")).json(); } catch (e) {}
  for (const [id, name] of Object.entries(META.amis)) $("iami").append(h("option", {value: id}, name));
  for (const [k, d] of Object.entries(META.types)) $("itype").append(h("option", {value: k}, k + " — " + d + (k === "t2.micro" ? " (Free tier)" : "")));
  $("itype").value = "t2.micro";

  $("launch").onclick = (e) => act("ec2.launch", {name: $("iname").value, ami: $("iami").value, type: $("itype").value}, e.currentTarget);
  $("create").onclick = async (e) => {
    const j = await act("ddb.create", {name: $("tname").value, pk: $("tpk").value, pkt: $("tpkt").value, sk: $("tsk").value, skt: $("tskt").value}, e.currentTarget);
    if (j.ok) for (const id of ["tname", "tpk", "tsk"]) $(id).value = "";
  };
  document.querySelectorAll(".tab").forEach(b => b.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("on", x === b));
    $("tab-ec2").hidden = b.dataset.tab !== "ec2"; $("tab-ddb").hidden = b.dataset.tab !== "ddb";
  });
  $("lform").onsubmit = async (e) => {
    e.preventDefault();
    const j = await api("/api/join", {name: $("lname").value, group: $("lgroup").value});
    if (!j.ok) return $("lerr").textContent = j.msg;
    TOKEN = j.token; try { localStorage.setItem("a5_token", TOKEN); } catch (err) {}
    refresh();
  };
  if (TOKEN) refresh(); else $("login").hidden = false;
  setInterval(refresh, 2000);
}
init();
