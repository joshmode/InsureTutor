/* Controlled browser regressions for request/evidence lifecycle bugs.
 * API fixtures exercise UI behavior, not model factuality. Run against the built app.
 */
const path = require("node:path");
const fs = require("node:fs");
const assert = require("node:assert/strict");
const frontendRequire = require("node:module").createRequire(
  path.resolve(__dirname, "../frontend/package.json"),
);
const browsers = frontendRequire("playwright");
const engine = process.env.BROWSER_ENGINE || "chromium";
if (!["chromium", "firefox", "webkit"].includes(engine))
  throw new Error("Unknown browser engine");
const base = process.env.BASE_URL || "http://127.0.0.1:8018";
const output =
  process.env.AUDIT_OUTPUT_DIR ||
  path.resolve(__dirname, "../docs/audit/second-pass");
const citation = (id) => ({
  id,
  document: "FLEXI-ULife Prime Saver.pdf",
  page: 8,
  section: "UI test fixture " + id,
  excerpt: "UI fixture " + id,
});
const answer = (id) => ({
  message: "Source test " + id + " [1]",
  citations: [citation(id)],
  language: "en",
  kind: "answer",
  notices: [],
  used_retrieval: true,
});
(async () => {
  const browser = await browsers[engine].launch({
    ...(engine === "chromium"
      ? {
          executablePath:
            process.env.CHROMIUM_PATH ||
            (fs.existsSync("/usr/bin/chromium") ? "/usr/bin/chromium" : undefined),
          args: ["--no-sandbox"],
        }
      : {}),
    headless: true,
  });
  const checks = [];
  const errors = [];
  async function page(options = {}) {
    const p = await browser.newPage(options);
    p.on("pageerror", (e) => errors.push(e.message));
    await p.goto(base);
    await p.locator(".connection-status").waitFor();
    return p;
  }
  const p = await page();
  let attempt = 0;
  await p.route("**/api/chat", (r) =>
    ++attempt === 1
      ? r.fulfill({ status: 502, json: { detail: "controlled failure" } })
      : r.fulfill({ json: answer("retry") }),
  );
  await p.locator("#question").fill("Question A");
  await p.getByRole("button", { name: "Send question" }).click();
  await p.locator(".assistant-message[role=alert]").waitFor();
  await p.locator("#question").fill("Unsent draft B");
  await p.getByRole("button", { name: "Try again" }).click();
  await p.locator(".markdown").waitFor();
  assert.equal(await p.locator("#question").inputValue(), "Unsent draft B");
  assert.equal(await p.locator(".user-message").count(), 1);
  checks.push(
    "Retry preserves a different unsent draft and retains one submitted turn",
  );
  await p.close();

  const q = await page();
  let count = 0,
    release;
  await q.route("**/api/chat", async (r) => {
    const id = ++count === 1 ? "A" : "B";
    if (id === "B") await new Promise((resolve) => (release = resolve));
    await r.fulfill({ json: answer(id) });
  });
  await q.locator("#question").fill("First question");
  await q.getByRole("button", { name: "Send question" }).click();
  await q.locator(".markdown").waitFor();
  await q.locator("#question").fill("Second question");
  await q.getByRole("button", { name: "Send question" }).click();
  await q.getByRole("button", { name: "Stop", exact: true }).waitFor();
  await q
    .getByRole("button", { name: /Citation 1:/ })
    .first()
    .click();
  await q.locator("dialog[open]").waitFor();
  assert.equal(
    await q.locator(".source-excerpt blockquote").innerText(),
    "UI fixture A",
  );
  release();
  await q.waitForFunction(
    () => document.querySelectorAll(".markdown").length === 2,
  );
  assert.equal(
    await q.locator(".source-excerpt blockquote").innerText(),
    "UI fixture A",
  );
  const href = await q.locator(".source-excerpt a").getAttribute("href");
  assert(
    href.includes("document=FLEXI-ULife%20Prime%20Saver.pdf") &&
      href.includes("#page=8"),
  );
  await q.keyboard.press("Escape");
  await q.getByRole("button", { name: "Sources", exact: true }).last().click();
  assert.equal(
    await q.locator(".source-excerpt blockquote").innerText(),
    "UI fixture B",
  );
  checks.push(
    "Background answers preserve explicit evidence selection; generic Sources selects latest; PDF links identify the document",
  );
  await q.close();

  const t = await page();
  let n = 0;
  await t.route("**/api/chat", async (r) => {
    if (++n === 1) await new Promise((resolve) => setTimeout(resolve, 300));
    try {
      await r.fulfill({ json: answer("stopped") });
    } catch {}
  });
  await t.locator("#question").fill("Question to stop");
  await t.getByRole("button", { name: "Send question" }).click();
  await t.getByRole("button", { name: "Stop", exact: true }).click();
  await t.getByRole("button", { name: "Send question" }).waitFor();
  assert.equal(await t.locator("#question").inputValue(), "Question to stop");
  await t.getByRole("button", { name: "Send question" }).click();
  await t.locator(".markdown").waitFor();
  assert.equal(await t.locator(".user-message").count(), 1);
  checks.push(
    "Stop removes the canceled turn before resubmission, without duplicate questions",
  );
  await t.close();

  const timer = await browser.newPage();
  timer.on("pageerror", (e) => errors.push(e.message));
  await timer.addInitScript(() => {
    const native = setTimeout.bind(window);
    window.__chatDelays = [];
    window.setTimeout = (fn, delay, ...args) => {
      window.__chatDelays.push(delay);
      return native(fn, delay, ...args);
    };
  });
  await timer.route("**/api/health", (r) =>
    r.fulfill({
      json: {
        status: "ok",
        llm_configured: false,
        request_timeout_seconds: 285,
      },
    }),
  );
  await timer.route("**/api/chat", (r) =>
    r.fulfill({ json: answer("timeout") }),
  );
  await timer.goto(base);
  await timer.locator(".connection-status").waitFor();
  await timer.locator("#question").fill("Use the configured deadline");
  await timer.getByRole("button", { name: "Send question" }).click();
  await timer.locator(".markdown").waitFor();
  assert(await timer.evaluate(() => window.__chatDelays.includes(285000)));
  assert(!(await timer.evaluate(() => window.__chatDelays.includes(150000))));
  checks.push(
    "Client uses the advertised server deadline instead of aborting at 150 seconds",
  );
  await timer.close();

  for (const bad of [
    { notices: null },
    { message: { bad: "fixture" } },
    { citations: [{ ...citation("bad"), page: "8" }] },
    { language: ["en"] },
    { model_generated: "true" },
    { message: "   " },
  ]) {
    const badPage = await page();
    await badPage.route("**/api/chat", (r) =>
      r.fulfill({ json: { ...answer("bad"), ...bad } }),
    );
    await badPage.locator("#question").fill("Malformed success response");
    await badPage.getByRole("button", { name: "Send question" }).click();
    await badPage.locator(".assistant-message[role=alert]").waitFor();
    assert.equal(await badPage.locator("#question").count(), 1);
    assert.equal(await badPage.locator(".markdown").count(), 0);
    await badPage.close();
  }
  checks.push(
    "Malformed successful responses recover as errors rather than entering render state",
  );

  const copy = await browser.newPage();
  copy.on("pageerror", (e) => errors.push(e.message));
  await copy.addInitScript(() =>
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: () => Promise.reject(new Error("fixture permission denied")),
      },
    }),
  );
  await copy.route("**/api/chat", (r) => r.fulfill({ json: answer("copy") }));
  await copy.goto(base);
  await copy.locator(".connection-status").waitFor();
  await copy.locator("#question").fill("Clipboard fallback");
  await copy.getByRole("button", { name: "Send question" }).click();
  await copy.locator(".markdown").waitFor();
  await copy.getByRole("button", { name: "Copy answer", exact: true }).click();
  await copy
    .getByText(
      "Copy is unavailable. Select the answer text to copy it manually.",
      { exact: true },
    )
    .waitFor();
  for (const language of ["zh-Hans", "zh-Hant"]) {
    await copy.getByRole("combobox").selectOption(language);
    await copy.getByRole("button", { name: /引用 1/ }).waitFor();
  }
  checks.push(
    "Clipboard denial has visible accessible feedback; citation accessible names follow both Chinese locales",
  );
  await copy.close();

  const mobile = await page({ viewport: { width: 390, height: 844 } });
  await mobile.waitForFunction(
    () => document.querySelector(".conversation-scroll").scrollTop === 0,
  );
  assert(
    await mobile
      .locator("h1")
      .evaluate(
        (e) =>
          e.getBoundingClientRect().top >=
          document.querySelector(".conversation-scroll").getBoundingClientRect()
            .top,
      ),
  );
  await mobile.getByRole("button", { name: /02 The 4% rate/ }).click();
  await mobile.locator(".markdown").waitFor();
  await mobile.getByRole("button", { name: "New conversation" }).click();
  await mobile.waitForFunction(
    () => document.querySelector(".conversation-scroll").scrollTop === 0,
  );
  checks.push(
    "Mobile welcome and New conversation start at the top of the reading region",
  );
  await mobile.close();
  assert.deepEqual(errors, []);
  fs.mkdirSync(output, { recursive: true });
  fs.writeFileSync(
    path.join(output, "ui-regressions.json"),
    JSON.stringify(
      {
        browser_engine: engine,
        checks,
        passed: checks.length,
        unhandled_page_errors: errors,
        fixture_scope:
          "Controlled API/clipboard/deadline fixtures; last mobile chat uses real API",
      },
      null,
      2,
    ) + "\n",
  );
  console.log(checks.join("\n"));
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
