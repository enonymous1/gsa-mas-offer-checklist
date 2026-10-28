/* GSA MAS New Offer Checklist — single-page app, no dependencies.
 *
 * Data: checklist.json (generated from the source workbook by
 * tools/build_data.py) and provision_texts.json (Refresh 16 excerpts).
 * State: one versioned localStorage object; nothing leaves the browser.
 * All user and source text is inserted with textContent / DOM nodes only —
 * never innerHTML — so checklist content can never inject markup.
 */
(function () {
  "use strict";

  var STATE_KEY = "gsa-offer-checklist.v1";
  var THEME_KEY = "gsa-offer-checklist.v1.theme";
  var GSA_PDF_URL =
    "https://www.gsa.gov/system/files/MAS_Refresh_16_SCP-FSS-001_July_2023.pdf";

  var state = { offer: {}, checked: {}, comments: {} };
  var checklist = null;
  var provisionTexts = {};
  var filters = { query: "", group: "all", status: "all" };
  var currentDialogKey = null;

  /* ---------- state ---------- */

  function loadState() {
    try {
      var raw = localStorage.getItem(STATE_KEY);
      if (!raw) return;
      var parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        if (parsed.offer && typeof parsed.offer === "object") state.offer = parsed.offer;
        if (parsed.checked && typeof parsed.checked === "object") state.checked = parsed.checked;
        if (parsed.comments && typeof parsed.comments === "object") state.comments = parsed.comments;
      }
    } catch (e) {
      /* Corrupt or unavailable storage: start empty, keep the app usable. */
    }
  }

  function saveState() {
    try {
      localStorage.setItem(STATE_KEY, JSON.stringify(state));
    } catch (e) {
      setStatus("Could not save progress: browser storage is unavailable.");
    }
  }

  function itemKey(groupId, sectionIndex, line) {
    return groupId + "/" + sectionIndex + "/" + line;
  }

  function allItems() {
    var out = [];
    checklist.groups.forEach(function (group, gi) {
      group.sections.forEach(function (section, si) {
        section.items.forEach(function (item) {
          out.push({ group: group, groupIndex: gi, section: section, sectionIndex: si, item: item });
        });
      });
    });
    return out;
  }

  function isChecked(entry) {
    return !!state.checked[itemKey(entry.group.id, entry.sectionIndex, entry.item.line)];
  }

  function userNote(entry) {
    return state.comments[itemKey(entry.group.id, entry.sectionIndex, entry.item.line)] || "";
  }

  /* ---------- safe text with links ---------- */

  // Build a fragment for source text, turning only known, allowlisted
  // references into links. Everything else stays plain text.
  function linkify(text) {
    var fragment = document.createDocumentFragment();
    var pattern =
      /(https?:\/\/[^\s)]+|www\.[^\s)]+)|Provision\s+SCP-FSS-001|SCP-FSS-001|SAM registration|NIST\s+SP\s+800-145|Section\s+508|TAA Compliance|FAR\s+\d+[\d.\-]*/gi;
    var last = 0;
    var match;
    while ((match = pattern.exec(text)) !== null) {
      if (match.index > last) {
        fragment.appendChild(document.createTextNode(text.slice(last, match.index)));
      }
      var token = match[0];
      var href = null;
      if (/^https?:\/\//i.test(token) || /^www\./i.test(token)) {
        href = /^www\./i.test(token) ? "https://" + token : token;
      } else if (/SCP-FSS-001/i.test(token)) {
        href = GSA_PDF_URL;
      } else if (/SAM registration/i.test(token)) {
        href = "https://sam.gov";
      } else if (/NIST/i.test(token)) {
        href = "https://csrc.nist.gov/publications/detail/sp/800-145/final";
      } else if (/Section\s+508/i.test(token)) {
        href = "https://www.section508.gov/";
      } else if (/TAA Compliance/i.test(token)) {
        href = "https://www.acquisition.gov/far/part-25#FAR_25_4";
      } else if (/^FAR/i.test(token)) {
        var part = token.replace(/^FAR\s+/i, "").split(".")[0];
        href = "https://www.acquisition.gov/far/part-" + part;
      }
      if (href) {
        var a = document.createElement("a");
        a.href = href;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = token;
        fragment.appendChild(a);
      } else {
        fragment.appendChild(document.createTextNode(token));
      }
      last = match.index + token.length;
    }
    if (last < text.length) {
      fragment.appendChild(document.createTextNode(text.slice(last)));
    }
    return fragment;
  }

  function provisionKeyFor(ref) {
    var idx = ref.indexOf("SCP-FSS-001");
    if (idx === -1) return null;
    var suffix = ref.slice(idx + "SCP-FSS-001".length).trim();
    var norm = function (s) {
      return s.replace(/\s+/g, "").replace(/\.+$/, "");
    };
    var wanted = norm(suffix);
    var keys = Object.keys(provisionTexts);
    for (var i = 0; i < keys.length; i++) {
      if (norm(keys[i]) === wanted) return keys[i];
    }
    return null;
  }

  /* ---------- rendering ---------- */

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function setStatus(message) {
    document.getElementById("status-message").textContent = message || "";
  }

  function updateProgress() {
    var items = allItems();
    var done = items.filter(isChecked).length;
    var pct = items.length ? Math.round((done / items.length) * 100) : 0;
    var bar = document.getElementById("progress-bar");
    var fill = document.getElementById("progress-fill");
    bar.setAttribute("aria-valuenow", String(pct));
    fill.style.width = pct + "%";
    document.getElementById("progress-text").textContent =
      done + " of " + items.length + " items complete (" + pct + "%)";
    return { done: done, total: items.length };
  }

  function matchesFilters(entry) {
    var key = itemKey(entry.group.id, entry.sectionIndex, entry.item.line);
    if (filters.group !== "all" && entry.group.id !== filters.group) return false;
    if (filters.status === "remaining" && state.checked[key]) return false;
    if (filters.status === "completed" && !state.checked[key]) return false;
    if (filters.status === "noted" && !state.comments[key]) return false;
    if (filters.query) {
      var haystack = [
        entry.group.title,
        entry.section.title,
        entry.item.doc,
        entry.item.ref,
        entry.item.comments,
        entry.item.subcategory,
        entry.item.sin,
        "line " + entry.item.line,
      ].join("\n").toLowerCase();
      if (haystack.indexOf(filters.query) === -1) return false;
    }
    return true;
  }

  function renderJumpNav() {
    var nav = document.getElementById("jump-nav");
    nav.textContent = "";
    var items = allItems();
    checklist.groups.forEach(function (group) {
      var groupItems = items.filter(function (e) { return e.group === group; });
      var done = groupItems.filter(isChecked).length;
      var a = document.createElement("a");
      a.href = "#group-" + group.id;
      a.textContent = group.title + " (" + done + "/" + groupItems.length + ")";
      nav.appendChild(a);
    });
  }

  function renderChecklist(focusKey) {
    var container = document.getElementById("checklist");
    container.textContent = "";
    var visible = 0;

    checklist.groups.forEach(function (group, gi) {
      var groupEntries = [];
      group.sections.forEach(function (section, si) {
        section.items.forEach(function (item) {
          var entry = { group: group, groupIndex: gi, section: section, sectionIndex: si, item: item };
          if (matchesFilters(entry)) groupEntries.push(entry);
        });
      });
      if (filters.group !== "all" && group.id !== filters.group) return;
      if (groupEntries.length === 0 && filters.query === "" && filters.status === "all") {
        // Empty groups (no requirements in the source) still render, below.
      } else if (groupEntries.length === 0) {
        return;
      }

      var sectionEl = el("section", "group");
      sectionEl.id = "group-" + group.id;
      var head = el("div", "group-head");
      head.appendChild(el("h2", null, group.title));
      var allGroup = allItems().filter(function (e) { return e.group === group; });
      var doneGroup = allGroup.filter(isChecked).length;
      head.appendChild(el("p", "group-count", doneGroup + " of " + allGroup.length + " complete"));
      sectionEl.appendChild(head);

      if (allGroup.length === 0) {
        sectionEl.appendChild(el("p", "group-note",
          "No category-specific requirements for this category in the June 2025 checklist. The general Offer Review Checklist above still applies."));
      }

      group.sections.forEach(function (section, si) {
        var sectionEntries = groupEntries.filter(function (e) { return e.sectionIndex === si; });
        if (sectionEntries.length === 0) return;
        sectionEl.appendChild(el("h3", null, section.title));
        var list = el("ul", "item-list");
        sectionEntries.forEach(function (entry) {
          list.appendChild(renderItem(entry));
          visible += 1;
        });
        sectionEl.appendChild(list);
      });
      container.appendChild(sectionEl);
    });

    if (visible === 0) {
      var empty = el("div", "card empty-state");
      empty.appendChild(el("p", null, "No requirements match the current search and filters."));
      var clear = el("button", null, "Clear search and filters");
      clear.type = "button";
      clear.addEventListener("click", function () {
        filters = { query: "", group: "all", status: "all" };
        document.getElementById("search").value = "";
        document.getElementById("group-filter").value = "all";
        document.getElementById("status-filter").value = "all";
        renderAll();
        document.getElementById("search").focus();
      });
      empty.appendChild(clear);
      container.appendChild(empty);
    }

    if (focusKey) {
      var target = container.querySelector('[data-item-key="' + focusKey + '"] input[type="checkbox"]');
      if (target) target.focus();
    }
  }

  function renderItem(entry) {
    var item = entry.item;
    var key = itemKey(entry.group.id, entry.sectionIndex, item.line);
    var checked = isChecked(entry);
    var note = userNote(entry);

    var li = el("li", "item" + (checked ? " done" : ""));
    li.dataset.itemKey = key;

    var checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = "check-" + key.replace(/\//g, "-");
    checkbox.checked = checked;
    checkbox.setAttribute("aria-label", "Mark line " + item.line + " complete: " + item.doc.slice(0, 80));
    checkbox.addEventListener("change", function () {
      if (checkbox.checked) state.checked[key] = true;
      else delete state.checked[key];
      saveState();
      renderAll(key);
    });
    li.appendChild(checkbox);

    var main = el("div", "item-main");
    var docP = el("p", "item-doc");
    var lineBadge = el("span", "line-number", "Line " + item.line);
    docP.appendChild(lineBadge);
    docP.appendChild(linkify(item.doc));
    if (note) {
      docP.appendChild(el("span", "note-badge", "Note"));
    }
    main.appendChild(docP);

    var metaParts = [];
    if (item.ref) metaParts.push("Ref: " + item.ref);
    if (item.subcategory) metaParts.push("Subcategory: " + item.subcategory);
    if (item.sin) metaParts.push("SIN: " + item.sin);
    if (metaParts.length) {
      var meta = el("p", "item-meta");
      meta.appendChild(linkify(metaParts.join("  ·  ")));
      main.appendChild(meta);
    }
    if (item.comments) {
      var guidance = el("p", "item-meta", "Guidance: " + item.comments);
      main.appendChild(guidance);
    }
    li.appendChild(main);

    var actions = el("div", "item-actions");
    var detailsBtn = el("button", null, "Details");
    detailsBtn.type = "button";
    detailsBtn.addEventListener("click", function () { openDialog(entry); });
    actions.appendChild(detailsBtn);
    li.appendChild(actions);
    return li;
  }

  function renderAll(focusKey) {
    updateProgress();
    renderJumpNav();
    renderChecklist(focusKey);
  }

  /* ---------- dialog ---------- */

  function openDialog(entry) {
    var item = entry.item;
    var key = itemKey(entry.group.id, entry.sectionIndex, item.line);
    currentDialogKey = key;
    var dialog = document.getElementById("item-dialog");
    document.getElementById("dialog-title").textContent =
      entry.group.title + " — Line " + item.line;
    document.getElementById("dialog-line").textContent =
      entry.section.title + "  ·  " + entry.group.title;
    var docEl = document.getElementById("dialog-doc");
    docEl.textContent = "";
    docEl.appendChild(linkify(item.doc));

    var refSection = document.getElementById("dialog-ref-section");
    if (item.ref) {
      refSection.hidden = false;
      var refEl = document.getElementById("dialog-ref");
      refEl.textContent = "";
      refEl.appendChild(linkify(item.ref));
    } else {
      refSection.hidden = true;
    }

    var metaSection = document.getElementById("dialog-meta-section");
    var metaText = [];
    if (item.subcategory) metaText.push("Subcategory: " + item.subcategory);
    if (item.sin) metaText.push("SIN: " + item.sin);
    if (metaText.length) {
      metaSection.hidden = false;
      document.getElementById("dialog-meta").textContent = metaText.join("\n");
    } else {
      metaSection.hidden = true;
    }

    var guidanceSection = document.getElementById("dialog-guidance-section");
    if (item.comments) {
      guidanceSection.hidden = false;
      document.getElementById("dialog-guidance").textContent = item.comments;
    } else {
      guidanceSection.hidden = true;
    }

    var provisionSection = document.getElementById("dialog-provision-section");
    var pkey = provisionKeyFor(item.ref || "");
    if (pkey && provisionTexts[pkey]) {
      provisionSection.hidden = false;
      document.getElementById("dialog-provision").textContent = provisionTexts[pkey];
    } else {
      provisionSection.hidden = true;
    }

    document.getElementById("dialog-note").value = userNote(entry);
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    document.getElementById("dialog-note").focus();
  }

  function closeDialog() {
    var dialog = document.getElementById("item-dialog");
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
    currentDialogKey = null;
  }

  /* ---------- export / import ---------- */

  function download(filename, text, type) {
    var blob = new Blob([text], { type: type });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function csvCell(value) {
    var text = value === undefined || value === null ? "" : String(value);
    if (/[",\n\r]/.test(text)) return '"' + text.replace(/"/g, '""') + '"';
    return text;
  }

  function exportJson() {
    var payload = {
      app: "gsa-mas-new-offer-checklist",
      version: 1,
      exportedAt: new Date().toISOString(),
      dataSource: checklist.meta.sourceFile + " (" + checklist.meta.sourceDate + ")",
      offer: state.offer,
      checked: state.checked,
      comments: state.comments,
    };
    download("gsa-offer-checklist-progress.json", JSON.stringify(payload, null, 2) + "\n", "application/json");
    setStatus("Progress exported as JSON.");
  }

  function exportCsv() {
    var rows = [["Group", "Section", "Line", "Requirement", "Reference", "Subcategory", "SIN", "Guidance", "Done", "My note"]];
    allItems().forEach(function (entry) {
      rows.push([
        entry.group.title,
        entry.section.title,
        entry.item.line,
        entry.item.doc,
        entry.item.ref,
        entry.item.subcategory,
        entry.item.sin,
        entry.item.comments,
        isChecked(entry) ? "Yes" : "No",
        userNote(entry),
      ]);
    });
    var header = [];
    if (state.offer.offerorName) header.push(["Offeror", state.offer.offerorName]);
    if (state.offer.offerNumber) header.push(["Offer number", state.offer.offerNumber]);
    if (state.offer.uei) header.push(["UEI", state.offer.uei]);
    if (state.offer.sinsOffered) header.push(["SINs offered", state.offer.sinsOffered]);
    if (state.offer.commodityType) header.push(["Commodity type", state.offer.commodityType]);
    var lines = header.map(function (pair) { return pair.map(csvCell).join(","); });
    lines.push("");
    lines = lines.concat(rows.map(function (row) { return row.map(csvCell).join(","); }));
    download("gsa-offer-checklist.csv", "\uFEFF" + lines.join("\r\n") + "\r\n", "text/csv");
    setStatus("Checklist exported as CSV (" + rows.length + " rows).");
  }

  function importState(file) {
    var reader = new FileReader();
    reader.onload = function () {
      try {
        var parsed = JSON.parse(reader.result);
        if (!parsed || typeof parsed !== "object") throw new Error("not an object");
        var knownKeys = {};
        allItems().forEach(function (entry) {
          knownKeys[itemKey(entry.group.id, entry.sectionIndex, entry.item.line)] = true;
        });
        var checked = {};
        var comments = {};
        if (parsed.checked && typeof parsed.checked === "object") {
          Object.keys(parsed.checked).forEach(function (k) {
            if (knownKeys[k] && parsed.checked[k]) checked[k] = true;
          });
        }
        if (parsed.comments && typeof parsed.comments === "object") {
          Object.keys(parsed.comments).forEach(function (k) {
            if (knownKeys[k] && typeof parsed.comments[k] === "string" && parsed.comments[k]) {
              comments[k] = parsed.comments[k];
            }
          });
        }
        var offer = {};
        if (parsed.offer && typeof parsed.offer === "object") {
          ["offerorName", "offerNumber", "uei", "sinsOffered", "commodityType"].forEach(function (field) {
            if (typeof parsed.offer[field] === "string") offer[field] = parsed.offer[field];
          });
        }
        state = { offer: offer, checked: checked, comments: comments };
        saveState();
        fillOfferForm();
        renderAll();
        setStatus("Imported progress: " + Object.keys(checked).length + " items complete, " +
          Object.keys(comments).length + " notes. Unknown keys were ignored.");
      } catch (e) {
        setStatus("Import failed: that file is not a valid checklist progress export.");
      }
    };
    reader.readAsText(file);
  }

  /* ---------- offer form ---------- */

  function fillOfferForm() {
    document.getElementById("offeror-name").value = state.offer.offerorName || "";
    document.getElementById("offer-number").value = state.offer.offerNumber || "";
    document.getElementById("uei").value = state.offer.uei || "";
    document.getElementById("sins-offered").value = state.offer.sinsOffered || "";
    var radios = document.querySelectorAll('input[name="commodityType"]');
    radios.forEach(function (radio) {
      radio.checked = (state.offer.commodityType || "product") === radio.value;
    });
  }

  function readOfferForm() {
    var selected = document.querySelector('input[name="commodityType"]:checked');
    state.offer = {
      offerorName: document.getElementById("offeror-name").value,
      offerNumber: document.getElementById("offer-number").value,
      uei: document.getElementById("uei").value,
      sinsOffered: document.getElementById("sins-offered").value,
      commodityType: selected ? selected.value : "product",
    };
    saveState();
  }

  /* ---------- theme ---------- */

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var btn = document.getElementById("theme-toggle");
    btn.textContent = theme === "dark" ? "Light mode" : "Dark mode";
    btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* ignore */ }
  }

  /* ---------- init ---------- */

  function init() {
    loadState();
    applyTheme(document.documentElement.getAttribute("data-theme") || "light");

    document.getElementById("theme-toggle").addEventListener("click", function () {
      var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
    });

    document.getElementById("offer-form").addEventListener("input", readOfferForm);
    fillOfferForm();

    var searchTimer = null;
    document.getElementById("search").addEventListener("input", function (e) {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function () {
        filters.query = e.target.value.trim().toLowerCase();
        renderAll();
      }, 120);
    });
    document.getElementById("group-filter").addEventListener("change", function (e) {
      filters.group = e.target.value;
      renderAll();
    });
    document.getElementById("status-filter").addEventListener("change", function (e) {
      filters.status = e.target.value;
      renderAll();
    });

    document.getElementById("export-json").addEventListener("click", exportJson);
    document.getElementById("export-csv").addEventListener("click", exportCsv);
    document.getElementById("print-button").addEventListener("click", function () { window.print(); });
    document.getElementById("clear-button").addEventListener("click", function () {
      if (!window.confirm("Clear all saved progress, notes, and offer details in this browser?")) return;
      state = { offer: {}, checked: {}, comments: {} };
      try { localStorage.removeItem(STATE_KEY); } catch (e) { /* ignore */ }
      fillOfferForm();
      renderAll();
      setStatus("Saved data cleared.");
    });
    document.getElementById("import-button").addEventListener("click", function () {
      document.getElementById("import-file").click();
    });
    document.getElementById("import-file").addEventListener("change", function (e) {
      if (e.target.files && e.target.files[0]) importState(e.target.files[0]);
      e.target.value = "";
    });

    document.getElementById("dialog-close").addEventListener("click", closeDialog);
    document.getElementById("item-dialog").addEventListener("click", function (e) {
      if (e.target === this) closeDialog();
    });
    document.getElementById("dialog-save-note").addEventListener("click", function () {
      if (!currentDialogKey) return;
      var value = document.getElementById("dialog-note").value.trim();
      if (value) state.comments[currentDialogKey] = value;
      else delete state.comments[currentDialogKey];
      saveState();
      renderAll();
      setStatus(value ? "Note saved." : "Note removed.");
      closeDialog();
    });
    document.getElementById("dialog-clear-note").addEventListener("click", function () {
      if (!currentDialogKey) return;
      delete state.comments[currentDialogKey];
      document.getElementById("dialog-note").value = "";
      saveState();
      renderAll();
      setStatus("Note removed.");
    });

    Promise.all([
      fetch("checklist.json").then(function (r) {
        if (!r.ok) throw new Error("checklist.json HTTP " + r.status);
        return r.json();
      }),
      fetch("provision_texts.json").then(function (r) {
        if (!r.ok) throw new Error("provision_texts.json HTTP " + r.status);
        return r.json();
      }),
    ]).then(function (results) {
      checklist = results[0];
      provisionTexts = (results[1] && results[1].texts) || {};
      var select = document.getElementById("group-filter");
      checklist.groups.forEach(function (group) {
        var opt = document.createElement("option");
        opt.value = group.id;
        opt.textContent = group.title;
        select.appendChild(opt);
      });
      document.getElementById("data-meta").textContent =
        checklist.meta.itemCount + " requirements  ·  Source: " +
        checklist.meta.sourceFile + " (" + checklist.meta.sourceDate + ")  ·  " +
        checklist.meta.solicitation + ". Generated by " + checklist.meta.generatedBy + ".";
      renderAll();
    }).catch(function (err) {
      document.getElementById("data-meta").textContent = "";
      var container = document.getElementById("checklist");
      container.textContent = "";
      var box = el("div", "card error");
      box.appendChild(el("p", null,
        "Could not load the checklist data (" + err.message + "). " +
        "Serve this folder with a local web server instead of opening index.html directly, for example: python3 -m http.server 8000"));
      container.appendChild(box);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
