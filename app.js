if (location.protocol === "file:") {
  const page = location.pathname.split("/").pop() || "index.html";
  location.replace(`http://127.0.0.1:8000/${page}${location.search}${location.hash}`);
}

const state = {
  user: null,
  school: null,
  threads: [],
  filter: new URLSearchParams(location.search).get("curriculum") || "",
  bookmarkedOnly: new URLSearchParams(location.search).get("bookmarked") === "1",
  schoolAbort: null,
  pendingVerificationEmail: "",
};

const ALL_CURRICULA = ["AP Curriculum", "IB Diploma", "A-Levels", "SAT / ACT", "GCSE", "Research"];

const SECTIONS_BY_CURRICULUM = {
  "AP Curriculum": [
    "AP Biology",
    "AP Chemistry",
    "AP Physics 1",
    "AP Physics C: Mechanics",
    "AP Calculus AB",
    "AP Calculus BC",
    "AP Statistics",
    "AP Computer Science A",
    "AP English Language",
    "AP English Literature",
    "AP US History",
    "AP World History",
  ],
  "IB Diploma": [
    "Biology HL",
    "Chemistry HL",
    "Physics HL",
    "Mathematics AA HL",
    "Mathematics AI HL",
    "English A",
    "History HL",
    "Economics HL",
    "Theory of Knowledge",
    "Extended Essay",
  ],
  "A-Levels": [
    "Mathematics",
    "Further Mathematics",
    "Physics",
    "Chemistry",
    "Biology",
    "Economics",
    "English Literature",
    "History",
  ],
  "SAT / ACT": [
    "SAT Reading and Writing",
    "SAT Math",
    "ACT English",
    "ACT Math",
    "ACT Reading",
    "ACT Science",
  ],
  "GCSE": [
    "Mathematics",
    "English Language",
    "English Literature",
    "Combined Science",
    "Biology",
    "Chemistry",
    "Physics",
    "History",
    "Geography",
  ],
  "Research": [
    "Research Methods",
    "Literature Review",
    "Data Analysis",
    "Citation and Sources",
    "Abstract Writing",
    "Presentation",
  ],
};

const customSectionsByCurriculum = {};
const SECTION_CHOICE_SEPARATOR = "|||";
const THEME_KEY = "studera-theme";
const THEME_MODE_KEY = "studera-theme-mode";
const COLOR_THEME_KEY = "studera-color-theme";
const THEME_CHOICE_COOKIE = "studera_theme_choice";
const THEME_RENDER_COOKIE = "studera_theme_render";
const COLOR_THEME_COOKIE = "studera_color_theme";
const AUTH_HINT_KEY = "studera-authenticated";
const THEME_MODES = ["light", "dark", "system"];
const COLOR_THEMES = [
  { id: "studera", label: "Studera", colors: ["#F8FAFC", "#1A365D", "#8A5A14", "#E2E8F0"], darkColors: ["#0E1622", "#233D66", "#D5A455", "#2A3A4F"] },
  { id: "github", label: "GitHub", colors: ["#F6F8FA", "#1F6FEB", "#9A6700", "#D0D7DE"], darkColors: ["#0D1117", "#1F6FEB", "#D29922", "#303A46"] },
  { id: "ayu", label: "Ayu", colors: ["#FAFAFA", "#399EE6", "#FF9940", "#DFE3E6"], darkColors: ["#0B0E14", "#39BAE6", "#FFD580", "#263242"] },
  { id: "monokai-pro", label: "Monokai Pro", colors: ["#FFFDF7", "#FF6188", "#78DCE8", "#DED8CD"], darkColors: ["#221F22", "#FC9867", "#78DCE8", "#4A4650"] },
  { id: "min", label: "Min Theme", colors: ["#FFFFFF", "#1F2937", "#006EDB", "#E5E7EB"], darkColors: ["#101318", "#E7E9EE", "#A7C7FF", "#303A46"] },
  { id: "everforest", label: "Everforest", colors: ["#FDF6E3", "#8DA101", "#DFA000", "#E0D6BA"], darkColors: ["#1E2326", "#A7C080", "#DBBC7F", "#45504D"] },
  { id: "amethyst", label: "Amethyst", colors: ["#FBF8FF", "#7C3AED", "#B892FF", "#E8DDF8"], darkColors: ["#15121F", "#B892FF", "#FFD166", "#3A3152"] },
  { id: "better-solarized", label: "Better Solarized", colors: ["#FDF6E3", "#268BD2", "#B58900", "#D8CFB5"], darkColors: ["#002B36", "#2AA198", "#D6A600", "#1D5662"] },
];

function storedThemeMode() {
  try {
    return (
      localStorage.getItem(THEME_MODE_KEY) ||
      localStorage.getItem(THEME_KEY) ||
      document.documentElement.dataset.themeChoice ||
      (isPublicLightPage() ? "light" : "dark")
    );
  } catch {
    return document.documentElement.dataset.themeChoice || (isPublicLightPage() ? "light" : "dark");
  }
}

function storedColorTheme() {
  try {
    return localStorage.getItem(COLOR_THEME_KEY) || document.documentElement.dataset.colorTheme || "studera";
  } catch {
    return document.documentElement.dataset.colorTheme || "studera";
  }
}

