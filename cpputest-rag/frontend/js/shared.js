/**
 * Shared utilities and project context management
 */

// Project context management using localStorage
const ProjectContext = {
    get() {
        const stored = localStorage.getItem('currentProject');
        return stored ? JSON.parse(stored) : null;
    },

    set(projectPath) {
        localStorage.setItem('currentProject', JSON.stringify({
            path: projectPath,
            timestamp: Date.now()
        }));
        this.updateUI();
    },

    clear() {
        localStorage.removeItem('currentProject');
        this.updateUI();
    },

    updateUI() {
        const banner = document.getElementById('project-banner');
        const project = this.get();

        if (banner) {
            if (project) {
                banner.innerHTML = `
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                            </svg>
                            <span class="text-sm font-medium text-gray-700">Current Project:</span>
                            <span class="text-sm font-semibold text-blue-600">${project.path}</span>
                        </div>
                        <button onclick="ProjectContext.clear()" class="text-xs text-red-600 hover:text-red-800 font-medium">
                            Clear
                        </button>
                    </div>
                `;
                banner.classList.remove('hidden');
            } else {
                banner.classList.add('hidden');
            }
        }

        // Update all navigation Generate links
        const generateLinks = document.querySelectorAll('[data-nav-generate]');
        generateLinks.forEach(link => {
            if (project) {
                link.href = `generate.html?project=${encodeURIComponent(project.path)}`;
            } else {
                link.href = 'generate.html';
            }
        });
    }
};

// Load available projects
async function loadProjectsList() {
    try {
        const data = await api.listProjects();
        // API returns array directly, not wrapped in object
        return Array.isArray(data) ? data : (data.projects || []);
    } catch (err) {
        console.error('Failed to load projects:', err);
        return [];
    }
}

// Populate project selector dropdown
async function populateProjectSelector(selectElement, includeManual = true) {
    if (!selectElement) return;

    const projects = await loadProjectsList();
    const currentProject = ProjectContext.get();

    selectElement.innerHTML = '<option value="">Select a project...</option>';

    if (includeManual) {
        selectElement.innerHTML += '<option value="__manual__">📝 Enter path manually...</option>';
    }

    projects.forEach(proj => {
        const option = document.createElement('option');
        option.value = proj.path;
        option.textContent = `${proj.name} (${proj.path})`;
        if (currentProject && currentProject.path === proj.path) {
            option.selected = true;
        }
        selectElement.appendChild(option);
    });
}

// Initialize shared components on page load
document.addEventListener('DOMContentLoaded', () => {
    ProjectContext.updateUI();
});
