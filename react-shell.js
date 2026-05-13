(function () {
  const { createElement: h, useEffect, useState } = React;
  const { createRoot } = ReactDOM;

  const api = async (path, options = {}) => {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Request failed");
    return data;
  };

  function NavLink({ href, active, children }) {
    return h("a", { className: active ? "active" : "", href }, children);
  }

  function ReactNav() {
    const [user, setUser] = useState(null);
    const [open, setOpen] = useState(false);
    const page = document.body.dataset.page;
    const params = new URLSearchParams(location.search);
    const bookmarked = page === "feed" && params.get("bookmarked") === "1";

    useEffect(() => {
      let alive = true;
      const syncSession = (event) => setUser(event.detail || null);
      window.addEventListener("studera:session", syncSession);
      api("/api/session").then((data) => {
        if (alive) {
          setUser(data.user);
          window.dispatchEvent(new CustomEvent("studera:session", { detail: data.user }));
        }
      }).catch(() => {});
      return () => {
        alive = false;
        window.removeEventListener("studera:session", syncSession);
      };
    }, []);

    async function logout() {
      await api("/api/auth/logout", { method: "POST", body: "{}" });
      try {
        localStorage.removeItem("studera-authenticated");
      } catch {
        // Local storage can be blocked in some browser privacy modes.
      }
      setUser(null);
      window.dispatchEvent(new CustomEvent("studera:session", { detail: null }));
      location.href = "index.html";
    }

    const brandHref = user?.is_site_admin ? "site-admin.html" : (user ? "feed.html" : "index.html");
    const navLinks = !user
      ? [
          h(NavLink, { key: "about", href: "about.html", active: page === "about" }, "About"),
          h(NavLink, { key: "contact", href: "contact.html", active: page === "contact" }, "Contact"),
        ]
      : user?.is_site_admin
      ? [
          h(NavLink, { key: "site-admin", href: "site-admin.html", active: page === "site-admin" || page === "audit" }, "Site Admin"),
          h(NavLink, { key: "settings", href: "settings.html", active: page === "settings" }, "Settings"),
        ]
      : [
          h(NavLink, { key: "feed", href: "feed.html", active: (page === "feed" && !bookmarked) || page === "thread" }, "Feed"),
          h(NavLink, { key: "bookmarked", href: "feed.html?bookmarked=1", active: bookmarked }, "Bookmarked"),
          user.is_school_admin ? h(NavLink, { key: "admin", href: "admin.html", active: page === "admin" || page === "audit" }, "Admin") : null,
          h(NavLink, { key: "settings", href: "settings.html", active: page === "settings" }, "Settings"),
        ];

    useEffect(() => {
      const shell = document.querySelector(".site-nav");
      if (!shell) return;
      shell.classList.toggle("open", open);
      return () => shell.classList.remove("open");
    }, [open]);

    return h("div", { className: "nav-inner" },
      h("a", { className: "brand", href: brandHref }, "Studera"),
      h("button", { className: "mobile-menu", type: "button", onClick: () => setOpen(!open) }, "Menu"),
      h("div", { className: "nav-links" }, navLinks),
      h("div", { className: "nav-actions" },
        h("a", { className: `nav-help${page === "help" ? " active" : ""}`, href: "help.html", "data-nav-help": true }, "Help"),
        h("button", {
          className: "primary",
          type: "button",
          onClick: () => {
            if (user) location.href = "settings.html";
            else location.href = "index.html#auth";
          },
        }, user ? user.name : "Sign In"),
        user ? h("button", { type: "button", onClick: logout }, "Sign Out") : null
      )
    );
  }

  function mountReactShell() {
    const legacyNav = document.querySelector(".site-nav");
    if (!legacyNav) return;
    if (legacyNav.dataset.reactMounted === "true") return;
    legacyNav.dataset.reactMounted = "true";
    legacyNav.innerHTML = "";
    createRoot(legacyNav).render(h(ReactNav));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountReactShell);
  } else {
    mountReactShell();
  }
})();