function resolveTheme(choice) {
  if (choice === "system") {
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return choice === "dark" ? "dark" : "light";
}

function isPublicLightPage() {
  const page = document.body?.dataset?.page || "";
  const filename = location.pathname.split("/").pop() || "index.html";
  return ["home", "about", "contact"].includes(page) || ["", "index.html", "about.html", "contact.html"].includes(filename);
}

function shouldForceLightTheme() {
  return isPublicLightPage();
}

function writeThemeCookie(name, value) {
  try {
    document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=31536000; SameSite=Lax`;
  } catch {
    // Cookies can be blocked in some browser privacy modes.
  }
}

function validColorTheme(value) {
  return COLOR_THEMES.some((theme) => theme.id === value) ? value : "studera";
}

function persistTheme(normalized, resolved, colorTheme, forcedLight) {
  try {
    localStorage.setItem(THEME_MODE_KEY, normalized);
    localStorage.setItem(THEME_KEY, normalized);
    localStorage.setItem(COLOR_THEME_KEY, colorTheme);
  } catch {
    // Local storage can be blocked in some browser privacy modes.
  }
  writeThemeCookie(THEME_CHOICE_COOKIE, normalized);
  writeThemeCookie(COLOR_THEME_COOKIE, colorTheme);
  if (!forcedLight) writeThemeCookie(THEME_RENDER_COOKIE, resolved);
}

function applyTheme(choice = storedThemeMode(), colorChoice = storedColorTheme()) {
  const normalized = THEME_MODES.includes(choice) ? choice : "light";
  const colorTheme = validColorTheme(colorChoice);
  const forcedLight = shouldForceLightTheme();
  const resolved = forcedLight ? "light" : resolveTheme(normalized);
  document.documentElement.dataset.themeChoice = normalized;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.colorTheme = colorTheme;
  document.documentElement.style.colorScheme = resolved;
  document.documentElement.style.backgroundColor = resolved === "dark" ? "#0E1622" : "#F8FAFC";
  document.documentElement.style.color = resolved === "dark" ? "#E5EAF2" : "#1E293B";
  persistTheme(normalized, resolved, colorTheme, forcedLight);
  renderThemeChoiceGrid();
}

function setAuthHint(user) {
  try {
    if (user) localStorage.setItem(AUTH_HINT_KEY, "1");
    else localStorage.removeItem(AUTH_HINT_KEY);
  } catch {
    // Local storage can be blocked in some browser privacy modes.
  }
}

function initTheme() {
  applyTheme();
  window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener?.("change", () => {
    if (storedThemeMode() === "system") applyTheme("system", storedColorTheme());
  });
}

initTheme();

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function $(selector, root = document) {
  return root.querySelector(selector);
}

function $all(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

function toast(message) {
  const node = $("[data-toast]");
  if (!node) return;
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 2600);
}

function setMessage(selector, text, type = "") {
  const node = $(selector);
  if (!node) return;
  node.textContent = text;
  node.className = `form-message ${type}`;
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function compactText(value, max = 180) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function avatarMarkup(path, className = "avatar") {
  const safePath = String(path || "").trim();
  return safePath
    ? `<span class="${className} has-image" aria-hidden="true"><img src="${escapeHtml(safePath)}" srcset="${escapeHtml(safePath)} 1x, ${escapeHtml(safePath)} 2x" alt="" decoding="async" /></span>`
    : `<span class="${className}" aria-hidden="true"></span>`;
}

function setAvatarPreview(node, path) {
  if (!node) return;
  const safePath = String(path || "").trim();
  node.classList.toggle("has-image", Boolean(safePath));
  node.innerHTML = safePath ? `<img src="${escapeHtml(safePath)}" srcset="${escapeHtml(safePath)} 1x, ${escapeHtml(safePath)} 2x" alt="" decoding="async" />` : "";
}

function renderLatex(source, displayMode = false) {
  const latex = String(source || "");
  if (!window.katex) return escapeHtml(displayMode ? `$$${latex}$$` : `$${latex}$`);
  try {
    return window.katex.renderToString(latex, {
      displayMode,
      throwOnError: false,
      strict: "ignore",
      trust: false,
    });
  } catch {
    return escapeHtml(displayMode ? `$$${latex}$$` : `$${latex}$`);
  }
}

function renderRichText(value) {
  const text = String(value || "");
  if (!text) return "";
  const pattern = /(\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$\$[\s\S]+?\$\$|\$[^\n$]+\$)/g;
  let cursor = 0;
  let html = "";
  text.replace(pattern, (match, _unused, index) => {
    html += escapeHtml(text.slice(cursor, index)).replace(/\n/g, "<br>");
    if (match.startsWith("$$")) {
      html += renderLatex(match.slice(2, -2), true);
    } else if (match.startsWith("\\[")) {
      html += renderLatex(match.slice(2, -2), true);
    } else if (match.startsWith("\\(")) {
      html += renderLatex(match.slice(2, -2), false);
    } else {
      html += renderLatex(match.slice(1, -1), false);
    }
    cursor = index + match.length;
    return match;
  });
  html += escapeHtml(text.slice(cursor)).replace(/\n/g, "<br>");
  return `<div class="rich-text">${html}</div>`;
}

function attachmentsFor(item) {
  const attachments = Array.isArray(item?.attachments) ? [...item.attachments] : [];
  const legacyPath = item?.attachment_path || item?.image_path || "";
  if (legacyPath && !attachments.some((attachment) => attachment.path === legacyPath)) {
    attachments.unshift({
      path: legacyPath,
      name: item.attachment_name || item.image_name || "Attachment",
      type: item.attachment_type || (item.image_path ? "image/*" : "application/octet-stream"),
    });
  }
  return attachments.filter((attachment) => attachment?.path);
}

function isImageAttachment(attachment) {
  return Boolean(attachment?.type?.startsWith("image/") || /\.(png|jpe?g|webp|gif|svg|avif)$/i.test(attachment?.name || attachment?.path || ""));
}

function renderOneAttachment(attachment) {
  if (isImageAttachment(attachment)) {
    return `
      <figure class="attachment image-attachment">
        <a href="${escapeHtml(attachment.path)}" target="_blank" rel="noopener">
          <img src="${escapeHtml(attachment.path)}" alt="${escapeHtml(attachment.name)}" loading="lazy" />
        </a>
        <figcaption>${escapeHtml(attachment.name)}</figcaption>
      </figure>
    `;
  }
  return `
    <a class="file-attachment" href="${escapeHtml(attachment.path)}" target="_blank" rel="noopener">
      <span class="file-icon" aria-hidden="true">□</span>
      <span>
        <strong>${escapeHtml(attachment.name)}</strong>
        <small>${escapeHtml(attachment.type || "File")}</small>
      </span>
    </a>
  `;
}

function renderAttachments(item) {
  return attachmentsFor(item).map(renderOneAttachment).join("");
}

function readUploadFile(file) {
  return new Promise((resolve, reject) => {
    if (!file) return resolve(null);
    if (file.size > 15 * 1024 * 1024) return reject(new Error("Attachments must be 15 MB or smaller."));
    const reader = new FileReader();
    reader.onload = () => resolve({ file_data: reader.result, file_name: file.name });
    reader.onerror = () => reject(new Error("Attachment could not be read."));
    reader.readAsDataURL(file);
  });
}

async function formPayload(form) {
  const data = Object.fromEntries(new FormData(form));
  if (form.matches("[data-thread-form]")) {
    const choice = decodeSectionChoice(data.section);
    if (choice.curriculum && choice.section) {
      data.curriculum = choice.curriculum;
      data.section = choice.section;
    }
  }
  delete data.image_file;
  delete data.file_upload;
  const fileInput = $("[data-file-input], [data-image-input]", form);
  const uploadFiles = selectedFiles(fileInput);
  if (uploadFiles.length) data.files = await Promise.all(uploadFiles.map(readUploadFile));
  return data;
}

function selectedFiles(input) {
  if (!input) return [];
  if (!Array.isArray(input._selectedFiles)) input._selectedFiles = [];
  return input._selectedFiles;
}

function addSelectedFiles(input, files) {
  if (!input) return;
  const existing = selectedFiles(input);
  Array.from(files || []).forEach((file) => {
    const key = `${file.name}:${file.size}:${file.lastModified}`;
    if (!existing.some((item) => `${item.name}:${item.size}:${item.lastModified}` === key)) {
      existing.push(file);
    }
  });
  input.value = "";
  updateFilePreview(input);
}

function removeSelectedFile(input, index) {
  selectedFiles(input).splice(index, 1);
  updateFilePreview(input);
}

function updateFilePreview(input) {
  const drop = input.closest("[data-file-drop]");
  const preview = input.closest(".field")?.querySelector("[data-file-preview], [data-image-preview]");
  const label = drop?.querySelector("span");
  const files = selectedFiles(input);
  if (label) label.textContent = files.length ? `${files.length} file${files.length === 1 ? "" : "s"} selected` : "Attach a PDF, image, document, or any file";
  if (!preview) return;
  preview.innerHTML = files.length ? `
    <div class="pending-files">
      ${files.map((file, index) => `
        <div class="pending-file">
          <span>
            <strong>${escapeHtml(file.name)}</strong>
            <small>${Math.max(1, Math.round(file.size / 1024))} KB</small>
          </span>
          <button class="file-remove" type="button" data-remove-file="${index}" aria-label="Remove ${escapeHtml(file.name)}">×</button>
        </div>
      `).join("")}
    </div>
  ` : "";
}

function installFileInputs() {
  document.addEventListener("change", (event) => {
    const input = event.target.closest("[data-file-input], [data-image-input]");
    if (!input) return;
    addSelectedFiles(input, input.files);
  });

  document.addEventListener("click", (event) => {
    const remove = event.target.closest("[data-remove-file]");
    if (!remove) return;
    const field = remove.closest(".field");
    const input = field?.querySelector("[data-file-input], [data-image-input]");
    if (!input) return;
    removeSelectedFile(input, Number(remove.dataset.removeFile));
  });

  document.addEventListener("click", (event) => {
    const drop = event.target.closest("[data-file-drop]");
    if (!drop || event.target.matches("input")) return;
    drop.querySelector("[data-file-input], [data-image-input]")?.click();
  });

  document.addEventListener("dragenter", (event) => {
    const drop = event.target.closest("[data-file-drop]");
    if (!drop) return;
    event.preventDefault();
    drop.classList.add("drag-over");
    const label = drop.querySelector("span");
    if (label) label.textContent = "Drop here";
  });

  document.addEventListener("dragover", (event) => {
    const drop = event.target.closest("[data-file-drop]");
    if (!drop) return;
    event.preventDefault();
    drop.classList.add("drag-over");
  });

  document.addEventListener("dragleave", (event) => {
    const drop = event.target.closest("[data-file-drop]");
    if (!drop || drop.contains(event.relatedTarget)) return;
    drop.classList.remove("drag-over");
    updateFilePreview(drop.querySelector("[data-file-input], [data-image-input]"));
  });

  document.addEventListener("drop", (event) => {
    const drop = event.target.closest("[data-file-drop]");
    if (!drop) return;
    event.preventDefault();
    drop.classList.remove("drag-over");
    const input = drop.querySelector("[data-file-input], [data-image-input]");
    if (!input || !event.dataTransfer?.files?.length) return;
    addSelectedFiles(input, event.dataTransfer.files);
  });
}

function roleBadge(role) {
  const labels = { teacher: "Teacher", staff: "Staff", student: "Student" };
  const normalized = labels[role] ? role : "student";
  return `<span class="badge ${normalized}">${labels[normalized]}</span>`;
}

function statusBadge(status) {
  const labels = { open: "Open", answered: "Answered", archived: "Archived", locked: "Locked" };
  const normalized = labels[status] ? status : "open";
  return `<span class="badge status ${normalized}">${labels[normalized]}</span>`;
}

function canManageThread(thread) {
  return Boolean(state.user?.is_school_admin);
}

function statusOptionsForThread(thread) {
  const isAdmin = Boolean(state.user?.is_school_admin);
  if (!isAdmin) return [];
  return ["open", "locked", "archived"];
}

function profileHref(userId) {
  return `profile.html?id=${encodeURIComponent(userId)}`;
}

function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

function auditDay(timestamp) {
  return String(timestamp || "Unknown date").replace(/\s+\d{2}:\d{2}$/, "");
}

function auditLabel(action) {
  return String(action || "admin_action")
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function renderAuditGroups(logs = [], { limit = 0, empty = "No admin actions recorded yet." } = {}) {
  const visible = limit ? logs.slice(0, limit) : logs;
  if (!visible.length) return `<p class="upload-empty">${escapeHtml(empty)}</p>`;
  const groups = new Map();
  visible.forEach((log) => {
    const day = auditDay(log.created_at);
    if (!groups.has(day)) groups.set(day, []);
    groups.get(day).push(log);
  });
  return Array.from(groups.entries()).map(([day, items]) => `
    <section class="audit-group">
      <h3>${escapeHtml(day)}</h3>
      <div class="audit-list">
        ${items.map((log) => `
          <article class="admin-row audit-row">
            <div>
              <strong>${escapeHtml(auditLabel(log.action))}</strong>
              <span>${escapeHtml(log.actor_email || "system")} · ${escapeHtml(log.actor_scope || "admin")} · ${escapeHtml(log.target_type || "target")} ${escapeHtml(log.target_id || "")} · ${escapeHtml(log.created_at)}</span>
              <small>${escapeHtml(JSON.stringify(log.details || {}))}</small>
            </div>
            ${log.school ? `<span class="badge section">${escapeHtml(log.school)}</span>` : ""}
          </article>
        `).join("")}
      </div>
    </section>
  `).join("");
}

function auditLink(scope) {
  return `audit.html?scope=${encodeURIComponent(scope)}`;
}

function closeModal() {
  $("[data-modal-root]")?.remove();
  document.body.classList.remove("modal-open");
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && $("[data-modal-root]")) closeModal();
});

function openModal({ title, eyebrow = "Edit", body = "", titleValue = "", titleField = false, submitLabel = "Save", onSubmit }) {
  closeModal();
  const root = document.createElement("div");
  root.className = "modal-backdrop";
  root.dataset.modalRoot = "true";
  root.innerHTML = `
    <section class="studera-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <form data-modal-form>
        <div class="modal-head">
          <div>
            <p class="eyebrow">${escapeHtml(eyebrow)}</p>
            <h2 id="modal-title">${escapeHtml(title)}</h2>
          </div>
          <button class="modal-close" type="button" data-modal-close aria-label="Close">×</button>
        </div>
        ${titleField ? `
          <div class="field">
            <label for="modal-title-field">Title</label>
            <input id="modal-title-field" name="title" value="${escapeHtml(titleValue)}" required />
          </div>
        ` : ""}
        <div class="field">
          <label for="modal-body">Contribution</label>
          <textarea id="modal-body" name="body" required>${escapeHtml(body)}</textarea>
        </div>
        <p class="form-message" data-modal-message></p>
        <div class="modal-actions">
          <button class="button secondary" type="button" data-modal-close>Cancel</button>
          <button class="button" type="submit">${escapeHtml(submitLabel)}</button>
        </div>
      </form>
    </section>
  `;
  document.body.appendChild(root);
  document.body.classList.add("modal-open");
  const textarea = $("textarea", root);
  requestAnimationFrame(() => {
    const firstField = titleField ? $("input[name='title']", root) : textarea;
    firstField.focus({ preventScroll: true });
    firstField.setSelectionRange(firstField.value.length, firstField.value.length);
  });
  root.addEventListener("click", (event) => {
    if (event.target === root || event.target.closest("[data-modal-close]")) closeModal();
  });
  root.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = $("button[type='submit']", root);
    const form = event.target.closest("form");
    if (!form) return;
    submit.disabled = true;
    try {
      await onSubmit(Object.fromEntries(new FormData(form)));
      closeModal();
    } catch (error) {
      setMessage("[data-modal-message]", error.message, "error");
      submit.disabled = false;
    }
  });
}

function openDangerConfirmModal({ title, eyebrow = "Danger", message, confirmLabel = "DELETE", submitLabel = "Delete", onSubmit }) {
  closeModal();
  const root = document.createElement("div");
  root.className = "modal-backdrop";
  root.dataset.modalRoot = "true";
  root.innerHTML = `
    <section class="studera-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <form data-modal-form>
        <div class="modal-head">
          <div>
            <p class="eyebrow danger">${escapeHtml(eyebrow)}</p>
            <h2 id="modal-title">${escapeHtml(title)}</h2>
          </div>
          <button class="modal-close" type="button" data-modal-close aria-label="Close">×</button>
        </div>
        <p class="modal-copy">${escapeHtml(message)}</p>
        <div class="field">
          <label for="modal-confirm-field">Type ${escapeHtml(confirmLabel)} to confirm</label>
          <input id="modal-confirm-field" name="confirm" autocomplete="off" required />
        </div>
        <p class="form-message" data-modal-message></p>
        <div class="modal-actions">
          <button class="button secondary" type="button" data-modal-close>Cancel</button>
          <button class="button danger" type="submit">${escapeHtml(submitLabel)}</button>
        </div>
      </form>
    </section>
  `;
  document.body.appendChild(root);
  document.body.classList.add("modal-open");
  requestAnimationFrame(() => $("#modal-confirm-field", root)?.focus({ preventScroll: true }));
  root.addEventListener("click", (event) => {
    if (event.target === root || event.target.closest("[data-modal-close]")) closeModal();
  });
  root.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target.closest("form");
    const submit = $("button[type='submit']", root);
    if (!form) return;
    const data = Object.fromEntries(new FormData(form));
    if (data.confirm !== confirmLabel) {
      setMessage("[data-modal-message]", `Type ${confirmLabel} exactly to continue.`, "error");
      return;
    }
    submit.disabled = true;
    try {
      await onSubmit(data);
      closeModal();
    } catch (error) {
      setMessage("[data-modal-message]", error.message, "error");
      submit.disabled = false;
    }
  });
}

function openReportModal({ targetType, targetId }) {
  closeModal();
  const root = document.createElement("div");
  root.className = "modal-backdrop";
  root.dataset.modalRoot = "true";
  const options = [
    {
      value: "off-topic",
      title: "Off topic",
      description: "This does not belong in the current academic discussion or section.",
    },
    {
      value: "inappropriate",
      title: "Inappropriate",
      description: "This contains offensive, abusive, unsafe, or guideline-breaking content.",
    },
    {
      value: "spam",
      title: "Spam or vandalism",
      description: "This is promotional, repeated, misleading, or not useful to the discussion.",
    },
    {
      value: "academic-integrity",
      title: "Academic integrity",
      description: "This may include cheating, uncited generated work, or misconduct.",
    },
    {
      value: "something-else",
      title: "Something else",
      description: "This needs moderator attention for another reason.",
    },
  ];
  root.innerHTML = `
    <section class="studera-modal report-modal" role="dialog" aria-modal="true" aria-labelledby="report-title">
      <form data-report-form>
        <div class="modal-head">
          <div>
            <p class="eyebrow">Community Report</p>
            <h2 id="report-title">Report ${escapeHtml(targetType)}</h2>
          </div>
          <button class="modal-close" type="button" data-modal-close aria-label="Close">×</button>
        </div>
        <p class="modal-copy">School moderators will review the report and decide whether action is needed.</p>
        <fieldset class="report-options">
          <legend>What should be reviewed?</legend>
          ${options.map((option, index) => `
            <label class="report-option">
              <input type="radio" name="category" value="${escapeHtml(option.value)}" ${index === 0 ? "checked" : ""} />
              <span aria-hidden="true"></span>
              <strong>${escapeHtml(option.title)}</strong>
              <small>${escapeHtml(option.description)}</small>
            </label>
          `).join("")}
        </fieldset>
        <div class="field">
          <label for="report-reason">Reason</label>
          <textarea id="report-reason" name="reason" placeholder="Add the specific context moderators should know." required></textarea>
        </div>
        <p class="form-message" data-modal-message></p>
        <div class="modal-actions">
          <button class="button secondary" type="button" data-modal-close>Cancel</button>
          <button class="button" type="submit">Send Report</button>
        </div>
      </form>
    </section>
  `;
  document.body.appendChild(root);
  document.body.classList.add("modal-open");
  requestAnimationFrame(() => $("#report-reason", root)?.focus({ preventScroll: true }));
  root.addEventListener("click", (event) => {
    if (event.target === root || event.target.closest("[data-modal-close]")) closeModal();
  });
  root.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target.closest("[data-report-form]");
    if (!form) return;
    const submit = $("button[type='submit']", root);
    const data = Object.fromEntries(new FormData(form));
    const category = options.find((option) => option.value === data.category);
    const reason = String(data.reason || "").trim();
    if (!reason) {
      setMessage("[data-modal-message]", "Add a short reason for the moderators.", "error");
      return;
    }
    submit.disabled = true;
    try {
      await api("/api/reports", {
        method: "POST",
        body: JSON.stringify({
          target_type: targetType,
          target_id: targetId,
          reason: `${category?.title || "Report"}\n${reason}`,
        }),
      });
      closeModal();
      toast("Report sent to school admins.");
    } catch (error) {
      setMessage("[data-modal-message]", error.message, "error");
      submit.disabled = false;
    }
  });
}

function openCommunityGuidelinesModal() {
  closeModal();
  const schoolName = state.school?.institution || state.user?.institution || "";
  const guidelines = String(state.school?.guidelines || "").trim();
  const title = schoolName ? `${schoolName} Community Guidelines` : "Community Guidelines";
  const body = guidelines
    ? renderRichText(guidelines)
    : `<p class="modal-copy">${escapeHtml(
        state.user
          ? "Your school has not published custom community guidelines yet."
          : "Sign in to view the community guidelines set by your school."
      )}</p>`;
  const root = document.createElement("div");
  root.className = "modal-backdrop";
  root.dataset.modalRoot = "true";
  root.innerHTML = `
    <section class="studera-modal guidelines-modal" role="dialog" aria-modal="true" aria-labelledby="guidelines-title">
      <div class="modal-static">
        <div class="modal-head">
          <div>
            <p class="eyebrow">School Policy</p>
            <h2 id="guidelines-title">${escapeHtml(title)}</h2>
          </div>
          <button class="modal-close" type="button" data-modal-close aria-label="Close">×</button>
        </div>
        <div class="guidelines-body">
          ${body}
        </div>
        <div class="modal-actions">
          <button class="button" type="button" data-modal-close>Close</button>
        </div>
      </div>
    </section>
  `;
  document.body.appendChild(root);
  document.body.classList.add("modal-open");
  root.addEventListener("click", (event) => {
    if (event.target === root || event.target.closest("[data-modal-close]")) closeModal();
  });
  requestAnimationFrame(() => $("[data-modal-close]", root)?.focus({ preventScroll: true }));
}

function updateAuthUI() {
  document.body.classList.toggle("is-authed", Boolean(state.user));
  setAuthHint(state.user);
  applyTheme(storedThemeMode(), storedColorTheme());
  $(".brand")?.setAttribute("href", state.user?.is_site_admin ? "site-admin.html" : (state.user ? "feed.html" : "index.html"));
  renderNavLinks();
  $all("[data-auth-open]").forEach((button) => {
    button.textContent = state.user ? state.user.name : "Sign In";
    button.onclick = () => {
      if (state.user?.is_site_admin) location.href = "site-admin.html";
      else if (state.user) location.href = "feed.html";
      else location.href = "index.html#auth";
    };
  });
  $all("[data-logout]").forEach((button) => {
    button.classList.toggle("hidden", !state.user);
  });
  window.dispatchEvent(new CustomEvent("studera:session", { detail: state.user }));
}

function renderNavLinks() {
  if ($(".site-nav")?.dataset.reactMounted === "true") return;
  const nav = $(".nav-links");
  if (!nav) return;
  if (!state.user) {
    nav.innerHTML = `
      <a data-nav-about href="about.html">About</a>
      <a data-nav-contact href="contact.html">Contact</a>
    `;
    updateNavState();
    return;
  }
  if (state.user.is_site_admin) {
    nav.innerHTML = `
      <a data-nav-site-admin href="site-admin.html">Site Admin</a>
      <a data-nav-settings href="settings.html">Settings</a>
    `;
  } else {
    nav.innerHTML = `
      <a data-nav-feed href="feed.html">Feed</a>
      <a data-nav-bookmarked href="feed.html?bookmarked=1">Bookmarked</a>
      ${state.user.is_school_admin ? `<a data-nav-admin href="admin.html">Admin</a>` : ""}
      <a data-nav-settings href="settings.html">Settings</a>
    `;
  }
  updateNavState();
}

function cleanupLegacyNav() {
  $all(".nav-links a").forEach((link) => {
    const label = link.textContent.trim().toLowerCase();
    if (label === "threads" || label === "institutions") link.remove();
  });
}

function updateFeedHeader() {
  if (document.body.dataset.page !== "feed") return;
  const eyebrow = $(".page-title .eyebrow");
  const title = $(".page-title h1");
  const lead = $(".page-title .lead");
  if (state.bookmarkedOnly) {
    if (eyebrow) eyebrow.textContent = "Saved Archive";
    if (title) title.textContent = "Bookmarked";
    if (lead) {
      lead.textContent = "Review threads you saved or authored.";
      lead.classList.remove("hidden");
    }
    return;
  }
  if (eyebrow) eyebrow.textContent = "Community Archive";
  if (title) title.textContent = "Discussion Feed";
  if (lead) {
    lead.textContent = "";
    lead.classList.add("hidden");
  }
}

function updateNavState() {
  cleanupLegacyNav();
  document.body.classList.toggle("is-bookmarked", state.bookmarkedOnly);
  updateFeedHeader();
  $all(".nav-links a").forEach((link) => link.classList.remove("active"));
  if (document.body.dataset.page === "feed" && state.bookmarkedOnly) {
    $("[data-nav-bookmarked]")?.classList.add("active");
    return;
  }
  if (document.body.dataset.page === "feed" || document.body.dataset.page === "thread") {
    $("[data-nav-feed]")?.classList.add("active");
  }
  if (document.body.dataset.page === "settings") {
    $("[data-nav-settings]")?.classList.add("active");
  }
  if (document.body.dataset.page === "about") {
    $("[data-nav-about]")?.classList.add("active");
  }
  if (document.body.dataset.page === "contact") {
    $("[data-nav-contact]")?.classList.add("active");
  }
  $all("[data-nav-help]").forEach((link) => link.classList.toggle("active", document.body.dataset.page === "help"));
  if (document.body.dataset.page === "admin") {
    $("[data-nav-admin]")?.classList.add("active");
  }
  if (document.body.dataset.page === "site-admin") {
    $("[data-nav-site-admin]")?.classList.add("active");
  }
  if (document.body.dataset.page === "audit") {
    (state.user?.is_site_admin ? $("[data-nav-site-admin]") : $("[data-nav-admin]"))?.classList.add("active");
  }
}

async function loadSession() {
  const data = await api("/api/session");
  state.user = data.user;
  state.school = data.school || null;
  const page = document.body.dataset.page;
  const publicPages = ["home", "about", "contact", "help"];
  if (state.user?.is_site_admin && ["home", "feed", "thread", "admin"].includes(page)) {
    location.replace("site-admin.html");
    return;
  }
  if (state.user && page === "home") {
    location.replace("feed.html");
    return;
  }
  if (!state.user && !publicPages.includes(page)) {
    location.replace("index.html");
    return;
  }
  updateAuthUI();
  setCustomSections(state.school?.custom_curricula || []);
  if (state.user?.curricula) setCurriculumOptions(state.user.curricula);
  renderSettings();
  renderAdmin();
  renderSiteAdmin();
}

function installNav() {
  if ($(".site-nav")?.dataset.reactMounted === "true") return;
  const nav = $(".site-nav");
  $("[data-menu-toggle]")?.addEventListener("click", () => nav?.classList.toggle("open"));
  $all("[data-logout]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api("/api/auth/logout", { method: "POST", body: "{}" });
      state.user = null;
      state.school = null;
      setCustomSections([]);
      updateAuthUI();
      toast("Signed out.");
      location.href = "index.html";
    });
  });
}

function installFooterGuidelines() {
  document.addEventListener("click", (event) => {
    const link = event.target.closest("[data-community-guidelines]");
    if (!link) return;
    event.preventDefault();
    openCommunityGuidelinesModal();
  });
}

function installNavShadow() {
  const nav = $(".site-nav");
  if (!nav) return;
  let ticking = false;
  const update = () => {
    ticking = false;
    const progress = Math.min(window.scrollY / 90, 1);
    nav.style.setProperty("--nav-shadow-alpha", (progress * 0.14).toFixed(3));
    nav.style.setProperty("--nav-edge-alpha", (progress * 0.18).toFixed(3));
    nav.style.setProperty("--nav-glass-alpha", progress.toFixed(3));
  };
  const requestUpdate = () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(update);
  };
  update();
  window.addEventListener("scroll", requestUpdate, { passive: true });
  window.addEventListener("hashchange", requestUpdate);
}

function replayPop(element) {
  if (!element || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  element.classList.remove("content-pop");
  void element.offsetWidth;
  element.classList.add("content-pop");
}

function installContentMotion() {
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    requestAnimationFrame(() => document.body.classList.add("page-mounted"));
  }

  document.addEventListener("click", (event) => {
    const threadTab = event.target.closest("[data-thread-tab]");
    if (threadTab) {
      setTimeout(() => {
        const panel = $(`[data-thread-panel="${threadTab.dataset.threadTab}"]`);
        replayPop(panel);
      }, 0);
      return;
    }

    const link = event.target.closest("a[href]");
    if (!link || link.target || link.hasAttribute("download")) return;
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    const rawHref = link.getAttribute("href");
    if (!rawHref || rawHref === "#") return;
    let url;
    try {
      url = new URL(link.href, location.href);
    } catch {
      return;
    }
    if (url.origin !== location.origin) return;

    const sameDocument = url.pathname === location.pathname && url.search === location.search;
    if (sameDocument && url.hash) {
      const target = document.getElementById(decodeURIComponent(url.hash.slice(1)));
      if (!target) return;
      event.preventDefault();
      history.pushState(null, "", url);
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      replayPop(target.closest(".settings-panel, .settings-form, .thread-main, .profile-page") || target);
      updateNavState();
      return;
    }

    const navigatesToPage = /\.html$/i.test(url.pathname) || url.pathname.endsWith("/");
    if (!navigatesToPage || url.href === location.href) return;
    event.preventDefault();
    document.body.classList.add("page-leaving");
    setTimeout(() => { location.href = url.href; }, 150);
  });

  window.addEventListener("hashchange", () => {
    const target = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : $("main.page");
    replayPop(target?.closest(".settings-panel, .settings-form, .thread-main, .profile-page") || target);
  });
}

function installAuthForms() {
  $("[data-login-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const verificationStep = $("[data-post-register-verification]");
    if (verificationStep) verificationStep.classList.add("hidden");
    try {
      const data = Object.fromEntries(new FormData(form));
      const result = await api("/api/auth/login", { method: "POST", body: JSON.stringify(data) });
      if (result.requires_verification) {
        state.user = null;
        state.school = null;
        state.pendingVerificationEmail = result.verification_email || data.email || "";
        setCustomSections([]);
        updateAuthUI();
        if (verificationStep) {
          verificationStep.classList.remove("hidden");
          verificationStep.open = true;
          const tokenInput = $("#verify-token-home");
          if (tokenInput) {
            tokenInput.value = "";
            tokenInput.focus();
          }
          replayPop(verificationStep);
        }
        setMessage("[data-login-message]", `We sent a verification code to ${result.verification_email || "your email"}. Enter it before entering Studera.`, "ok");
        setMessage("[data-verify-message]", "Enter the verification code from your email.", "ok");
        return;
      }
      state.user = result.user;
      updateAuthUI();
      const target = state.user?.is_site_admin ? "site-admin.html" : "feed.html";
      setMessage("[data-login-message]", state.user?.is_site_admin ? "Signed in. Redirecting to the global console." : "Signed in. Redirecting to the community.", "ok");
      setTimeout(() => location.href = target, 350);
    } catch (error) {
      setMessage("[data-login-message]", error.message, "error");
    }
  });

  $("[data-register-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const verificationStep = $("[data-post-register-verification]");
    if (verificationStep) verificationStep.classList.add("hidden");
    try {
      const data = Object.fromEntries(new FormData(form));
      if (!data.curricula) {
        throw new Error("Choose your school from the suggestions so Studera can apply the right curriculum.");
      }
      const result = await api("/api/auth/register", { method: "POST", body: JSON.stringify(data) });
      if (result.requires_verification) {
        state.user = null;
        state.pendingVerificationEmail = result.verification_email || data.email || "";
        updateAuthUI();
        if (verificationStep) {
          verificationStep.classList.remove("hidden");
          verificationStep.open = true;
          const tokenInput = $("#verify-token-home");
          if (tokenInput) {
            tokenInput.value = "";
            tokenInput.focus();
          }
          replayPop(verificationStep);
        }
        setMessage("[data-register-message]", `Verification sent to ${result.verification_email || "your email"}. Your profile will be created after you enter the code.`, "ok");
        setMessage("[data-verify-message]", "Enter the verification code from your email.", "ok");
        return;
      }
      state.user = result.user;
      updateAuthUI();
      const target = state.user?.is_site_admin ? "site-admin.html" : "feed.html";
      setMessage("[data-register-message]", state.user?.is_site_admin ? "Profile created. Redirecting to the global console." : "Profile created. Redirecting to the community.", "ok");
      setTimeout(() => location.href = target, 350);
    } catch (error) {
      setMessage("[data-register-message]", error.message, "error");
    }
  });

  $all("[data-verify-form]").forEach((verifyForm) => verifyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      const result = await api("/api/auth/verify", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form))) });
      state.user = result.user || state.user;
      updateAuthUI();
      setMessage("[data-verify-message]", "Email verified. You can post and reply now.", "ok");
      setTimeout(() => location.href = "feed.html", 350);
    } catch (error) {
      setMessage("[data-verify-message]", error.message, "error");
    }
  }));

  $("[data-request-verification]")?.addEventListener("click", async () => {
    try {
      const result = await api("/api/auth/request-verification", { method: "POST", body: "{}" });
      setMessage("[data-verify-message]", result.already_verified ? "Your email is already verified." : `Verification email sent to ${result.email || "your address"}.`, "ok");
    } catch (error) {
      setMessage("[data-verify-message]", error.message, "error");
    }
  });

  $("[data-resend-verification]")?.addEventListener("click", async () => {
    const email = state.pendingVerificationEmail || $("#register-email")?.value || $("#login-email")?.value || "";
    try {
      const result = await api("/api/auth/resend-verification", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setMessage("[data-verify-message]", result.sent ? `Verification email resent to ${result.email || email}. Check spam or school mail filters if it does not arrive.` : result.message, "ok");
    } catch (error) {
      setMessage("[data-verify-message]", error.message, "error");
    }
  });

  $all("[data-reset-request-form]").forEach((resetRequestForm) => resetRequestForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api("/api/auth/request-password-reset", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form))) });
      setMessage("[data-reset-message]", "If that account exists, a reset code has been emailed.", "ok");
    } catch (error) {
      setMessage("[data-reset-message]", error.message, "error");
    }
  }));

  $all("[data-reset-form]").forEach((resetForm) => resetForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api("/api/auth/reset-password", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form))) });
      form.reset();
      setMessage("[data-reset-message]", "Password updated. Sign in with the new password.", "ok");
    } catch (error) {
      setMessage("[data-reset-message]", error.message, "error");
    }
  }));
}

function renderSettings() {
  if (document.body.dataset.page !== "settings") return;
  const guest = $("[data-settings-guest]");
  const form = $("[data-settings-form]");
  if (!guest || !form) return;
  guest.classList.toggle("hidden", Boolean(state.user));
  form.classList.toggle("hidden", !state.user);
  if (!state.user) return;
  $("#settings-name").value = state.user.name || "";
  $("#settings-title").value = state.user.profile_title || "";
  $("#settings-bio").value = state.user.bio || "";
  setAvatarPreview($("[data-settings-avatar-preview]"), state.user.avatar_path || "");
  const removeAvatar = $("[data-remove-avatar]");
  if (removeAvatar) removeAvatar.classList.toggle("hidden", !state.user.avatar_path);
  const avatarInput = $("[data-avatar-input]");
  if (avatarInput) avatarInput.value = "";
  setStaticSelectValue($("[data-settings-role]"), state.user.role || "student");
  setStaticSelectValue($("[data-settings-visibility]"), state.user.profile_visibility || "school");
  renderThemeChoiceGrid();
  setStaticSelectValue($("[data-theme-mode-select]"), storedThemeMode());
  updateThemePreviewState(storedColorTheme());
  $("[name='show_school']", form).checked = Boolean(state.user.show_school);
  $("[name='show_email']", form).checked = Boolean(state.user.show_email);
  $("[name='email_replies']", form).checked = Boolean(state.user.email_replies);
  $("[name='email_digest']", form).checked = Boolean(state.user.email_digest);
  const schoolMeta = [state.user.institution, state.user.institution_country, state.user.institution_domain].filter(Boolean).join(" · ");
  const currentSchool = $("[data-current-school]");
  if (currentSchool) currentSchool.textContent = `Current school: ${schoolMeta || "None selected"}`;
  $all("[data-section-save]", form).forEach((node) => node.classList.add("hidden"));
}

function updateThemePreviewState(activeTheme = storedColorTheme()) {
  const selected = validColorTheme(activeTheme);
  $all("[data-color-theme-option]").forEach((button) => {
    button.classList.toggle("active", button.dataset.colorThemeOption === selected);
    button.setAttribute("aria-pressed", button.dataset.colorThemeOption === selected ? "true" : "false");
  });
}

function previewColorsForTheme(theme, mode = document.documentElement.dataset.theme || "light") {
  return mode === "dark" && theme.darkColors ? theme.darkColors : theme.colors;
}

function renderThemeChoiceGrid() {
  const grid = $("[data-color-theme-grid]");
  if (!grid) return;
  const previewMode = document.documentElement.dataset.theme || resolveTheme(storedThemeMode());
  if (grid.dataset.rendered === "true" && grid.dataset.previewMode === previewMode) {
    updateThemePreviewState(storedColorTheme());
    return;
  }
  grid.innerHTML = COLOR_THEMES.map((theme) => {
    const colors = previewColorsForTheme(theme, previewMode);
    return `
      <button class="theme-choice-card" type="button" data-color-theme-option="${theme.id}" aria-pressed="false">
        <span class="theme-preview-window" aria-hidden="true" style="border-color:${colors[3]}">
          <span class="theme-preview-bar" style="background:${colors[1]}"></span>
          <span class="theme-preview-body" style="background:${colors[0]}">
            <span class="theme-preview-line strong" style="background:${colors[1]}"></span>
            <span class="theme-preview-line" style="background:${colors[3]}"></span>
            <span class="theme-preview-line short" style="background:${colors[2]}"></span>
          </span>
        </span>
        <span class="theme-choice-name">${theme.label}</span>
      </button>
    `;
  }).join("");
  grid.dataset.rendered = "true";
  grid.dataset.previewMode = previewMode;
  updateThemePreviewState(storedColorTheme());
}

function installAppearanceControls() {
  if (document.body.dataset.page !== "settings") return;
  renderThemeChoiceGrid();
  setStaticSelectValue($("[data-theme-mode-select]"), storedThemeMode());
  $("#settings-theme-mode")?.addEventListener("change", (event) => {
    applyTheme(event.target.value, storedColorTheme());
    toast("Theme mode updated.");
  });
  $("[data-color-theme-grid]")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-color-theme-option]");
    if (!button) return;
    applyTheme(storedThemeMode(), button.dataset.colorThemeOption);
    toast(`${button.querySelector(".theme-choice-name")?.textContent || "Theme"} applied.`);
  });
}

function installSettings() {
  const form = $("[data-settings-form]");
  if (!form) return;
  let pendingAvatarData = "";
  let pendingAvatarName = "";
  let removeAvatar = false;

  function setSectionMessage(saveArea, message, type = "") {
    const node = $("[data-settings-message]", saveArea);
    if (!node) return;
    node.textContent = message;
    node.className = `form-message ${type}`.trim();
  }

  function showSectionSave(target) {
    const panel = target.closest("[data-settings-section]");
    const saveArea = panel ? $("[data-section-save]", panel) : null;
    if (!saveArea) return;
    saveArea.classList.remove("hidden");
    setSectionMessage(saveArea, "", "");
  }

  form.addEventListener("input", (event) => showSectionSave(event.target));
  form.addEventListener("change", (event) => showSectionSave(event.target));

  $("[data-avatar-input]")?.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast("Choose an image file for your profile picture.");
      event.target.value = "";
      return;
    }
    const upload = await readUploadFile(file);
    pendingAvatarData = upload.file_data;
    pendingAvatarName = upload.file_name;
    removeAvatar = false;
    setAvatarPreview($("[data-settings-avatar-preview]"), pendingAvatarData);
    $("[data-remove-avatar]")?.classList.remove("hidden");
    showSectionSave(event.target);
  });

  $("[data-remove-avatar]")?.addEventListener("click", (event) => {
    pendingAvatarData = "";
    pendingAvatarName = "";
    removeAvatar = true;
    const input = $("[data-avatar-input]");
    if (input) input.value = "";
    setAvatarPreview($("[data-settings-avatar-preview]"), "");
    event.currentTarget.classList.add("hidden");
    showSectionSave(event.currentTarget);
  });

  $all("[data-save-settings]").forEach((button) => button.addEventListener("click", async (event) => {
    event.preventDefault();
    const saveArea = event.currentTarget.closest("[data-section-save]");
    try {
      const data = {
        name: $("#settings-name").value,
        profile_title: $("#settings-title").value,
        role: $("#settings-role").value,
        bio: $("#settings-bio").value,
        profile_visibility: $("#settings-visibility").value,
        show_school: $("[name='show_school']", form).checked,
        show_email: $("[name='show_email']", form).checked,
        email_replies: $("[name='email_replies']", form).checked,
        email_digest: $("[name='email_digest']", form).checked,
      };
      if (pendingAvatarData) {
        data.avatar_file_data = pendingAvatarData;
        data.avatar_file_name = pendingAvatarName;
      }
      if (removeAvatar) data.remove_avatar = true;
      const result = await api("/api/settings", { method: "POST", body: JSON.stringify(data) });
      state.user = result.user;
      pendingAvatarData = "";
      pendingAvatarName = "";
      removeAvatar = false;
      updateAuthUI();
      renderSettings();
      if (saveArea) {
        saveArea.classList.remove("hidden");
        setSectionMessage(saveArea, "Saved.", "ok");
        setTimeout(() => saveArea.classList.add("hidden"), 1200);
      }
    } catch (error) {
      if (saveArea) setSectionMessage(saveArea, error.message, "error");
      else toast(error.message);
    }
  }));

  $("[data-change-school-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const schoolForm = event.currentTarget;
    try {
      const data = Object.fromEntries(new FormData(schoolForm));
      if (!data.curricula) {
        throw new Error("Choose your new school from the suggestions so Studera can apply the right curriculum.");
      }
      const result = await api("/api/settings/school", { method: "POST", body: JSON.stringify(data) });
      state.user = result.user;
      updateAuthUI();
      setCurriculumOptions(state.user.curricula || []);
      renderSettings();
      schoolForm.reset();
      $all("input[type='hidden']", schoolForm).forEach((input) => { input.value = ""; });
      setMessage("[data-school-change-message]", "School changed. Your forum view now follows the new school.", "ok");
      toast("School changed.");
    } catch (error) {
      setMessage("[data-school-change-message]", error.message, "error");
    }
  });

  $("[data-delete-account-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const deleteForm = event.currentTarget;
    if (!confirm("Permanently delete this account and its content?")) return;
    try {
      await api("/api/settings/delete-account", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(deleteForm))),
      });
      state.user = null;
      updateAuthUI();
      toast("Account deleted.");
      location.href = "index.html";
    } catch (error) {
      setMessage("[data-delete-account-message]", error.message, "error");
    }
  });
}

async function renderAdmin() {
  if (document.body.dataset.page !== "admin") return;
  const guest = $("[data-admin-guest]");
  const denied = $("[data-admin-denied]");
  const dashboard = $("[data-admin-dashboard]");
  if (!guest || !denied || !dashboard) return;
  guest.classList.toggle("hidden", Boolean(state.user));
  denied.classList.toggle("hidden", !state.user || Boolean(state.user.is_school_admin));
  dashboard.classList.toggle("hidden", !state.user?.is_school_admin);
  if (!state.user?.is_school_admin) return;
  try {
    const [data, reportData, auditData] = await Promise.all([
      api("/api/admin/school"),
      api("/api/admin/reports").catch(() => ({ reports: [] })),
      api("/api/admin/audit").catch(() => ({ logs: [] })),
    ]);
    const school = data.school;
    $("[data-admin-school-name]").textContent = school.institution || state.user.institution;
    $("[data-admin-school-meta]").textContent = [
      school.institution_country,
      school.institution_domain,
      school.has_join_key ? `Join key: ${school.join_key || "active"}` : "No join key set",
    ].filter(Boolean).join(" · ");
    const curriculumBox = $("[data-admin-curricula]");
    if (curriculumBox) {
      const selected = new Set(school.curricula || []);
      curriculumBox.innerHTML = ALL_CURRICULA.map((curriculum) => `
        <label class="check-card">
          <input type="checkbox" name="curricula" value="${escapeHtml(curriculum)}" ${selected.has(curriculum) ? "checked" : ""} />
          <span>${escapeHtml(curriculum)}</span>
        </label>
      `).join("");
    }
    renderCustomCurriculaEditor(school.custom_curricula || []);
    $("#admin-guidelines").value = school.guidelines || "";
    $("#admin-join-key").value = "";
    const joinPreview = $("[data-admin-join-preview]");
    if (joinPreview) joinPreview.textContent = school.has_join_key ? `Current join key: ${school.join_key || "hidden"}` : "No join key is currently required.";
    const members = $("[data-admin-members]");
    if (members) {
      members.innerHTML = data.members.map((member) => `
        <article class="admin-row">
          <div>
            <strong>${escapeHtml(member.name)}</strong>
            <span>${escapeHtml(member.email)} · ${escapeHtml(member.role)}</span>
          </div>
          <div class="admin-row-actions">
            ${member.is_school_admin ? `<span class="badge teacher">Admin</span>` : `<span class="badge student">Member</span>`}
            ${member.is_school_admin && member.email !== state.user.email ? `<button class="text-action danger" type="button" data-admin-revoke="${escapeHtml(member.email)}">Revoke Admin</button>` : ""}
            ${member.email !== state.user.email ? `<button class="text-action danger" type="button" data-admin-delete-member="${escapeHtml(member.email)}" data-admin-delete-name="${escapeHtml(member.name)}">Delete Account</button>` : ""}
          </div>
        </article>
      `).join("");
    }
    const threads = $("[data-admin-threads]");
    if (threads) {
      threads.innerHTML = data.threads.length ? data.threads.map((thread) => `
        <article class="admin-row">
          <div>
            <strong>${escapeHtml(thread.title)}</strong>
            <span>${escapeHtml(thread.section)} · ${escapeHtml(thread.author_name)} · ${thread.replies} replies · ${escapeHtml(thread.created_at)}</span>
          </div>
          <div class="admin-row-actions">
            <a class="text-action" href="thread.html?id=${thread.id}">Open</a>
            <button class="text-action danger" type="button" data-admin-delete-thread="${thread.id}">Delete</button>
          </div>
        </article>
      `).join("") : `<p class="upload-empty">No school threads yet.</p>`;
    }
    const reports = $("[data-admin-reports]");
    if (reports) {
      reports.innerHTML = reportData.reports.length ? reportData.reports.map((report) => `
        <article class="admin-row report-row">
          <div>
            <strong>${escapeHtml(report.target_type)} report · ${escapeHtml(report.status)}</strong>
            <span>${escapeHtml(report.thread_title)} · reported by ${escapeHtml(report.reporter_name)} · ${escapeHtml(report.created_at)}</span>
            <small>${escapeHtml(report.reason)}${report.reply_body ? ` · Reply: ${escapeHtml(report.reply_body.slice(0, 140))}` : ""}</small>
          </div>
          <div class="admin-row-actions">
            <a class="text-action" href="thread.html?id=${report.thread_id}">Review</a>
            <button class="text-action" type="button" data-report-status="${report.id}" data-status="reviewing">Reviewing</button>
            <button class="text-action" type="button" data-report-status="${report.id}" data-status="resolved">Resolve</button>
            <button class="text-action" type="button" data-report-status="${report.id}" data-status="dismissed">Dismiss</button>
          </div>
        </article>
      `).join("") : `<p class="upload-empty">No reports in the moderation queue.</p>`;
    }
    const audit = $("[data-admin-audit]");
    if (audit) {
      audit.innerHTML = `
        ${renderAuditGroups(auditData.logs, { limit: 5, empty: "No admin actions recorded yet." })}
        <a class="button secondary audit-more" href="${auditLink("school")}">View Full Audit Log</a>
      `;
    }
  } catch (error) {
    setMessage("[data-admin-message]", error.message, "error");
  }
}

function customCurriculumRow(item = {}) {
  const sections = Array.isArray(item.sections) ? item.sections.join("\n") : "";
  return `
    <article class="custom-curriculum-row" data-custom-curriculum-row>
      <div class="form-grid">
        <div class="field">
          <label>Curriculum Name</label>
          <input name="custom_curriculum_name" type="text" value="${escapeHtml(item.name || "")}" placeholder="Independent Research Program" />
        </div>
        <div class="field wide">
          <label>Classes / Sections</label>
          <textarea name="custom_curriculum_sections" rows="4" placeholder="One class per line">${escapeHtml(sections)}</textarea>
        </div>
      </div>
      <button class="text-action danger" type="button" data-remove-custom-curriculum>Remove custom curriculum</button>
    </article>
  `;
}

function renderCustomCurriculaEditor(items) {
  const list = $("[data-custom-curricula]");
  if (!list) return;
  list.innerHTML = (items && items.length ? items : []).map(customCurriculumRow).join("");
  if (!list.innerHTML) list.innerHTML = `<p class="upload-empty">No custom curricula yet.</p>`;
}

function collectCustomCurricula(form) {
  return $all("[data-custom-curriculum-row]", form).map((row) => {
    const name = $("input[name='custom_curriculum_name']", row)?.value.trim() || "";
    const sections = ($("textarea[name='custom_curriculum_sections']", row)?.value || "")
      .split(/\n|,/)
      .map((section) => section.trim())
      .filter(Boolean);
    return { name, sections };
  }).filter((item) => item.name && item.sections.length);
}

function installAdmin() {
  if (document.body.dataset.page !== "admin") return;
  $("[data-admin-school-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const curricula = $all("input[name='curricula']:checked", form).map((input) => input.value);
    try {
      await api("/api/admin/school", {
        method: "POST",
        body: JSON.stringify({
          curricula,
          custom_curricula: collectCustomCurricula(form),
          join_key: form.elements.join_key.value,
          clear_join_key: Boolean(form.elements.clear_join_key?.checked),
          regenerate_join_key: Boolean(form.elements.regenerate_join_key?.checked),
          guidelines: form.elements.guidelines.value,
        }),
      });
      if (form.elements.clear_join_key) form.elements.clear_join_key.checked = false;
      if (form.elements.regenerate_join_key) form.elements.regenerate_join_key.checked = false;
      form.elements.join_key.value = "";
      setMessage("[data-admin-message]", "School settings saved.", "ok");
      await loadSession();
    } catch (error) {
      setMessage("[data-admin-message]", error.message, "error");
    }
  });

  $("[data-add-custom-curriculum]")?.addEventListener("click", () => {
    const list = $("[data-custom-curricula]");
    if (!list) return;
    const empty = $(".upload-empty", list);
    if (empty) empty.remove();
    list.insertAdjacentHTML("beforeend", customCurriculumRow());
    replayPop(list.lastElementChild);
    $("input[name='custom_curriculum_name']", list.lastElementChild)?.focus();
  });

  $("[data-admin-grant-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api("/api/admin/grant", { method: "POST", body: JSON.stringify({ email: form.elements.email.value }) });
      form.reset();
      setMessage("[data-admin-grant-message]", "Admin access granted.", "ok");
      await renderAdmin();
    } catch (error) {
      setMessage("[data-admin-grant-message]", error.message, "error");
    }
  });

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-admin-delete-thread]");
    const reportStatus = event.target.closest("[data-report-status]");
    const exportButton = event.target.closest("[data-admin-export]");
    const revokeAdmin = event.target.closest("[data-admin-revoke]");
    const deleteMember = event.target.closest("[data-admin-delete-member]");
    const removeCustom = event.target.closest("[data-remove-custom-curriculum]");
    if (removeCustom) {
      const row = removeCustom.closest("[data-custom-curriculum-row]");
      row?.remove();
      if (!$("[data-custom-curriculum-row]") && $("[data-custom-curricula]")) {
        $("[data-custom-curricula]").innerHTML = `<p class="upload-empty">No custom curricula yet.</p>`;
      }
      return;
    }
    if (revokeAdmin) {
      if (!confirm("Remove school admin access for this account?")) return;
      try {
        await api("/api/admin/revoke", { method: "POST", body: JSON.stringify({ email: revokeAdmin.dataset.adminRevoke }) });
        toast("Admin access revoked.");
        await renderAdmin();
      } catch (error) {
        toast(error.message);
      }
      return;
    }
    if (deleteMember) {
      const email = deleteMember.dataset.adminDeleteMember;
      const name = deleteMember.dataset.adminDeleteName || email;
      openDangerConfirmModal({
        title: "Delete Member Account",
        eyebrow: "Member Deletion",
        message: `This will permanently delete ${name}'s account and remove their threads, replies, sessions, reports, bookmarks, and supports from your school archive.`,
        submitLabel: "Delete Account",
        onSubmit: async (data) => {
          await api("/api/admin/members/delete", {
            method: "POST",
            body: JSON.stringify({ email, confirm: data.confirm }),
          });
          toast("Member account deleted.");
          await renderAdmin();
        },
      });
      return;
    }
    if (reportStatus) {
      try {
        await api("/api/admin/reports/status", {
          method: "POST",
          body: JSON.stringify({ id: reportStatus.dataset.reportStatus, status: reportStatus.dataset.status }),
        });
        toast("Report updated.");
        await renderAdmin();
      } catch (error) {
        toast(error.message);
      }
      return;
    }
    if (exportButton) {
      try {
        const data = await api("/api/admin/export");
        downloadJson(`studera-${(data.school || "school").replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-archive.json`, data);
        toast("School archive exported.");
      } catch (error) {
        toast(error.message);
      }
      return;
    }
    if (!button) return;
    if (!confirm("Delete this school thread and all replies?")) return;
    try {
      await api(`/api/threads/${button.dataset.adminDeleteThread}`, { method: "DELETE" });
      toast("Thread deleted.");
      await renderAdmin();
    } catch (error) {
      toast(error.message);
    }
  });
}

