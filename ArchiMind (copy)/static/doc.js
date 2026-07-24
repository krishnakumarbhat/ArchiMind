import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.esm.min.mjs";

const backendData = window.__ARCHIMIND_DATA__ || {};

mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    securityLevel: "loose",
    flowchart: {
        useMaxWidth: true,
        htmlLabels: true,
        curve: "basis",
    },
    themeVariables: {
        primaryColor: "#17cca3",
        primaryTextColor: "#f5f8fc",
        primaryBorderColor: "#17cca3",
        lineColor: "#17cca3",
        secondaryColor: "#12202f",
        tertiaryColor: "#163247",
        background: "#08131d",
        mainBkg: "#12202f",
        textColor: "#f5f8fc",
    },
});

const markedApi = window.marked;
const sanitizer = window.DOMPurify;

const state = {
    graphsRendered: false,
    activeDiagram: "hld",
};

const setChatPlaceholder = () => {
    const chatStream = document.getElementById("chatStream");
    if (!chatStream || chatStream.childElementCount) {
        return;
    }

    chatStream.innerHTML = '<p class="chat-placeholder">Ask about routes, data flow, dependencies, or specific files in this repository.</p>';
};

const renderMarkdown = (markdown, enableHeaders = true) => {
    if (!markedApi || !sanitizer) {
        return markdown;
    }

    markedApi.setOptions({
        breaks: true,
        gfm: true,
        headerIds: enableHeaders,
        mangle: false,
    });

    return sanitizer.sanitize(markedApi.parse(markdown || ""));
};

const buildDownload = (filename, content, mimeType) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
};

const appendChatMessage = (role, content, asMarkdown = false) => {
    const chatStream = document.getElementById("chatStream");
    if (!chatStream) {
        return;
    }

    const placeholder = chatStream.querySelector(".chat-placeholder");
    if (placeholder) {
        placeholder.remove();
    }

    const message = document.createElement("article");
    message.className = `chat-message ${role}`;

    const label = document.createElement("span");
    label.className = "chat-message-label";
    label.textContent = role === "assistant" ? "ArchiMind" : "You";

    const body = document.createElement("div");
    body.className = "chat-message-body";
    if (asMarkdown) {
        body.innerHTML = renderMarkdown(content, false);
    } else {
        body.textContent = content;
    }

    message.append(label, body);
    chatStream.appendChild(message);
    chatStream.scrollTop = chatStream.scrollHeight;
};

const renderDocumentation = () => {
    const docContent = document.getElementById("documentationContent");
    if (!docContent) {
        return;
    }

    if (!backendData.chat_response) {
        docContent.innerHTML = '<p class="empty-state">No documentation available.</p>';
        return;
    }

    docContent.innerHTML = renderMarkdown(backendData.chat_response, true);
    buildTableOfContents();
};

const buildTableOfContents = () => {
    const docContent = document.getElementById("documentationContent");
    const chapterNav = document.getElementById("chapterNav");
    if (!docContent || !chapterNav) {
        return;
    }

    const headings = Array.from(docContent.querySelectorAll("h2"));
    chapterNav.innerHTML = "";

    if (!headings.length) {
        chapterNav.innerHTML = '<span class="empty-state">No sections detected.</span>';
        return;
    }

    headings.forEach((heading, index) => {
        const id = `chapter-${index}`;
        heading.id = id;

        const link = document.createElement("a");
        link.href = `#${id}`;
        link.className = "chapter-link";
        link.textContent = heading.textContent.trim();
        link.addEventListener("click", (event) => {
            event.preventDefault();
            heading.scrollIntoView({ behavior: "smooth", block: "start" });
            document.querySelectorAll(".chapter-link").forEach((item) => item.classList.remove("active"));
            link.classList.add("active");
        });
        chapterNav.appendChild(link);
    });

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) {
                    return;
                }
                document.querySelectorAll(".chapter-link").forEach((item) => item.classList.remove("active"));
                const activeLink = chapterNav.querySelector(`a[href="#${entry.target.id}"]`);
                if (activeLink) {
                    activeLink.classList.add("active");
                }
            });
        },
        { rootMargin: "-20% 0px -70% 0px" },
    );

    headings.forEach((heading) => observer.observe(heading));
};

const renderGraph = async (diagramName, canvasId) => {
    const canvas = document.getElementById(canvasId);
    const graphPayload = backendData[`${diagramName}_graph`];
    if (!canvas) {
        return;
    }

    if (!graphPayload || graphPayload.status !== "ok" || !graphPayload.graph?.mermaid_code) {
        canvas.innerHTML = `<div class="graph-message">${graphPayload?.message || "No diagram available."}</div>`;
        return;
    }

    canvas.innerHTML = `
        <div class="mermaid-container">
            <div class="mermaid">${graphPayload.graph.mermaid_code}</div>
        </div>
    `;

    try {
        await mermaid.run({ querySelector: `#${canvasId} .mermaid` });
    } catch (error) {
        canvas.innerHTML = `<div class="graph-message error">${error.message}</div>`;
    }
};

