// script.js

class ArchiMindApp {
    constructor() {
        this.currentData = null;
        this.network = null;
        this.currentView = 'hld';
        this.isProcessing = false;
        
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // Generate button
        const generateButton = document.getElementById('generateButton');
        const repoInput = document.getElementById('repoInput');
        
        generateButton.addEventListener('click', () => this.handleGenerate());
        repoInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.handleGenerate();
            }
        });

        // Tab switching
        const tabs = document.querySelectorAll('.tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });

        // Graph view switching
        const viewButtons = document.querySelectorAll('.view-button');
        viewButtons.forEach(button => {
            button.addEventListener('click', () => this.switchGraphView(button.dataset.view));
        });

        // Chat functionality
        const chatSendButton = document.getElementById('chatSendButton');
        const chatInput = document.getElementById('chatInput');
        
        chatSendButton.addEventListener('click', () => this.sendChatMessage());
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendChatMessage();
            }
        });
    }

    async handleGenerate() {
        const repoInput = document.getElementById('repoInput');
        const repoUrl = repoInput.value.trim();
        
        if (!repoUrl) {
            this.showStatus('Please enter a GitHub repository URL', 'error');
            return;
        }

        if (!this.isValidGitHubUrl(repoUrl)) {
            this.showStatus('Please enter a valid GitHub repository URL', 'error');
            return;
        }

        this.setLoadingState(true);
        this.showStatus('Analyzing repository...', 'warning');

        try {
            const response = await fetch('/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: repoUrl })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to process repository');
            }

            this.currentData = data;
            this.showMainContent();
            this.renderDocumentation(data.readme);
            this.renderGraph(data.hld, data.lld);
            this.showStatus('Repository analyzed successfully!', 'success');

        } catch (error) {
            console.error('Error processing repository:', error);
            this.showStatus(`Error: ${error.message}`, 'error');
        } finally {
            this.setLoadingState(false);
        }
    }

    isValidGitHubUrl(url) {
        const githubRegex = /^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+(\/)?$/;
        return githubRegex.test(url);
    }

    setLoadingState(loading) {
        this.isProcessing = loading;
        const generateButton = document.getElementById('generateButton');
        const loadingIndicator = document.getElementById('loadingIndicator');
        
        generateButton.disabled = loading;
        loadingIndicator.style.display = loading ? 'flex' : 'none';
    }

    showStatus(message, type) {
        // Remove existing status messages
        const existingStatus = document.querySelector('.status-message');
        if (existingStatus) {
            existingStatus.remove();
        }

        // Create new status message
        const statusDiv = document.createElement('div');
        statusDiv.className = `status-message status-${type}`;
        statusDiv.textContent = message;
        
        // Insert after the generate button
        const generateButton = document.getElementById('generateButton');
        generateButton.parentNode.insertBefore(statusDiv, generateButton.nextSibling);

        // Auto-remove success messages after 5 seconds
        if (type === 'success') {
            setTimeout(() => {
                if (statusDiv.parentNode) {
                    statusDiv.remove();
                }
            }, 5000);
        }
    }

    showMainContent() {
        const mainContent = document.getElementById('mainContent');
        mainContent.style.display = 'block';
        mainContent.scrollIntoView({ behavior: 'smooth' });
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(tabName).classList.add('active');

        // If switching to graph tab and we have data, render the current view
        if (tabName === 'graph' && this.currentData) {
            this.renderGraph(this.currentData.hld, this.currentData.lld);
        }
    }

    renderDocumentation(readme) {
        const documentationContent = document.getElementById('documentationContent');
        
        if (!readme || readme.trim() === '') {
            documentationContent.innerHTML = '<p>No README documentation found for this repository.</p>';
            return;
        }

        // Convert markdown-like content to HTML (basic conversion)
        let htmlContent = readme
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^#### (.*$)/gim, '<h4>$1</h4>')
            .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
            .replace(/\*(.*)\*/gim, '<em>$1</em>')
            .replace(/`([^`]+)`/gim, '<code>$1</code>')
            .replace(/```([\s\S]*?)```/gim, '<pre><code>$1</code></pre>')
            .replace(/\n/gim, '<br>');

        documentationContent.innerHTML = htmlContent;
    }

    renderGraph(hldData, lldData) {
        const graphStatus = document.getElementById('graphStatus');
        
        if (!hldData || !lldData) {
            graphStatus.textContent = 'No graph data available';
            return;
        }

        const data = this.currentView === 'hld' ? hldData : lldData;
        
        if (!data.nodes || data.nodes.length === 0) {
            graphStatus.textContent = 'No nodes found in the graph';
            return;
        }

        graphStatus.textContent = `${this.currentView.toUpperCase()} view - ${data.nodes.length} nodes, ${data.edges.length} edges`;

        // Prepare data for Vis.js
        const nodes = new vis.DataSet(data.nodes.map(node => ({
            id: node.id,
            label: node.label,
            group: node.group || node.type,
            title: node.title || `${node.type}: ${node.label}`,
            color: this.getNodeColor(node.group || node.type)
        })));

        const edges = new vis.DataSet(data.edges.map(edge => ({
            from: edge.from,
            to: edge.to,
            arrows: 'to',
            label: edge.label || '',
            color: { color: '#666', highlight: '#10B981' }
        })));

        const container = document.getElementById('graph-network');
        
        // Clear existing network
        if (this.network) {
            this.network.destroy();
        }

        // Create network
        const networkData = { nodes, edges };
        const options = {
            nodes: {
                shape: 'box',
                font: {
                    color: '#F9FAFB',
                    size: 12
                },
                borderWidth: 1,
                shadow: true
            },
            edges: {
                font: {
                    color: '#9CA3AF',
                    size: 10
                },
                width: 2,
                smooth: {
                    type: 'continuous'
                }
            },
            physics: {
                enabled: true,
                stabilization: { iterations: 100 },
                barnesHut: {
                    gravitationalConstant: -2000,
                    centralGravity: 0.3,
                    springLength: 95,
                    springConstant: 0.04,
                    damping: 0.09
                }
            },
            interaction: {
                hover: true,
                tooltipDelay: 200
            }
        };

        this.network = new vis.Network(container, networkData, options);
    }

    getNodeColor(type) {
        const colors = {
            'file': '#3B82F6',
            'class': '#8B5CF6',
            'function': '#10B981',
            'default': '#6B7280'
        };
        return colors[type] || colors.default;
    }

    switchGraphView(view) {
        this.currentView = view;
        
        // Update view buttons
        document.querySelectorAll('.view-button').forEach(button => {
            button.classList.remove('active');
        });
        document.querySelector(`[data-view="${view}"]`).classList.add('active');

        // Re-render graph if we have data
        if (this.currentData) {
            this.renderGraph(this.currentData.hld, this.currentData.lld);
        }
    }

    async sendChatMessage() {
        const chatInput = document.getElementById('chatInput');
        const message = chatInput.value.trim();
        
        if (!message) return;

        // Add user message to chat
        this.addChatMessage(message, 'user');
        chatInput.value = '';

        // Disable input while processing
        const chatSendButton = document.getElementById('chatSendButton');
        chatSendButton.disabled = true;

        try {
            // Send message to backend
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message })
            });

            if (!response.ok) {
                throw new Error('Failed to send message');
            }

            // Handle streaming response
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let assistantMessage = '';

            // Add assistant message container
            const messageId = this.addChatMessage('', 'assistant', true);

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            
                            if (data.content) {
                                assistantMessage += data.content;
                                this.updateChatMessage(messageId, assistantMessage);
                            }
                            
                            if (data.done) {
                                break;
                            }
                            
                            if (data.error) {
                                throw new Error(data.error);
                            }
                        } catch (e) {
                            console.error('Error parsing chunk:', e);
                        }
                    }
                }
            }

        } catch (error) {
            console.error('Error sending chat message:', error);
            this.addChatMessage(`Error: ${error.message}`, 'assistant');
        } finally {
            chatSendButton.disabled = false;
        }
    }

    addChatMessage(content, sender, isStreaming = false) {
        const chatMessages = document.getElementById('chatMessages');
        const messageId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        messageDiv.id = messageId;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;
        
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString();
        
        messageDiv.appendChild(contentDiv);
        messageDiv.appendChild(timeDiv);
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return messageId;
    }

    updateChatMessage(messageId, content) {
        const messageDiv = document.getElementById(messageId);
        if (messageDiv) {
            const contentDiv = messageDiv.querySelector('.message-content');
            contentDiv.textContent = content;
            
            // Scroll to bottom
            const chatMessages = document.getElementById('chatMessages');
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }
}

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ArchiMindApp();
});