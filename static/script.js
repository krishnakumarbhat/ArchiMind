document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;
    const isAuthenticated = body.dataset.authenticated === 'true';

    const repoInput = document.getElementById('repoInput');
    const generateButton = document.getElementById('generateButton');
    const statusShell = document.getElementById('statusShell');
    const statusText = document.getElementById('statusText');
    const progressPanel = document.getElementById('progressPanel');
    const progressStage = document.getElementById('progressStage');
    const progressPercent = document.getElementById('progressPercent');
    const progressFill = document.getElementById('progressFill');
    const progressMessage = document.getElementById('progressMessage');
    const previewCard = document.getElementById('previewCard');
    const previewRepoName = document.getElementById('previewRepoName');
    const previewDescription = document.getElementById('previewDescription');
    const previewLanguage = document.getElementById('previewLanguage');
    const previewStars = document.getElementById('previewStars');
    const previewUpdated = document.getElementById('previewUpdated');
    const previewTopics = document.getElementById('previewTopics');
    const previewLink = document.getElementById('previewLink');
    const resultsLinkContainer = document.getElementById('resultsLinkContainer');
    const resultsLink = document.getElementById('resultsLink');
    const historySection = document.getElementById('historySection');
    const historyList = document.getElementById('historyList');
    const loginModal = document.getElementById('loginModal');
    const closeLoginModal = document.getElementById('closeLoginModal');
    const sampleRepoButtons = Array.from(document.querySelectorAll('[data-sample-repo]'));

    if (!repoInput || !generateButton || !statusShell || !statusText) {
        return;
    }

    const STORAGE_KEY = 'archimind_active_analysis';
    const PREVIEW_DEBOUNCE_MS = 320;
    let previewTimeoutId = null;
    let previewRequestCounter = 0;
    let statusPollTimer = null;

    const isValidGitHubUrl = (value) => {
        return /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?\/?$/.test(value.trim());
    };

    const setStatus = (message, isError = false) => {
        statusShell.hidden = false;
        statusText.textContent = message;
        statusText.classList.toggle('error-text', isError);
    };

    const clearStatus = () => {
        statusShell.hidden = true;
        statusText.textContent = '';
        statusText.classList.remove('error-text');
    };

    const setLoading = (isLoading, message = 'Preparing analysis...') => {
        generateButton.disabled = isLoading;
        if (isLoading) {
            setStatus(message, false);
        } else if (!progressPanel || progressPanel.hidden) {
            clearStatus();
        }
    };

    const resetProgress = () => {
        if (!progressPanel) {
            return;
        }
        progressPanel.hidden = true;
        progressStage.textContent = 'queued';
        progressPercent.textContent = '0%';
        progressFill.style.width = '0%';
        progressMessage.textContent = 'Waiting to start.';
    };

    const showProgress = (statusPayload) => {
        if (!progressPanel) {
            return;
        }

        const stage = statusPayload.stage || 'processing';
        const progress = Number(statusPayload.progress || 0);
        const message = statusPayload.message || 'Analysis in progress.';

        progressPanel.hidden = false;
        progressStage.textContent = stage;
        progressPercent.textContent = `${Math.max(0, Math.min(100, progress))}%`;
        progressFill.style.width = `${Math.max(0, Math.min(100, progress))}%`;
        progressMessage.textContent = message;
        setStatus(message, false);
    };

    const showError = (message) => {
        resetProgress();
        setLoading(false);
        setStatus(message, true);
    };

    const hidePreview = () => {
        if (!previewCard) {
            return;
        }
        previewCard.hidden = true;
        previewCard.classList.remove('loading');
        if (previewTopics) {
            previewTopics.innerHTML = '';
        }
    };

    const renderPreview = (data) => {
        if (!previewCard) {
            return;
        }

        previewCard.hidden = false;
        previewCard.classList.remove('loading');
        previewRepoName.textContent = data.full_name || 'Repository preview';
        previewDescription.textContent = data.description || 'No repository description provided.';
        previewLanguage.textContent = data.language || 'Unknown';
        previewStars.textContent = typeof data.stars === 'number' ? String(data.stars) : '0';
        previewUpdated.textContent = data.updated_at ? new Date(data.updated_at).toLocaleDateString() : 'Unknown';
        previewLink.href = data.html_url || '#';
        previewTopics.innerHTML = (data.topics || []).map((topic) => `<span class="repo-topic">${topic}</span>`).join('');
    };

    const fetchPreview = async (repoUrl) => {
        const trimmed = repoUrl.trim();
        if (!isValidGitHubUrl(trimmed)) {
            hidePreview();
            return;
        }

        const requestId = ++previewRequestCounter;
        previewCard.hidden = false;
        previewCard.classList.add('loading');

        try {
            const response = await fetch(`/api/preview?repo_url=${encodeURIComponent(trimmed)}`);
            if (!response.ok) {
                if (requestId === previewRequestCounter) {
                    hidePreview();
                }
                return;
            }

            const data = await response.json();
            if (requestId !== previewRequestCounter) {
                return;
            }

            renderPreview(data);
        } catch (_) {
            if (requestId === previewRequestCounter) {
                hidePreview();
            }
        }
    };

    const schedulePreviewFetch = () => {
        clearTimeout(previewTimeoutId);
        previewTimeoutId = setTimeout(() => {
            fetchPreview(repoInput.value);
        }, PREVIEW_DEBOUNCE_MS);
    };

    const clearActiveAnalysis = () => {
        sessionStorage.removeItem(STORAGE_KEY);
    };

    const saveActiveAnalysis = (analysisId, docUrl, repoUrl) => {
        sessionStorage.setItem(
            STORAGE_KEY,
            JSON.stringify({ analysisId, docUrl, repoUrl }),
        );
    };

    const showResultsLink = (docUrl) => {
        if (!resultsLinkContainer || !resultsLink) {
            return;
        }
        resultsLink.href = docUrl;
        resultsLinkContainer.hidden = false;
    };

    const stopPolling = () => {
        if (statusPollTimer) {
            clearInterval(statusPollTimer);
            statusPollTimer = null;
        }
    };

    const pollStatus = async (analysisId, docUrl) => {
        stopPolling();

        const pollOnce = async () => {
            try {
                const response = await fetch(`/api/status?analysis_id=${analysisId}`);
                const data = await response.json();

                if (!response.ok) {
                    showError(data.error || 'Analysis status could not be loaded.');
                    stopPolling();
                    return;
                }

                if (data.status === 'completed') {
                    stopPolling();
                    clearActiveAnalysis();
                    setLoading(false);
                    resetProgress();
                    showResultsLink(docUrl || `/doc?analysis_id=${analysisId}`);
                    setStatus('Architecture generated successfully.', false);
                    return;
                }

                if (data.status === 'error') {
                    stopPolling();
                    clearActiveAnalysis();
                    showError(data.error || 'Analysis failed.');
                    return;
                }

                showProgress(data);
            } catch (_) {
                stopPolling();
                clearActiveAnalysis();
                showError('Failed to get analysis status.');
            }
        };

        await pollOnce();
        statusPollTimer = setInterval(pollOnce, 3000);
    };

    const restoreActiveAnalysis = async () => {
        const raw = sessionStorage.getItem(STORAGE_KEY);
        if (!raw) {
            return;
        }

        try {
            const { analysisId, docUrl, repoUrl } = JSON.parse(raw);
            if (!analysisId || !docUrl) {
                clearActiveAnalysis();
                return;
            }

            if (repoUrl) {
                repoInput.value = repoUrl;
                fetchPreview(repoUrl);
            }
            setLoading(true, 'Resuming analysis...');
            await pollStatus(analysisId, docUrl);
        } catch (_) {
            clearActiveAnalysis();
        }
    };

    const loadHistory = async () => {
        if (!isAuthenticated || !historySection || !historyList) {
            return;
        }

        try {
            const response = await fetch('/api/history');
            const data = await response.json();
            historySection.hidden = false;

            if (!response.ok || !data.history || data.history.length === 0) {
                historyList.innerHTML = '<div class="history-empty">No repository history yet.</div>';
                return;
            }

            historyList.innerHTML = data.history
                .map((repo) => {
                    const lastAccessed = repo.last_accessed ? new Date(repo.last_accessed).toLocaleDateString() : 'Unknown';
                    return `
                        <button class="history-item" type="button" data-history-repo="${repo.repo_url}">
                            <div>
                                <div class="history-item-name">${repo.repo_name}</div>
                                <div class="history-item-time">Last accessed: ${lastAccessed}</div>
                            </div>
                            <span>Load</span>
                        </button>
                    `;
                })
                .join('');
        } catch (_) {
            historySection.hidden = false;
            historyList.innerHTML = '<div class="history-empty">History could not be loaded.</div>';
        }
    };

    repoInput.addEventListener('input', schedulePreviewFetch);
    repoInput.addEventListener('blur', schedulePreviewFetch);

    sampleRepoButtons.forEach((button) => {
        button.addEventListener('click', () => {
            repoInput.value = button.dataset.sampleRepo || '';
            schedulePreviewFetch();
            repoInput.focus();
        });
    });

    document.addEventListener('click', (event) => {
        const historyButton = event.target.closest('[data-history-repo]');
        if (!historyButton) {
            return;
        }

        repoInput.value = historyButton.dataset.historyRepo || '';
        schedulePreviewFetch();
        repoInput.focus();
    });

    generateButton.addEventListener('click', async () => {
        const repoUrl = repoInput.value.trim();

        if (!repoUrl) {
            showError('Please enter a GitHub repository URL.');
            return;
        }

        if (!isValidGitHubUrl(repoUrl)) {
            showError('Enter a valid public GitHub repository URL.');
            return;
        }

        stopPolling();
        resetProgress();
        if (resultsLinkContainer) {
            resultsLinkContainer.hidden = true;
        }
        setLoading(true, 'Starting analysis...');

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo_url: repoUrl }),
            });
            const data = await response.json();

            if (response.status === 202) {
                const analysisId = data.analysis_id;
                const docUrl = data.doc_url || `/doc?analysis_id=${analysisId}`;
                saveActiveAnalysis(analysisId, docUrl, repoUrl);
                showProgress({
                    status: 'processing',
                    stage: 'queued',
                    progress: 0,
                    message: data.message || 'Analysis queued.',
                });
                await pollStatus(analysisId, docUrl);
                return;
            }

            if (response.status === 403 && loginModal) {
                setLoading(false);
                loginModal.hidden = false;
                return;
            }

            showError(data.error || 'Failed to start analysis.');
        } catch (_) {
            showError('Unable to start analysis.');
        }
    });

    if (closeLoginModal && loginModal) {
        closeLoginModal.addEventListener('click', () => {
            loginModal.hidden = true;
        });
        loginModal.addEventListener('click', (event) => {
            if (event.target === loginModal) {
                loginModal.hidden = true;
            }
        });
    }

    if (repoInput.value.trim()) {
        schedulePreviewFetch();
    }

    restoreActiveAnalysis();
    loadHistory();
});
