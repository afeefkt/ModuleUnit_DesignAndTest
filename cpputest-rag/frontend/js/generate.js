/**
 * Generate page logic - Redesigned
 */

let currentOutputDir = null;
let lastTestResult = null;  // Store last test result for report generation
let lastTestDirectory = null;  // Store test directory name

document.addEventListener('DOMContentLoaded', async () => {
    // Load projects into dropdown
    await populateProjectSelector(document.getElementById('project-selector'), false);

    // Auto-fill from URL query param or localStorage
    const params = new URLSearchParams(window.location.search);
    const projectFromUrl = params.get('project');
    const projectFromContext = ProjectContext.get();

    const targetProject = projectFromUrl || (projectFromContext ? projectFromContext.path : null);

    if (targetProject) {
        const selector = document.getElementById('project-selector');
        selector.value = targetProject;
        ProjectContext.set(targetProject);
    }
});

async function generateTests() {
    const selector = document.getElementById('project-selector');
    const path = selector.value.trim();
    const funcName = document.getElementById('function-name').value.trim();

    if (!path) {
        showToast('Please select a project', 'error');
        return;
    }

    // Save to context
    ProjectContext.set(path);

    const target = funcName || 'ALL functions';
    if (!confirm(`Generate CppUTest cases for ${target}?\n\nProject: ${path}\n\nThis may take several minutes.`)) {
        return;
    }

    // Show loading, hide others
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('results').classList.add('hidden');
    document.getElementById('error').classList.add('hidden');
    document.getElementById('test-results').classList.add('hidden');

    try {
        const data = await api.generateTests(path, funcName);

        // Fill stats
        document.getElementById('stat-analyzed').textContent = data.functions_analyzed;
        document.getElementById('stat-generated').textContent = data.tests_generated;
        document.getElementById('stat-failed').textContent = data.failed_functions.length;
        document.getElementById('stat-time').textContent = data.elapsed_seconds.toFixed(1) + 's';
        document.getElementById('output-dir').textContent = data.output_directory;

        // Save output directory for running tests later
        currentOutputDir = data.output_directory;

        // Show failed functions if any
        if (data.failed_functions.length > 0) {
            document.getElementById('failed-section').classList.remove('hidden');
            document.getElementById('failed-list').innerHTML =
                data.failed_functions.map(f => `<li class="py-1">${f}</li>`).join('');
        } else {
            document.getElementById('failed-section').classList.add('hidden');
        }

        // Show results
        document.getElementById('results').classList.remove('hidden');
        showToast(`Generated ${data.tests_generated} test(s) successfully!`, 'success');

    } catch (err) {
        const errorMsg = err.message || String(err);
        document.getElementById('error-msg').textContent = errorMsg;
        document.getElementById('error').classList.remove('hidden');
        showToast(errorMsg, 'error');
    } finally {
        document.getElementById('loading').classList.add('hidden');
    }
}

async function rebuildIndex() {
    const resultEl = document.getElementById('index-result');
    const msgEl = document.getElementById('index-msg');

    try {
        const data = await api.rebuildIndex();
        msgEl.textContent = `Index rebuilt successfully — ${data.examples_indexed} examples indexed`;
        resultEl.classList.remove('hidden');
        showToast('Index rebuilt successfully', 'success');
        setTimeout(() => resultEl.classList.add('hidden'), 5000);
    } catch (err) {
        const errorMsg = err.message || String(err);
        showToast('Failed to rebuild index: ' + errorMsg, 'error');
    }
}

