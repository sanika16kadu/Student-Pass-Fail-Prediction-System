/**
 * Student Pass & Fail Prediction System
 * Interactive Frontend Client Script
 */

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initAnimatedCounters();
    initPredictionForm();
    initStudentTableFilter();
});

// ----------------- THEME MANAGEMENT -----------------
function initTheme() {
    const savedTheme = localStorage.getItem('app-theme') || 'light';
    applyTheme(savedTheme);

    const toggleBtn = document.getElementById('themeToggleBtn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const current = document.body.classList.contains('dark') ? 'dark' : 'light';
            const next = current === 'dark' ? 'light' : 'dark';
            applyTheme(next);
        });
    }
}

function applyTheme(theme) {
    if (theme === 'dark') {
        document.body.classList.remove('light');
        document.body.classList.add('dark');
        document.documentElement.setAttribute('data-bs-theme', 'dark');
    } else {
        document.body.classList.remove('dark');
        document.body.classList.add('light');
        document.documentElement.setAttribute('data-bs-theme', 'light');
    }
    localStorage.setItem('app-theme', theme);
    
    const themeIcon = document.getElementById('themeToggleIcon');
    if (themeIcon) {
        themeIcon.className = theme === 'dark' ? 'bi bi-sun-fill text-warning' : 'bi bi-moon-stars-fill text-white';
    }
}

// ----------------- ANIMATED DASHBOARD COUNTERS -----------------
function initAnimatedCounters() {
    const counters = document.querySelectorAll('.animate-counter');
    counters.forEach(counter => {
        const target = parseFloat(counter.getAttribute('data-target') || '0');
        const isPercent = counter.getAttribute('data-percent') === 'true';
        const duration = 900; // ms
        const startTime = performance.now();

        function update(now) {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1.0);
            // Ease out cubic
            const ease = 1 - Math.pow(1 - progress, 3);
            const current = target * ease;

            if (isPercent) {
                counter.textContent = current.toFixed(1) + '%';
            } else {
                counter.textContent = Math.round(current);
            }

            if (progress < 1.0) {
                requestAnimationFrame(update);
            } else {
                if (isPercent) counter.textContent = target.toFixed(1) + '%';
                else counter.textContent = target;
            }
        }

        requestAnimationFrame(update);
    });
}

// ----------------- PREDICTION FORM & AJAX -----------------
function initPredictionForm() {
    const form = document.getElementById('academicPredictionForm');
    if (!form) return;

    const submitBtn = document.getElementById('predictSubmitBtn');
    const resetBtn = document.getElementById('formResetBtn');
    const btnText = document.getElementById('predictBtnText');
    const spinner = document.getElementById('predictSpinner');
    const errorAlert = document.getElementById('predictErrorAlert');
    const resultContainer = document.getElementById('ajaxResultContainer');

    // Live range indicators on inputs
    const inputs = form.querySelectorAll('input[type="number"]');
    inputs.forEach(input => {
        input.addEventListener('input', () => {
            validateSingleInput(input);
        });
    });

    // Reset button
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            form.reset();
            if (resultContainer) resultContainer.innerHTML = '';
            if (errorAlert) {
                errorAlert.classList.add('d-none');
                errorAlert.textContent = '';
            }
            inputs.forEach(inp => inp.classList.remove('is-invalid', 'is-valid'));
        });
    }

    // Submit handler
    form.addEventListener('submit', async (e) => {
        // We use AJAX to call the existing /api/predict endpoint seamlessly
        e.preventDefault();

        if (errorAlert) {
            errorAlert.classList.add('d-none');
            errorAlert.textContent = '';
        }

        // Validate client inputs
        let hasError = false;
        inputs.forEach(input => {
            if (!validateSingleInput(input)) {
                hasError = true;
            }
        });

        if (hasError) {
            showError("Please check the highlighted fields for invalid or out-of-range values.");
            return;
        }

        // Payload for existing API
        const payload = {
            attendance: parseFloat(document.getElementById('attendance').value),
            prev_sem_percentage: parseFloat(document.getElementById('prev_sem_percentage').value),
            internal_marks: parseFloat(document.getElementById('internal_marks').value),
            assignment_marks: parseFloat(document.getElementById('assignment_marks').value),
            practical_marks: parseFloat(document.getElementById('practical_marks').value),
            study_hours: parseFloat(document.getElementById('study_hours').value),
            backlogs: parseInt(document.getElementById('backlogs').value, 10)
        };

        // UI Loading state
        setLoadingState(true);

        try {
            const response = await fetch('/api/predict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (!response.ok || data.status === 'error') {
                const errMsg = data.message || (data.errors ? data.errors.join(', ') : 'Prediction request failed.');
                showError(errMsg);
                return;
            }

            // Render Result Card
            renderPredictionResult(data);

            // Scroll result into view smoothly
            if (resultContainer) {
                resultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }

        } catch (err) {
            showError("Network or server connection issue: " + err.message);
        } finally {
            setLoadingState(false);
        }
    });

    function setLoadingState(loading) {
        if (!submitBtn) return;
        submitBtn.disabled = loading;
        if (loading) {
            spinner.classList.remove('d-none');
            btnText.textContent = "Analyzing Student Data...";
        } else {
            spinner.classList.add('d-none');
            btnText.textContent = "Predict Result";
        }
    }

    function showError(msg) {
        if (!errorAlert) return;
        errorAlert.textContent = msg;
        errorAlert.classList.remove('d-none');
    }

    function validateSingleInput(input) {
        const val = parseFloat(input.value);
        const min = parseFloat(input.min !== '' ? input.min : -Infinity);
        const max = parseFloat(input.max !== '' ? input.max : Infinity);

        if (isNaN(val) || val < min || val > max) {
            input.classList.add('is-invalid');
            input.classList.remove('is-valid');
            return false;
        } else {
            input.classList.remove('is-invalid');
            input.classList.add('is-valid');
            return true;
        }
    }
}

