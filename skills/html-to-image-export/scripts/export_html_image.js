#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const net = require("net");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");
const { pathToFileURL } = require("url");

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      throw new Error(`Unexpected argument: ${token}`);
    }
    const key = token.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
    } else {
      args[key] = next;
      i += 1;
    }
  }
  return args;
}

function usage() {
  return [
    "Usage:",
    "  node export_html_image.js --input <html-path-or-url> --out <png-or-dir> [options]",
    "",
    "Options:",
    "  --selector <css>             Export every matching element as a separate PNG",
    "  --wait-for-selector <css>    Wait for an element before capture",
    "  --width <px>                 Viewport width, default 1280",
    "  --height <px>                Viewport height, default 720",
    "  --scale <number>             Device scale factor, default 2",
    "  --full-page                  Capture full page instead of viewport",
    "  --delay <ms>                 Extra wait after load and fonts, default 200",
    "  --clip-padding <px>          Padding around selector capture, default 0",
    "  --preserve-layout            Keep selector elements in the original page layout",
    "  --transparent                Preserve transparent page background",
    "  --chrome <path>              Explicit Chrome or Edge executable",
  ].join("\n");
}

function numberOption(args, key, fallback) {
  if (args[key] === undefined || args[key] === true) {
    return fallback;
  }
  const value = Number(args[key]);
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`--${key} must be a positive number`);
  }
  return value;
}

function findBrowser(explicitPath) {
  const candidates = [
    explicitPath,
    process.env.CHROME_PATH,
    process.env.BROWSER_PATH,
    path.join(process.env.ProgramFiles || "", "Google", "Chrome", "Application", "chrome.exe"),
    path.join(process.env["ProgramFiles(x86)"] || "", "Google", "Chrome", "Application", "chrome.exe"),
    path.join(process.env.LOCALAPPDATA || "", "Google", "Chrome", "Application", "chrome.exe"),
    path.join(process.env.ProgramFiles || "", "Microsoft", "Edge", "Application", "msedge.exe"),
    path.join(process.env["ProgramFiles(x86)"] || "", "Microsoft", "Edge", "Application", "msedge.exe"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/microsoft-edge",
  ].filter(Boolean);

  return candidates.find((file) => fs.existsSync(file));
}

function targetUrl(input) {
  if (/^(https?:|file:)/i.test(input)) {
    return input;
  }
  const absolute = path.resolve(input);
  if (!fs.existsSync(absolute)) {
    throw new Error(`Input does not exist: ${absolute}`);
  }
  return pathToFileURL(absolute).href;
}

function defaultOutput(input, selector) {
  if (selector) {
    return path.resolve("html-image-export");
  }
  if (/^https?:/i.test(input)) {
    return path.resolve("screenshot.png");
  }
  const parsed = path.parse(path.resolve(input));
  return path.join(parsed.dir, `${parsed.name}.png`);
}

function sanitizeFileName(value, fallback) {
  const cleaned = String(value || fallback || "capture")
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 120);
  return cleaned || fallback || "capture";
}

function requestJson(method, urlString) {
  const url = new URL(urlString);
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        method,
        hostname: url.hostname,
        port: url.port,
        path: `${url.pathname}${url.search}`,
      },
      (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          const body = Buffer.concat(chunks).toString("utf8");
          if (res.statusCode < 200 || res.statusCode >= 300) {
            reject(new Error(`${method} ${urlString} failed: ${res.statusCode} ${body}`));
            return;
          }
          try {
            resolve(JSON.parse(body));
          } catch (error) {
            reject(new Error(`Invalid JSON from ${urlString}: ${error.message}`));
          }
        });
      }
    );
    req.on("error", reject);
    req.end();
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForJson(url, timeoutMs = 10000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      return await requestJson("GET", url);
    } catch (_) {
      await sleep(150);
    }
  }
  throw new Error(`Timed out waiting for Chrome DevTools: ${url}`);
}

function encodeFrame(text) {
  const payload = Buffer.from(text);
  const mask = crypto.randomBytes(4);
  let headerLength = 6;
  if (payload.length >= 126 && payload.length <= 65535) {
    headerLength = 8;
  } else if (payload.length > 65535) {
    headerLength = 14;
  }

  const frame = Buffer.alloc(headerLength + payload.length);
  frame[0] = 0x81;
  if (payload.length < 126) {
    frame[1] = 0x80 | payload.length;
    mask.copy(frame, 2);
    for (let i = 0; i < payload.length; i += 1) {
      frame[6 + i] = payload[i] ^ mask[i % 4];
    }
  } else if (payload.length <= 65535) {
    frame[1] = 0x80 | 126;
    frame.writeUInt16BE(payload.length, 2);
    mask.copy(frame, 4);
    for (let i = 0; i < payload.length; i += 1) {
      frame[8 + i] = payload[i] ^ mask[i % 4];
    }
  } else {
    frame[1] = 0x80 | 127;
    frame.writeBigUInt64BE(BigInt(payload.length), 2);
    mask.copy(frame, 10);
    for (let i = 0; i < payload.length; i += 1) {
      frame[14 + i] = payload[i] ^ mask[i % 4];
    }
  }
  return frame;
}

