
    const toggleButton = document.getElementById("dark-mode-toggle");

    toggleButton.addEventListener("click", () => {
        if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
            document.documentElement.classList.remove("dark");
        } else {
            document.documentElement.classList.add("dark");
        }
    });
