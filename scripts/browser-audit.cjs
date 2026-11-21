/* Run with Playwright available to Node; BASE_URL defaults to the local audit server.
 * CHROMIUM_PATH selects a system browser, otherwise Playwright's installed Chromium is used.
 * This audits the built client and both real and controlled API responses.
 */
const path = require("node:path");
const frontendRequire = require("node:module").createRequire(
  path.resolve(__dirname, "../frontend/package.json"),
);
const browsers = frontendRequire("playwright");
const engine = process.env.BROWSER_ENGINE || "chromium";
if (!["chromium", "firefox", "webkit"].includes(engine))
  throw new Error("Unknown browser engine");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const base = process.env.BASE_URL || "http://127.0.0.1:8010";
const output =
  process.env.AUDIT_OUTPUT_DIR || path.resolve(__dirname, "../docs/audit");
const axePath =
  process.env.AXE_PATH || frontendRequire.resolve("axe-core/axe.min.js");
fs.mkdirSync(output, { recursive: true });
const citation = {
  id: "fixture-chunk",
  document: "FLEXI-ULife Prime Saver.pdf",
  page: 8,
  section: "Value-creating Advantages",
  excerpt:
    "The current assumed base crediting interest rate and the current assumed retrospective additional interest rate are not guaranteed.",
};
const answer = {
  message:
    "The assumed rate is **not guaranteed [1]**.\n\n| Detail | Evidence |\n| --- | --- |\n| Interest | Check the brochure [1] |",
  citations: [citation],
  notices: [
    "Brochure facts only.",
    "Confirm your own circumstances with the insurer.",
  ],
  language: "en",
  kind: "answer",
  used_retrieval: true,
  retrieval_mode: "lexical",
};
answer.message +=
  "\n\n![tracking image](https://example.invalid/tracker.png) [Untrusted link](https://example.invalid/verify)";
