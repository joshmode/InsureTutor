/* Private upload regression flow. CI runs without an LLM key; require model
 * output explicitly with REQUIRE_MODEL=1 for funded-provider verification. */
const path = require("node:path");
const fs = require("node:fs");
const assert = require("node:assert/strict");
const frontendRequire = require("node:module").createRequire(path.resolve(__dirname, "../frontend/package.json"));
const browsers = frontendRequire("playwright");
const engine = process.env.BROWSER_ENGINE || "chromium";
if (!["chromium", "firefox", "webkit"].includes(engine)) throw new Error("Unknown browser engine");
const base = process.env.BASE_URL || "http://127.0.0.1:8000";
const output = process.env.AUDIT_OUTPUT_DIR || "/tmp/insuretutor-private-ui";
fs.mkdirSync(output, { recursive: true });

(async () => {
  const browser = await browsers[engine].launch({ headless: true, ...(engine === "chromium" && fs.existsSync("/usr/bin/chromium") ? { executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium", args: ["--no-sandbox"] } : {}) });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage(), errors = [], knownIds = [];
  const result = { engine, checks: [], uploads: [], answers: [], errors };
  const save = () => fs.writeFileSync(path.join(output, "private-brochures.json"), JSON.stringify(result, null, 2));
  const waiters = new Map();
  page.on("pageerror", e => errors.push(e.message));
  // Capture an actual fetch clone before history updates can evict Chromium's
  // inspector body cache. Request/response data is never substituted.
  await page.exposeFunction("capturePrivateResponse", event => { const done = waiters.get(event.path); if (done) { waiters.delete(event.path); done(event); } });
  await page.addInitScript(() => {
    const original = window.fetch;
    window.fetch = async (...args) => {
      const response = await original(...args), route = new URL(response.url).pathname;
      if (["/api/chat", "/api/brochures"].includes(route) && response.status !== 204) {
        await window.capturePrivateResponse({ path: route, status: response.status, data: await response.clone().json() });
      }
      return response;
    };
  });
  const nextResponse = route => new Promise((resolve, reject) => {
    const timer = setTimeout(() => { waiters.delete(route); reject(new Error("Response deadline: " + route)); }, 195000);
    timer.unref(); waiters.set(route, event => { clearTimeout(timer); resolve(event); });
  });
  async function upload(name) {
    await page.getByRole("button", { name: /^(Upload|Change) brochure$/ }).click();
    assert.equal(await page.locator("#brochure-file").inputValue(), "");
    await page.locator("#brochure-file").setInputFiles(path.resolve(__dirname, `../tests/fixtures/${name.toLowerCase()}-brochure.pdf`));
    const pending = nextResponse("/api/brochures");
    await page.getByRole("button", { name: "Use this brochure", exact: true }).click();
    const {status, data} = await pending;
    assert.equal(status, 201, JSON.stringify(data));
    assert.ok(["hybrid", "lexical"].includes(data.retrieval_mode));
    if (process.env.REQUIRE_EMBEDDINGS === "1") assert.equal(data.retrieval_mode, "hybrid");
    knownIds.push(data.id); result.uploads.push(data); save();
    await page.locator(".brochure-dialog").waitFor({state:"hidden"});
    await page.locator(".workspace-bar").getByText(data.filename, {exact:true}).waitFor();
    return data;
  }
  async function ask(amount) {
    const pending = nextResponse("/api/chat");
    await page.getByRole("textbox").fill("What is the administrative charge?");
    await page.getByRole("textbox").press("Enter");
    const {status, data} = await pending; result.answers.push(data); save();
    assert.equal(status, 200); assert.equal(data.kind, "answer");
    assert.ok(data.message.includes("US$" + amount), data.message);
    assert.ok(data.citations.length);
    if (process.env.REQUIRE_MODEL === "1") assert.equal(data.model_generated, true);
    await page.locator(".markdown").last().waitFor();
    return data;
  }
  try {
    await page.goto(base); await page.locator(".connection-status").waitFor();
    const cedar = await upload("Cedar"), first = await ask(12);
    assert.ok(first.citations.every(c => c.document === "cedar-brochure.pdf"));
    await page.screenshot({path:path.join(output,"private-chat.png")});
    const other = await browser.newContext();
    assert.equal((await other.request.get(base + "/source-document?brochure_id=" + cedar.id)).status(), 404);
    await other.close();
    await page.getByRole("button", {name:/^Citation 1:/}).first().click();
    const source = await page.locator(".source-excerpt a").getAttribute("href");
    assert.ok(source.includes("brochure_id=" + cedar.id));
    assert.equal((await context.request.get(base + source.split("#")[0])).status(), 200);
    await page.screenshot({path:path.join(output,"private-source.png")}); await page.keyboard.press("Escape");
    result.checks.push("Private PDF, owned citations and cross-browser access isolation");
    const maple = await upload("Maple");
    assert.equal(await page.locator(".conversation").count(), 0);
    assert.equal((await context.request.get(base + "/source-document?brochure_id=" + cedar.id)).status(), 404);
    const second = await ask(34); assert.ok(second.citations.every(c => c.document === "maple-brochure.pdf"));
    result.checks.push("Replacement rebuilds reference, clears history and answers from new document");
    await page.getByRole("button", {name:"Change brochure"}).click();
    await page.locator("#brochure-file").setInputFiles({name:"invalid.pdf",mimeType:"application/pdf",buffer:Buffer.from("%PDF-invalid")});
    const invalid = nextResponse("/api/brochures");
    await page.getByRole("button", {name:"Use this brochure",exact:true}).click();
    assert.equal((await invalid).status, 422); await page.getByRole("alert").waitFor();
    await page.getByRole("button", {name:"Cancel",exact:true}).click();
    assert.ok((await page.locator("body").innerText()).includes("maple-brochure.pdf"));
    result.checks.push("Invalid upload preserves active brochure and conversation");
    for (const width of [390,320]) {
      await page.setViewportSize({width,height:844});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.getByRole("button", {name:"Change brochure"}).click();
      for (let i=0;i<7;i++) { await page.keyboard.press("Tab"); assert.ok(await page.locator(".brochure-dialog").evaluate(d => d.contains(document.activeElement))); }
      await page.screenshot({path:path.join(output,`upload-${width}.png`)}); await page.keyboard.press("Escape");
    }
    const removed = page.waitForResponse(r => r.request().method() === "DELETE");
    await page.getByRole("button", {name:"New conversation",exact:true}).click();
    assert.equal((await removed).status(), 204);
    await page.getByRole("button", {name:"Upload brochure",exact:true}).waitFor();
    assert.equal((await context.request.get(base + "/source-document?brochure_id=" + maple.id)).status(), 404);
    result.checks.push("Mobile layout, modal focus, deletion and default reset");
    const expired = await upload("Cedar");
    assert.equal((await context.request.delete(base + "/api/brochures/" + expired.id)).status(), 204);
    const missing = nextResponse("/api/chat");
    await page.getByRole("textbox").fill("What is the administrative charge?"); await page.getByRole("textbox").press("Enter");
    assert.equal((await missing).status, 404);
    await page.getByText("This brochure has expired or been removed.", {exact:false}).waitFor();
    assert.equal(await page.getByRole("button", {name:"Retry",exact:true}).count(), 0);
    result.checks.push("Expired references never silently use default evidence and show recovery guidance");
    assert.deepEqual(errors, []); save();
  } finally {
    for (const id of knownIds) await context.request.delete(base + "/api/brochures/" + id).catch(() => {});
    await browser.close();
  }
  console.log(`${engine}: ${result.checks.length} private-brochure groups passed`);
})().catch(error => { console.error(error); process.exit(1); });
