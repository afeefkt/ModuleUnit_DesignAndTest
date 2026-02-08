/**
 * CppUTest Generator — API Client
 * All backend communication goes through this module.
 * Uses /api/ prefix which nginx proxies to the backend.
 */

const API_BASE = '/api';

const api = {
    /** Health check */
    async health() {
        const res = await fetch(`${API_BASE}/health`);
        return res.json();
    },

    /** List registered projects */
    async listProjects() {
        const res = await fetch(`${API_BASE}/projects`);
        if (!res.ok) throw new Error('Failed to load projects');
        return res.json();
    },

    /** Upload a project zip */
    async uploadProject(file) {
        const form = new FormData();
        form.append('file', file);
        const res = await fetch(`${API_BASE}/upload-project`, {
            method: 'POST',
            body: form
        });
        if (!res.ok) {
            let errorMsg = 'Upload failed';
            try {
                const err = await res.json();
                errorMsg = err.detail || errorMsg;
            } catch {
                errorMsg = `${errorMsg} (HTTP ${res.status})`;
            }
            throw new Error(errorMsg);
        }
        return res.json();
    },

    /** Analyze a C project */
    async analyzeProject(projectPath) {
        const res = await fetch(
            `${API_BASE}/analyze-project?project_path=${encodeURIComponent(projectPath)}`
        );
        if (!res.ok) {
            let errorMsg = 'Analysis failed';
            try {
                const err = await res.json();
                errorMsg = err.detail || errorMsg;
            } catch {
                errorMsg = `${errorMsg} (HTTP ${res.status})`;
            }
            throw new Error(errorMsg);
        }
        return res.json();
    },

    /** Generate tests */
    async generateTests(projectPath, functionName) {
        const res = await fetch(`${API_BASE}/generate-tests`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_path: projectPath,
                function_name: functionName || null,
                generate_all: !functionName
            })
        });
        if (!res.ok) {
            let errorMsg = 'Generation failed';
            try {
                const err = await res.json();
                errorMsg = err.detail || errorMsg;
            } catch {
                errorMsg = `${errorMsg} (HTTP ${res.status})`;
            }
            throw new Error(errorMsg);
        }
        return res.json();
    },

    /** Get generation history */
    async getHistory() {
        const res = await fetch(`${API_BASE}/generation-history`);
        if (!res.ok) throw new Error('Failed to load history');
        return res.json();
    },

    /** Rebuild RAG examples index */
    async rebuildIndex() {
        const res = await fetch(`${API_BASE}/rebuild-examples-index`, { method: 'POST' });
        if (!res.ok) throw new Error('Failed to rebuild index');
        return res.json();
    },

    /** Run tests in a directory */
    async runTests(testDirectory) {
        const res = await fetch(
            `${API_BASE}/run-tests?test_directory=${encodeURIComponent(testDirectory)}`,
            { method: 'POST' }
        );
        if (!res.ok) {
            let errorMsg = 'Test execution failed';
            try {
                const err = await res.json();
                errorMsg = err.detail || errorMsg;
            } catch {
                errorMsg = `${errorMsg} (HTTP ${res.status})`;
            }
            throw new Error(errorMsg);
        }
        return res.json();
    },

    /** List test directories */
    async listTestDirectories() {
        const res = await fetch(`${API_BASE}/test-directories`);
        if (!res.ok) throw new Error('Failed to list test directories');
        return res.json();
    }
};

/** Show a toast notification */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}
