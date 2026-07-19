/**
 * History page logic
 */

document.addEventListener('DOMContentLoaded', loadHistory);

async function loadHistory() {
    const loadingEl = document.getElementById('loading');
    const emptyEl = document.getElementById('empty');
    const tableEl = document.getElementById('history-table');
    const bodyEl = document.getElementById('history-body');

    // Show loading
    loadingEl.classList.remove('hidden');
    emptyEl.classList.add('hidden');
    tableEl.classList.add('hidden');

    try {
        const history = await api.getHistory();

        if (history.length === 0) {
            emptyEl.classList.remove('hidden');
            return;
        }

        bodyEl.innerHTML = history.map(h => {
            const failedCount = h.failed_functions ? h.failed_functions.length : 0;
            const date = new Date(h.created_at);
            const dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            return `
                <tr class="border-b border-gray-100 hover:bg-gray-50">
                    <td class="py-3 px-2">
                        <span class="font-medium text-gray-800">${h.project_name}</span>
                        <div class="text-xs text-gray-400 truncate max-w-xs" title="${h.output_dir}">${h.output_dir}</div>
                    </td>
                    <td class="py-3 px-2 text-center">${h.functions_analyzed}</td>
                    <td class="py-3 px-2 text-center">
                        <span class="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs font-medium">
                            ${h.tests_generated}
                        </span>
                    </td>
                    <td class="py-3 px-2 text-center">
                        ${failedCount > 0
                            ? `<span class="bg-red-100 text-red-700 px-2 py-0.5 rounded text-xs font-medium">${failedCount}</span>`
                            : '<span class="text-gray-400">0</span>'
                        }
                    </td>
                    <td class="py-3 px-2 text-right text-gray-600">${h.elapsed_seconds.toFixed(1)}s</td>
                    <td class="py-3 px-2 text-right text-gray-500 text-xs">${dateStr}</td>
                </tr>
            `;
        }).join('');

        tableEl.classList.remove('hidden');

    } catch (err) {
        showToast('Failed to load history: ' + err.message, 'error');
    } finally {
        loadingEl.classList.add('hidden');
    }
}