function renderMetricCards(totals = {}) {
  const node = $("[data-site-metrics]");
  if (!node) return;
  const metrics = [
    ["Schools", totals.schools || 0],
    ["Members", totals.members || 0],
    ["School Admins", totals.school_admins || 0],
    ["Site Admins", totals.site_admins || 0],
    ["Threads", totals.threads || 0],
  ];
  node.innerHTML = metrics.map(([label, value]) => `
    <article class="metric-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </article>
  `).join("");
}

async function renderSiteAdmin() {
  if (document.body.dataset.page !== "site-admin") return;
  const guest = $("[data-site-admin-guest]");
  const denied = $("[data-site-admin-denied]");
  const dashboard = $("[data-site-admin-dashboard]");
  if (!guest || !denied || !dashboard) return;
  guest.classList.toggle("hidden", Boolean(state.user));
  denied.classList.toggle("hidden", !state.user || Boolean(state.user.is_site_admin));
  dashboard.classList.toggle("hidden", !state.user?.is_site_admin);
  if (!state.user?.is_site_admin) return;
  try {
    const [data, auditData] = await Promise.all([
      api("/api/site-admin"),
      api("/api/site-admin/audit").catch(() => ({ logs: [] })),
    ]);
    renderMetricCards(data.totals);
    const privacy = $("[data-site-privacy]");
    if (privacy) {
      privacy.innerHTML = `
        <article class="admin-row">
          <div>
            <strong>Forum Access</strong>
            <span>${escapeHtml(data.privacy?.forum_access || "blocked")}</span>
          </div>
          <span class="badge teacher">Locked</span>
        </article>
        <article class="admin-row">
          <div>
            <strong>Thread Content</strong>
            <span>${escapeHtml(data.privacy?.thread_content || "not available")}</span>
          </div>
          <span class="badge student">Private</span>
        </article>
        <article class="admin-row">
          <div>
            <strong>Allowed Scope</strong>
            <span>${escapeHtml(data.privacy?.scope || "aggregate administration only")}</span>
          </div>
        </article>
      `;
    }
    const curriculumBox = $("[data-site-school-curricula]");
    if (curriculumBox) {
      curriculumBox.innerHTML = ALL_CURRICULA.map((curriculum) => `
        <label class="check-card">
          <input type="checkbox" name="curricula" value="${escapeHtml(curriculum)}" checked />
          <span>${escapeHtml(curriculum)}</span>
        </label>
      `).join("");
    }
    const grantCurricula = $("[data-site-grant-curricula]");
    if (grantCurricula) {
      grantCurricula.innerHTML = ALL_CURRICULA.map((curriculum) => `
        <label class="check-card">
          <input type="checkbox" name="grant_curricula" value="${escapeHtml(curriculum)}" checked />
          <span>${escapeHtml(curriculum)}</span>
        </label>
      `).join("");
    }
    const schools = $("[data-site-schools]");
    if (schools) {
      schools.innerHTML = data.schools.length ? data.schools.map((school) => `
        <article class="admin-row site-school-row">
          <div>
            <strong>${escapeHtml(school.institution)}</strong>
            <span>${[
              school.institution_country,
              school.institution_domain,
              `${school.member_count} members`,
              `${school.school_admin_count} admins`,
              `${school.thread_count} threads`,
              school.has_join_key ? "join key active" : "no join key",
            ].filter(Boolean).map(escapeHtml).join(" · ")}</span>
            <small>${escapeHtml((school.curricula || []).join(", "))}</small>
          </div>
          <button class="text-action" type="button"
            data-site-load-school="${escapeHtml(school.institution)}"
            data-country="${escapeHtml(school.institution_country)}"
            data-domain="${escapeHtml(school.institution_domain)}"
            data-curricula="${escapeHtml((school.curricula || []).join("|"))}"
            data-guidelines="${escapeHtml(school.guidelines || "")}">Edit</button>
        </article>
      `).join("") : `<p class="upload-empty">No schools registered yet.</p>`;
    }
    const schoolAdmins = $("[data-site-school-admins]");
    if (schoolAdmins) {
      schoolAdmins.innerHTML = data.school_admins.length ? data.school_admins.map((admin) => `
        <article class="admin-row">
          <div>
            <strong>${escapeHtml(admin.name)}</strong>
            <span>${escapeHtml(admin.email)} · ${escapeHtml(admin.institution)}${admin.institution_domain ? ` · ${escapeHtml(admin.institution_domain)}` : ""}</span>
          </div>
          <button class="text-action danger" type="button" data-site-revoke-school-admin="${escapeHtml(admin.email)}">Revoke</button>
        </article>
      `).join("") : `<p class="upload-empty">No school admins yet.</p>`;
    }
    const siteAdmins = $("[data-site-site-admins]");
    if (siteAdmins) {
      siteAdmins.innerHTML = data.site_admins.map((admin) => `
        <article class="admin-row">
          <div>
            <strong>${escapeHtml(admin.name)}</strong>
            <span>${escapeHtml(admin.email)} · ${escapeHtml(admin.created_at)}</span>
          </div>
          ${admin.is_self ? `<span class="badge teacher">You</span>` : `<button class="text-action danger" type="button" data-site-revoke-site-admin="${escapeHtml(admin.email)}">Revoke</button>`}
        </article>
      `).join("");
    }
    const audit = $("[data-site-audit]");
    if (audit) {
      const platformLogs = auditData.platform_logs || auditData.logs || [];
      audit.innerHTML = `
        ${renderAuditGroups(platformLogs, { limit: 5, empty: "No overarching admin actions recorded yet." })}
        <a class="button secondary audit-more" href="${auditLink("site")}">View Full Audit Log</a>
      `;
    }
  } catch (error) {
    setMessage("[data-site-admin-message]", error.message, "error");
  }
}

