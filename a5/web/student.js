// Talaba sahifasi: server holatini har 2 soniyada oladi va faqat o'zgargan qismlarni qayta chizadi.
let META = {amis: {}, types: {}};
let TOKEN = null, openName = null, cache = {}, toastT;
let doneSeen = null, lastScore = null, seenIds = null, seenItems = new Set(), seenLog = null, lastIp = {};
const DEMO = new URLSearchParams(location.search).has("demo"), TKEY = DEMO ? "a5_demo" : "a5_token";
try { TOKEN = localStorage.getItem(TKEY); } catch (e) {}

const BUSY = ["pending", "stopping", "rebooting", "shutting-down", "CREATING", "DELETING"];
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
  lastErr = j.ok ? null : {msg: j.msg || "Xato", op};
  if (j.ok && op === "ddb.get" && !j.item) lastErr = {msg: "Bunday kalitli element jadvalda yo'q. Pastdagi «Elementlar» ro'yxatiga qarang: kalit aynan shunday yozilganmi (masalan T001 — bosh harf T)?", op};
  if (j.state) render(j.state);
  return j;
}
function logout() {
  TOKEN = null; try { localStorage.removeItem(TKEY); } catch (e) {}
  $("app").hidden = true; $("login").hidden = false;
}
async function refresh() {
  if (!TOKEN) return;
  const j = await api("/api/state?token=" + encodeURIComponent(TOKEN));
  if (j.ok) { $("login").hidden = true; $("app").hidden = false; render(j.state); }
}

// ---------------------------------------------------------------- umumiy chizish
let hintFor = null, hintOn = false, lastErr = null;
const SECI = {ec2: "server", ddb: "db", fin: "trophy"};
function showTab(name) {
  document.querySelectorAll(".nav").forEach(x => x.classList.toggle("on", x.dataset.tab === name));
  for (const t of ["ec2", "ddb", "cli"]) $("tab-" + t).hidden = t !== name;
  guide();
}
function render(st) {
  $("who").textContent = st.name;
  $("placeS").textContent = st.place + "-o'rin / " + st.class_n;
  const myTeam = st.teams.find(t => t.id === st.team);
  if (myTeam && changed("teamS", [myTeam.place, myTeam.avg])) $("teamS").replaceChildren(teamChip(myTeam, myTeam.place + "-o'rin"));
  if (changed("teams", [st.teams, st.team])) renderTeams(st.teams, st.team);
  $("score").textContent = st.score;
  const n = st.tasks.filter(t => t.state === "done").length;
  $("doneN").textContent = n + " / " + st.tasks.length + " bajarildi";
  $("bar").style.width = (100 * n / st.tasks.length) + "%";
  if (lastScore !== null && st.score > lastScore) bump($("scorebox"));
  lastScore = st.score;

  const fresh = [];
  for (const t of st.tasks) if (t.state === "done" && doneSeen && !doneSeen.includes(t.id)) fresh.push(t.id);
  if (fresh.length) toast("Bajarildi: " + st.tasks.find(t => t.id === fresh[0]).title + " (+10 ball)", true);
  doneSeen = st.tasks.filter(t => t.state === "done").map(t => t.id);

  $("hbar").style.width = (100 * n / st.tasks.length) + "%";
  $("doneS").textContent = n + " / " + st.tasks.length;
  if (changed("tasks", [st.tasks.map(t => [t.state, t.check]), hintOn, lastErr, st.flow, st.demo])) renderTask(st, fresh);
  $("lockov").hidden = !st.flow.blocked;
  $("lockmsg").textContent = st.flow.blocked || "";
  if (changed("inst", st.instances)) renderInstances(st.instances);
  if (changed("tables", [openName, st.tables.map(t => [t.name, t.status, t.pk, t.sk, t.items.length])])) renderTables(st.tables);
  renderOpen(st);
  if (changed("log", st.log)) renderLog(st.log);
  CUR = st.flow.blocked ? null : st.tasks.find(t => t.state === "current") || null;
  guide();
}

