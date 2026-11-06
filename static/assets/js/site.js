/* sepehrkhasto.github.io: menu, section tracking, lightbox, copy button and the encryption demo. */
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");

  /* ---------- Buttons and downloads: a soft light follows the pointer (mouse only, never with reduced motion) ---------- */
  if (finePointer.matches && !reduceMotion.matches) {
    let frame = 0, last = null;
    document.addEventListener("pointermove", (ev) => {
      const el = ev.target instanceof Element ? ev.target.closest(".btn, .dl") : null;
      if (!el) return;
      last = { el, x: ev.clientX, y: ev.clientY };
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const r = last.el.getBoundingClientRect();
        last.el.style.setProperty("--mx", `${(last.x - r.left).toFixed(0)}px`);
        last.el.style.setProperty("--my", `${(last.y - r.top).toFixed(0)}px`);
      });
    }, { passive: true });
  }

  /* ---------- Hero: a faint glow follows the pointer (mouse only, never with reduced motion) ---------- */
  const hero = $(".hero");
  if (hero && window.matchMedia("(hover: hover) and (pointer: fine)").matches && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    let frame = 0;
    hero.addEventListener("pointermove", (ev) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const r = hero.getBoundingClientRect();
        hero.style.setProperty("--hx", `${((ev.clientX - r.left) / r.width * 100).toFixed(1)}%`);
        hero.style.setProperty("--hy", `${((ev.clientY - r.top) / r.height * 100).toFixed(1)}%`);
      });
    });
  }

  /* ---------- Day / night theme ---------- */
  const themeBtn = $(".theme-btn");
  if (themeBtn) {
    const root = document.documentElement;
    const isDay = () => root.getAttribute("data-theme") === "day";
    const sync = () => {
      themeBtn.setAttribute("aria-pressed", String(isDay()));
      const m = $('meta[name="theme-color"]');
      if (m) m.setAttribute("content", isDay() ? "#F6F0E3" : "#070B1F");
    };
    sync();
    let current = isDay() ? "day" : "night"; // kept here too, so two quick clicks still alternate
    themeBtn.addEventListener("click", () => {
      const next = current === "day" ? "night" : "day";
      current = next;
      // The choice is saved at once; the page itself may switch a frame later, inside the transition.
      try { localStorage.setItem("theme", next); } catch (e) { /* private mode: the choice lasts for this visit */ }
      const apply = () => { root.setAttribute("data-theme", next); sync(); };
      if (typeof document.startViewTransition !== "function" || reduceMotion.matches) { apply(); return; }
      // The new theme is revealed outward from the button, as a circle. Browsers without the API just switch.
      const r = themeBtn.getBoundingClientRect();
      const x = r.left + r.width / 2, y = r.top + r.height / 2;
      const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
      const ms = (parseFloat(getComputedStyle(root).getPropertyValue("--t-theme")) || 0.75) * 1000;
      root.classList.add("theme-vt"); // the circle rules apply only to this transition, not to the page-to-page fade
      const vt = document.startViewTransition(apply);
      vt.finished.finally(() => root.classList.remove("theme-vt"));
      vt.ready.then(() => root.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: ms, easing: "cubic-bezier(.23,1,.32,1)", pseudoElement: "::view-transition-new(root)" }
      )).catch(() => {});
    });
  }

  /* ---------- Mobile menu ---------- */
  const menuBtn = $(".menu-btn");
  const nav = $("#site-nav");
  if (menuBtn && nav) {
    const label = $("span", menuBtn);
    const setOpen = (open) => {
      nav.classList.toggle("open", open);
      menuBtn.setAttribute("aria-expanded", String(open));
      label.textContent = open ? menuBtn.dataset.close : menuBtn.dataset.open;
    };
    menuBtn.addEventListener("click", () => setOpen(!nav.classList.contains("open")));
    nav.addEventListener("click", (ev) => { if (ev.target.closest("a")) setOpen(false); });
    document.addEventListener("click", (ev) => { if (nav.classList.contains("open") && !ev.target.closest(".site-header")) setOpen(false); });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && nav.classList.contains("open")) { setOpen(false); menuBtn.focus(); }
    });
    window.matchMedia("(min-width: 56.3125em)").addEventListener("change", () => setOpen(false));
  }

  /* ---------- Current section in the nav ---------- */
  const navLinks = $$(".nav-links a[data-nav]");
  const sections = navLinks.map((a) => $(a.getAttribute("href"))).filter(Boolean);
  if ("IntersectionObserver" in window && sections.length) {
    const visible = new Map();
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => visible.set(en.target.id, en.isIntersecting));
      const current = sections.find((s) => visible.get(s.id));
      navLinks.forEach((a) => {
        if (current && a.getAttribute("href") === `#${current.id}`) a.setAttribute("aria-current", "true");
        else a.removeAttribute("aria-current");
      });
    }, { rootMargin: "-40% 0px -55% 0px" });
    sections.forEach((s) => io.observe(s));
  }

  /* ---------- Current project in the Work tabs ---------- */
  const tabLinks = $$(".case-tabs a[data-case]");
  const cases = tabLinks.map((a) => $(a.getAttribute("href"))).filter(Boolean);
  if ("IntersectionObserver" in window && cases.length) {
    const seen = new Map();
    // One gold line under the tabs that glides to the current one (an aria-hidden list item, so the list stays a list).
    const tabList = tabLinks[0].closest("ol");
    const ind = document.createElement("li");
    ind.className = "ct-ind";
    ind.setAttribute("aria-hidden", "true");
    tabList.appendChild(ind);
    let currentTab = null;
    const place = () => {
      if (!currentTab) { tabList.classList.remove("has-ind"); return; }
      ind.style.setProperty("--x", `${currentTab.offsetLeft}px`);
      ind.style.setProperty("--w", String(currentTab.offsetWidth / 100));
      tabList.classList.add("has-ind");
      // The first placement is instant; later ones glide.
      requestAnimationFrame(() => tabList.classList.add("ready"));
    };
    if ("ResizeObserver" in window) new ResizeObserver(place).observe(tabList);
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => seen.set(en.target.id, en.isIntersecting));
      const current = cases.find((c) => seen.get(c.id));
      currentTab = null;
      tabLinks.forEach((a) => {
        const on = Boolean(current) && a.getAttribute("href") === `#${current.id}`;
        if (on) {
          currentTab = a;
          a.setAttribute("aria-current", "true");
          const list = a.closest("ol");
          const r = a.getBoundingClientRect();
          const box = list.getBoundingClientRect();
          if (r.left < box.left) list.scrollBy({ left: r.left - box.left - 16 });
          else if (r.right > box.right) list.scrollBy({ left: r.right - box.right + 16 });
        } else a.removeAttribute("aria-current");
      });
      place();
    }, { rootMargin: "-30% 0px -60% 0px" });
    cases.forEach((c) => io.observe(c));
  }

  /* ---------- Screenshots open full size in a dialog ---------- */
  const box = $("#lightbox");
  if (box && typeof box.showModal === "function") {
    const img = $("img", box);
    const cap = $("figcaption", box);
    $$("a[data-lightbox]").forEach((link) => {
      link.addEventListener("click", (ev) => {
        if (ev.metaKey || ev.ctrlKey || ev.shiftKey) return; // let people open it in a new tab
        ev.preventDefault();
        const shot = $("img", link);
        img.src = link.getAttribute("href");
        img.alt = shot.alt;
        cap.textContent = shot.alt;
        box.showModal();
      });
    });
    // Closing eases out first (the opening one is in CSS); with reduced motion it just closes.
    const closeBox = () => {
      if (!box.open || box.classList.contains("closing")) return;
      if (reduceMotion.matches) { box.close(); return; }
      box.classList.add("closing");
      const done = () => { if (!box.classList.contains("closing")) return; box.classList.remove("closing"); if (box.open) box.close(); };
      box.addEventListener("animationend", (ev) => { if (ev.target === box) done(); }, { once: true });
      setTimeout(done, 400); // if the animation never reports back
    };
    box.addEventListener("cancel", (ev) => { ev.preventDefault(); closeBox(); });
    $("[data-close]", box).addEventListener("click", closeBox);
    box.addEventListener("click", (ev) => { if (ev.target === box) closeBox(); });
    box.addEventListener("close", () => { img.removeAttribute("src"); });
  }

  /* ---------- Copy email ---------- */
  $$("[data-copy]").forEach((btn) => {
    const label = $("span", btn);
    const status = $("[data-copy-status]");
    const original = label.textContent;
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(btn.dataset.copy);
        label.textContent = btn.dataset.done;
        btn.classList.add("done");
        if (status) status.textContent = btn.dataset.done;
        setTimeout(() => { label.textContent = original; btn.classList.remove("done"); if (status) status.textContent = ""; }, 2000);
      } catch {
        window.location.href = `mailto:${btn.dataset.copy}`;
      }
    });
  });

  /* ---------- Key-hierarchy demo: the Aegis scheme, entirely in the browser ----------
     master password --PBKDF2-SHA256 (600k)--> KEK
     random DEK --AES-256-GCM--> ciphertext
     KEK --AES-GCM wrap--> wrapped DEK
     Unlock: derive KEK, unwrap DEK (a wrong password fails the GCM tag check), decrypt. */
  const i18nEl = $("#i18n");
  if (!$("#vault") || !i18nEl) return;
  const t = JSON.parse(i18nEl.textContent);
  const el = {
    note: $("#vault-note"), pass: $("#vault-pass"), salt: $("#vault-salt"), wrapped: $("#vault-wrapped"),
    cipher: $("#vault-cipher"), status: $("#vault-status"), tryPass: $("#vault-try"),
    unlock: $("#vault-unlock"), result: $("#vault-result"),
  };
  el.note.dir = document.documentElement.dir;
  const setResult = (text, kind = "") => { el.result.textContent = text; el.result.className = `vault-result ${kind}`.trim(); };

  if (!(window.crypto && crypto.subtle)) {
    setResult(t.msg_unsupported, "bad");
    el.unlock.disabled = true;
    return;
  }

  const ITERATIONS = 600000;
  const enc = new TextEncoder();
  const dec = new TextDecoder();
  const b64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)));
  const flash = (node) => {
    node.classList.add("fresh");
    requestAnimationFrame(() => requestAnimationFrame(() => node.classList.remove("fresh")));
  };

  const steps = $$(".vault-steps li");
  let stepTimer = 0;
  const showStep = (n, hold = false) => {
    clearTimeout(stepTimer);
    steps.forEach((li) => li.classList.toggle("is-active", li.dataset.step === String(n)));
    if (!hold) stepTimer = setTimeout(() => steps.forEach((li) => li.classList.remove("is-active")), 700);
  };

  const salt = crypto.getRandomValues(new Uint8Array(16));
  el.salt.textContent = b64(salt);

  const deriveKek = async (password) => {
    const base = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
    return crypto.subtle.deriveKey(
      { name: "PBKDF2", salt, iterations: ITERATIONS, hash: "SHA-256" },
      base, { name: "AES-GCM", length: 256 }, false, ["wrapKey", "unwrapKey"],
    );
  };

  const state = { dek: null, wrapped: null, wrapIv: null, ct: null, ctIv: null };
  let kekFor = null;
  let passTimer = 0;
  let noteTimer = 0;
  let seq = 0;

  const encryptNote = async () => {
    state.ctIv = crypto.getRandomValues(new Uint8Array(12));
    state.ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv: state.ctIv }, state.dek, enc.encode(el.note.value));
    el.cipher.textContent = b64(state.ct);
    flash(el.cipher);
    showStep(2);
  };

  const wrapWith = async (password) => {
    const mine = ++seq;
    if (!password) { el.status.textContent = t.msg_need_pass; return; }
    el.status.textContent = t.msg_working;
    showStep(1, true);
    const kek = await deriveKek(password);
    if (mine !== seq) return; // a newer password won
    showStep(3);
    state.wrapIv = crypto.getRandomValues(new Uint8Array(12));
    state.wrapped = await crypto.subtle.wrapKey("raw", state.dek, kek, { name: "AES-GCM", iv: state.wrapIv });
    kekFor = password;
    el.wrapped.textContent = b64(state.wrapped);
    el.status.textContent = "";
    flash(el.wrapped);
  };

  const unlock = async () => {
    if (!state.wrapped) return;
    const password = el.tryPass.value;
    if (!password) { setResult(t.msg_type_first, "bad"); return; }
    setResult(t.msg_working);
    try {
      const kek = await deriveKek(password);
      const dek = await crypto.subtle.unwrapKey(
        "raw", state.wrapped, kek, { name: "AES-GCM", iv: state.wrapIv },
        { name: "AES-GCM", length: 256 }, false, ["decrypt"],
      );
      const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: state.ctIv }, dek, state.ct);
      setResult(t.msg_ok + dec.decode(plain), "ok");
    } catch {
      setResult(t.msg_bad, "bad");
    }
  };

  const start = async () => {
    // The data key is created once. A password change only re-wraps it, as in Aegis.
    state.dek = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
    await encryptNote();
    await wrapWith(el.pass.value);
  };
  // Start after the page has loaded, so key derivation never competes with first paint.
  if (document.readyState === "complete") setTimeout(start, 300);
  else window.addEventListener("load", () => setTimeout(start, 300), { once: true });

  el.note.addEventListener("input", () => { clearTimeout(noteTimer); noteTimer = setTimeout(encryptNote, 120); });
  el.pass.addEventListener("input", () => {
    clearTimeout(passTimer);
    passTimer = setTimeout(() => { if (el.pass.value !== kekFor) wrapWith(el.pass.value); }, 450);
  });
  el.unlock.addEventListener("click", unlock);
  el.tryPass.addEventListener("keydown", (ev) => { if (ev.key === "Enter") unlock(); });
})();