function installSiteAdmin() {
  if (document.body.dataset.page !== "site-admin") return;
  $("[data-site-school-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const curricula = $all("input[name='curricula']:checked", form).map((input) => input.value);
    try {
      await api("/api/site-admin/schools", {
        method: "POST",
        body: JSON.stringify({
          institution: form.elements.institution.value,
          institution_country: form.elements.institution_country.value,
          institution_domain: form.elements.institution_domain.value,
          curricula,
          join_key: form.elements.join_key.value,
          clear_join_key: form.elements.clear_join_key.checked,
          regenerate_join_key: Boolean(form.elements.regenerate_join_key?.checked),
          guidelines: form.elements.guidelines.value,
        }),
      });
      form.elements.join_key.value = "";
      form.elements.clear_join_key.checked = false;
      if (form.elements.regenerate_join_key) form.elements.regenerate_join_key.checked = false;
      setMessage("[data-site-school-message]", "School saved.", "ok");
      await renderSiteAdmin();
    } catch (error) {
      setMessage("[data-site-school-message]", error.message, "error");
    }
  });

  $("[data-site-grant-school-admin-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const curricula = $all("input[name='grant_curricula']:checked", form).map((input) => input.value);
    try {
      await api("/api/site-admin/school-admins", {
        method: "POST",
        body: JSON.stringify({
          email: form.elements.email.value,
          institution: form.elements.institution.value,
          institution_country: form.elements.institution_country.value,
          institution_domain: form.elements.institution_domain.value,
          curricula,
        }),
      });
      setMessage("[data-site-grant-message]", "School admin granted.", "ok");
      await renderSiteAdmin();
    } catch (error) {
      setMessage("[data-site-grant-message]", error.message, "error");
    }
  });

  $("[data-site-grant-site-admin-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api("/api/site-admin/site-admins", { method: "POST", body: JSON.stringify({ email: form.elements.email.value }) });
      form.reset();
      setMessage("[data-site-root-message]", "Site admin granted.", "ok");
      await renderSiteAdmin();
    } catch (error) {
      setMessage("[data-site-root-message]", error.message, "error");
    }
  });

  document.addEventListener("click", async (event) => {
    const loadSchool = event.target.closest("[data-site-load-school]");
    const revokeSchool = event.target.closest("[data-site-revoke-school-admin]");
    const revokeSite = event.target.closest("[data-site-revoke-site-admin]");
    const backup = event.target.closest("[data-site-backup]");
    try {
      if (backup) {
        const data = await api("/api/site-admin/backup");
        downloadJson(`studera-platform-backup-${Date.now()}.json`, data);
        toast("Platform backup exported without thread bodies.");
        return;
      }
      if (loadSchool) {
        const form = $("[data-site-school-form]");
        form.elements.institution.value = loadSchool.dataset.siteLoadSchool || "";
        form.elements.institution.dataset.selectedSchool = loadSchool.dataset.siteLoadSchool || "";
        form.elements.institution_country.value = loadSchool.dataset.country || "";
        form.elements.institution_domain.value = loadSchool.dataset.domain || "";
        form.elements.guidelines.value = loadSchool.dataset.guidelines || "";
        const selected = new Set((loadSchool.dataset.curricula || "").split("|").filter(Boolean));
        $all("input[name='curricula']", form).forEach((input) => {
          input.checked = selected.has(input.value);
        });
        location.hash = "schools";
      }
      if (revokeSchool) {
        if (!confirm("Remove school admin access for this account?")) return;
        await api("/api/site-admin/school-admins/revoke", { method: "POST", body: JSON.stringify({ email: revokeSchool.dataset.siteRevokeSchoolAdmin }) });
        toast("School admin access revoked.");
        await renderSiteAdmin();
      }
      if (revokeSite) {
        if (!confirm("Remove site admin access for this account?")) return;
        await api("/api/site-admin/site-admins/revoke", { method: "POST", body: JSON.stringify({ email: revokeSite.dataset.siteRevokeSiteAdmin }) });
        toast("Site admin access revoked.");
        await renderSiteAdmin();
      }
    } catch (error) {
      toast(error.message);
    }
  });
}