// Joriy vazifada bosilishi kerak bo'lgan joy yonib-o'chib turadi (noldan boshlaganlar uchun).
let CUR = null;
const GUIDE = {
  e1: ["#launch"], e2: ['[data-g="stop"]'], e3: ['[data-g="modify"]'], e4: ['[data-g="start"]'], e5: ['[data-g="reboot"]'],
  d1: ["#create"], d2: ['[data-g="open-Talabalar"]', "#tvput .btn.primary"], d3: ["#tvget .btn"],
  d4: ["#create", '[data-g="open-Baholar"]', "#tvput .btn.primary"], f1: ['[data-g="terminate"]'],
};
function guide() {
  document.querySelectorAll(".guide").forEach(e => e.classList.remove("guide"));
  if (!CUR) return;
  if (!CUR.where) return;
  const nav = document.querySelector('.nav[data-tab="' + CUR.where + '"]');
  if (nav && !nav.classList.contains("on")) return nav.classList.add("guide");
  const table = CUR.id === "d4" ? "Baholar" : "Talabalar";
  for (const sel of GUIDE[CUR.id] || []) {
    if (sel.startsWith("#tv") && openName !== table) continue;  // faqat kerakli jadval ochiq bo'lsa
    document.querySelectorAll(sel).forEach(e => e.classList.add("guide"));
  }
}
function bump(el) { el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump"); }

const LETTER = ["A", "B", "C", "D"];
let ANS = {}, WRONG = {};
const PILL = {kutish: ["clock", "Kuting", "wait"], namuna: ["eye", "O'qituvchini kuzating", "watch"],
              mustaqil: ["pencil", "O'zingiz bajaring", ""], yakun: ["flag", "Missiya yakuni", "done"]};

function renderTask(st, fresh) {
  const box = $("task"), f = st.flow, M = st.missions.find(m => m.no === f.mission);
  const cur = st.tasks.find(t => t.state === "current"), allDone = st.tasks.every(t => t.state === "done");
  if (cur && cur.id !== hintFor) { hintFor = cur.id; hintOn = false; }
  const p = allDone ? ["check", "Hammasi bajarildi", "done"] : st.demo ? ["screen", "Namuna konsoli (o'qituvchi)", "watch"] : PILL[f.step];
  $("state").replaceChildren(icon(p[0]), p[1]); $("state").className = "pill " + p[2];
  $("mSmall").textContent = f.mission + "-missiya / " + st.missions.length;
  $("mTitle").textContent = M.title;
  box.replaceChildren();
  if (allDone) box.append(h("div", {class: "finish"}, h("div", {class: "big"}, icon("trophy")), h("h2", null, "Tabriklaymiz!"),
    h("p", {class: "muted"}, "A5 laboratoriya ishi to'liq bajarildi: " + st.score + " / " + st.total + " ball.")));
  else if (!st.demo && f.step === "kutish") box.append(waitCard());
  else if (!st.demo && f.step === "namuna") box.append(namunaCard(M));
  else if (!st.demo && f.step === "yakun") box.append(yakunCard(M, st));
  else if (!cur) box.append(h("div", {class: "finish"}, h("div", {class: "big"}, icon("check")), h("h2", null, "Barakalla!"),
    h("p", {class: "muted"}, f.mission + "-missiya vazifalari bajarildi. Keyingi missiyani o'qituvchi ochadi — kuting.")));
  else box.append(...taskCard(st, cur));
  box.append(allList(st, cur, fresh));
}

function waitCard() {
  return h("div", {class: "finish"}, h("div", {class: "big wait"}, icon("clock")), h("h2", null, "Dars hali boshlanmagan"),
    h("p", {class: "muted"}, "O'qituvchi darsni boshlashini kuting. Bu orada o'ngdagi konsol bilan tanishing: EC2 — virtual mashinalar, DynamoDB — jadvallar."));
}

function namunaCard(M) {
  return h("div", null, h("span", {class: "chip"}, M.no + "-MISSIYA · NAMUNA"), h("h3", {class: "goal"}, M.title),
    h("p", {class: "muted"}, M.goal),
    h("div", {class: "watch"}, icon("eye"), h("div", null, h("b", null, "O'qituvchini kuzating"),
      "U hozir shu amallarni ekranda ko'rsatadi. Vazifalar keyin ochiladi.")),
    h("div", {class: "nlist"}, M.namuna.map((x, i) => h("div", {class: "nitem"}, h("span", {class: "rnum"}, i + 1),
      h("div", null, h("code", null, x.do), h("p", null, x.mean))))));
}

function yakunCard(M, st) {
  const ts = st.tasks.filter(t => t.mission === M.no), d = ts.filter(t => t.state === "done").length;
  return h("div", null, h("span", {class: "chip"}, M.no + "-MISSIYA · YAKUN"), h("h3", {class: "goal"}, M.title),
    h("div", {class: d === ts.length ? "success" : "watch"}, icon(d === ts.length ? "check" : "info"),
      h("div", null, h("b", null, d + " / " + ts.length + " vazifa bajarildi"),
        d === ts.length ? "Ajoyib! Hammasi to'g'ri." : "Qolgan vazifalar keyingi missiya bilan birga ochiq qoladi.")),
    h("h4", {style: "margin-top:16px"}, icon("star"), "Siz nimani o'rgandingiz"),
    h("div", {class: "nlist"}, M.learned.map(x => h("div", {class: "ck ok"}, h("i", null, icon("check")), h("span", null, x)))));
}

function taskCard(st, cur) {
  const mt = st.tasks.filter(t => t.mission === cur.mission), k = mt.indexOf(cur) + 1;
  const tabName = cur.where;
  const rows = h("div", {class: "rows"});
  if (tabName) rows.append(h("div", {class: "row"}, h("span", null, "Qayerda"),
    h("button", {class: "where", onclick: () => { showTab(tabName); if (window.innerWidth <= 1000) $("tab-" + tabName).scrollIntoView({behavior: "smooth", block: "start"}); }},
      tabName === "ec2" ? "EC2 (Virtual mashinalar)" : "DynamoDB (Jadvallar)", icon("open"))));
  if (cur.steps) rows.append(h("div", {class: "row"}, h("span", null, "Qadamlar"), h("ol", {class: "steps"}, cur.steps.map(x => h("li", null, rich(x))))));
  if (cur.expect) rows.append(h("div", {class: "row"}, h("span", null, "Natija"), h("div", null, cur.expect)));
  const out = [h("span", {class: "chip"}, cur.mission + "-MISSIYA · " + k + "/" + mt.length + "-VAZIFA" + (cur.kind === "quiz" ? " · SAVOL" : "")),
    h("h3", {class: "goal"}, cur.title), cur.kind === "quiz" ? null : rows];
  if (cur.kind === "answer") {
    const inp = h("input", {class: "ansin", placeholder: cur.placeholder || "", autocomplete: "off", spellcheck: "false", "data-k": "ans"});
    inp.value = ANS[cur.id] || "";
    inp.oninput = () => { ANS[cur.id] = inp.value; };
    const send = (e) => act("task.answer", {id: cur.id, value: inp.value}, e && e.currentTarget);
    inp.onkeydown = (e) => { if (e.key === "Enter") send(); };
    out.push(h("div", {class: "ansbox"}, h("label", null, "Javobingiz", inp),
      h("button", {class: "btn primary", "data-g": "answer", onclick: send}, icon("check"), "Tekshirish")));
  }
  if (cur.kind === "quiz") {
    const wrong = WRONG[cur.id] || [];
    out.push(h("div", {class: "quiz"}, cur.options.map((o, i) => h("button", {class: "opt" + (wrong.includes(i) ? " wrong" : ""), ...(wrong.includes(i) ? {disabled: ""} : {}),
      onclick: async (e) => { const j = await act("task.answer", {id: cur.id, value: i}, e.currentTarget);
        if (!j.ok) { (WRONG[cur.id] = WRONG[cur.id] || []).push(i); renderTask(j.state || st, []); } }},
      h("b", null, LETTER[i]), h("span", null, o)))));
  }
  out.push(lastErr ? h("div", {class: "errbox"}, icon("x"), h("div", null, h("b", null, "Bajarilmadi"), lastErr.msg,
    h("small", null, cur.kind === "do" ? "Xabarni o'qing, tuzating va tugmani qayta bosing." : "Tuzatib, qayta urinib ko'ring."))) : null);
  if (cur.kind === "do") out.push(checkBox(cur.check || []));
  out.push(hintOn ? h("div", {class: "hint"}, h("b", null, "Maslahat: "), cur.hint)
    : h("button", {class: "hintb", onclick: () => { hintOn = true; renderTask(st, []); }}, icon("bulb"), "Maslahat olish", h("small", null, "bepul")));
  return out.filter(Boolean);
}

function allList(st, cur, fresh) {
  const all = h("div", {class: "all"}), open = cur ? cur.mission : st.flow.mission;
  for (const m of st.missions) {
    const ts = st.tasks.filter(t => t.mission === m.no), d = ts.filter(t => t.state === "done").length;
    const locked = !st.demo && m.no > st.flow.mission;
    all.append(h("div", {class: "secrow" + (locked ? " locked" : "")}, icon(locked ? "lock" : m.icon), h("b", null, m.no + ". " + m.title),
      h("span", null, d + " / " + ts.length), h("div", {class: "bar" + (d === ts.length ? " full" : "")}, h("i", {style: "width:" + (100 * d / ts.length) + "%"}))));
    if (m.no === open) ts.forEach(t => all.append(h("div", {class: "ti " + t.state + (fresh.includes(t.id) ? " pop" : "")},
      h("i", null, t.state === "done" ? icon("check") : t.state === "locked" ? icon("lock") : ts.indexOf(t) + 1), t.title)));
  }
  return all;
}

// Jamoalar reytingi (chap kartaning pastida)
function renderTeams(teams, mine) {
  const box = $("teams");
  const max = Math.max(10, ...teams.map(t => t.avg));
  box.replaceChildren(h("h4", null, icon("trophy"), "Jamoalar reytingi"),
    ...teams.map(t => h("div", {class: "trow" + (t.id === mine ? " mine" : ""), style: "--tc:" + t.color},
      placeBadge(t.place), teamIcon(t), h("b", null, t.name + (t.id === mine ? " (siz)" : "")),
      h("div", {class: "tbar"}, h("i", {style: "width:" + (100 * t.avg / max) + "%"})), h("span", null, t.avg))),
    h("p", {class: "small muted"}, "Jamoa balli — a'zolar ballining o'rtachasi."));
}

// Jonli tekshiruv: har bir shart ✓/✗; xato bo'lsa — "sizda" va "kerak" yonma-yon.
function checkBox(items) {
  if (!items.length) return null;
  const ok = items.filter(x => x.ok).length;
  return h("div", {class: "check"},
    h("div", {class: "chh"}, icon("search"), h("b", null, "Tekshiruv"), h("span", null, ok + " / " + items.length + " shart bajarildi"),
      h("div", {class: "bar" + (ok === items.length ? " full" : "")}, h("i", {style: "width:" + (100 * ok / items.length) + "%"}))),
    items.map(x => h("div", {class: "ck " + (x.ok ? "ok" : "no")}, h("i", null, icon(x.ok ? "check" : "x")),
      h("div", null, h("span", null, x.label + (x.ok && x.want ? ": " + x.want : "")),
        !x.ok && x.got != null ? h("div", {class: "diff"}, h("s", null, "sizda: " + x.got), icon("open"), h("b", null, "kerak: " + (x.want ?? ""))) :
        !x.ok && x.want ? h("div", {class: "diff"}, h("b", null, "kerak: " + x.want)) : null))));
}

// ---------------------------------------------------------------- EC2
const FLOW = [["pending", "running", "stopping", "stopped"], ["running", "rebooting", "running"], ["shutting-down", "terminated"]];
function renderFlow(list) {
  const alive = list.filter(i => i.state !== "terminated");
  const cur = (alive.filter(i => i.name === "web-server").pop() || alive.pop() || list[list.length - 1] || {}).state;
  const box = $("flow"); let lit = false; box.replaceChildren(h("b", null, "Hayot sikli:"));
  FLOW.forEach((row, r) => {
    if (r) box.append(h("span", null, " · "));
    row.forEach((s, n) => { if (n) box.append("→"); const on = s === cur && !lit; if (on) lit = true; box.append(h("span", {class: "st" + (on ? " on" : "")}, s)); });
  });
}

function renderInstances(list) {
  renderFlow(list);
  const box = $("instances");
  if (!list.length) { seenIds = new Set(); return box.replaceChildren(empty("server", "Hozircha namuna yo'q. Yuqoridagi shakl orqali birinchi virtual mashinani ishga tushiring.")); }
  const btn = (i, ic, label, op, cls, ask) => h("button", {class: "btn sm " + (cls || ""), "data-g": i.name === "web-server" ? op.slice(4) : "", onclick: (e) => {
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
        h("button", {class: "btn sm", "data-g": i.name === "web-server" ? "modify" : "", onclick: (e) => act("ec2.modify", {id: i.id, type: sel.value}, e.currentTarget)}, icon("cpu"), "Turini o'zgartirish"), kill);
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
      t.status === "ACTIVE" ? h("button", {class: "btn sm primary", "data-g": "open-" + t.name, onclick: (e) => openTable(t.name, e.currentTarget)}, icon("open"), "Ochish") : null,
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
  document.querySelectorAll(".nav").forEach(b => b.onclick = () => showTab(b.dataset.tab));
  $("lform").onsubmit = async (e) => {
    e.preventDefault();
    const j = await api("/api/join", {name: $("lname").value, group: $("lgroup").value});
    if (!j.ok) return $("lerr").textContent = j.msg;
    TOKEN = j.token; try { localStorage.setItem(TKEY, TOKEN); } catch (err) {}
    refresh();
  };
  if (DEMO && !TOKEN) {  // o'qituvchining namuna konsoli
    const r = await fetch("/api/teacher/demo", {method: "POST"});
    const j = await r.json().catch(() => ({}));
    if (j.token) { TOKEN = j.token; try { localStorage.setItem(TKEY, TOKEN); } catch (e) {} }
    else { document.body.textContent = "Namuna konsoli uchun avval /teacher sahifasida o'qituvchi sifatida kiring."; return; }
  }
  if (TOKEN) refresh(); else $("login").hidden = false;
  setInterval(refresh, 2000);
}
init();