const renderGraphsIfNeeded = async () => {
    if (state.graphsRendered) {
        return;
    }
    await renderGraph("hld", "hldCanvas");
    await renderGraph("lld", "lldCanvas");
    await renderGraph("flow", "flowCanvas");
    state.graphsRendered = true;
};

const populateFacts = () => {
    const repoFacts = document.getElementById("repoFacts");
    if (!repoFacts) {
        return;
    }

    const facts = [
        ["Repository", backendData.repo_name || "Unknown"],
        ["Source", backendData.repo_url || "Unavailable"],
        ["Backend", backendData.generation_backend || "local"],
        [
            "Diagrams",
            ["hld", "lld", "flow"]
                .filter((name) => backendData[`${name}_graph`]?.status === "ok")
                .map((name) => name.toUpperCase())
                .join(", ") || "None",
        ],
    ];

    repoFacts.innerHTML = facts
        .map(([label, value]) => `<div class="fact-row"><span>${label}</span><strong>${value}</strong></div>`)
        .join("");
};

const askQuestion = async (question) => {
    const chatMeta = document.getElementById("chatMeta");
    const submitButton = document.getElementById("chatSubmit");

    appendChatMessage("user", question, false);
    submitButton.disabled = true;
    chatMeta.textContent = "Searching the indexed repository context…";

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                repo_url: backendData.repo_url,
                repo_name: backendData.repo_name,
                question,
            }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Question failed.");
        }

        appendChatMessage("assistant", data.answer, true);
        chatMeta.textContent = `Answered using ${data.backend || "local"}.`;
    } catch (error) {
        appendChatMessage("assistant", error.message || "Question failed.", false);
        chatMeta.textContent = "Question failed. Try again with a narrower prompt.";
    } finally {
        submitButton.disabled = false;
    }
};

document.addEventListener("DOMContentLoaded", () => {
    renderDocumentation();
    populateFacts();
    setChatPlaceholder();

    const summaryContent = document.getElementById("repoSummaryContent");
    if (summaryContent) {
        summaryContent.innerHTML = backendData.chat_summary
            ? renderMarkdown(backendData.chat_summary, false)
            : '<p class="empty-state">No onboarding summary available.</p>';
    }

    document.querySelectorAll(".tab").forEach((tab) => {
        tab.addEventListener("click", async () => {
            document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach((item) => item.classList.remove("active"));
            tab.classList.add("active");
            document.getElementById(tab.dataset.tab)?.classList.add("active");

            if (tab.dataset.tab === "graphs") {
                await renderGraphsIfNeeded();
            }
        });
    });

    document.querySelectorAll(".graph-subtab").forEach((subtab) => {
        subtab.addEventListener("click", () => {
            state.activeDiagram = subtab.dataset.diagram;
            document.querySelectorAll(".graph-subtab").forEach((item) => item.classList.remove("active"));
            document.querySelectorAll(".graph-canvas").forEach((item) => item.classList.remove("active"));
            subtab.classList.add("active");
            document.getElementById(`${subtab.dataset.diagram}Canvas`)?.classList.add("active");
        });
    });

    document.getElementById("downloadMarkdownButton")?.addEventListener("click", () => {
        buildDownload(`${backendData.repo_name || "archimind"}-handbook.md`, backendData.chat_response || "", "text/markdown;charset=utf-8");
    });

    document.getElementById("downloadJsonButton")?.addEventListener("click", () => {
        buildDownload(`${backendData.repo_name || "archimind"}-analysis.json`, JSON.stringify(backendData, null, 2), "application/json;charset=utf-8");
    });

    document.getElementById("copyDiagramButton")?.addEventListener("click", async () => {
        const graphPayload = backendData[`${state.activeDiagram}_graph`];
        const code = graphPayload?.graph?.mermaid_code;
        if (!code) {
            return;
        }

        await navigator.clipboard.writeText(code);
        const button = document.getElementById("copyDiagramButton");
        if (button) {
            const original = button.textContent;
            button.textContent = "Copied diagram";
            window.setTimeout(() => {
                button.textContent = original;
            }, 1200);
        }
    });

    document.getElementById("chatForm")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const input = document.getElementById("chatQuestion");
        const question = input.value.trim();
        if (!question) {
            return;
        }
        input.value = "";
        await askQuestion(question);
    });
});