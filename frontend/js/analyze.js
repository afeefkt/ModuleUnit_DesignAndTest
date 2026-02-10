/**
 * Analyze page logic - Redesigned
 */

document.addEventListener('DOMContentLoaded', async () => {
    // Load projects into dropdown
    await populateProjectSelector(document.getElementById('project-selector'), true);

    // Auto-fill from URL query param or localStorage
    const params = new URLSearchParams(window.location.search);
    const projectFromUrl = params.get('project');
    const projectFromContext = ProjectContext.get();

    if (projectFromUrl) {
        setProjectPath(projectFromUrl);
        analyzeProject();
    } else if (projectFromContext) {
        setProjectPath(projectFromContext.path);
    }

    // Handle project selector change
    document.getElementById('project-selector').addEventListener('change', (e) => {
        const value = e.target.value;
        if (value === '__manual__') {
            showManualInput();
        } else if (value) {
            setProjectPath(value);
            document.getElementById('manual-path-section').classList.add('hidden');
            document.getElementById('manual-btn').textContent = '✏️ Manual Path';
        }
    });
});

function setProjectPath(path) {
    const selector = document.getElementById('project-selector');
    const manualInput = document.getElementById('project-path-manual');

    // Try to select from dropdown
    const option = Array.from(selector.options).find(opt => opt.value === path);
    if (option) {
        selector.value = path;
    } else {
        // Show manual input with the path
        selector.value = '__manual__';
        manualInput.value = path;
        showManualInput();
    }
}

function showManualInput() {
    const section = document.getElementById('manual-path-section');
    const btn = document.getElementById('manual-btn');

    if (section.classList.contains('hidden')) {
        section.classList.remove('hidden');
        btn.textContent = '✏️ Hide Manual';
        document.getElementById('project-selector').value = '__manual__';
    } else {
        section.classList.add('hidden');
        btn.textContent = '✏️ Manual Path';
        document.getElementById('project-selector').value = '';
    }
}

function getSelectedProjectPath() {
    const selector = document.getElementById('project-selector');
    if (selector.value === '__manual__') {
        return document.getElementById('project-path-manual').value.trim();
    }
    return selector.value.trim();
}

async function analyzeProject() {
    const path = getSelectedProjectPath();

    if (!path) {
        showToast('Please select or enter a project path', 'error');
        return;
    }

    // Save to context
    ProjectContext.set(path);

    // Show loading, hide others
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('results').classList.add('hidden');
    document.getElementById('error').classList.add('hidden');

    try {
        const data = await api.analyzeProject(path);

        // Fill summary stats
        document.getElementById('stat-files').textContent = data.total_files;
        document.getElementById('stat-functions').textContent = data.total_functions;
        document.getElementById('stat-lines').textContent = data.project_structure.total_lines;

        // Fill file list
        document.getElementById('file-list').innerHTML =
            data.project_structure.files.map(f => `
                <div class="py-1 text-gray-700 hover:text-purple-600 transition">${f}</div>
            `).join('');

        // Fill function list
        const funcListEl = document.getElementById('function-list');
        if (data.functions.length === 0) {
            funcListEl.innerHTML = `
                <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
                    <svg class="w-8 h-8 text-yellow-600 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <p class="text-yellow-700 font-medium">No functions found</p>
                    <p class="text-yellow-600 text-sm mt-1">Check if files contain valid C function definitions</p>
                </div>
            `;
        } else {
            funcListEl.innerHTML = data.functions.map(func => {
                const params = func.parameters.map(p => `${p.type} ${p.name}`).join(', ');
                const fileName = func.file_path.split('/').pop().split('\\').pop();
                const complexityColor = func.complexity_score > 10 ? 'text-red-600' :
                                       func.complexity_score > 5 ? 'text-yellow-600' : 'text-green-600';
                return `
                    <div class="border-2 border-gray-200 rounded-lg p-4 hover:border-purple-400 hover:shadow-md transition card-hover">
                        <div class="font-mono text-sm font-semibold text-gray-800 mb-2">
                            <span class="text-blue-600">${func.return_type}</span>
                            <span class="text-purple-600 font-bold">${func.name}</span>
                            <span class="text-gray-600">(${params || 'void'})</span>
                        </div>
                        <div class="flex items-center gap-4 text-xs text-gray-500">
                            <span class="flex items-center gap-1">
                                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                                </svg>
                                ${fileName}
                            </span>
                            <span>Line ${func.line_number}</span>
                            <span class="flex items-center gap-1 ${complexityColor} font-medium">
                                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                                </svg>
                                Complexity: ${func.complexity_score}
                            </span>
                        </div>
                    </div>
                `;
            }).join('');
        }

        // Update generate link
        const generateUrl = `generate.html?project=${encodeURIComponent(path)}`;
        document.getElementById('generate-link').href = generateUrl;

        // Show results
        document.getElementById('results').classList.remove('hidden');
        showToast(`Found ${data.total_functions} functions in ${data.total_files} files`, 'success');

    } catch (err) {
        document.getElementById('error-msg').textContent = err.message;
        document.getElementById('error').classList.remove('hidden');
        showToast(err.message, 'error');
    } finally {
        document.getElementById('loading').classList.add('hidden');
    }
}