function installCustomSelects() {
  $all("[data-static-select]").forEach((wrapper) => {
    const alreadyEnhanced = wrapper.dataset.enhanced === "true";
    const input = $("input[type='hidden']", wrapper);
    const button = $(".custom-select-button", wrapper);
    const options = $all(".custom-option", wrapper);

    options.forEach((option) => {
      if (option.dataset.bound === "true") return;
      option.dataset.bound = "true";
      option.addEventListener("click", () => {
        if (option.disabled) return;
        input.value = option.dataset.value;
        input.dataset.curriculum = option.dataset.curriculum || "";
        button.textContent = option.dataset.label || option.textContent.trim();
        if (wrapper.matches("[data-section-select]")) {
          const choice = decodeSectionChoice(option.dataset.value);
          const curriculumInput = $("#thread-curriculum");
          if (curriculumInput && choice.curriculum) curriculumInput.value = choice.curriculum;
        }
        options.forEach((item) => item.classList.toggle("active", item === option));
        wrapper.classList.remove("open");
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
    });

    if (!alreadyEnhanced) {
      button.addEventListener("click", () => {
        $all(".custom-select.open").forEach((node) => {
          if (node !== wrapper) node.classList.remove("open");
        });
        wrapper.classList.toggle("open");
      });
      wrapper.dataset.enhanced = "true";
    }
  });

  if (installCustomSelects.documentBound !== "true") {
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".custom-select")) {
        $all(".custom-select.open").forEach((node) => node.classList.remove("open"));
      }
    });
    installCustomSelects.documentBound = "true";
  }
}