function encodeControlFrame(opcode, data = Buffer.alloc(0)) {
  const frame = Buffer.alloc(2 + data.length);
  frame[0] = 0x80 | opcode;
  frame[1] = data.length;
  data.copy(frame, 2);
  return frame;
}

function parseFrames(buffer) {
  const messages = [];
  let offset = 0;

  while (buffer.length - offset >= 2) {
    const byte1 = buffer[offset];
    const byte2 = buffer[offset + 1];
    const fin = Boolean(byte1 & 0x80);
    const opcode = byte1 & 0x0f;
    const masked = Boolean(byte2 & 0x80);
    let length = byte2 & 0x7f;
    let headerLength = 2;

    if (length === 126) {
      if (buffer.length - offset < 4) break;
      length = buffer.readUInt16BE(offset + 2);
      headerLength = 4;
    } else if (length === 127) {
      if (buffer.length - offset < 10) break;
      length = Number(buffer.readBigUInt64BE(offset + 2));
      headerLength = 10;
    }

    const maskLength = masked ? 4 : 0;
    const frameLength = headerLength + maskLength + length;
    if (buffer.length - offset < frameLength) break;

    let payload = buffer.subarray(offset + headerLength + maskLength, offset + frameLength);
    if (masked) {
      const mask = buffer.subarray(offset + headerLength, offset + headerLength + 4);
      payload = Buffer.from(payload.map((byte, index) => byte ^ mask[index % 4]));
    }
    messages.push({ fin, opcode, payload });
    offset += frameLength;
  }

  return { messages, rest: buffer.subarray(offset) };
}

function connectWebSocket(wsUrl) {
  const url = new URL(wsUrl);
  const key = crypto.randomBytes(16).toString("base64");
  const socket = net.connect(Number(url.port), url.hostname);
  let buffer = Buffer.alloc(0);
  let open = false;
  let fragment = null;
  const messageHandlers = [];
  const closeHandlers = [];

  function dispatchFrames(data) {
    buffer = Buffer.concat([buffer, data]);
    const parsed = parseFrames(buffer);
    buffer = parsed.rest;
    for (const frame of parsed.messages) {
      if (frame.opcode === 0x8) {
        socket.end();
        closeHandlers.forEach((handler) => handler());
      } else if (frame.opcode === 0x9) {
        socket.write(encodeControlFrame(0xA, frame.payload));
      } else if (frame.opcode === 0x1 || frame.opcode === 0x2) {
        if (frame.fin) {
          messageHandlers.forEach((handler) => handler(frame.payload.toString("utf8")));
        } else {
          fragment = Buffer.from(frame.payload);
        }
      } else if (frame.opcode === 0x0 && fragment) {
        fragment = Buffer.concat([fragment, frame.payload]);
        if (frame.fin) {
          messageHandlers.forEach((handler) => handler(fragment.toString("utf8")));
          fragment = null;
        }
      }
    }
  }

  return new Promise((resolve, reject) => {
    socket.once("connect", () => {
      socket.write(
        [
          `GET ${url.pathname}${url.search} HTTP/1.1`,
          `Host: ${url.host}`,
          "Upgrade: websocket",
          "Connection: Upgrade",
          `Sec-WebSocket-Key: ${key}`,
          "Sec-WebSocket-Version: 13",
          "",
          "",
        ].join("\r\n")
      );
    });

    socket.on("data", (data) => {
      if (!open) {
        buffer = Buffer.concat([buffer, data]);
        const headerEnd = buffer.indexOf("\r\n\r\n");
        if (headerEnd === -1) return;
        const header = buffer.subarray(0, headerEnd).toString("utf8");
        if (!/^HTTP\/1\.1 101/i.test(header)) {
          reject(new Error(`WebSocket handshake failed: ${header.split("\r\n")[0]}`));
          socket.destroy();
          return;
        }
        open = true;
        const remaining = buffer.subarray(headerEnd + 4);
        buffer = Buffer.alloc(0);
        resolve({
          send(text) {
            socket.write(encodeFrame(text));
          },
          onMessage(handler) {
            messageHandlers.push(handler);
          },
          onClose(handler) {
            closeHandlers.push(handler);
          },
          close() {
            socket.end();
          },
        });
        if (remaining.length) dispatchFrames(remaining);
        return;
      }
      dispatchFrames(data);
    });

    socket.once("error", reject);
  });
}

