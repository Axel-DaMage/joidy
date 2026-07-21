#!/usr/bin/env node
const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

const CACHE_DIR = path.join(os.homedir(), ".joidy");
const REPO = "https://github.com/Axel-DaMage/joidy.git";

function checkDep(cmd) {
  try { execSync(`which ${cmd}`, { stdio: "ignore" }); }
  catch { console.error(`Error: ${cmd} is required but not installed.`); process.exit(1); }
}

function ensureRepo() {
  checkDep("git");
  checkDep("docker");
  if (!fs.existsSync(CACHE_DIR)) {
    console.log("Downloading Joidy...");
    execSync(`git clone --depth 1 ${REPO} "${CACHE_DIR}"`, { stdio: "inherit" });
  }
}

const cmd = process.argv[2] || "help";

ensureRepo();

switch (cmd) {
  case "up":
  case "start":
    execSync("docker compose up -d", { cwd: CACHE_DIR, stdio: "inherit" });
    console.log("\nJoidy running at http://localhost:3000");
    break;
  case "down":
  case "stop":
    execSync("docker compose down", { cwd: CACHE_DIR, stdio: "inherit" });
    break;
  case "logs":
    execSync("docker compose logs -f", { cwd: CACHE_DIR, stdio: "inherit" });
    break;
  case "status":
  case "ps":
    execSync("docker compose ps", { cwd: CACHE_DIR, stdio: "inherit" });
    break;
  case "update":
    execSync("git pull", { cwd: CACHE_DIR, stdio: "inherit" });
    execSync("docker compose pull", { cwd: CACHE_DIR, stdio: "inherit" });
    console.log("Joidy updated");
    break;
  case "restart":
    execSync("docker compose down", { cwd: CACHE_DIR, stdio: "inherit" });
    execSync("docker compose up -d", { cwd: CACHE_DIR, stdio: "inherit" });
    break;
  default:
    console.log(`
Joidy - personal knowledge management with gamification

Usage: npx @joidy-app/cli <command>

Commands:
  up        Start Joidy
  down      Stop Joidy
  restart   Restart all services
  logs      View live logs
  status    Service status
  update    Pull latest version
  help      Show this help

Website: https://joidy-web.vercel.app
`);
    break;
}
