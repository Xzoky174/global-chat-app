var socket = io();

var form = document.getElementById("form");
var messages = document.getElementById("messages");
var messageInput = document.getElementById("message");
var noMessages = document.getElementById("noMessages");
var sendBtn = document.getElementById("submit-btn");

let prevKey = "";
let holdingShift = false;

function goDown() {
  messages.scrollTop = messages.scrollHeight;
}
function removeTypingMessage() {
  let typing = document.querySelector(".typing");

  if (typing !== null && typing !== undefined) typing.remove();
  noMessages = document.getElementById("noMessages");
}
function clearInput() {
  messageInput.value = "";
}

goDown();

function initialize(username, uid) {
  form.addEventListener("submit", (e) => {
    e.preventDefault();

    if (messageInput.value.trim().length !== 0) {
      socket.emit("message", {
        message: messageInput.value,
        author: username,
        author_uid: uid,
      });

      socket.emit("stop-typing");
    }

    clearInput();
  });

  const inputChangeListener = () => {
    let lines = messageInput.value.split(/\r|\r\n|\n/).length;
    let root = document.querySelector(":root");

    if (lines > 1) {
      root.style.setProperty("--input-padding-top-bottom", "2px");
    } else {
      root.style.setProperty("--input-padding-top-bottom", "15px");
    }

    if (messageInput.value === "") {
      socket.emit("stop-typing");
    } else {
      socket.emit("typing", username);
    }
  };

  messageInput.addEventListener("input", inputChangeListener);
  messageInput.addEventListener("paste", inputChangeListener);
  messageInput.addEventListener("change", inputChangeListener);

  const keyDown = (e) => {
    let code = e.code;

    if (code === "Enter" && !prevKey.includes("Shift")) {
      sendBtn.click();

      messageInput.blur();
    }

    prevKey = code === "Enter" && prevKey.includes("Shift") ? "Shift" : code;
  };

  messageInput.addEventListener("focusin", () => {
    messageInput.addEventListener("keydown", keyDown);
  });
  messageInput.addEventListener("focusout", () => {
    messageInput.removeEventListener("keydown", keyDown);
  });

  socket.on("message", (info) => {
    let { message, author } = info;
    author = author === username ? "You" : author;

    messages.innerHTML += `<li class="message-item">
      <div class="message">
        <p class="message-author">${filterXSS(author)}</p>
        <p class="message-message">${filterXSS(message)}</p>
      </div>
    </li>`;
    noMessages = document.getElementById("noMessages");

    if (noMessages !== null && noMessages !== undefined) {
      noMessages.classList.add("hidden");
    }

    author === "You" && messageInput.focus();

    goDown();
  });
  socket.on("typing", (username) => {
    removeTypingMessage();

    messages.innerHTML += `
      <p class="typing">
        <span class="typing-username">
          ${username}
        </span> 
        is Typing...
      </p>
    `;
    goDown();
  });
  socket.on("stop-typing", () => {
    removeTypingMessage();
  });
}
