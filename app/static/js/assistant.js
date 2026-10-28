/**
 * Floating "Ask StudyMind" assistant widget - a general-purpose chat bubble
 * available on every authenticated page. Loads history lazily on first
 * open, sends messages to /assistant/message, and renders Markdown replies.
 */
(() => {
  const fab = document.querySelector("[data-assistant-fab]");
  const panel = document.querySelector("[data-assistant-panel]");
  if (!fab || !panel) return;

  const messagesEl = panel.querySelector("[data-assistant-messages]");
  const form = panel.querySelector("[data-assistant-form]");
  const textarea = panel.querySelector("[data-assistant-input]");
  const sendBtn = panel.querySelector("[data-assistant-send]");
  const clearBtn = panel.querySelector("[data-assistant-clear]");
  const closeBtn = panel.querySelector("[data-assistant-close]");

  let historyLoaded = false;
  let isOpen = false;

  function renderMarkdown(text) {
    if (window.marked) return marked.parse(text || "", { breaks: true });
    const div = document.createElement("div");
    div.textContent = text || "";
    return div.innerHTML;
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function showEmptyState() {
    messagesEl.innerHTML = `
      <div class="assistant-empty">
        👋 Hi! I'm your StudyMind assistant.<br>
        Ask me about using the app, study tips, or anything else -
        for questions about a specific PDF, open that document's own chat instead.
      </div>`;
  }

  function messageNode(role, content) {
    const row = document.createElement("div");
    row.className = `assistant-msg ${role}`;
    const avatar = role === "user" ? "You" : "AI";
    row.innerHTML = `
      <div class="avatar ${role === 'user' ? 'user' : 'assistant'}">${avatar}</div>
      <div class="assistant-bubble">${renderMarkdown(content)}</div>`;
    return row;
  }

  function typingNode() {
    const row = document.createElement("div");
    row.className = "assistant-msg assistant";
    row.dataset.typing = "true";
    row.innerHTML = `
      <div class="avatar assistant">AI</div>
      <div class="assistant-bubble"><div class="assistant-typing"><span></span><span></span><span></span></div></div>`;
    return row;
  }

  async function loadHistory() {
    try {
      const res = await fetch("/assistant/history", { headers: StudyMind.getCsrfHeaders() });
      const data = await res.json();
      if (data.success && data.messages.length) {
        messagesEl.innerHTML = "";
        data.messages.forEach((m) => messagesEl.appendChild(messageNode(m.role, m.content)));
        scrollToBottom();
      } else {
        showEmptyState();
      }
    } catch (err) {
      showEmptyState();
    }
    historyLoaded = true;
  }

  function openPanel() {
    isOpen = true;
    fab.classList.add("is-open");
    panel.classList.add("is-open");
    if (!historyLoaded) loadHistory();
    setTimeout(() => textarea.focus(), 150);
  }

  function closePanel() {
    isOpen = false;
    fab.classList.remove("is-open");
    panel.classList.remove("is-open");
  }

  fab.addEventListener("click", () => (isOpen ? closePanel() : openPanel()));
  closeBtn?.addEventListener("click", closePanel);

  clearBtn?.addEventListener("click", async () => {
    if (!confirm("Clear this conversation?")) return;
    await fetch("/assistant/clear", { method: "POST", headers: StudyMind.getCsrfHeaders() });
    showEmptyState();
  });

  async function sendMessage(text) {
    document.querySelector(".assistant-empty")?.remove();
    messagesEl.appendChild(messageNode("user", text));
    const typing = typingNode();
    messagesEl.appendChild(typing);
    scrollToBottom();
    sendBtn.disabled = true;

    try {
      const res = await fetch("/assistant/message", {
        method: "POST",
        headers: StudyMind.getCsrfHeaders(),
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      typing.remove();
      if (!data.success) {
        StudyMind.toast(data.error || "The assistant couldn't respond.", "error");
        return;
      }
      messagesEl.appendChild(messageNode("assistant", data.message.content));
      scrollToBottom();
    } catch (err) {
      typing.remove();
      StudyMind.toast("Network error while messaging the assistant.", "error");
    } finally {
      sendBtn.disabled = false;
    }
  }

  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = textarea.value.trim();
    if (!text) return;
    textarea.value = "";
    textarea.style.height = "auto";
    sendMessage(text);
  });

  textarea?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  textarea?.addEventListener("input", () => {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 100) + "px";
  });
})();