function setStaticSelectValue(wrapper, value) {
  if (!wrapper) return;
  const input = $("input[type='hidden']", wrapper);
  const button = $(".custom-select-button", wrapper);
  const options = $all(".custom-option", wrapper);
  const target = options.find((option) => option.dataset.value === value) || options.find((option) => !option.disabled);
  if (!input || !button || !target) return;
  input.value = target.dataset.value;
  input.dataset.curriculum = target.dataset.curriculum || "";
  button.textContent = target.dataset.label || target.textContent.trim();
  if (wrapper.matches("[data-section-select]")) {
    const choice = decodeSectionChoice(target.dataset.value);
    const curriculumInput = $("#thread-curriculum");
    if (curriculumInput && choice.curriculum) curriculumInput.value = choice.curriculum;
  }
  options.forEach((item) => item.classList.toggle("active", item === target));
}

function setCustomSections(customCurricula) {
  Object.keys(customSectionsByCurriculum).forEach((key) => delete customSectionsByCurriculum[key]);
  (customCurricula || []).forEach((item) => {
    const name = String(item.name || "").trim();
    const sections = Array.isArray(item.sections) ? item.sections.map((section) => String(section || "").trim()).filter(Boolean) : [];
    if (name && sections.length) customSectionsByCurriculum[name] = sections;
  });
}

function sectionsForCurriculum(curriculum) {
  return customSectionsByCurriculum[curriculum] || SECTIONS_BY_CURRICULUM[curriculum] || [];
}

function encodeSectionChoice(curriculum, section) {
  return `${curriculum}${SECTION_CHOICE_SEPARATOR}${section}`;
}

function decodeSectionChoice(value) {
  const text = String(value || "");
  if (!text.includes(SECTION_CHOICE_SEPARATOR)) return { curriculum: "", section: text };
  const [curriculum, ...sectionParts] = text.split(SECTION_CHOICE_SEPARATOR);
  return { curriculum, section: sectionParts.join(SECTION_CHOICE_SEPARATOR) };
}

function composerCurriculaForSections() {
  const allowed = allowedCurricula();
  if (state.filter && allowed.includes(state.filter)) return [state.filter];
  return allowed;
}

function composerSectionChoices() {
  const curricula = composerCurriculaForSections();
  const rawChoices = [];
  const sectionCounts = new Map();

  curricula.forEach((curriculum) => {
    sectionsForCurriculum(curriculum).forEach((section) => {
      if (!section) return;
      rawChoices.push({ curriculum, section });
      sectionCounts.set(section, (sectionCounts.get(section) || 0) + 1);
    });
  });

  const seen = new Set();
  return rawChoices.filter((choice) => {
    const key = encodeSectionChoice(choice.curriculum, choice.section);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).map((choice) => {
    const needsCurriculumLabel = curricula.length > 1 && sectionCounts.get(choice.section) > 1;
    return {
      ...choice,
      label: needsCurriculumLabel ? `${choice.section} · ${choice.curriculum}` : choice.section,
      value: encodeSectionChoice(choice.curriculum, choice.section),
    };
  });
}

function uniqueSectionsForAllowedCurricula() {
  const curricula = state.filter ? [state.filter] : allowedCurricula();
  const seen = new Set();
  curricula.forEach((curriculum) => {
    sectionsForCurriculum(curriculum).forEach((section) => {
      if (section) seen.add(section);
    });
  });
  return Array.from(seen);
}

function updateClassFilterOptions() {
  const wrapper = $("[data-class-filter]");
  const menu = $("[data-class-filter-menu]");
  if (!wrapper || !menu) return;
  const input = $("#feed-section");
  const current = input?.value || "";
  const sections = uniqueSectionsForAllowedCurricula();
  menu.innerHTML = [
    `<button class="custom-option active" type="button" data-value="">All Classes</button>`,
    ...sections.map((section) => `<button class="custom-option" type="button" data-value="${escapeHtml(section)}">${escapeHtml(section)}</button>`),
  ].join("");
  installCustomSelects();
  setStaticSelectValue(wrapper, sections.includes(current) ? current : "");
}

function updateSectionOptions() {
  const wrapper = $("[data-section-select]");
  const menu = $("[data-section-menu]");
  if (!wrapper || !menu) return;
  const input = $("#thread-section");
  const current = input?.value || "";
  const currentDecoded = decodeSectionChoice(current);
  const choices = composerSectionChoices();
  const selectedValue = choices.some((choice) => choice.value === current)
    ? current
    : choices.find((choice) => choice.section === currentDecoded.section)?.value || choices[0]?.value || "";

  menu.innerHTML = choices.map((choice, index) => (
    `<button class="custom-option ${choice.value === selectedValue || (!selectedValue && index === 0) ? "active" : ""}" type="button" data-value="${escapeHtml(choice.value)}" data-curriculum="${escapeHtml(choice.curriculum)}" data-label="${escapeHtml(choice.label)}">${escapeHtml(choice.label)}</button>`
  )).join("");
  setStaticSelectValue(wrapper, selectedValue);
  installCustomSelects();
}

function allowedCurricula() {
  return state.user?.curricula?.length ? state.user.curricula : ALL_CURRICULA;
}

function composerCurriculum() {
  const allowed = allowedCurricula();
  if (state.filter && allowed.includes(state.filter)) return state.filter;
  return allowed[0] || "AP Curriculum";
}

function syncComposerCurriculum() {
  const input = $("#thread-curriculum");
  if (!input) return;
  const curriculum = composerCurriculum();
  input.value = curriculum;
  updateSectionOptions();
}

function renderCurriculumFilters(allowedList) {
  const values = ["", ...allowedList];
  $all(".filter-list").forEach((list) => {
    const isThreadPage = document.body.dataset.page === "thread" || list.querySelector("a");
    list.innerHTML = values.map((value, index) => {
      const label = index === 0 ? "All Threads" : value;
      const active = value === state.filter || (!value && !state.filter);
      if (isThreadPage) {
        const href = value ? `feed.html?curriculum=${encodeURIComponent(value)}` : "feed.html";
        return `<a class="filter-item ${active ? "active" : ""}" data-curriculum="${escapeHtml(value)}" href="${href}">${escapeHtml(label)}</a>`;
      }
      return `<button class="filter-item ${active ? "active" : ""}" data-curriculum="${escapeHtml(value)}" type="button">${escapeHtml(label)}</button>`;
    }).join("");
  });
}

function setCurriculumOptions(allowed) {
  const allowedList = allowed && allowed.length ? allowed : ALL_CURRICULA;
  const allowSet = new Set(allowedList);
  renderCurriculumFilters(allowedList);
  updateClassFilterOptions();

  $all("[data-curriculum]").forEach((button) => {
    const value = button.dataset.curriculum;
    const visible = !state.user || !value || allowSet.has(value);
    button.classList.toggle("hidden", !visible);
  });

  if (state.user && state.filter && !allowSet.has(state.filter)) {
    state.filter = allowedList[0] || "";
    $all("[data-curriculum]").forEach((button) => button.classList.toggle("active", button.dataset.curriculum === state.filter));
    if (document.body.dataset.page === "feed") loadThreads();
  }
  syncComposerCurriculum();
  updateClassFilterOptions();
}

function installInstitutionAutocomplete() {
  const roots = $all("[data-institution-autocomplete]");
  if (!roots.length) return;

  async function searchSchools(query) {
    if (state.schoolAbort) state.schoolAbort.abort();
    state.schoolAbort = new AbortController();
    const response = await fetch(`/api/institutions?q=${encodeURIComponent(query)}`, {
      credentials: "same-origin",
      signal: state.schoolAbort.signal,
    });
    const data = await response.json();
    return data.institutions || [];
  }

  roots.forEach((root) => {
    if (root.dataset.autocompleteBound === "true") return;
    root.dataset.autocompleteBound = "true";
    const input = $("input[name='institution']", root);
    const results = $("[data-institution-results]", root);
    const form = root.closest("form");
    let searchTimer = null;
    let latestQuery = "";
    if (!input || !results || !form) return;

    const countryInput = $("[data-institution-country]", root) || form.elements.institution_country;
    const domainInput = $("[data-institution-domain]", root) || form.elements.institution_domain;
    const hiddenCurricula = $("[data-institution-curricula]", root);
    const curriculaTarget = root.dataset.curriculaTarget || "";

    function setCurriculaValues(rawCurricula) {
      if (hiddenCurricula) hiddenCurricula.value = rawCurricula;
      if (!curriculaTarget) return;
      const selected = new Set(rawCurricula.split("|").filter(Boolean));
      $all(`input[name='${curriculaTarget}']`, form).forEach((checkbox) => {
        checkbox.checked = selected.has(checkbox.value);
      });
    }

    function clearMetadata() {
      if (countryInput) countryInput.value = "";
      if (domainInput) domainInput.value = "";
      setCurriculaValues("");
    }

    function render(items) {
      const shouldKeepTyping = document.activeElement === input;
      const selectionStart = input.selectionStart;
      const selectionEnd = input.selectionEnd;

      results.innerHTML = items.map((school) => `
        <div class="autocomplete-option" role="option" tabindex="-1" data-school="${escapeHtml(school.name)}" data-country="${escapeHtml(school.country || "")}" data-domain="${escapeHtml(school.domain || "")}" data-curricula="${escapeHtml((school.curricula || []).join("|"))}">
          ${escapeHtml(school.name)}
          <span class="autocomplete-meta">${escapeHtml(school.country)}${school.domain ? ` · ${escapeHtml(school.domain)}` : ""}${school.curricula?.length ? ` · ${escapeHtml(school.curricula.join(", "))}` : ""}${school.source ? ` · ${escapeHtml(school.source)}` : ""}</span>
        </div>
      `).join("");
      root.classList.toggle("open", items.length > 0);

      if (shouldKeepTyping) {
        requestAnimationFrame(() => {
          try {
            if (document.activeElement !== input) input.focus({ preventScroll: true });
          } catch {
            input.focus();
          }
          if (typeof selectionStart === "number" && typeof selectionEnd === "number") {
            input.setSelectionRange(selectionStart, selectionEnd);
          }
        });
      }
    }

    input.addEventListener("input", () => {
      const query = input.value.trim();
      latestQuery = query;
      clearTimeout(searchTimer);
      if (input.value !== input.dataset.selectedSchool) {
        input.dataset.selectedSchool = "";
        clearMetadata();
      }
      if (query.length < 1) {
        render([]);
        return;
      }
      searchTimer = setTimeout(async () => {
        try {
          const schools = await searchSchools(query);
          if (latestQuery === query) render(schools);
        } catch (error) {
          if (error.name !== "AbortError" && latestQuery === query) render([]);
        }
      }, 180);
    });

    results.addEventListener("pointerdown", (event) => {
      if (event.target.closest("[data-school]")) event.preventDefault();
    });

    results.addEventListener("pointerup", (event) => {
      const option = event.target.closest("[data-school]");
      if (!option) return;
      event.preventDefault();
      input.value = option.dataset.school;
      if (countryInput) countryInput.value = option.dataset.country || "";
      if (domainInput) domainInput.value = option.dataset.domain || "";
      setCurriculaValues(option.dataset.curricula || "");
      input.dataset.selectedSchool = option.dataset.school;
      render([]);
    });
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest("[data-institution-autocomplete]")) {
      roots.forEach((root) => root.classList.remove("open"));
    }
  });
}

function renderEmptyThreads() {
  const title = state.bookmarkedOnly ? "Nothing bookmarked" : "No threads yet";
  const school = state.user?.institution ? ` at ${state.user.institution}` : "";
  const filter = state.filter ? ` in ${state.filter}` : "";
  const copy = state.bookmarkedOnly
    ? "Saved and authored threads will appear here."
    : `No one has started a thread${school}${filter} yet. Use the composer above when you are ready to begin the archive.`;
  return `
    <section class="empty-state">
      <div>
        <div class="empty-mark">▧</div>
        <h2>${title}</h2>
        <p>${copy}</p>
      </div>
    </section>
  `;
}

function supportCountFromText(value) {
  const match = String(value || "").match(/-?\d+/);
  return match ? Number(match[0]) : 0;
}

function updateThreadSupportButton(button, active) {
  if (!button) return;
  const current = supportCountFromText(button.textContent);
  const wasActive = button.classList.contains("active");
  const next = Math.max(0, current + (active && !wasActive ? 1 : !active && wasActive ? -1 : 0));
  button.classList.toggle("active", active);
  button.textContent = `Support ${next}`;
}

function updateReplySupportButton(button, active) {
  if (!button) return;
  const row = button.closest(".response-row");
  const countNode = row?.querySelector(".vote strong");
  const current = supportCountFromText(countNode?.textContent);
  const wasActive = button.classList.contains("active");
  const next = Math.max(0, current + (active && !wasActive ? 1 : !active && wasActive ? -1 : 0));
  button.classList.toggle("active", active);
  if (countNode) countNode.textContent = String(next);
}

