var socket = io();

var form = document.getElementById("form");
var messages = document.getElementById("messages");
var messageInput = document.getElementById("message");
var noMessages = document.getElementById("noMessages");

function goDown() {
  messages.scrollTop = messages.scrollHeight;
}

function removeTypingMessage() {
  let typing = document.querySelector(".typing");

  if (typing !== null && typing !== undefined) typing.remove();
  noMessages = document.getElementById("noMessages");
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

      messageInput.value = "";
      messageInput.blur();
    }
  });

  messageInput.addEventListener("input", () => {
    if (messageInput.value === "") {
      socket.emit("stop-typing");
    } else {
      socket.emit("typing", username);
    }
  });
  messageInput.addEventListener("focusout", () => {
    socket.emit("stop-typing");
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
