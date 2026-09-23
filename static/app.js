// ApplyFlow AI - Dashboard Client Logic

let configData = null;
let currentInterval = 12;
let allJobs = [];

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
    connectWebSocket();
    fetchStatus();
    fetchConfig();
    fetchJobs();
    fetchResumes();
    setInterval(fetchStatus, 5000);
});

// WebSocket Connection for Real-Time Terminal Streaming
function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/logs`;
    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            appendLog(data);
        } catch (e) {
            console.error("WS Parse Error", e);
        }
    };

    socket.onclose = () => {
        setTimeout(connectWebSocket, 3000);
    };
}

function appendLog(log) {
    const terminal = document.getElementById("terminalBody");
    const row = document.createElement("div");
    row.className = `log-row log-${log.level || 'info'}`;
    
    let levelBadge = "";
    if (log.level === "success") levelBadge = `<span class="text-emerald-400 font-bold">[SUCCESS]</span>`;
    else if (log.level === "warning") levelBadge = `<span class="text-amber-400 font-bold">[WARN]</span>`;
    else if (log.level === "error") levelBadge = `<span class="text-rose-400 font-bold">[ERR]</span>`;
    else levelBadge = `<span class="text-slate-500">[LOG]</span>`;

    row.innerHTML = `<span class="text-slate-600">${log.timestamp}</span> ${levelBadge} ${escapeHtml(log.message)}`;
    terminal.appendChild(row);
    terminal.scrollTop = terminal.scrollHeight;
}

function clearTerminal() {
    document.getElementById("terminalBody").innerHTML = `<div class="text-slate-500">// Terminal cleared.</div>`;
}

function escapeHtml(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Tab Switching
function switchTab(tabId) {
    document.querySelectorAll(".tab-content").forEach(el => el.classList.add("hidden"));
    document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));
    
    const targetView = document.getElementById(`view-${tabId}`);
    const targetBtn = document.getElementById(`tab-${tabId}`);
    
    if (targetView) targetView.classList.remove("hidden");
    if (targetBtn) targetBtn.classList.add("active");
    lucide.createIcons();
}

// Fetch Engine Status & KPIs
async function fetchStatus() {
    try {
        const res = await fetch("/api/status");
        const data = await res.json();

        // Update Engine Status
        const engineDot = document.getElementById("engineDot");
        const engineStatus = document.getElementById("engineStatus");
        const btnRunText = document.getElementById("btnRunText");
        const btnRunIcon = document.getElementById("btnRunIcon");

        if (data.is_running) {
            engineDot.className = "w-2 h-2 rounded-full bg-brand-emerald animate-ping";
            engineStatus.textContent = "HUNTING ACTIVE";
            engineStatus.className = "text-brand-emerald font-semibold";
            btnRunText.textContent = "Engine Running...";
        } else {
            engineDot.className = "w-2 h-2 rounded-full bg-slate-500";
            engineStatus.textContent = "Idle";
            engineStatus.className = "text-slate-400";
            btnRunText.textContent = "Run Applications";
        }

        // Update LinkedIn Auth Pill
        const authDot = document.getElementById("authDot");
        const authText = document.getElementById("authText");
        const btnConnect = document.getElementById("btnConnectLinkedIn");

        if (data.linkedin_connected) {
            authDot.className = "w-2 h-2 rounded-full bg-brand-emerald";
            authText.textContent = "LinkedIn Connected";
            authText.className = "text-slate-300";
            btnConnect.classList.add("hidden");
        } else {
            authDot.className = "w-2 h-2 rounded-full bg-rose-500";
            authText.textContent = "LinkedIn Disconnected";
            authText.className = "text-rose-400";
            btnConnect.classList.remove("hidden");
        }

        // Update KPIs
        if (data.stats) {
            document.getElementById("kpiApplied").textContent = data.stats.APPLIED || 0;
            document.getElementById("kpiSkipped").textContent = data.stats.SKIPPED || 0;
        }

        // Update Scheduler toggle
        const toggle = document.getElementById("schedulerToggle");
        if (toggle) toggle.checked = !!data.schedule_enabled;

    } catch (e) {
        console.error("Status fetch error", e);
    }
}

