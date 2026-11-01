/* sepehrkhasto.github.io: menu, section tracking, lightbox, copy button and the encryption demo. */
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

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
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && nav.classList.contains("open")) { setOpen(false); menuBtn.focus(); }
    });
    window.matchMedia("(min-width: 901px)").addEventListener("change", () => setOpen(false));
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
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => seen.set(en.target.id, en.isIntersecting));
      const current = cases.find((c) => seen.get(c.id));
      tabLinks.forEach((a) => {
        const on = Boolean(current) && a.getAttribute("href") === `#${current.id}`;
        if (on) {
          a.setAttribute("aria-current", "true");
          const list = a.closest("ol");
          const r = a.getBoundingClientRect();
          const box = list.getBoundingClientRect();
          if (r.left < box.left) list.scrollBy({ left: r.left - box.left - 16 });
          else if (r.right > box.right) list.scrollBy({ left: r.right - box.right + 16 });
        } else a.removeAttribute("aria-current");
      });
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
    $("[data-close]", box).addEventListener("click", () => box.close());
    box.addEventListener("click", (ev) => { if (ev.target === box) box.close(); });
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
