/**
 * Chat page behavior: sends questions to /chat/<id>/message, renders the
 * dual-answer (PDF answer + AI explanation) response, and wires up
 * per-message actions (copy, regenerate, edit, delete).
 */
(() => {
  const root = document.querySelector("[data-chat-root]");
  if (!root) return;

  let chatId = root.dataset.chatId || null;  // empty string in draft mode
  const pdfId = root.dataset.pdfId;
  const messagesEl = document.querySelector("[data-chat-messages]");
  const form = document.querySelector("[data-chat-form]");
  const textarea = document.querySelector("[data-chat-input]");
  const sendBtn = document.querySelector("[data-chat-send]");
  const titleEl = document.querySelector("[data-chat-title]");

  function renderMarkdown(text) {
    if (window.marked) {
      const html = marked.parse(text || "", { breaks: true });
      return html;
    }
    return `<p>${(text || "").replace(/\n/g, "<br>")}</p>`;
  }

  function highlightAll(container) {
    if (window.hljs) {
      container.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block));
    }
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function userMessageNode(content) {
    const row = document.createElement("div");
    row.className = "message-row user";
    row.innerHTML = `
      <div class="avatar user">You</div>
      <div class="message-bubble">
        <div class="bubble-content">${escapeHtml(content)}</div>
      </div>`;
    return row;
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function assistantMessageNode(messageId, data) {
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.dataset.messageId = messageId;

    const confidencePct = Math.round((data.confidence || 0) * 100);
    const sourcesHtml = (data.sources || [])
      .map((s) => `<span class="source-chip" title="${escapeHtml(s.snippet)}">📄 Page ${s.page ?? "?"} · ${Math.round(s.score * 100)}%</span>`)
      .join("");

    row.innerHTML = `
      <div class="avatar assistant">AI</div>
      <div class="message-bubble">
        <div class="answer-card pdf-answer">
          <div class="answer-card-header">📘 Answer From PDF</div>
          <div class="answer-card-body pdf-answer-body">${renderMarkdown(data.pdf_answer)}</div>
        </div>
        <div class="answer-card ai-explanation">
          <div class="answer-card-header">💡 AI Explanation</div>
          <div class="answer-card-body">${renderMarkdown(data.ai_explanation)}</div>
        </div>
        ${data.sources && data.sources.length ? `<div class="sources-list">${sourcesHtml}</div>` : ""}
        <div class="confidence-bar">
          <span>Confidence</span>
          <div class="confidence-track"><div class="confidence-fill" style="width:${confidencePct}%"></div></div>
          <span>${confidencePct}%</span>
        </div>
        <div class="message-actions">
          <button type="button" data-action="copy" title="Copy answer">⧉</button>
          <button type="button" data-action="regenerate" title="Regenerate">↻</button>
          <button type="button" data-action="delete" title="Delete">🗑</button>
        </div>
      </div>`;
    highlightAll(row);
    return row;
  }

  function typingIndicatorNode() {
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.dataset.typing = "true";
    row.innerHTML = `
      <div class="avatar assistant">AI</div>
      <div class="message-bubble">
        <div class="answer-card pdf-answer"><div class="typing-indicator"><span></span><span></span><span></span></div></div>
      </div>`;
    return row;
  }

  async function sendMessage(question) {
    messagesEl.appendChild(userMessageNode(question));
    // In draft mode, the empty-state placeholder is still in the DOM - clear it now that a real message exists
    document.querySelector(".empty-state")?.remove();
    const typingNode = typingIndicatorNode();
    messagesEl.appendChild(typingNode);
    scrollToBottom();

    sendBtn.disabled = true;
    try {
      const isDraft = !chatId;
      const url = isDraft ? `/chat/pdf/${pdfId}/message` : `/chat/${chatId}/message`;
      const res = await fetch(url, {
        method: "POST",
        headers: StudyMind.getCsrfHeaders(),
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      typingNode.remove();

      if (!data.success) {
        StudyMind.toast(data.error || "Something went wrong.", "error");
        return;
      }

      if (isDraft && data.chat_url) {
        // The conversation now exists for real - navigate to its permanent
        // URL so the sidebar, pin/export/delete controls, and message
        // history all reflect the persisted state.
        window.location.href = data.chat_url;
        return;
      }

      messagesEl.appendChild(assistantMessageNode(data.message.id, data.message));
      if (data.chat_title && titleEl) titleEl.textContent = data.chat_title;
      scrollToBottom();
    } catch (err) {
      typingNode.remove();
      StudyMind.toast("Network error while sending your message.", "error");
    } finally {
      sendBtn.disabled = false;
    }
  }

  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const question = textarea.value.trim();
    if (!question) return;
    textarea.value = "";
    textarea.style.height = "auto";
    sendMessage(question);
  });

  textarea?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  textarea?.addEventListener("input", () => {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 160) + "px";
  });

  messagesEl?.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const row = btn.closest(".message-row");
    const messageId = row.dataset.messageId;
    const action = btn.dataset.action;

    if (action === "copy") {
      const text = row.querySelector(".pdf-answer-body").innerText;
      navigator.clipboard.writeText(text);
      StudyMind.toast("Copied to clipboard.", "success", 1800);
    }

    if (action === "delete") {
      if (!confirm("Delete this message?")) return;
      const res = await fetch(`/chat/message/${messageId}`, { method: "DELETE", headers: StudyMind.getCsrfHeaders() });
      const data = await res.json();
      if (data.success) row.remove();
    }

    if (action === "regenerate") {
      btn.disabled = true;
      const res = await fetch(`/chat/message/${messageId}/regenerate`, { method: "POST", headers: StudyMind.getCsrfHeaders() });
      const data = await res.json();
      if (data.success) {
        const newRow = assistantMessageNode(messageId, data.message);
        row.replaceWith(newRow);
      } else {
        StudyMind.toast(data.error || "Could not regenerate.", "error");
        btn.disabled = false;
      }
    }
  });

  document.querySelectorAll("[data-highlight-on-load]").forEach((el) => highlightAll(el));
  scrollToBottom();

  // ---------------- Rename conversation ----------------
  const renameBtn = document.querySelector("[data-rename-btn]");
  renameBtn?.addEventListener("click", () => {
    if (!chatId) return;
    const currentTitle = titleEl.textContent.trim();
    const input = document.createElement("input");
    input.type = "text";
    input.value = currentTitle;
    input.maxLength = 255;
    input.style.cssText = "font-size:14px; font-weight:700; padding:3px 8px; width:220px;";

    titleEl.replaceWith(input);
    renameBtn.style.display = "none";
    input.focus();
    input.select();

    let settled = false;
    async function commit() {
      if (settled) return;
      settled = true;
      const newTitle = input.value.trim();
      input.replaceWith(titleEl);
      renameBtn.style.display = "";

      if (!newTitle || newTitle === currentTitle) {
        titleEl.textContent = currentTitle;
        return;
      }
      titleEl.textContent = newTitle; // optimistic update

      try {
        const res = await fetch(`/chat/${chatId}/rename`, {
          method: "POST",
          headers: StudyMind.getCsrfHeaders(),
          body: JSON.stringify({ title: newTitle }),
        });
        const data = await res.json();
        if (!data.success) {
          titleEl.textContent = currentTitle;
          StudyMind.toast(data.error || "Could not rename conversation.", "error");
          return;
        }
        titleEl.textContent = data.title;
        // keep the sidebar list entry for this conversation in sync
        const sidebarLabel = document.querySelector(
          `[data-chat-list-item="${chatId}"] [data-chat-list-title]`
        );
        if (sidebarLabel) sidebarLabel.textContent = data.title;
      } catch (err) {
        titleEl.textContent = currentTitle;
        StudyMind.toast("Network error while renaming.", "error");
      }
    }

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); commit(); }
      if (e.key === "Escape") { e.preventDefault(); settled = true; input.replaceWith(titleEl); renameBtn.style.display = ""; }
    });
    input.addEventListener("blur", commit);
  });
})();