// Toggle Run / Start Applications
async function toggleEngineRun() {
    try {
        const res = await fetch("/api/run/start", { method: "POST" });
        const data = await res.json();
        if (data.status === "started") {
            switchTab("terminal");
            fetchStatus();
        }
    } catch (e) {
        alert("Error starting engine: " + e.message);
    }
}

// Interactive LinkedIn Auth
async function triggerLinkedInAuth() {
    try {
        await fetch("/api/auth/login", { method: "POST" });
        alert("A Chromium window has opened on your desktop. Log in to LinkedIn, solve any 2FA, and return here!");
    } catch (e) {
        alert("Auth error: " + e.message);
    }
}

// Fetch and Render Config
async function fetchConfig() {
    try {
        const res = await fetch("/api/config");
        configData = await res.json();

        // Render Search Queries
        renderSearchQueries();

        // Render Whitelist & Blacklist
        const filters = configData.title_filters || {};
        document.getElementById("whitelistInput").value = (filters.whitelist_keywords || []).join(", ");
        document.getElementById("blacklistInput").value = (filters.blacklist_keywords || []).join(", ");

        // Render Smart Answers
        const fa = configData.form_answers || {};
        const tm = fa.text_mappings || {};
        const ey = fa.experience_years || {};

        if (tm.english) document.getElementById("ansEnglish").value = tm.english;
        if (tm.salary_expectation) document.getElementById("ansSalary").value = tm.salary_expectation;
        if (ey.java) document.getElementById("ansJava").value = ey.java;
        if (ey.react) document.getElementById("ansReact").value = ey.react;

        document.getElementById("kpiQueries").textContent = (configData.job_searches || []).length;

    } catch (e) {
        console.error("Config fetch error", e);
    }
}

