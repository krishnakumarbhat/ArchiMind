document.addEventListener('DOMContentLoaded', () => {
    const generateButton = document.getElementById('generateButton');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const resultsLinkContainer = document.getElementById('resultsLinkContainer');
    const repoInput = document.getElementById('repoInput');

    if (!generateButton || !loadingIndicator || !repoInput) {
        return;
    }

    const defaultLoadingMarkup = loadingIndicator.innerHTML;

    const setLoading = (isLoading) => {
        loadingIndicator.style.display = isLoading ? 'inline-flex' : 'none';
        generateButton.disabled = isLoading;
        if (isLoading) {
            loadingIndicator.innerHTML = defaultLoadingMarkup;
        }
    };

    const showError = (message) => {
        loadingIndicator.style.display = 'block';
        loadingIndicator.innerHTML = `<div style="color:#f87171; font-weight:500;">${message}</div>`;
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
        setLoading(true);

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo_url: repoUrl }),
            });

            const data = await response.json();

            if (response.ok && data.status === 'success') {
                resultsLinkContainer.classList.add('visible');
            } else {
                showError(data.message || 'Analysis failed.');
            }
        } catch (error) {
            console.error('Fetch error:', error);
            showError('Unable to analyze repository. Check console for details.');
        } finally {
            setLoading(false);
        }
    });
});