async function createCdpClient(wsUrl) {
  const ws = await connectWebSocket(wsUrl);
  const pending = new Map();
  const eventWaiters = new Map();
  let nextId = 1;

  ws.onMessage((raw) => {
    const message = JSON.parse(raw);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) {
        reject(new Error(message.error.message || "Chrome DevTools Protocol error"));
      } else {
        resolve(message.result || {});
      }
      return;
    }
    if (message.method && eventWaiters.has(message.method)) {
      const waiters = eventWaiters.get(message.method);
      eventWaiters.delete(message.method);
      waiters.forEach((resolve) => resolve(message.params || {}));
    }
  });

  return {
    send(method, params = {}) {
      const id = nextId;
      nextId += 1;
      ws.send(JSON.stringify({ id, method, params }));
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
      });
    },
    waitFor(method, timeoutMs = 10000) {
      return new Promise((resolve, reject) => {
        if (!eventWaiters.has(method)) {
          eventWaiters.set(method, []);
        }
        eventWaiters.get(method).push(resolve);
        setTimeout(() => reject(new Error(`Timed out waiting for event: ${method}`)), timeoutMs);
      });
    },
    close() {
      ws.close();
    },
  };
}

async function waitForSelector(cdp, selector, timeoutMs) {
  const expression = `
    new Promise((resolve, reject) => {
      const selector = ${JSON.stringify(selector)};
      const timeout = ${timeoutMs};
      const start = Date.now();
      const check = () => {
        if (document.querySelector(selector)) {
          resolve(true);
          return;
        }
        if (Date.now() - start > timeout) {
          reject(new Error("Selector not found: " + selector));
          return;
        }
        setTimeout(check, 100);
      };
      check();
    })
  `;
  await cdp.send("Runtime.evaluate", { expression, awaitPromise: true });
}

async function evaluateValue(cdp, expression) {
  const response = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (response.exceptionDetails) {
    throw new Error(response.exceptionDetails.text || "Runtime evaluation failed");
  }
  return response.result ? response.result.value : undefined;
}

async function pageReady(cdp, delayMs) {
  await evaluateValue(
    cdp,
    "document.fonts && document.fonts.ready ? document.fonts.ready.then(() => true) : true"
  );
  if (delayMs > 0) {
    await sleep(delayMs);
  }
}

async function prepareSelectorCapture(cdp, selector, preserveLayout) {
  const expression = `
    (() => {
      const nodes = Array.from(document.querySelectorAll(${JSON.stringify(selector)}));
      nodes.forEach((el, index) => {
        el.setAttribute("data-html-image-export-index", String(index + 1));
      });

      if (!${JSON.stringify(Boolean(preserveLayout))}) {
        let style = document.getElementById("html-image-export-quality-style");
        if (!style) {
          style = document.createElement("style");
          style.id = "html-image-export-quality-style";
          style.textContent = [
            "[data-html-image-export-index] {",
            "  contain: none !important;",
            "  display: block !important;",
            "  margin-left: 0 !important;",
            "  margin-right: 0 !important;",
            "  max-width: none !important;",
            "  min-width: max-content !important;",
            "  overflow: visible !important;",
            "  width: max-content !important;",
            "}",
            "[data-html-image-export-index] .drawing,",
            "[data-html-image-export-index] .diagram,",
            "[data-html-image-export-index] .chart,",
            "[data-html-image-export-index] figure,",
            "[data-html-image-export-index] svg,",
            "[data-html-image-export-index] canvas {",
            "  max-width: none !important;",
            "  overflow: visible !important;",
            "}",
            "[data-html-image-export-index] svg {",
            "  flex: 0 0 auto !important;",
            "}",
            "[data-html-image-export-index] .caption,",
            "[data-html-image-export-index] figcaption {",
            "  width: 100% !important;",
            "}"
          ].join("\\n");
          document.head.appendChild(style);
        }
      }

      return nodes.length;
    })()
  `;
  return evaluateValue(cdp, expression);
}

async function getElementClips(cdp, selector) {
  const expression = `
    Array.from(document.querySelectorAll(${JSON.stringify(selector)})).map((el, index) => {
      const rect = el.getBoundingClientRect();
      const caption = el.querySelector("figcaption,.caption")?.textContent || "";
      const name =
        el.getAttribute("data-export-name") ||
        el.getAttribute("aria-label") ||
        el.getAttribute("title") ||
        el.id ||
        caption ||
        el.tagName.toLowerCase() + "-" + (index + 1);
      return {
        index: index + 1,
        name,
        x: rect.left + window.scrollX,
        y: rect.top + window.scrollY,
        width: rect.width,
        height: rect.height
      };
    }).filter((item) => item.width > 0 && item.height > 0)
  `;
  return evaluateValue(cdp, expression);
}

