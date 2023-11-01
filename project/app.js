const flipBack = document.querySelector(".flip-back");

flipBack.addEventListener("click", () => {
    const newDescription = "New flip description goes here.";
    flipBack.querySelector("p").textContent = newDescription;
});