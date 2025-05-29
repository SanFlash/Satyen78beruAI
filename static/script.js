const GOOGLE_API_KEY = "AIzaSyDzZQuDnsIgqUDyYhJ77UV9XJ0G-0M2pp0";
const SEARCH_ENGINE_ID = "b456c73a132774aa1";

document.getElementById("generateBtn").addEventListener("click", async () => {
  const mainTopic = document.getElementById("mainTopicInput").value.trim();
  const question = document.getElementById("questionInput").value.trim();
  const style = document.getElementById("styleSelect").value;
  const language = document.getElementById("languageInput").value.trim();
  const textAnswer = document.getElementById("textAnswer");
  const imageResults = document.getElementById("imageResults");

  textAnswer.innerHTML = "Generating answer...";
  imageResults.innerHTML = "";

  if (!mainTopic || !question) {
    textAnswer.innerHTML = "Please enter both Main Topic and Question.";
    return;
  }

  let fullQuestion = `Main topic: ${mainTopic}\nQuestion: ${question}`;
  if (language) fullQuestion += `\nProvide code samples in ${language}.`;

  try {
    const response = await fetch("/api/generate-answer", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: fullQuestion, style})
    });

    const data = await response.json();
    if (!response.ok) {
      textAnswer.innerHTML = `Error: ${data.error}`;
      return;
    }

    textAnswer.innerHTML = parseSimpleMarkup(data.answer);

    const imageQuery = encodeURIComponent(question + " diagram OR figure OR image");
    const imageResponse = await fetch(
      `https://www.googleapis.com/customsearch/v1?q=${imageQuery}&cx=${SEARCH_ENGINE_ID}&searchType=image&num=3&key=${GOOGLE_API_KEY}`
    );

    const imageData = await imageResponse.json();
    const items = imageData.items || [];
    items.forEach(item => {
      const img = document.createElement("img");
      img.src = item.link;
      img.alt = item.title || "Related image";
      img.style.maxWidth = "100%";
      img.style.margin = "5px 0";
      imageResults.appendChild(img);
    });

  } catch (error) {
    textAnswer.innerHTML = "An error occurred. Try again later.";
    console.error(error);
  }
});

function parseSimpleMarkup(text) {
  if (!text) return "";
  text = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/\*(.+?)\*/g, "<em>$1</em>");
  text = text.replace(/==(.+?)==/g, "<mark>$1</mark>");
  text = text.replace(/```([\s\S]+?)```/g, "<pre><code>$1</code></pre>");
  text = text.replace(/\n/g, "<br>");
  return text;
}