async function capturePng(cdp, file, clip, fullPage) {
  const params = {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: Boolean(fullPage || clip),
  };
  if (clip) {
    params.clip = clip;
  }
  const screenshot = await cdp.send("Page.captureScreenshot", params);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, Buffer.from(screenshot.data, "base64"));
}

function waitForProcessExit(child, timeoutMs = 1500) {
  if (child.exitCode !== null || child.signalCode !== null) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, timeoutMs);
    child.once("exit", () => {
      clearTimeout(timer);
      resolve();
    });
  });
}

function buildClip(item, padding) {
  const x = Math.max(0, Math.floor(item.x - padding));
  const y = Math.max(0, Math.floor(item.y - padding));
  const right = Math.ceil(item.x + item.width + padding);
  const bottom = Math.ceil(item.y + item.height + padding);
  return {
    x,
    y,
    width: Math.max(1, right - x),
    height: Math.max(1, bottom - y),
    scale: 1,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || args.h || !args.input) {
    console.log(usage());
    process.exit(args.input ? 0 : 1);
  }

  const input = args.input;
  const selector = args.selector && args.selector !== true ? args.selector : "";
  const out = path.resolve(args.out && args.out !== true ? args.out : defaultOutput(input, selector));
  const width = Math.round(numberOption(args, "width", 1280));
  const height = Math.round(numberOption(args, "height", 720));
  const scale = numberOption(args, "scale", 2);
  const delay = Math.round(numberOption(args, "delay", 200));
  const clipPadding = Number(args["clip-padding"] || 0);
  const browser = findBrowser(args.chrome && args.chrome !== true ? args.chrome : "");

  if (!browser) {
    throw new Error("Chrome or Edge was not found. Pass --chrome <path> to the browser executable.");
  }

  const port = 41000 + Math.floor(Math.random() * 2000);
  const userDataDir = path.join(os.tmpdir(), `html-image-export-${process.pid}-${Date.now()}`);
  const chrome = spawn(browser, [
    "--headless=new",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    "--disable-gpu",
    "--disable-crash-reporter",
    "--disable-breakpad",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "about:blank",
  ], { stdio: "ignore" });

  let cdp;
  try {
    await waitForJson(`http://127.0.0.1:${port}/json/version`);
    const target = await requestJson("PUT", `http://127.0.0.1:${port}/json/new?about:blank`);
    cdp = await createCdpClient(target.webSocketDebuggerUrl);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: scale,
      mobile: false,
      screenWidth: width,
      screenHeight: height,
    });
    if (args.transparent) {
      await cdp.send("Emulation.setDefaultBackgroundColorOverride", {
        color: { r: 0, g: 0, b: 0, a: 0 },
      });
    }

    const loaded = cdp.waitFor("Page.loadEventFired", 30000);
    await cdp.send("Page.navigate", { url: targetUrl(input) });
    await loaded;

    if (args["wait-for-selector"] && args["wait-for-selector"] !== true) {
      await waitForSelector(cdp, args["wait-for-selector"], 15000);
    }
    await pageReady(cdp, delay);

    const written = [];
    if (selector) {
      const preparedCount = await prepareSelectorCapture(cdp, selector, Boolean(args["preserve-layout"]));
      if (!preparedCount) {
        throw new Error(`No elements matched selector: ${selector}`);
      }
      await pageReady(cdp, 50);
      const elements = await getElementClips(cdp, selector);
      if (!elements.length) {
        throw new Error(`No visible elements matched selector: ${selector}`);
      }
      const outLooksLikePng = path.extname(out).toLowerCase() === ".png";
      for (const item of elements) {
        const file = outLooksLikePng && elements.length === 1
          ? out
          : path.join(out, `${String(item.index).padStart(2, "0")}_${sanitizeFileName(item.name, `element-${item.index}`)}.png`);
        await capturePng(cdp, file, buildClip(item, clipPadding), false);
        written.push(file);
      }
    } else {
      const file = path.extname(out).toLowerCase() === ".png" ? out : path.join(out, "screenshot.png");
      await capturePng(cdp, file, null, Boolean(args["full-page"]));
      written.push(file);
    }

    written.forEach((file) => console.log(file));
  } finally {
    if (cdp) cdp.close();
    chrome.kill();
    await waitForProcessExit(chrome);
    try {
      fs.rmSync(userDataDir, { recursive: true, force: true });
    } catch (error) {
      console.warn(`Warning: could not remove temporary Chrome profile: ${userDataDir}`);
    }
  }
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
