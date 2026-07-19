/**
 * Dashboard page logic
 */

document.addEventListener('DOMContentLoaded', async () => {
    await Promise.all([
        checkHealth(),
        loadProjects(),
        loadHistorySummary()
    ]);

    // Link quick-project dropdown to analyze page
    document.getElementById('quick-project').addEventListener('change', (e) => {
        if (e.target.value) {
            document.getElementById('analyze-link').href =
                `analyze.html?project=${encodeURIComponent(e.target.value)}`;
        }
    });
});

async function checkHealth() {
    const el = document.getElementById('health-status');
    try {
        const data = await api.health();
        if (data.status === 'healthy') {
            el.textContent = `Healthy | ${data.model} | ${data.examples_count} examples`;
            el.className = 'px-4 py-2 rounded-lg bg-green-50 text-green-700 text-sm font-medium';
        }
    } catch {
        el.textContent = 'Backend Offline';
        el.className = 'px-4 py-2 rounded-lg bg-red-50 text-red-700 text-sm font-medium';
    }
}

async function loadProjects() {
    const listEl = document.getElementById('projects-list');
    const selectEl = document.getElementById('quick-project');

    try {
        const projects = await api.listProjects();

        if (projects.length === 0) {
            listEl.innerHTML = '<p class="text-gray-500">No projects yet. Upload a ZIP to get started.</p>';
            return;
        }

        // Populate project cards
        listEl.innerHTML = projects.map(p => `
            <div class="border border-gray-200 rounded-lg p-4 flex justify-between items-center hover:bg-gray-50 transition mb-2">
                <div>
                    <h3 class="font-semibold text-gray-800">${p.name}</h3>
                    <p class="text-xs text-gray-500">${p.path} &middot; ${p.c_files_count} C/H files &middot; ${new Date(p.created_at).toLocaleDateString()}</p>
                </div>
                <div class="flex gap-2">
                    <a href="analyze.html?project=${encodeURIComponent(p.path)}"
                       class="px-3 py-1 bg-blue-500 text-white rounded text-xs font-medium hover:bg-blue-600 transition">
                        Analyze
                    </a>
                    <a href="generate.html?project=${encodeURIComponent(p.path)}"
                       class="px-3 py-1 bg-green-500 text-white rounded text-xs font-medium hover:bg-green-600 transition">
                        Generate
                    </a>
                </div>
            </div>
        `).join('');

        // Populate quick select
        projects.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.path;
            opt.textContent = p.name;
            selectEl.appendChild(opt);
        });

    } catch (err) {
        listEl.innerHTML = '<p class="text-red-500">Failed to load projects</p>';
    }
}

async function loadHistorySummary() {
    try {
        const history = await api.getHistory();
        document.getElementById('history-summary').textContent =
            `${history.length} run${history.length !== 1 ? 's' : ''}`;
    } catch {
        document.getElementById('history-summary').textContent = '--';
    }
}

async function uploadProject() {
    const fileInput = document.getElementById('upload-file');
    const statusEl = document.getElementById('upload-status');
    const file = fileInput.files[0];

    if (!file) {
        showToast('Please select a ZIP file', 'error');
        return;
    }

    statusEl.className = 'mt-2 text-sm text-gray-500';
    statusEl.textContent = 'Uploading...';

    try {
        const result = await api.uploadProject(file);
        statusEl.className = 'mt-2 text-sm text-green-600';
        statusEl.textContent = `Uploaded "${result.project_name}" (${result.c_files_count} C/H files)`;
        showToast('Project uploaded successfully', 'success');
        fileInput.value = '';
        await loadProjects();
    } catch (err) {
        statusEl.className = 'mt-2 text-sm text-red-600';
        statusEl.textContent = `Error: ${err.message}`;
        showToast(err.message, 'error');
    }
}