function renderSearchQueries() {
    const container = document.getElementById("searchQueriesContainer");
    container.innerHTML = "";
    const searches = configData.job_searches || [];

    searches.forEach((item, index) => {
        const row = document.createElement("div");
        row.className = "p-3 rounded-xl bg-dark-900/80 border border-white/5 flex items-center justify-between";
        row.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="text-xs px-2 py-0.5 rounded bg-brand-cyan/10 text-brand-cyan font-mono">${item.type.toUpperCase()}</span>
                <span class="text-xs font-semibold text-white">${escapeHtml(item.query)}</span>
                <span class="text-[11px] text-slate-400">📍 ${escapeHtml(item.location)}</span>
            </div>
            <button onclick="removeSearchQuery(${index})" class="text-slate-500 hover:text-rose-400 transition p-1">
                <i data-lucide="trash" class="w-3.5 h-3.5"></i>
            </button>
        `;
        container.appendChild(row);
    });
    lucide.createIcons();
}

function addSearchQuery() {
    const title = document.getElementById("newQueryTitle").value.trim();
    const loc = document.getElementById("newQueryLocation").value.trim() || "Remote";
    const type = document.getElementById("newQueryType").value;

    if (!title) return alert("Please enter a job title/keyword");

    configData.job_searches = configData.job_searches || [];
    configData.job_searches.push({ query: title, location: loc, type: type });

    document.getElementById("newQueryTitle").value = "";
    document.getElementById("newQueryLocation").value = "";
    renderSearchQueries();
    saveConfigToServer();
}

function removeSearchQuery(index) {
    configData.job_searches.splice(index, 1);
    renderSearchQueries();
    saveConfigToServer();
}

async function saveFilterConfig() {
    const whitelist = document.getElementById("whitelistInput").value.split(",").map(s => s.trim()).filter(Boolean);
    const blacklist = document.getElementById("blacklistInput").value.split(",").map(s => s.trim()).filter(Boolean);

    configData.title_filters = {
        whitelist_keywords: whitelist,
        blacklist_keywords: blacklist
    };

    await saveConfigToServer();
    alert("Filters saved successfully!");
}

async function saveSmartAnswers() {
    configData.form_answers = configData.form_answers || {};
    configData.form_answers.text_mappings = configData.form_answers.text_mappings || {};
    configData.form_answers.experience_years = configData.form_answers.experience_years || {};

    configData.form_answers.text_mappings.english = document.getElementById("ansEnglish").value;
    configData.form_answers.text_mappings.salary_expectation = document.getElementById("ansSalary").value;
    configData.form_answers.experience_years.java = parseInt(document.getElementById("ansJava").value) || 1;
    configData.form_answers.experience_years.react = parseInt(document.getElementById("ansReact").value) || 1;

    await saveConfigToServer();
    alert("Smart answers saved!");
}

async function saveConfigToServer() {
    await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(configData)
    });
}

// Resume Uploads
async function uploadCv(input, slot) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];
    const formData = new FormData();
    formData.append("file", file);
    formData.append("target_slot", slot);

    try {
        const res = await fetch("/api/resumes/upload", {
            method: "POST",
            body: formData
        });
        const data = await res.json();
        alert(`Resume uploaded successfully as ${data.filename}!`);
        fetchResumes();
    } catch (e) {
        alert("Upload failed: " + e.message);
    }
}

async function fetchResumes() {
    try {
        const res = await fetch("/api/resumes/list");
        const data = await res.json();
        const files = data.resumes || [];
        
        const fsFile = files.find(f => f.name.includes("FullStack"));
        if (fsFile) document.getElementById("fullstackFileLabel").textContent = `${fsFile.name} (${fsFile.size_kb} KB)`;

        const daFile = files.find(f => f.name.includes("DataAnalyst"));
        if (daFile) document.getElementById("dataAnalystFileLabel").textContent = `${daFile.name} (${daFile.size_kb} KB)`;
    } catch (e) {}
}

// Scheduler Settings
function selectInterval(hours) {
    currentInterval = hours;
    document.querySelectorAll(".interval-card").forEach(el => el.classList.remove("active"));
    event.currentTarget.classList.add("active");
    document.getElementById("kpiScheduler").textContent = `Every ${hours}h`;
    saveSchedulerSettings();
}

async function saveSchedulerSettings() {
    const enabled = document.getElementById("schedulerToggle").checked;
    const formData = new FormData();
    formData.append("enabled", enabled);
    formData.append("interval_hours", currentInterval);

    await fetch("/api/scheduler/update", {
        method: "POST",
        body: formData
    });
}

// History & Analytics Table
async function fetchJobs() {
    try {
        const res = await fetch("/api/jobs");
        const data = await res.json();
        allJobs = data.jobs || [];
        renderJobsTable(allJobs);
    } catch (e) {}
}

function renderJobsTable(jobs) {
    const tbody = document.getElementById("jobsTableBody");
    tbody.innerHTML = "";

    if (jobs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-slate-500">No applications recorded yet.</td></tr>`;
        return;
    }

    jobs.forEach(job => {
        const tr = document.createElement("tr");
        tr.className = "hover:bg-white/[0.02] transition";
        
        const isApplied = job.status === "APPLIED";
        const badge = isApplied 
            ? `<span class="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">APPLIED</span>`
            : `<span class="px-2 py-0.5 rounded-full bg-slate-700 text-slate-400 border border-white/5">SKIPPED</span>`;

        tr.innerHTML = `
            <td class="py-3 px-4 font-semibold text-white">${escapeHtml(job.job_title || 'N/A')}</td>
            <td class="py-3 px-4 text-slate-300">${escapeHtml(job.company || 'N/A')}</td>
            <td class="py-3 px-4 text-slate-400">${escapeHtml(job.location || 'Remote')}</td>
            <td class="py-3 px-4 font-mono text-[11px] text-slate-500">${(job.applied_date || '').slice(0, 16).replace('T', ' ')}</td>
            <td class="py-3 px-4">${badge}</td>
            <td class="py-3 px-4 text-right">
                <a href="${job.job_url}" target="_blank" class="text-brand-cyan hover:underline font-semibold flex items-center justify-end gap-1">
                    View <i data-lucide="external-link" class="w-3 h-3"></i>
                </a>
            </td>
        `;
        tbody.appendChild(tr);
    });
    lucide.createIcons();
}

function filterJobsTable() {
    const q = document.getElementById("jobSearchFilter").value.toLowerCase();
    const filtered = allJobs.filter(j => 
        (j.job_title && j.job_title.toLowerCase().includes(q)) ||
        (j.company && j.company.toLowerCase().includes(q)) ||
        (j.location && j.location.toLowerCase().includes(q))
    );
    renderJobsTable(filtered);
}
