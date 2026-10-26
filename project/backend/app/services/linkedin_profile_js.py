"""
JavaScript run inside LinkedIn pages by the profile scraper
============================================================
Each constant is a function body Playwright passes to page.evaluate(). They
live here as raw strings, so their regexes reach the browser exactly as
written, and the generated scraper script embeds them with repr().
"""

JS_PERSONAL = r"""
() => {
    const r = {};
    // Name
    const h1 = document.querySelector("h1.text-heading-xlarge, h1[aria-label], h1");
    if (h1) r.name = (h1.innerText || h1.textContent || "").trim();
    // Headline – first .text-body-medium inside top section (not nav, not buttons)
    const topSection = document.querySelector(".pv-text-details__left-panel, .mt2.relative, section.artdeco-card");
    if (topSection) {
        const hl = topSection.querySelector(".text-body-medium");
        if (hl) r.headline = (hl.innerText || hl.textContent || "").trim();
    }
    if (!r.headline) {
        const hl = document.querySelector(".text-body-medium.break-words");
        if (hl) r.headline = (hl.innerText || hl.textContent || "").trim();
    }
    // Location
    const locCandidates = [
        ".pv-text-details__left-panel span.text-body-small.t-black--light",
        "span.t-black--light.break-words",
        ".pv-top-card--list.pv-top-card--list-bullet li",
    ];
    for (const sel of locCandidates) {
        const el = document.querySelector(sel);
        if (el) { r.location = (el.innerText || el.textContent || "").trim(); break; }
    }
    return r;
}
"""

JS_SUMMARY = r"""
() => {
    const cards = document.querySelectorAll("section, div.artdeco-card");
    for (const card of cards) {
        const anchor = card.querySelector("#about");
        if (!anchor) continue;
        const spans = card.querySelectorAll('span[aria-hidden="true"]');
        for (const sp of spans) {
            const t = (sp.innerText || sp.textContent || "").trim();
            if (t.length > 60) return t;
        }
    }
    const ab = document.querySelector(".pv-about-section, .pv-about__summary-text");
    if (ab) return (ab.innerText || ab.textContent || "").trim();
    return null;
}
"""

JS_CONTACT = r"""
() => {
    const result = {};
    // Section titles map us to the following sibling value
    const sections = Array.from(document.querySelectorAll("section"));
    for (const sec of sections) {
        const h3 = sec.querySelector("h3");
        if (!h3) continue;
        const title = (h3.innerText || h3.textContent || "").trim().toLowerCase();
        const valEl = sec.querySelector("a, span.t-14");
        if (!valEl) continue;
        const val  = (valEl.getAttribute("href") || valEl.innerText || valEl.textContent || "").trim();
        if (title.includes("email"))   { result.email   = val.replace("mailto:",""); }
        if (title.includes("phone"))   { result.phone   = val; }
        if (title.includes("website") || title.includes("url")) { result.website = val; }
    }
    // Fallback: walk all links
    const links = Array.from(document.querySelectorAll("a[href]"));
    for (const a of links) {
        const href = (a.getAttribute("href") || "").trim();
        if (href.startsWith("mailto:") && !result.email)   { result.email   = href.replace("mailto:",""); }
        if (href.startsWith("http")   && !href.includes("linkedin.com") && !result.website) { result.website = href; }
        if (href.includes("linkedin.com/in/") && !result.linkedin_url) { result.linkedin_url = href.split("?")[0].replace(/[/]$/, ""); }
    }
    // Phone: any span that looks like a phone number
    if (!result.phone) {
        const spans = Array.from(document.querySelectorAll("span, a"));
        for (const sp of spans) {
            const t = (sp.innerText || sp.textContent || "").trim();
            if (new RegExp('^[+.(0-9][0-9 .()+/-](6,)$').test(t) && t.replace(/[^0-9]/g,'').length >= 6) { result.phone = t; break; }
        }
    }
    return result;
}
"""

JS_LIST_ITEMS = r"""
() => {
    const selectors = [
        "li.pvs-list__paged-list-item",
        "li.artdeco-list__item",
    ];
    for (const sel of selectors) {
        const items = Array.from(document.querySelectorAll(sel));
        if (items.length === 0) continue;
        return items.map(item => {
            const spans = Array.from(item.querySelectorAll('span[aria-hidden="true"]'))
                            .map(s => (s.innerText || s.textContent || "").trim())
                            .filter(t => t.length > 0);
            // external links
            let url = null;
            for (const a of item.querySelectorAll("a[href]")) {
                const h = a.getAttribute("href") || "";
                if (h.startsWith("http") && !h.includes("linkedin.com")) { url = h; break; }
            }
            return { spans, url };
        }).filter(e => e.spans.length > 0);
    }
    return [];
}
"""

