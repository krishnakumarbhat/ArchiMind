document.addEventListener('DOMContentLoaded', () => {
    const generateButton = document.getElementById('generateButton');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const resultsLinkContainer = document.getElementById('resultsLinkContainer');
    const repoInput = document.getElementById('repoInput');

    if (!generateButton || !loadingIndicator || !repoInput) {
        return;
    }

    const defaultLoadingMarkup = loadingIndicator.innerHTML;

    const setLoading = (isLoading, message = 'Analyzing repository...') => {
        generateButton.disabled = isLoading;
        loadingIndicator.style.display = isLoading ? 'inline-flex' : 'none';
        if (isLoading) {
            loadingIndicator.querySelector('div').textContent = message;
        }
    };

    const showError = (message) => {
        loadingIndicator.style.display = 'block';
        loadingIndicator.innerHTML = `<div style="color:#f87171; font-weight:500;">${message}</div>`;
        generateButton.disabled = false;
    };

    const pollStatus = () => {
        const interval = setInterval(async () => {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();

                if (data.status === 'completed') {
                    clearInterval(interval);
                    setLoading(false);
                    resultsLinkContainer.classList.add('visible');
                } else if (data.status === 'error') {
                    clearInterval(interval);
                    showError(data.error || 'An unknown error occurred.');
                } else {
                    // Still processing
                    setLoading(true, 'Analysis in progress...');
                }
            } catch (error) {
                clearInterval(interval);
                showError('Failed to get analysis status.');
            }
        }, 3000); // Poll every 3 seconds
    };

    generateButton.addEventListener('click', async () => {
        const repoUrl = repoInput.value.trim();

        if (!repoUrl) {
            showError('Please enter a GitHub repository URL.');
            return;
        }

        if (!repoUrl.includes('github.com')) {
            showError('Enter a valid GitHub repository URL.');
            return;
        }

        resultsLinkContainer.classList.remove('visible');
        setLoading(true, 'Starting analysis...');

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo_url: repoUrl }),
            });

            if (response.status === 202) {
                pollStatus();
            } else if (response.status === 403) {
                // Rate limit reached - show login modal
                const data = await response.json();
                setLoading(false);
                loadingIndicator.innerHTML = defaultLoadingMarkup;
                
                const modal = document.getElementById('loginModal');
                if (modal) {
                    modal.style.display = 'flex';
                }
            } else {
                const data = await response.json();
                showError(data.error || 'Failed to start analysis.');
            }
        } catch (error) {
            showError('Unable to start analysis. Check console for details.');
        }
    });
});