// ----------------- RENDER RESULT CARD -----------------
function renderPredictionResult(data) {
    const container = document.getElementById('ajaxResultContainer');
    if (!container) return;

    const isPass = data.prediction === 'PASS';
    const confidence = parseFloat(data.confidence || 0).toFixed(1);
    const passProb = (parseFloat(data.pass_probability || 0) * 100).toFixed(1);
    const failProb = (parseFloat(data.fail_probability || 0) * 100).toFixed(1);
    const algo = data.algorithm || 'Machine Learning Classification Model';

    let html = `
    <div class="result-card-container mt-4">
        <div class="${isPass ? 'result-badge-pass' : 'result-badge-fail'} mb-4">
            <div class="row align-items-center g-4">
                <div class="col-lg-5 text-center border-lg-end">
                    <div class="text-uppercase small fw-bold tracking-wide opacity-75 mb-2">
                        ${isPass ? '<i class="bi bi-check-circle-fill text-success me-1"></i> Prediction Complete' : '<i class="bi bi-exclamation-triangle-fill text-danger me-1"></i> Prediction Requires Attention'}
                    </div>
                    <div class="display-3 fw-800 ${isPass ? 'text-success' : 'text-danger'} mb-2">
                        ${isPass ? 'PASS' : 'FAIL'}
                    </div>
                    <div class="h5 fw-bold mb-3">
                        Confidence: <span class="badge ${isPass ? 'bg-success' : 'bg-danger'} px-3 py-2 fs-6">${confidence}%</span>
                    </div>
                    <div class="d-flex justify-content-center gap-2">
                        <button type="button" onclick="window.scrollTo({top: 0, behavior: 'smooth'})" class="btn btn-sm btn-outline-secondary">
                            <i class="bi bi-arrow-up-circle"></i> Predict Again
                        </button>
                        <button type="button" onclick="document.getElementById('formResetBtn').click()" class="btn btn-sm btn-outline-danger">
                            <i class="bi bi-x-circle"></i> Reset Form
                        </button>
                    </div>
                </div>

                <div class="col-lg-7 ps-lg-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h6 class="fw-bold mb-0">Model Probability Breakdown</h6>
                        <span class="badge bg-secondary-subtle text-secondary small">${algo}</span>
                    </div>

                    <!-- Pass Probability -->
                    <div class="mb-3">
                        <div class="d-flex justify-content-between small fw-semibold mb-1">
                            <span><i class="bi bi-check2 text-success"></i> Pass Probability</span>
                            <span class="text-success">${passProb}%</span>
                        </div>
                        <div class="confidence-meter">
                            <div class="confidence-fill-pass" style="width: ${passProb}%"></div>
                        </div>
                    </div>

                    <!-- Fail Probability -->
                    <div class="mb-3">
                        <div class="d-flex justify-content-between small fw-semibold mb-1">
                            <span><i class="bi bi-x-lg text-danger"></i> Fail Probability</span>
                            <span class="text-danger">${failProb}%</span>
                        </div>
                        <div class="confidence-meter">
                            <div class="confidence-fill-fail" style="width: ${failProb}%"></div>
                        </div>
                    </div>

                    <p class="small text-muted mb-0">
                        <i class="bi bi-info-circle me-1"></i> Predictions are generated dynamically by evaluating student metrics against trained statistical decision boundaries.
                    </p>
                </div>
            </div>
        </div>
    `;

    // ACADEMIC FACTORS BREAKDOWN (ESPECIALLY VALUABLE FOR FAIL)
    if (data.factors && data.factors.length > 0) {
        html += `
        <div class="dash-card">
            <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                <div>
                    <h5 class="fw-bold mb-1">
                        <i class="bi bi-clipboard2-data-fill text-primary me-2"></i>
                        Student Academic Factors Breakdown
                    </h5>
                    <p class="text-muted small mb-0">
                        ${isPass 
                            ? 'Overview of student academic inputs and baseline educational benchmarks.' 
                            : 'Specific factors evaluated against academic benchmarks to assist teachers in targeted remedial advising.'}
                    </p>
                </div>
                <span class="badge ${isPass ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger'} px-3 py-2 fw-bold">
                    ${isPass ? 'Meeting Academic Standards' : 'At-Risk Factors Detected'}
                </span>
            </div>

            <div class="table-responsive">
                <table class="table table-hover align-middle text-center mb-0">
                    <thead class="table-light">
                        <tr>
                            <th class="text-start">Academic Metric</th>
                            <th>Entered Value</th>
                            <th>Educational Benchmark</th>
                            <th>Evaluation Status</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        data.factors.forEach(f => {
            const statusClass = f.badge === 'success' ? 'status-pass' : (f.badge === 'danger' ? 'status-fail' : 'status-warning');
            const icon = f.badge === 'success' ? 'bi-check-circle-fill' : (f.badge === 'danger' ? 'bi-exclamation-octagon-fill' : 'bi-exclamation-triangle-fill');
            const benchmarkText = f.key === 'backlogs' ? '0 subjects' : `&ge; ${f.benchmark} ${f.unit}`;

            html += `
                <tr>
                    <td class="text-start fw-semibold text-secondary">
                        ${f.label}
                    </td>
                    <td class="fw-bold">
                        ${f.value} ${f.unit}
                    </td>
                    <td class="text-muted">
                        ${benchmarkText}
                    </td>
                    <td>
                        <span class="status-pill ${statusClass}">
                            <i class="bi ${icon}"></i> ${f.status}
                        </span>
                    </td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>

            ${!isPass ? `
            <div class="alert alert-warning d-flex align-items-center gap-3 mt-3 mb-0 small">
                <i class="bi bi-lightbulb-fill fs-4 text-warning"></i>
                <div>
                    <strong>Actionable Teacher Guidance:</strong> Metrics flagged with <em>Needs Improvement</em> or <em>Critical</em> indicate priority areas for remedial tutoring, backlog clearance, and attendance intervention.
                </div>
            </div>
            ` : ''}
        </div>
        `;
    }

    html += `</div>`;
    container.innerHTML = html;
}

// ----------------- SAMPLE PRESETS -----------------
function loadSample(type) {
    if (type === 'pass') {
        document.getElementById('attendance').value = '92.0';
        document.getElementById('prev_sem_percentage').value = '84.0';
        document.getElementById('internal_marks').value = '78.0';
        document.getElementById('assignment_marks').value = '82.0';
        document.getElementById('practical_marks').value = '85.0';
        document.getElementById('study_hours').value = '5.0';
        document.getElementById('backlogs').value = '0';
    } else if (type === 'fail') {
        document.getElementById('attendance').value = '46.0';
        document.getElementById('prev_sem_percentage').value = '40.0';
        document.getElementById('internal_marks').value = '28.0';
        document.getElementById('assignment_marks').value = '32.0';
        document.getElementById('practical_marks').value = '35.0';
        document.getElementById('study_hours').value = '1.0';
        document.getElementById('backlogs').value = '3';
    }

    // Trigger input validation styling
    const inputs = document.querySelectorAll('#academicPredictionForm input[type="number"]');
    inputs.forEach(input => {
        input.classList.remove('is-invalid');
        input.classList.add('is-valid');
    });

    // Clear previous results
    const container = document.getElementById('ajaxResultContainer');
    if (container) container.innerHTML = '';
}

// ----------------- TABLE SEARCH / FILTER -----------------
function initStudentTableFilter() {
    const searchInput = document.getElementById('studentTableSearch');
    if (!searchInput) return;

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        const rows = document.querySelectorAll('#studentsTableBody tr');

        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            if (text.includes(query)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
}