const checks = [];
(async () => {
  const browser = await browsers[engine].launch({
    ...(engine === "chromium"
      ? {
          executablePath:
            process.env.CHROMIUM_PATH ||
            (fs.existsSync("/usr/bin/chromium")
              ? "/usr/bin/chromium"
              : undefined),
          args: ["--no-sandbox"],
        }
      : {}),
    headless: true,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    permissions:
      engine === "chromium" ? ["clipboard-read", "clipboard-write"] : [],
    reducedMotion: "reduce",
  });
  const p = await context.newPage();
  const errors = [];
  p.on("console", (message) => {
    if (message.type() === "error") {
      const expectedMockError = message.location().url === `${base}/api/chat` && /Failed to load resource.*(?:502|429|413)/.test(message.text());
      if (!expectedMockError) errors.push(message.text());
    }
  });
  const externalRequests = [];
  p.on("request", (request) => {
    if (request.url().includes("example.invalid"))
      externalRequests.push(request.url());
  });
  p.on("pageerror", (e) => errors.push(e.message));
  await p.goto(base);
  await p.getByRole("heading", { level: 1 }).waitFor();
  for (const width of [1440, 1024, 768, 390, 320]) {
    await p.setViewportSize({ width, height: 844 });
    assert(
      await p.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      `overflow at ${width}`,
    );
    assert(
      await p.locator("#question").evaluate((e) => {
        const r = e.getBoundingClientRect();
        return r.top >= 0 && r.bottom <= innerHeight;
      }),
    );
    assert.equal(await p.locator("dialog").evaluate((d) => d.open), false);
    const rect = await p.locator(".conversation-scroll").boundingBox(),
      dock = await p.locator(".composer-dock").boundingBox();
    assert(rect.y + rect.height <= dock.y + 1, "composer overlaps content");
  }
  checks.push(
    "viewport reflow 320, 390, 768, 1024, 1440; composer stays outside scroll region",
  );
  await p.setViewportSize({ width: 1440, height: 1000 });
  await p.screenshot({ path: path.join(output, "after-desktop.png") });
  // Live request exercises actual retrieval, not a mocked success path.
  await p.getByRole("button", { name: /02 The 4% rate/ }).click();
  await p.locator(".markdown").waitFor();
  assert(await p.locator(".markdown").innerText());
  assert.equal(await p.locator('[role="log"]').getAttribute("aria-live"), "polite");
  assert(await p.getByRole("button", { name: /Citation 1:/ }).count());
  await p.screenshot({ path: path.join(output, "after-chat.png") });
  await p
    .getByRole("button", { name: /Citation 1:/ })
    .first()
    .click();
  await p.locator("dialog[open]").waitFor();
  assert(await p.locator(".source-excerpt blockquote").innerText());
  assert(
    (await p.locator(".source-excerpt a").getAttribute("href")).includes(
      "#page=",
    ),
  );
  await p.keyboard.press("Escape");
  await p.waitForFunction(() => !document.querySelector("dialog").open);
  assert(
    (
      await p.evaluate(() => document.activeElement?.getAttribute("aria-label"))
    )?.includes("Citation 1:"),
  );
  checks.push(
    "real API chat, source excerpt, PDF page link, Escape and focus return",
  );
  // Native selector, persisted language, all three scripts.
  for (const lang of ["zh-Hans", "zh-Hant", "en"]) {
    await p.getByRole("combobox").selectOption(lang);
    await p.reload();
    assert.equal(await p.locator("html").getAttribute("lang"), lang);
  }
  checks.push(
    "English, Simplified and Traditional language selection persists across reload",
  );
  await p.route("**/api/chat", (r) => r.fulfill({ json: answer }));
  await p.locator("#question").fill("Nested citation test");
  await p.getByRole("button", { name: "Send question" }).click();
  await p.getByText("The assumed rate is").waitFor();
  assert.equal(
    await p.getByRole("button", { name: /Citation 1:/ }).count(),
    2,
    "nested strong and table citation chips",
  );
  assert(
    await p
      .getByText("Confirm your own circumstances with the insurer.")
      .isVisible(),
  );
  await p.getByRole("button", { name: "Copy answer", exact: true }).click();
  if (engine === "chromium") {
    assert(
      (await p.evaluate(() => navigator.clipboard.readText())).includes(
        "**not guaranteed [1]**",
      ),
    );
  } else {
    await p.getByText("Copied", { exact: true }).waitFor();
  }
  checks.push(
    "nested Markdown citations in emphasis/table; every notice visible; copy original answer",
  );
  await p
    .getByRole("button", {
      name: "Citation 1: FLEXI-ULife Prime Saver.pdf, page 8",
    })
    .first()
    .click();
  await p.locator("dialog[open]").waitFor();
  for (let i = 0; i < 12; i++) {
    await p.keyboard.press("Tab");
    assert(
      await p.evaluate(() =>
        document.querySelector("dialog").contains(document.activeElement),
      ),
      "dialog focus escaped",
    );
  }
  await p.screenshot({ path: path.join(output, "after-sources.png") });
  await p.keyboard.press("Escape");
  checks.push("source dialog traps keyboard focus and closes with Escape");
  assert.equal(
    await p.locator('.markdown img, .markdown a[href^="https:"]').count(),
    0,
  );
  assert.deepEqual(externalRequests, []);
  checks.push(
    "model-supplied images and external links cannot trigger external browsing requests",
  );
  // Repeat error then retry without duplicating the user turn.
  await p.getByRole("button", { name: "New conversation" }).click();
  await p.unroute("**/api/chat");
  let tries = 0;
  await p.route("**/api/chat", (r) =>
    ++tries === 1
      ? r.fulfill({ status: 502, json: { detail: "failed" } })
      : r.fulfill({ json: answer }),
  );
  await p.locator("#question").fill("Retry me");
  await p.getByRole("button", { name: "Send question" }).click();
  await p.locator(".assistant-message[role=alert]").waitFor();
  await p.getByRole("button", { name: "Try again" }).click();
  await p.locator(".markdown").waitFor();
  assert.equal(await p.locator(".user-message").count(), 1);
  checks.push("network error and retry keep one user turn");
  for (const [status, phrase] of [
    [429, "request allowance"],
    [413, "conversation is too long"],
  ]) {
    await p.getByRole("button", { name: "New conversation" }).click();
    await p.unroute("**/api/chat");
    await p.route("**/api/chat", (route) =>
      route.fulfill({ status, json: { detail: "Not displayed raw" } }),
    );
    await p.locator("#question").fill("Check the error explanation");
    await p.getByRole("button", { name: "Send question" }).click();
    await p.locator(".assistant-message[role=alert]").waitFor();
    assert(
      (await p.locator(".assistant-message[role=alert]").innerText()).includes(
        phrase,
      ),
    );
  }
  checks.push("quota and length limits show accurate recovery instructions");
  // Preserve a follow-up drafted while an earlier answer is loading.
  await p.getByRole("button", { name: "New conversation" }).click();
  await p.unroute("**/api/chat");
  await p.route("**/api/chat", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 700));
    try {
      await route.fulfill({ json: answer });
    } catch {}
  });
  await p.locator("#question").fill("Question A");
  await p.getByRole("button", { name: "Send question" }).click();
  await p.getByRole("button", { name: "Stop", exact: true }).waitFor();
  await p.locator("#question").fill("Draft B");
  await p.getByRole("button", { name: "Stop", exact: true }).click();
  await p.getByRole("button", { name: "Send question" }).waitFor();
  assert.equal(await p.locator("#question").inputValue(), "Draft B");
  checks.push("stopping an answer preserves a newer draft");

  // A canceled request must not mutate a fresh conversation.
  await p.getByRole("button", { name: "New conversation" }).click();
  await p.unroute("**/api/chat");
  await p.route("**/api/chat", async (r) => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    try {
      await r.fulfill({ json: answer });
    } catch {}
  });
  await p.locator("#question").fill("Old conversation");
  await p.getByRole("button", { name: "Send question" }).click();
  await p.getByRole("button", { name: "Stop", exact: true }).waitFor();
  await p.getByRole("button", { name: "New conversation" }).click();
  await p.waitForTimeout(600);
  assert.equal(await p.locator(".markdown").count(), 0);
  assert.equal(await p.locator(".user-message").count(), 0);
  checks.push(
    "new conversation cancels pending request without resurrecting stale messages",
  );
  await p.setViewportSize({ width: 390, height: 844 });
  await p.screenshot({ path: path.join(output, "after-mobile.png") });
  // Layout at 200% browser-equivalent effective width, and short keyboard-like viewport.
  for (const size of [
    { width: 720, height: 500 },
    { width: 390, height: 420 },
  ]) {
    await p.setViewportSize(size);
    await p.waitForFunction(
      () => {
        const r = document.querySelector("#question").getBoundingClientRect();
        return r.top >= 0 && r.bottom <= innerHeight;
      },
      null,
      { timeout: 3000 },
    );
    await p.evaluate(() => new Promise(requestAnimationFrame));
    assert(
      await p.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    assert(
      await p.locator("#question").evaluate((e) => {
        const r = e.getBoundingClientRect();
        return r.top >= 0 && r.bottom <= innerHeight;
      }),
    );
  }
  checks.push(
    "720px effective viewport (1440 at 200%); short 390x420 viewport",
  );
  if (axePath) {
    await p.setViewportSize({ width: 1440, height: 1000 });
    // Run trusted diagnostic code through browser automation; do not relax the page CSP.
    await p.evaluate(fs.readFileSync(axePath, "utf8"));
    let result = await p.evaluate(() =>
      axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
      }),
    );
    fs.writeFileSync(
      path.join(output, "axe-home.json"),
      JSON.stringify(result, null, 2),
    );
    assert.equal(
      result.violations.length,
      0,
      JSON.stringify(
        result.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => n.target),
        })),
      ),
    );
    await p
      .getByRole("button", { name: "Sources", exact: true })
      .last()
      .click();
    result = await p.evaluate(() =>
      axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
      }),
    );
    fs.writeFileSync(
      path.join(output, "axe-sources.json"),
      JSON.stringify(result, null, 2),
    );
    assert.equal(
      result.violations.length,
      0,
      JSON.stringify(
        result.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => n.target),
        })),
      ),
    );
    checks.push("axe WCAG A/AA home and open source dialog: zero violations");
  }
  assert.deepEqual(errors, [], "browser runtime and console errors");
  checks.push(
    "no unexpected browser JavaScript or console errors (including CSP violations)",
  );
  fs.writeFileSync(
    path.join(output, "browser-risk-results.json"),
    JSON.stringify({ engine, checks, passed: checks.length }, null, 2),
  );
  console.log(checks.join("\n"));
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