async function runGeneratedTests() {
    if (!currentOutputDir) {
        showToast('No tests generated yet', 'error');
        return;
    }

    // Extract just the directory name from the full path
    const dirName = currentOutputDir.split('/').pop().split('\\').pop();

    const runBtn = document.getElementById('run-tests-btn');
    const runningEl = document.getElementById('test-running');
    const resultsEl = document.getElementById('test-results');
    const buildOut = document.getElementById('build-output');
    const testOut = document.getElementById('test-output');

    runBtn.disabled = true;
    runningEl.classList.remove('hidden');
    resultsEl.classList.add('hidden');

    // Show live progress
    buildOut.textContent = '⏳ Starting build process...\n';
    testOut.textContent = 'Waiting for build to complete...\n';

    // Show results section immediately with "in progress" state
    resultsEl.classList.remove('hidden');
    const titleEl = document.getElementById('test-results-title');
    titleEl.innerHTML = `
        <div class="flex items-center gap-2">
            <div class="spinner" style="width: 20px; height: 20px; border-width: 2px;"></div>
            <span>Building and Running Tests...</span>
        </div>
    `;
    titleEl.className = 'text-lg font-bold mb-4 flex items-center gap-2 text-blue-700';

    try {
        // Simulate progress updates
        buildOut.textContent += `📁 Test directory: ${dirName}\n`;
        buildOut.textContent += `🔨 Running: docker exec cpputest-runner make...\n`;
        buildOut.textContent += `\n--- Build Output ---\n`;

        const data = await api.runTests(dirName);

        // Store test result for report generation
        lastTestResult = data;
        lastTestDirectory = dirName;

        // Clear progress messages and show actual output
        const testSection = document.getElementById('test-output-section');
        const reportButtons = document.getElementById('report-buttons');

        if (data.status === 'build_failed') {
            titleEl.innerHTML = `
                <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                ❌ Build Failed
            `;
            titleEl.className = 'text-lg font-bold mb-4 flex items-center gap-2 text-red-700';

            buildOut.textContent = '=== BUILD OUTPUT ===\n\n';
            buildOut.textContent += (data.build_output || 'No build output');
            buildOut.textContent += '\n\n=== BUILD ERROR ===\n\n';
            buildOut.textContent += (data.build_error || 'No error details');

            testSection.classList.add('hidden');
            reportButtons.classList.remove('hidden');  // Show download button even for build failures
            showToast('Build failed - check output for details', 'error');
        } else {
            buildOut.textContent = '=== BUILD OUTPUT ===\n\n';
            buildOut.textContent += (data.build_output || 'No build output');

            testOut.textContent = '=== TEST EXECUTION ===\n\n';
            testOut.textContent += (data.test_output || 'No test output');

            if (data.test_error) {
                testOut.textContent += '\n\n=== TEST ERRORS ===\n\n';
                testOut.textContent += data.test_error;
            }

            if (data.status === 'passed') {
                titleEl.innerHTML = `
                    <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    ✅ All Tests Passed! Report saved to: ${dirName}/test-report.html
                `;
                titleEl.className = 'text-lg font-bold mb-4 flex items-center gap-2 text-green-700';
                showToast('All tests passed! HTML report generated.', 'success');
            } else {
                titleEl.innerHTML = `
                    <svg class="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    ⚠️ Some Tests Failed
                `;
                titleEl.className = 'text-lg font-bold mb-4 flex items-center gap-2 text-orange-700';
                showToast(`Tests completed with failures (exit code: ${data.exit_code || 'N/A'})`, 'error');
            }
            testSection.classList.remove('hidden');
            reportButtons.classList.remove('hidden');  // Show download button
        }

        // Show/hide coverage buttons based on availability
        const viewCoverageBtn = document.getElementById('view-coverage-btn');
        const downloadLcovBtn = document.getElementById('download-lcov-btn');
        const downloadJunitBtn = document.getElementById('download-junit-btn');

        if (data.html_coverage_available) {
            viewCoverageBtn.classList.remove('hidden');
        } else {
            viewCoverageBtn.classList.add('hidden');
        }

        if (data.coverage_available) {
            downloadLcovBtn.classList.remove('hidden');
        } else {
            downloadLcovBtn.classList.add('hidden');
        }

        if (data.junit_xml_available) {
            downloadJunitBtn.classList.remove('hidden');
        } else {
            downloadJunitBtn.classList.add('hidden');
        }

        // Scroll to results
        resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
        console.error('Test execution error:', err);
        console.log('Error type:', typeof err);
        console.log('Error constructor:', err?.constructor?.name);
        console.log('Error keys:', Object.keys(err || {}));

        // Extract error details - handle all possible error formats
        let errorMsg = 'Unknown error';
        let errorDetails = '';

        if (err) {
            if (typeof err === 'string') {
                errorMsg = err;
                errorDetails = err;
            } else if (err.message) {
                errorMsg = err.message;
                errorDetails = `Message: ${err.message}\nName: ${err.name}\nStack: ${err.stack || 'N/A'}`;
            } else if (err.detail) {
                errorMsg = err.detail;
                errorDetails = JSON.stringify(err, null, 2);
            } else if (err.error) {
                errorMsg = err.error;
                errorDetails = JSON.stringify(err, null, 2);
            } else {
                errorMsg = String(err);
                errorDetails = `Type: ${typeof err}\nConstructor: ${err?.constructor?.name}\nString: ${String(err)}`;
            }

            // Try to get additional details
            if (!errorDetails) {
                try {
                    const errObj = {};
                    for (const key in err) {
                        errObj[key] = err[key];
                    }
                    errorDetails = JSON.stringify(errObj, null, 2);
                } catch {
                    errorDetails = String(err);
                }
            }
        }

        titleEl.innerHTML = `
            <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            ❌ Execution Error
        `;
        titleEl.className = 'text-lg font-bold mb-4 flex items-center gap-2 text-red-700';

        buildOut.textContent = '=== ERROR DETAILS ===\n\n';
        buildOut.textContent += `Error: ${errorMsg}\n\n`;
        buildOut.textContent += `Test directory: ${dirName}\n`;
        buildOut.textContent += `Full path: ${currentOutputDir}\n\n`;
        buildOut.textContent += `=== DEBUG INFO ===\n\n`;
        buildOut.textContent += errorDetails;

        testOut.textContent = `Check the browser console (F12) for more details.\n\n`;
        testOut.textContent += `Common issues:\n`;
        testOut.textContent += `- Test runner container not running\n`;
        testOut.textContent += `- Docker socket not accessible\n`;
        testOut.textContent += `- Invalid test directory path\n`;

        document.getElementById('test-output-section').classList.remove('hidden');

        showToast(`Execution failed: ${errorMsg}`, 'error');
    } finally {
        runBtn.disabled = false;
        runningEl.classList.add('hidden');
    }
}