function threadCard(thread) {
  const canDelete = state.user && (state.user.id === thread.author_id || state.user.is_school_admin);
  return `
    <article class="thread-card" data-thread-card="${thread.id}" role="link" tabindex="0" aria-label="Open thread ${escapeHtml(thread.title)}">
      <div class="meta-row">
        <a class="profile-link" href="${profileHref(thread.author_id)}">${escapeHtml(thread.author_name)}</a>
        ${roleBadge(thread.author_role)}
        <span class="badge section">${escapeHtml(thread.section)}</span>
        ${statusBadge(thread.status)}
        <span class="meta">${escapeHtml(thread.created_at)}</span>
      </div>
      <a href="thread.html?id=${thread.id}"><h2>${escapeHtml(thread.title)}</h2></a>
      <div class="action-row" style="margin-top:16px;">
        <button class="text-action ${thread.supported ? "active" : ""}" data-support-thread="${thread.id}" type="button">Support ${thread.supports}</button>
        <span class="meta">${thread.replies} responses</span>
        <button class="text-action ${thread.bookmarked ? "active" : ""}" data-bookmark-thread="${thread.id}" type="button">${thread.bookmarked ? "Bookmarked" : "Bookmark"}</button>
        ${canDelete ? `<button class="text-action danger" data-delete-thread="${thread.id}" type="button">Delete Thread</button>` : ""}
      </div>
    </article>
  `;
}

async function loadThreads() {
  const list = $("[data-thread-list]");
  if (!list) return;
  const params = new URLSearchParams();
  if (state.filter) params.set("curriculum", state.filter);
  if (state.bookmarkedOnly) params.set("bookmarked", "1");
  const q = $("[data-search-form] input")?.value.trim();
  if (q) params.set("q", q);
  const status = $("#feed-status")?.value;
  if (status) params.set("status", status);
  const section = $("#feed-section")?.value;
  if (section) params.set("section", section);
  if ($("[name='teacher_replied']")?.checked) params.set("teacher_replied", "1");
  if ($("[name='has_uploads']")?.checked) params.set("has_uploads", "1");
  const data = await api(`/api/threads?${params.toString()}`);
  state.threads = data.threads;
  list.innerHTML = data.threads.length ? data.threads.map(threadCard).join("") : renderEmptyThreads();
}

function installFeed() {
  if (document.body.dataset.page !== "feed") return;

  setCurriculumOptions(allowedCurricula());
  syncComposerCurriculum();

  $("[data-new-thread]")?.addEventListener("click", () => {
    const composer = $("[data-thread-composer]");
    composer?.classList.add("is-open");
    syncComposerCurriculum();
    composer?.scrollIntoView({ behavior: "smooth", block: "start" });
    window.requestAnimationFrame(() => $("#thread-title")?.focus());
  });

  $("[data-close-thread-composer]")?.addEventListener("click", () => {
    $("[data-thread-composer]")?.classList.remove("is-open");
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-curriculum]");
    if (!button || document.body.dataset.page !== "feed") return;
    state.filter = button.dataset.curriculum;
    state.bookmarkedOnly = false;
    $all("[data-curriculum]").forEach((item) => item.classList.toggle("active", item === button));
    updateClassFilterOptions();
    updateNavState();
    syncComposerCurriculum();
    loadThreads();
  });

  $("[data-search-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadThreads();
  });

  $("[data-search-form]")?.addEventListener("change", () => loadThreads());

  $("[data-thread-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      const data = await formPayload(form);
      const result = await api("/api/threads", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      $all("[data-file-input], [data-image-input]", form).forEach((input) => { input._selectedFiles = []; input.value = ""; });
      $all("[data-file-preview], [data-image-preview]", form).forEach((node) => { node.innerHTML = ""; });
      $all("[data-file-drop] span", form).forEach((node) => { node.textContent = "Attach a PDF, image, document, or any file"; });
      $all(".custom-select").forEach((wrapper) => {
        const select = $("select", wrapper);
        const hidden = $("input[type='hidden']", wrapper);
        const button = $(".custom-select-button", wrapper);
        if (select && button) button.textContent = select.options[select.selectedIndex]?.textContent || "Select";
        if (hidden && button) setStaticSelectValue(wrapper, hidden.value);
      });
      syncComposerCurriculum();
      toast("Discussion published.");
      location.href = `thread.html?id=${result.thread.id}`;
    } catch (error) {
      setMessage("[data-thread-message]", error.message, "error");
    }
  });

  document.addEventListener("click", async (event) => {
    const support = event.target.closest("[data-support-thread]");
    const bookmark = event.target.closest("[data-bookmark-thread]");
    const del = event.target.closest("[data-delete-thread]");
    const card = event.target.closest("[data-thread-card]");
    if (!support && !bookmark && !del && !card) return;
    if (support || bookmark || del) {
      event.preventDefault();
      event.stopPropagation();
    }
    if (card && !support && !bookmark && !del && !event.target.closest("a, button, input, textarea, select, label")) {
      location.href = `thread.html?id=${card.dataset.threadCard}`;
      return;
    }
    try {
      if (support) {
        const result = await api(`/api/threads/${support.dataset.supportThread}/support`, { method: "POST", body: "{}" });
        updateThreadSupportButton(support, Boolean(result.active));
        const thread = state.threads.find((item) => String(item.id) === String(support.dataset.supportThread));
        if (thread) {
          const wasActive = Boolean(thread.supported);
          thread.supported = Boolean(result.active);
          thread.supports = Math.max(0, Number(thread.supports || 0) + (result.active && !wasActive ? 1 : !result.active && wasActive ? -1 : 0));
        }
        return;
      }
      if (bookmark) await api(`/api/threads/${bookmark.dataset.bookmarkThread}/bookmark`, { method: "POST", body: "{}" });
      if (del) {
        if (!confirm("Delete this thread and all of its replies?")) return;
        await api(`/api/threads/${del.dataset.deleteThread}`, { method: "DELETE" });
        toast("Thread deleted.");
      }
      await loadThreads();
    } catch (error) {
      toast(error.message);
    }
  });

  document.addEventListener("keydown", (event) => {
    const card = event.target.closest("[data-thread-card]");
    if (!card || !["Enter", " "].includes(event.key)) return;
    if (event.target.closest("a, button, input, textarea, select, label")) return;
    event.preventDefault();
    location.href = `thread.html?id=${card.dataset.threadCard}`;
  });

  loadThreads();
}

function renderNoThread(message = "No thread selected") {
  const view = $("[data-thread-view]");
  if (!view) return;
  view.innerHTML = `
    <section class="empty-state">
      <div>
        <div class="empty-mark">▧</div>
        <h2>${escapeHtml(message)}</h2>
        <p>Open a discussion from the feed, or create the first community thread.</p>
        <p><a class="button" href="feed.html">Return to Feed</a></p>
      </div>
    </section>
  `;
}

