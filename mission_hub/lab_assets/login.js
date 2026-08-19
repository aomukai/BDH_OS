const form = document.querySelector("#loginForm");
const username = document.querySelector("#username");
const password = document.querySelector("#password");
const error = document.querySelector("#loginError");
const button = document.querySelector("#loginButton");
let setupRequired = false;

async function json(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || data.error || "Request failed");
  return data;
}

async function initialize() {
  try {
    const data = await json("/lab/api/bootstrap");
    setupRequired = data.setup_required;
    if (setupRequired) {
      document.querySelector("#loginKicker").textContent = "First local commissioning";
      document.querySelector("#loginTitle").textContent = "Make the Lab yours.";
      document.querySelector("#loginDetail").textContent = "Create the only local operator account before exposing the service through Tailscale.";
      button.textContent = "Create account";
      password.autocomplete = "new-password";
    }
  } catch (cause) {
    error.textContent = cause.message;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.textContent = "";
  button.disabled = true;
  try {
    await json(setupRequired ? "/lab/api/setup" : "/lab/api/login", {
      method: "POST",
      body: JSON.stringify({ username: username.value, password: password.value }),
    });
    window.location.replace("/");
  } catch (cause) {
    error.textContent = cause.message === "invalid_credentials" ? "That account or password did not match." : cause.message;
  } finally {
    button.disabled = false;
  }
});

initialize();