// Handle report buttons (view and download)
document.addEventListener('DOMContentLoaded', () => {
    const viewBtn = document.getElementById('view-report-btn');
    const downloadBtn = document.getElementById('download-report-btn');
    const viewCoverageBtn = document.getElementById('view-coverage-btn');
    const downloadLcovBtn = document.getElementById('download-lcov-btn');
    const downloadJunitBtn = document.getElementById('download-junit-btn');

    // View report button
    viewBtn.addEventListener('click', async () => {
        if (!lastTestDirectory) {
            showToast('No test report available', 'error');
            return;
        }

        // Open report in new tab
        const url = `/api/test-report/${encodeURIComponent(lastTestDirectory)}`;
        window.open(url, '_blank');
        showToast('Opening report in new tab...', 'success');
    });

    // View coverage button
    viewCoverageBtn.addEventListener('click', async () => {
        if (!lastTestDirectory) {
            showToast('No coverage report available', 'error');
            return;
        }

        // Open coverage report in new tab
        const url = `/api/coverage-html/${encodeURIComponent(lastTestDirectory)}/index.html`;
        window.open(url, '_blank');
        showToast('Opening coverage report in new tab...', 'success');
    });

    // Download LCOV button
    downloadLcovBtn.addEventListener('click', async () => {
        if (!lastTestDirectory) {
            showToast('No LCOV file available', 'error');
            return;
        }

        try {
            const url = `/api/coverage-lcov/${encodeURIComponent(lastTestDirectory)}`;
            const a = document.createElement('a');
            a.href = url;
            a.download = `coverage-${lastTestDirectory}.info`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            showToast('LCOV file downloaded!', 'success');
        } catch (err) {
            console.error('Download error:', err);
            showToast('Failed to download LCOV file', 'error');
        }
    });

    // Download JUnit XML button
    downloadJunitBtn.addEventListener('click', async () => {
        if (!lastTestDirectory) {
            showToast('No JUnit XML available', 'error');
            return;
        }

        try {
            const url = `/api/junit-xml/${encodeURIComponent(lastTestDirectory)}`;
            const a = document.createElement('a');
            a.href = url;
            a.download = `junit-${lastTestDirectory}.xml`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            showToast('JUnit XML downloaded!', 'success');
        } catch (err) {
            console.error('Download error:', err);
            showToast('Failed to download JUnit XML', 'error');
        }
    });

    // Download report button
    downloadBtn.addEventListener('click', async () => {
        if (!lastTestDirectory) {
            showToast('No test report available', 'error');
            return;
        }

        try {
            // Fetch the report HTML
            const url = `/api/test-report/${encodeURIComponent(lastTestDirectory)}`;
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
            a.download = `cpputest-report-${lastTestDirectory}.html`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(downloadUrl);

            showToast('Report downloaded successfully!', 'success');
        } catch (err) {
            console.error('Download report error:', err);
            showToast('Failed to download report: ' + (err.message || 'Unknown error'), 'error');
        }
    });
});
