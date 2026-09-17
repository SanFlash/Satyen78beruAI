const generateButton = document.getElementById("generateBtn");

if (generateButton) {
  generateButton.addEventListener("click", async () => {
    const mainTopic = document.getElementById("mainTopicInput")?.value.trim() || "";
    const question = document.getElementById("questionInput")?.value.trim() || "";
    const style = document.getElementById("styleSelect")?.value || "Easy";
    const language = document.getElementById("languageInput")?.value.trim() || "";
    const textAnswer = document.getElementById("textAnswer");
    const imageResults = document.getElementById("imageResults");

    if (!textAnswer) return;

    textAnswer.classList.remove("answer-ready", "answer-error");

    if (imageResults) imageResults.innerHTML = "";

    if (!mainTopic || !question) {
      textAnswer.innerHTML = "Please enter both Main Topic and Question.";
      textAnswer.classList.add("answer-error");
      return;
    }

    const originalLabel = generateButton.innerHTML;
    generateButton.disabled = true;
    generateButton.classList.add("is-loading");
    generateButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Generating…';
    textAnswer.innerHTML = '<div class="answer-loading"><span class="loading-dot"></span><span class="loading-dot"></span><span class="loading-dot"></span><span class="ms-2">Building your study answer…</span></div>';

    let fullQuestion = `Main topic: ${mainTopic}\nQuestion: ${question}`;
    if (language) fullQuestion += `\nProvide code samples in ${language}.`;

    try {
      const response = await fetch("/api/generate-answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: fullQuestion, style })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to generate an answer.");
      }

      textAnswer.innerHTML = parseSimpleMarkup(data.answer);
      textAnswer.classList.add("answer-ready");

      if (imageResults) {
        const imageResponse = await fetch(`/api/search-images?q=${encodeURIComponent(question)}`);
        const imageData = await imageResponse.json();
        const items = imageData.items || [];

        items.forEach((item) => {
          const figure = document.createElement("figure");
          figure.className = "result-image-card";

          const img = document.createElement("img");
          img.src = item.link;
          img.alt = item.title || "Related image";
          img.loading = "lazy";
          img.addEventListener("error", () => figure.remove());

          figure.appendChild(img);
          if (item.title) {
            const caption = document.createElement("figcaption");
            caption.textContent = item.title;
            figure.appendChild(caption);
          }

          imageResults.appendChild(figure);
        });
      }
    } catch (error) {
      textAnswer.innerHTML = `Unable to generate the answer right now.<br><small>${escapeHtml(error.message)}</small>`;
      textAnswer.classList.add("answer-error");
      console.error(error);
    } finally {
      generateButton.disabled = false;
      generateButton.classList.remove("is-loading");
      generateButton.innerHTML = originalLabel;
    }
  });
}

function parseSimpleMarkup(text) {
  if (!text) return "";

  let safe = escapeHtml(text);
  safe = safe.replace(/```([\s\S]+?)```/g, "<pre><code>$1</code></pre>");
  safe = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  safe = safe.replace(/\*(.+?)\*/g, "<em>$1</em>");
  safe = safe.replace(/==(.+?)==/g, "<mark>$1</mark>");
  safe = safe.replace(/^###\s+(.+)$/gm, "<h3>$1</h3>");
  safe = safe.replace(/^##\s+(.+)$/gm, "<h2>$1</h2>");
  safe = safe.replace(/^#\s+(.+)$/gm, "<h1>$1</h1>");
  safe = safe.replace(/\n/g, "<br>");
  return safe;
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[char]));
}