JS_EDUCATION = r"""
() => {
    function tc(el) {
        if (!el) return "";
        // Use textContent (not innerText) for reliability on hidden spans,
        // then normalise all whitespace.
        return (el.textContent || "").replace(/\s+/g, " ").trim();
    }
    function isDate(t) {
        return /[12][0-9]{3}/.test(t) && (/\u2013|\u2014|[-–—]|\bto\b|\bpresent\b/i.test(t));
    }
    function isDegree(t) {
        const KWORDS = [
            "bachelor","master","doctor","phd","b.tech","m.tech","b.e","m.e","mba",
            "b.sc","m.sc","b.a","m.a","associate","diploma","certificate",
            "high school","higher secondary","engineering","technology","science","arts","commerce",
        ];
        const lower = t.toLowerCase();
        return KWORDS.some(k => lower.includes(k));
    }

    const mainEl = document.querySelector(
        'main, [role="main"], div[class*="scaffold-layout__main"]'
    ) || document;

    // Only direct children of the root list to avoid sub-items
    const rootUl = mainEl.querySelector('ul.pvs-list, ul[class*="pvs-list"]');
    const rows = rootUl
        ? Array.from(rootUl.querySelectorAll(':scope > li'))
        : Array.from(mainEl.querySelectorAll('li.pvs-list__paged-list-item'));

    const results = [];

    for (const item of rows) {
        const edu = {};

        // ── School: first bold text node ──────────────────────────────────────
        const boldSel = [
            ".mr1.t-bold span[aria-hidden='true']",
            ".t-bold span[aria-hidden='true']",
            "span[aria-hidden='true']",         // last resort: very first span
        ];
        for (const sel of boldSel) {
            const el = item.querySelector(sel);
            const v = tc(el);
            if (v.length >= 3) { edu.school = v; break; }
        }
        if (!edu.school) continue;

        // ── Degree / field: ALL subtitle spans, deduplicated by value ─────────
        // Strictly target `span.t-14.t-normal` that are NOT `t-black--light`,
        // then take only their direct `span[aria-hidden]` child (the leaf).
        // Using querySelectorAll on the item, then filtering to avoid grabbing
        // spans that live inside nested sub-list items.
        const subtitleTexts = [];
        const seen = new Set();
        const subtitleEls = Array.from(
            item.querySelectorAll("span.t-14.t-normal:not(.t-black--light)")
        );
        for (const se of subtitleEls) {
            // Skip if this element is inside a nested <ul> (sub-item)
            if (se.closest('ul') !== rootUl && se.closest('ul') !== null) continue;
            // Prefer the aria-hidden child; fall back to the span itself
            const leaf = se.querySelector("span[aria-hidden='true']") || se;
            const v = tc(leaf);
            if (v.length > 0 && !seen.has(v)) {
                seen.add(v);
                subtitleTexts.push(v);
            }
        }

        // Assign degree and field from subtitle texts.
        // LinkedIn sometimes combines them in a single span: "B.Tech · Computer Science"
        // Expand any combined entries by splitting on " · " or ", " so each
        // token becomes its own element before degree/field assignment.
        const rawNonDate = subtitleTexts.filter(t => !isDate(t));
        const nonDate = [];
        for (const t of rawNonDate) {
            const parts = t.split(/\s*[·•,]\s*/).map(p => p.trim()).filter(p => p.length > 0);
            for (const p of parts) nonDate.push(p);
        }
        if (nonDate.length >= 1) {
            if (isDegree(nonDate[0])) {
                edu.degree = nonDate[0];
                if (nonDate[1]) edu.field = nonDate[1];
            } else {
                edu.degree = nonDate[0];
                if (nonDate[1] && isDegree(nonDate[1])) {
                    // swap: second token is actually the degree
                    edu.field = nonDate[0];
                    edu.degree = nonDate[1];
                } else if (nonDate[1]) {
                    edu.field = nonDate[1];
                }
            }
        }

        // ── Dates: caption wrapper first, then any dark-light span with year ─
        const capEl = item.querySelector("span.pvs-entity__caption-wrapper[aria-hidden='true']");
        if (capEl) {
            edu.dates = tc(capEl);
        } else {
            const darkEls = Array.from(
                item.querySelectorAll("span.t-14.t-normal.t-black--light span[aria-hidden='true']")
            ).map(tc).filter(isDate);
            if (darkEls.length > 0) edu.dates = darkEls[0];
        }

        // Require at least one data point beyond the school name
        if (!edu.degree && !edu.dates) continue;

        results.push(edu);
    }

    return results;
}
"""
