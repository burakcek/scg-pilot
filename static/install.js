(() => {
  let deferredPrompt = null;
  const button = document.getElementById("install-app");
  const help = document.getElementById("install-help");
  if (!button) return;

  const isInstalled = window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
  if (isInstalled) return;

  button.hidden = false;
  window.addEventListener("beforeinstallprompt", event => {
    event.preventDefault();
    deferredPrompt = event;
  });
  button.addEventListener("click", async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      button.hidden = true;
      return;
    }
    help.hidden = false;
    const language = document.documentElement.lang;
    help.textContent = language === "sq"
      ? "Në Chrome: hapni menynë ⋮ dhe zgjidhni “Install app” ose “Add to Home screen”."
      : language === "en"
        ? "In Chrome: open the ⋮ menu and choose “Install app” or “Add to Home screen”."
        : "Во Chrome: отвори го мени ⋮ и избери „Install app“ или „Add to Home screen“.";
  });
})();
