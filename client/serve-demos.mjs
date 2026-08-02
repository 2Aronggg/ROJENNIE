import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));
const port = Number(process.env.PORT || 5174);

const routes = new Map([
  ["/flow", "flow.html"],
  ["/flow.html", "flow.html"],
  ["/agent1", "index1.html"],
  ["/agent1.html", "index1.html"],
  ["/agent2", "index2.html"],
  ["/agent2.html", "index2.html"],
  ["/agent3", "index3.html"],
  ["/agent3.html", "index3.html"],
  ["/agent4", "index4.html"],
  ["/agent4.html", "index4.html"],
  ["/demo-agent1", "demo/agent1-case-builder.html"],
  ["/demo-agent2", "demo/agent2-hybrid-retriever.html"],
  ["/demo-agent3", "demo/agent3-logic-verification.html"],
  ["/demo-agent4", "demo/agent4-response-composer.html"],
  ["/demo-flow", "demo/kb-key-buddy-mobile-flow.html"],
]);

const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
};

function safePath(pathname) {
  let relativePath = routes.get(pathname) || pathname.replace(/^\/+/, "");

  if (relativePath === "") return null;
  if (relativePath.startsWith("demo/assets/")) {
    relativePath = relativePath.replace(/^demo\/assets\//, "assets/");
  }
  if (relativePath === "demo/agent-api.js") {
    relativePath = "agent-api.js";
  }

  const resolved = resolve(root, normalize(relativePath));
  if (resolved !== root.slice(0, -1) && !resolved.startsWith(root)) return null;
  return resolved;
}

function sendIndex(res) {
  res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  res.end(`<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>KB Key Buddy Local Demos</title>
    <style>
      body { margin: 0; min-height: 100vh; display: grid; place-items: center; font-family: "Segoe UI", "Noto Sans KR", Arial, sans-serif; background: #fff8df; color: #242424; }
      main { width: min(720px, calc(100vw - 40px)); padding: 32px; border-radius: 20px; background: #fffdf8; box-shadow: 0 24px 70px rgba(74, 54, 20, 0.16); }
      h1 { margin: 0 0 8px; font-size: 28px; }
      p { margin: 0 0 22px; color: #6b6256; }
      .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
      a { display: block; padding: 16px 18px; border: 1px solid rgba(184, 137, 28, 0.28); border-radius: 14px; color: #3b2b00; background: #fff7d0; font-weight: 800; text-decoration: none; }
      a:hover { background: #ffe36b; }
    </style>
  </head>
  <body>
    <main>
      <h1>KB Key Buddy Local Demos</h1>
      <p>서버가 켜져 있는 동안 아래 링크로 Agent 1-4와 유저 플로우를 볼 수 있습니다.</p>
      <div class="grid">
        <a href="/flow">User Flow</a>
        <a href="/agent1">Agent 1</a>
        <a href="/agent2">Agent 2</a>
        <a href="/agent3">Agent 3</a>
        <a href="/agent4">Agent 4</a>
        <a href="/demo-flow">Archived Flow</a>
      </div>
    </main>
  </body>
</html>`);
}

function serveFile(filePath, res) {
  if (!filePath || !existsSync(filePath) || !statSync(filePath).isFile()) {
    res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    res.end("Not found");
    return;
  }

  res.writeHead(200, {
    "content-type": mime[extname(filePath).toLowerCase()] || "application/octet-stream",
    "cache-control": "no-store",
  });
  createReadStream(filePath).pipe(res);
}

createServer((req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
  const pathname = decodeURIComponent(url.pathname);

  if (pathname === "/" || pathname === "/index") {
    sendIndex(res);
    return;
  }

  serveFile(safePath(pathname), res);
}).listen(port, "127.0.0.1", () => {
  console.log(`KB Key Buddy demos: http://127.0.0.1:${port}/`);
});
