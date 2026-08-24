/**
 * Loads site-data.json and wires stats + repository links.
 * repo-url.txt is written by Publish-Online.ps1 after GitHub publish.
 */

async function loadJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(path);
  return res.json();
}

function formatStat(key, value) {
  if (key === "registration_pct") return `${value}%`;
  if (key === "sparse_points" || key === "registered" || key === "images") {
    return Number(value).toLocaleString();
  }
  return String(value);
}

async function applySiteData() {
  try {
    const data = await loadJson("site-data.json");
    document.getElementById("hero-title")?.replaceChildren(document.createTextNode(data.title.split("—")[0].trim()));
    document.getElementById("hero-subtitle")?.replaceChildren(document.createTextNode(data.subtitle));
    document.getElementById("pipeline-status")?.replaceChildren(document.createTextNode(data.pipeline_status));

    for (const el of document.querySelectorAll("[data-stat]")) {
      const key = el.getAttribute("data-stat");
      if (data.stats[key] != null) {
        el.textContent = formatStat(key, data.stats[key]);
      }
    }

    const tools = document.getElementById("tool-list");
    if (tools && data.tools) {
      tools.innerHTML = data.tools.map((t) => `<li>${t}</li>`).join("");
    }
  } catch (e) {
    console.warn("site-data.json not loaded", e);
  }
}

async function applyRepoUrl() {
  let repoUrl = null;
  try {
    const res = await fetch("repo-url.txt");
    if (res.ok) {
      repoUrl = (await res.text()).trim();
    }
  } catch { /* optional */ }

  const repoLink = document.getElementById("repo-link");
  const cloneBox = document.getElementById("clone-box");
  const codeLinks = document.querySelectorAll("#code-link, #hero-code-btn");

  if (repoUrl && repoUrl.startsWith("http")) {
    repoLink.href = repoUrl;
    repoLink.textContent = "Open GitHub repository";
    document.getElementById("repo-fallback")?.remove();
    if (cloneBox) {
      cloneBox.querySelector("code").textContent = `git clone ${repoUrl}.git`;
    }
    for (const a of codeLinks) {
      a.href = repoUrl;
      if (a.id !== "hero-code-btn") a.target = "_blank";
    }
  } else {
    repoLink.href = "#code";
    repoLink.textContent = "Publish with Publish-Online.ps1";
    if (cloneBox) {
      cloneBox.querySelector("code").textContent = ".\\handoff\\scripts\\Publish-Online.ps1";
    }
  }
}

applySiteData();
applyRepoUrl();
