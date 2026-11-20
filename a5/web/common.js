// Umumiy yordamchilar: elementlar yaratish va SVG ikonkalar (tashqi kutubxonasiz).
const $ = (id) => document.getElementById(id);

const ICONS = {
  cloud: '<path d="M7 18h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.1 9.4 4.3 4.3 0 0 0 7 18z"/>',
  server: '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>',
  db: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
  play: '<path d="M7 4.5l12 7.5-12 7.5z"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  reboot: '<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M10 10h4v4h-4zM9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  rocket: '<path d="M9 15l-3-3c2-6 7-9 14-9 0 7-3 12-9 14z"/><path d="M6 12H3l3-4h4M12 18v3l4-3v-4"/><circle cx="15" cy="9" r="1.5"/><path d="M6 16c-1.5.5-2.5 2.5-2.5 4.5 2 0 4-1 4.5-2.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  list: '<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
  open: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  terminal: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M13 15h4"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
  star: '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
  bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  medal: '<circle cx="12" cy="15" r="6"/><path d="M8 3l2.5 6.5M16 3l-2.5 6.5M12 12.5v5"/>',
  logout: '<path d="M14 4h6v16h-6M10 17l-5-5 5-5M5 12h11"/>',
  screen: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a1 1 0 0 1 1-1h10"/>',
  trophy: '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  home: '<path d="M4 11l8-7 8 7v9H4z"/><path d="M10 20v-6h4v6"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  bulb: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
  pencil: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
};

function icon(name) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("class", "ic");
  s.setAttribute("aria-hidden", "true");
  for (const [k, v] of [["fill", "none"], ["stroke", "currentColor"], ["stroke-width", "2"], ["stroke-linecap", "round"], ["stroke-linejoin", "round"]]) s.setAttribute(k, v);
  s.innerHTML = ICONS[name] || "";
  return s;
}

function h(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of kids.flat(9)) if (c != null && c !== false) e.append(c instanceof Node ? c : String(c));
  return e;
}

// HTML ichidagi <i data-i="nom"></i> belgilarini ikonkaga almashtirish
function applyIcons(root) {
  (root || document).querySelectorAll("i[data-i]").forEach((e) => e.replaceWith(icon(e.dataset.i)));
}

// Jamoa belgisi: rangli doira ichida ikonka + nom
function teamIcon(t, size) {
  const d = h("span", {class: "tico", style: "background:" + t.color + (size ? ";width:" + size + "px;height:" + size + "px" : "")});
  d.append(icon(t.icon));
  return d;
}
function teamChip(t, extra) {
  return h("span", {class: "tchip", style: "--tc:" + t.color}, teamIcon(t), h("b", null, t.name), extra ? h("small", null, extra) : null);
}
const placeBadge = (n) => h("span", {class: "medal" + (n <= 3 ? " m" + n : "")}, n);
