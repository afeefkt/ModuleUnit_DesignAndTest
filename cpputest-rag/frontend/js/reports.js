/**
 * Reports page logic
 */

document.addEventListener('DOMContentLoaded', async () => {
    await loadReports();
});

async function loadReports() {
    const loadingEl = document.getElementById('loading');
    const containerEl = document.getElementById('reports-container');
    const noReportsEl = document.getElementById('no-reports');

    try {
        loadingEl.classList.remove('hidden');
        containerEl.classList.add('hidden');
        noReportsEl.classList.add('hidden');

        const data = await api.listReports();

        loadingEl.classList.add('hidden');

        if (!data.reports || data.reports.length === 0) {
            noReportsEl.classList.remove('hidden');
            return;
        }

        // Display reports
        containerEl.innerHTML = data.reports.map(report => createReportCard(report)).join('');
        containerEl.classList.remove('hidden');

    } catch (err) {
        console.error('Error loading reports:', err);
        loadingEl.classList.add('hidden');
        showToast('Failed to load reports: ' + (err.message || 'Unknown error'), 'error');
        noReportsEl.classList.remove('hidden');
    }
}

function createReportCard(report) {
    const date = new Date(report.created * 1000);
    const dateStr = date.toLocaleString();
    const sizeKB = (report.size / 1024).toFixed(1);

    return `
        <div class="bg-white rounded-lg shadow-md p-6 border border-gray-200 hover:shadow-lg transition">
            <div class="flex items-start justify-between">
                <div class="flex-1">
                    <div class="flex items-center gap-3 mb-3">
                        <svg class="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        </svg>
                        <div>
                            <h3 class="text-lg font-bold text-gray-800">${report.test_directory}</h3>
                            <p class="text-sm text-gray-600">Generated: ${dateStr}</p>
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-4 mb-4">
                        <div class="bg-gray-50 rounded-lg p-3 border border-gray-200">
                            <div class="text-xs text-gray-600 mb-1">Report Size</div>
                            <div class="text-lg font-bold text-gray-800">${sizeKB} KB</div>
                        </div>
                        <div class="bg-gray-50 rounded-lg p-3 border border-gray-200">
                            <div class="text-xs text-gray-600 mb-1">Test Directory</div>
                            <div class="text-sm font-mono text-gray-800">${report.test_directory}</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="flex gap-3 mt-4">
                <button
                    onclick="viewReport('${report.test_directory}')"
                    class="flex-1 px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition flex items-center justify-center gap-2">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                    </svg>
                    View Report
                </button>
                <button
                    onclick="downloadReport('${report.test_directory}')"
                    class="flex-1 px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition flex items-center justify-center gap-2">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"></path>
                    </svg>
                    Download
                </button>
            </div>
        </div>
    `;
}

async function viewReport(testDirectory) {
    try {
        // Open report in new window/tab
        const url = `/api/test-report/${encodeURIComponent(testDirectory)}`;
        window.open(url, '_blank');

        showToast('Opening report in new tab...', 'success');

    } catch (err) {
        console.error('Error viewing report:', err);
        showToast('Failed to open report: ' + (err.message || 'Unknown error'), 'error');
    }
}

async function downloadReport(testDirectory) {
    try {
        // Fetch the report HTML
        const url = `/api/test-report/${encodeURIComponent(testDirectory)}`;
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error('Failed to fetch report');
        }

        const htmlContent = await response.text();

        // Create blob and download
        const blob = new Blob([htmlContent], { type: 'text/html' });
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `cpputest-report-${testDirectory}.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(downloadUrl);

        showToast('Report downloaded successfully!', 'success');

    } catch (err) {
        console.error('Error downloading report:', err);
        showToast('Failed to download report: ' + (err.message || 'Unknown error'), 'error');
    }
}
