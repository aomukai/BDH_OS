const form = document.getElementById("loginForm");
const error = document.getElementById("loginError");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.textContent = "";
  const password = document.getElementById("password").value;
  const response = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (response.ok) window.location.href = "/";
  else if (response.status === 429) error.textContent = "Too many attempts. Try again later.";
  else error.textContent = "Invalid password.";
});