function extractLinks(text) {
  const matches = String(text || "").match(/https?:\/\/[^\s<>"')]+/g) || [];
  return matches.map((url) => url.replace(/[.,;:!?]+$/, ""));
}

function uploadSourceLabel(item, fallback) {
  return item.author_name ? `${item.author_name} · ${fallback}` : fallback;
}

function collectThreadUploads(thread, replies) {
  const sources = [
    { item: thread, kind: "Thread" },
    ...replies.map((reply) => ({ item: reply, kind: "Reply" })),
  ];
  const seenLinks = new Set();
  const links = [];
  const images = [];
  const files = [];

  sources.forEach(({ item, kind }) => {
    extractLinks(item.body).forEach((url) => {
      if (seenLinks.has(url)) return;
      seenLinks.add(url);
      links.push({ url, source: uploadSourceLabel(item, kind) });
    });

    attachmentsFor(item).forEach((attachment) => {
      const entry = { ...attachment, source: uploadSourceLabel(item, kind) };
      if (isImageAttachment(attachment)) images.push(entry);
      else files.push(entry);
    });
  });

  return { links, images, files };
}

function renderUploadEmpty(label) {
  return `<p class="upload-empty">No ${label} attached yet.</p>`;
}

function renderUploadsPanel(thread, replies) {
  const uploads = collectThreadUploads(thread, replies);
  return `
    <section class="uploads-panel">
      <section class="upload-category">
        <div class="upload-category-head">
          <h2>Links</h2>
          <span>${uploads.links.length}</span>
        </div>
        ${uploads.links.length ? `
          <div class="upload-list">
            ${uploads.links.map((link) => `
              <a class="upload-item" href="${escapeHtml(link.url)}" target="_blank" rel="noopener">
                <span class="file-icon" aria-hidden="true">↗</span>
                <span>
                  <strong>${escapeHtml(link.url)}</strong>
                  <small>${escapeHtml(link.source)}</small>
                </span>
              </a>
            `).join("")}
          </div>
        ` : renderUploadEmpty("links")}
      </section>

      <section class="upload-category">
        <div class="upload-category-head">
          <h2>Images</h2>
          <span>${uploads.images.length}</span>
        </div>
        ${uploads.images.length ? `
          <div class="upload-grid">
            ${uploads.images.map((image) => `
              <a class="upload-image" href="${escapeHtml(image.path)}" target="_blank" rel="noopener">
                <img src="${escapeHtml(image.path)}" alt="${escapeHtml(image.name)}" loading="lazy" />
                <strong>${escapeHtml(image.name)}</strong>
                <small>${escapeHtml(image.source)}</small>
              </a>
            `).join("")}
          </div>
        ` : renderUploadEmpty("images")}
      </section>

      <section class="upload-category">
        <div class="upload-category-head">
          <h2>Files</h2>
          <span>${uploads.files.length}</span>
        </div>
        ${uploads.files.length ? `
          <div class="upload-list">
            ${uploads.files.map((file) => `
              <a class="upload-item" href="${escapeHtml(file.path)}" target="_blank" rel="noopener">
                <span class="file-icon" aria-hidden="true">□</span>
                <span>
                  <strong>${escapeHtml(file.name)}</strong>
                  <small>${escapeHtml(file.type || "File")} · ${escapeHtml(file.source)}</small>
                </span>
              </a>
            `).join("")}
          </div>
        ` : renderUploadEmpty("files")}
      </section>
    </section>
  `;
}

function solutionCallout(answer) {
  if (!answer) return "";
  return `
    <aside class="solution-callout">
      <div>
        <span class="eyebrow">Solution</span>
        <h2>Accepted response by ${escapeHtml(answer.author_name)}</h2>
        <p>${escapeHtml(compactText(answer.body, 220))}</p>
      </div>
      <a class="button secondary" href="#reply-${answer.id}">View Solution</a>
    </aside>
  `;
}

function renderThreadDetail(thread, replies) {
  const view = $("[data-thread-view]");
  const canDelete = state.user && (state.user.id === thread.author_id || state.user.is_school_admin);
  const canManage = canManageThread(thread);
  const locked = ["locked", "archived"].includes(thread.status);
  const acceptedReply = replies.find((reply) => Number(reply.id) === Number(thread.answered_reply_id));
  view.innerHTML = `
    <div class="thread-tabs" data-thread-tabs>
      <button class="active" data-thread-tab="discussion" type="button">Thread</button>
      <button data-thread-tab="uploads" type="button">Uploads</button>
    </div>
    <section data-thread-panel="discussion">
      <article class="thread-detail">
        <header class="article-head">
          ${avatarMarkup(thread.author_avatar_path, "avatar")}
          <div>
            <h1>${escapeHtml(thread.title)}</h1>
            <div class="meta-row">
              <a class="profile-link" href="${profileHref(thread.author_id)}">${escapeHtml(thread.author_name)}</a>
              ${roleBadge(thread.author_role)}
              <span class="badge section">${escapeHtml(thread.section)}</span>
              ${statusBadge(thread.status)}
              <span class="meta">Published ${escapeHtml(thread.created_at)}</span>
            </div>
          </div>
        </header>
        <div class="thread-body">
          ${renderRichText(thread.body)}
        </div>
        ${renderAttachments(thread)}
        <div class="action-row thread-actions">
          <button class="text-action ${thread.supported ? "active" : ""}" data-detail-support="${thread.id}" type="button">Support ${thread.supports}</button>
          <span class="meta">${thread.replies} responses</span>
          <button class="text-action ${thread.bookmarked ? "active" : ""}" data-detail-bookmark="${thread.id}" type="button">${thread.bookmarked ? "Bookmarked" : "Bookmark"}</button>
          ${state.user ? `<button class="text-action" data-report-content="thread" data-target-id="${thread.id}" type="button">Report</button>` : ""}
          ${canDelete ? `<button class="text-action" data-edit-thread="${thread.id}" data-thread-title="${escapeHtml(thread.title)}" data-thread-body="${escapeHtml(thread.body)}" type="button">Edit Thread</button>` : ""}
          ${canDelete ? `<button class="text-action danger" data-detail-delete-thread="${thread.id}" type="button">Delete Thread</button>` : ""}
        </div>
        ${canManage ? `
          <div class="status-controls" aria-label="Thread status controls">
            <span>Status</span>
            ${statusOptionsForThread(thread).map((status) => `
              <button class="text-action ${thread.status === status ? "active" : ""}" data-thread-status="${status}" data-thread-id="${thread.id}" type="button">${status.charAt(0).toUpperCase() + status.slice(1)}</button>
            `).join("")}
          </div>
        ` : ""}
        ${solutionCallout(acceptedReply)}
      </article>
      <header class="responses-head"><h2>Responses</h2></header>
      <section class="content-stack" data-reply-list>
        ${replies.length ? replies.map((reply) => replyCard(reply, thread)).join("") : `<section class="empty-state"><div><div class="empty-mark">□</div><h2>No responses yet</h2><p>Be the first to contribute a reply.</p></div></section>`}
      </section>
      ${state.user && !locked ? replyForm(thread.id) : state.user ? `<section class="panel center"><div><h2>This thread is ${escapeHtml(thread.status)}</h2><p>Replies are closed while a thread is locked or archived.</p></div></section>` : `<section class="panel center"><div><h2>Sign in to reply</h2><p>Replies require an academic community account.</p><a class="button" href="index.html#auth">Sign In</a></div></section>`}
    </section>
    <section class="hidden" data-thread-panel="uploads">
      ${renderUploadsPanel(thread, replies)}
    </section>
  `;
}

function replyCard(reply, thread = {}) {
  const canDelete = state.user && (state.user.id === reply.author_id || state.user.is_school_admin);
  const featured = ["teacher", "staff"].includes(reply.author_role) ? " featured" : "";
  const accepted = Number(reply.id) === Number(thread.answered_reply_id);
  const canMarkAnswer = Boolean(state.user && state.user.id === thread.author_id && !["locked", "archived"].includes(thread.status));
  const replyPreview = compactText(reply.body, 150);
  return `
    <article class="response-row" id="reply-${reply.id}">
      <div class="vote">
        <button class="${reply.supported ? "active" : ""}" data-support-reply="${reply.id}" type="button" aria-label="Support reply"></button>
        <strong>${reply.supports}</strong>
        <span></span>
      </div>
      <section class="reply-card${featured}${accepted ? " solution" : ""}">
        <div class="reply-top">
          ${avatarMarkup(reply.author_avatar_path, "small-avatar")}
          <a class="profile-link" href="${profileHref(reply.author_id)}">${escapeHtml(reply.author_name)}</a>
          ${roleBadge(reply.author_role)}
          ${accepted ? `<span class="badge solution-badge">Solution</span>` : ""}
          <span class="meta">${escapeHtml(reply.created_at)}</span>
        </div>
        ${reply.reply_to ? `
          <a class="reply-context" href="#reply-${reply.reply_to.id}">
            <span>Replying to ${escapeHtml(reply.reply_to.author_name)}</span>
            <p>${escapeHtml(compactText(reply.reply_to.body, 160))}</p>
          </a>
        ` : ""}
        ${renderRichText(reply.body)}
        ${renderAttachments(reply)}
        <div class="response-actions">
          <button class="text-action" data-reply-to="${reply.id}" data-reply-author="${escapeHtml(reply.author_name)}" data-reply-preview="${escapeHtml(replyPreview)}" type="button">Reply</button>
          <button class="text-action" data-share-thread type="button">Share</button>
          ${state.user ? `<button class="text-action" data-report-content="reply" data-target-id="${reply.id}" type="button">Report</button>` : ""}
          ${canMarkAnswer ? `<button class="text-action" data-mark-answer="${reply.id}" type="button">Mark Answer</button>` : ""}
          ${canDelete ? `<button class="text-action" data-edit-reply="${reply.id}" data-reply-body="${escapeHtml(reply.body)}" type="button">Edit Reply</button>` : ""}
          ${canDelete ? `<button class="text-action danger" data-delete-reply="${reply.id}" type="button">Delete Reply</button>` : ""}
        </div>
      </section>
    </article>
  `;
}

function replyForm(threadId) {
  return `
    <form class="reply-composer" data-reply-form>
      <div class="reply-target hidden" data-reply-target>
        <div>
          <span>Replying to <strong data-reply-target-author></strong></span>
          <p data-reply-target-preview></p>
        </div>
        <button class="text-action" data-clear-reply-target type="button">Clear</button>
      </div>
      <div class="field">
        <label for="reply-body">Draft Your Contribution</label>
        <textarea id="reply-body" name="body" placeholder="Support your argument with citations where possible..." required></textarea>
      </div>
      <div class="field">
        <label for="reply-file">Attachment</label>
        <label class="file-drop" data-file-drop>
          <input id="reply-file" name="file_upload" type="file" data-file-input multiple />
          <span>Attach a PDF, image, document, or any file</span>
        </label>
        <div class="file-preview" data-file-preview></div>
      </div>
      <button class="button" type="submit">Submit Response</button>
      <p class="form-message" data-reply-message></p>
      <input type="hidden" name="thread_id" value="${threadId}" />
      <input type="hidden" name="parent_reply_id" value="" data-parent-reply-id />
    </form>
  `;
}

async function renderThread() {
  if (document.body.dataset.page !== "thread") return;
  const id = new URLSearchParams(location.search).get("id");
  if (!id) return renderNoThread();
  try {
    const data = await api(`/api/threads/${id}`);
    renderThreadDetail(data.thread, data.replies);
    replayPop($("[data-thread-view]"));
  } catch (error) {
    renderNoThread(error.message);
  }
}

function installThread() {
  if (document.body.dataset.page !== "thread") return;
  document.addEventListener("submit", async (event) => {
    if (!event.target.matches("[data-reply-form]")) return;
    event.preventDefault();
    try {
      const data = await formPayload(event.target);
      await api(`/api/threads/${data.thread_id}/replies`, { method: "POST", body: JSON.stringify(data) });
      toast("Reply posted.");
      await renderThread();
    } catch (error) {
      setMessage("[data-reply-message]", error.message, "error");
    }
  });

  document.addEventListener("click", async (event) => {
    const tab = event.target.closest("[data-thread-tab]");
    if (tab) {
      const name = tab.dataset.threadTab;
      $all("[data-thread-tab]").forEach((button) => button.classList.toggle("active", button === tab));
      $all("[data-thread-panel]").forEach((panel) => panel.classList.toggle("hidden", panel.dataset.threadPanel !== name));
      return;
    }
    const support = event.target.closest("[data-detail-support]");
    const bookmark = event.target.closest("[data-detail-bookmark]");
    const del = event.target.closest("[data-delete-reply]");
    const threadDel = event.target.closest("[data-detail-delete-thread]");
    const threadEdit = event.target.closest("[data-edit-thread]");
    const replyEdit = event.target.closest("[data-edit-reply]");
    const replySupport = event.target.closest("[data-support-reply]");
    const share = event.target.closest("[data-share-thread]");
    const report = event.target.closest("[data-report-content]");
    const statusButton = event.target.closest("[data-thread-status]");
    const markAnswer = event.target.closest("[data-mark-answer]");
    const replyTo = event.target.closest("[data-reply-to]");
    const clearReplyTarget = event.target.closest("[data-clear-reply-target]");
    if (!support && !bookmark && !del && !threadDel && !threadEdit && !replyEdit && !replySupport && !share && !report && !statusButton && !markAnswer && !replyTo && !clearReplyTarget) return;
    event.preventDefault();
    event.stopPropagation();
    try {
      if (replyTo) {
        const form = $("[data-reply-form]");
        if (!form) return;
        const target = $("[data-reply-target]", form);
        $("[data-parent-reply-id]", form).value = replyTo.dataset.replyTo;
        $("[data-reply-target-author]", form).textContent = replyTo.dataset.replyAuthor || "this response";
        $("[data-reply-target-preview]", form).textContent = replyTo.dataset.replyPreview || "";
        target?.classList.remove("hidden");
        form?.scrollIntoView({ behavior: "smooth", block: "center" });
        window.requestAnimationFrame(() => $("#reply-body")?.focus());
        return;
      }
      if (clearReplyTarget) {
        const form = clearReplyTarget.closest("[data-reply-form]");
        if (!form) return;
        $("[data-parent-reply-id]", form).value = "";
        $("[data-reply-target]", form)?.classList.add("hidden");
        return;
      }
      if (support) {
        const result = await api(`/api/threads/${support.dataset.detailSupport}/support`, { method: "POST", body: "{}" });
        updateThreadSupportButton(support, Boolean(result.active));
        return;
      }
      if (bookmark) await api(`/api/threads/${bookmark.dataset.detailBookmark}/bookmark`, { method: "POST", body: "{}" });
      if (del) await api(`/api/replies/${del.dataset.deleteReply}`, { method: "DELETE" });
      if (threadEdit) {
        openModal({
          eyebrow: "Edit Thread",
          title: "Revise thread",
          titleValue: threadEdit.dataset.threadTitle || "",
          titleField: true,
          body: threadEdit.dataset.threadBody || "",
          submitLabel: "Save Thread",
          onSubmit: async ({ title, body }) => {
            await api(`/api/threads/${threadEdit.dataset.editThread}`, {
              method: "PATCH",
              body: JSON.stringify({ title, body }),
            });
            toast("Thread updated.");
            await renderThread();
          },
        });
        return;
      }
      if (replyEdit) {
        openModal({
          eyebrow: "Edit Reply",
          title: "Revise your response",
          body: replyEdit.dataset.replyBody || "",
          submitLabel: "Save Reply",
          onSubmit: async ({ body }) => {
            await api(`/api/replies/${replyEdit.dataset.editReply}`, { method: "PATCH", body: JSON.stringify({ body }) });
            toast("Reply updated.");
            await renderThread();
          },
        });
        return;
      }
      if (threadDel) {
        if (!confirm("Delete this thread and all of its replies?")) return;
        await api(`/api/threads/${threadDel.dataset.detailDeleteThread}`, { method: "DELETE" });
        toast("Thread deleted.");
        location.href = "feed.html";
        return;
      }
      if (replySupport) {
        const result = await api(`/api/replies/${replySupport.dataset.supportReply}/support`, { method: "POST", body: "{}" });
        updateReplySupportButton(replySupport, Boolean(result.active));
        return;
      }
      if (report) {
        openReportModal({
          targetType: report.dataset.reportContent,
          targetId: report.dataset.targetId,
        });
        return;
      }
      if (statusButton) {
        await api(`/api/threads/${statusButton.dataset.threadId}/status`, {
          method: "POST",
          body: JSON.stringify({ status: statusButton.dataset.threadStatus }),
        });
        toast("Thread status updated.");
      }
      if (markAnswer) {
        const id = new URLSearchParams(location.search).get("id");
        await api(`/api/threads/${id}/status`, {
          method: "POST",
          body: JSON.stringify({ status: "answered", answered_reply_id: markAnswer.dataset.markAnswer }),
        });
        toast("Answer marked.");
      }
      if (share) {
        await navigator.clipboard?.writeText(location.href);
        toast("Thread link copied.");
      }
      await renderThread();
    } catch (error) {
      toast(error.message);
    }
  });
}

async function renderProfile() {
  if (document.body.dataset.page !== "profile") return;
  const root = $("[data-profile-view]");
  if (!root) return;
  const id = new URLSearchParams(location.search).get("id") || state.user?.id;
  if (!id) {
    root.innerHTML = `<section class="empty-state"><div><h2>No profile selected</h2><p>Open a profile from a thread or reply.</p></div></section>`;
    return;
  }
  try {
    const data = await api(`/api/users/${id}`);
    const profile = data.profile;
    root.innerHTML = `
      <section class="profile-hero">
        ${avatarMarkup(profile.avatar_path, "avatar large")}
        <div>
          <p class="eyebrow">${escapeHtml(profile.role || "Member")}</p>
          <h1>${escapeHtml(profile.name)}</h1>
          <p>${escapeHtml(profile.profile_title || profile.institution || "Studera community member")}</p>
          <div class="meta-row">
            ${roleBadge(profile.role)}
            ${profile.institution ? `<span class="badge section">${escapeHtml(profile.institution)}</span>` : ""}
            ${profile.email ? `<span class="meta">${escapeHtml(profile.email)}</span>` : ""}
          </div>
        </div>
      </section>
      ${profile.bio ? `<section class="settings-panel"><h2>About</h2>${renderRichText(profile.bio)}</section>` : ""}
      <section class="settings-panel">
        <div><p class="eyebrow">Authored Threads</p><h2>Recent discussions</h2></div>
        <div class="thread-list">${data.threads.length ? data.threads.map(threadCard).join("") : `<p class="upload-empty">No public threads yet.</p>`}</div>
      </section>
      <section class="settings-panel">
        <div><p class="eyebrow">Replies</p><h2>Recent responses</h2></div>
        <div class="admin-list">${data.replies.length ? data.replies.map((reply) => `
          <article class="admin-row">
            <div>
              <strong>${escapeHtml(reply.thread_title)}</strong>
              <span>${escapeHtml(reply.created_at)}</span>
              <small>${escapeHtml(reply.body)}</small>
            </div>
            <a class="text-action" href="thread.html?id=${reply.thread_id}">Open</a>
          </article>
        `).join("") : `<p class="upload-empty">No public replies yet.</p>`}</div>
      </section>
    `;
  } catch (error) {
    root.innerHTML = `<section class="empty-state"><div><h2>${escapeHtml(error.message)}</h2><p>This profile may be private or outside your school.</p></div></section>`;
  }
}

async function renderAuditPage() {
  if (document.body.dataset.page !== "audit") return;
  const guest = $("[data-audit-guest]");
  const denied = $("[data-audit-denied]");
  const view = $("[data-audit-view]");
  const title = $("[data-audit-title]");
  const lead = $("[data-audit-lead]");
  if (!guest || !denied || !view) return;
  guest.classList.toggle("hidden", Boolean(state.user));
  const hasAccess = Boolean(state.user?.is_site_admin || state.user?.is_school_admin);
  denied.classList.toggle("hidden", !state.user || hasAccess);
  view.classList.toggle("hidden", !hasAccess);
  if (!hasAccess) return;
  const scope = state.user.is_site_admin ? "site" : "school";
  try {
    const data = await api(scope === "site" ? "/api/site-admin/audit" : "/api/admin/audit");
    if (title) title.textContent = scope === "site" ? "Global Audit Log" : "School Audit Log";
    if (lead) {
      lead.textContent = scope === "site"
        ? "Overarching admin actions and school-admin actions are separated by ledger."
        : `Admin actions for ${state.user.institution}, grouped by day.`;
    }
    if (scope === "site") {
      view.innerHTML = `
        <section class="settings-panel">
          <div>
            <p class="eyebrow">Overarching Ledger</p>
            <h2>Site admin actions</h2>
            <p>Global account, school registry, backup, and platform-management actions.</p>
          </div>
          ${renderAuditGroups(data.platform_logs || [], { empty: "No overarching admin actions recorded yet." })}
        </section>
        <section class="settings-panel">
          <div>
            <p class="eyebrow">School Ledgers</p>
            <h2>School admin actions</h2>
            <p>Moderation and school-level administration actions from every school.</p>
          </div>
          ${renderAuditGroups(data.school_logs || [], { empty: "No school admin actions recorded yet." })}
        </section>
      `;
    } else {
      view.innerHTML = renderAuditGroups(data.logs, { empty: "No school admin actions recorded yet." });
    }
  } catch (error) {
    view.innerHTML = `<section class="empty-state"><div><h2>${escapeHtml(error.message)}</h2><p>Audit access is restricted to admin accounts.</p></div></section>`;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  updateNavState();
  installNavShadow();
  installContentMotion();
  installNav();
  installFooterGuidelines();
  installCustomSelects();
  installInstitutionAutocomplete();
  installFileInputs();
  installAuthForms();
  installAppearanceControls();
  installSettings();
  installAdmin();
  installSiteAdmin();
  installFeed();
  installThread();
  if (["about", "contact"].includes(document.body.dataset.page)) renderNavLinks();
  await loadSession();
  if (document.body.dataset.page === "feed") await loadThreads();
  if (document.body.dataset.page === "thread") await renderThread();
  if (document.body.dataset.page === "profile") await renderProfile();
  if (document.body.dataset.page === "audit") await renderAuditPage();
});
