document.addEventListener('DOMContentLoaded', () => {
    const generateButton = document.getElementById('generateButton');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const resultsLinkContainer = document.getElementById('resultsLinkContainer');

    generateButton.addEventListener('click', async () => {
        loadingIndicator.style.display = 'block';
        generateButton.disabled = true;
        resultsLinkContainer.classList.remove('visible');

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo_url: 'dummy_url' }),
            });

            const data = await response.json();

            if (data.status === 'success') {
                // Show the link and automatically open the results page
                resultsLinkContainer.classList.add('visible');
                window.open('/doc', '_blank');
            }
        } catch (error) {
            console.error("Fetch error:", error);
        } finally {
            loadingIndicator.style.display = 'none';
            generateButton.disabled = false;
        }
    });
});