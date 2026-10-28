/**
 * Drag-and-drop PDF upload with a client-side progress bar (via XHR so we
 * get upload progress events, which fetch() does not expose).
 */
(() => {
  const dropzone = document.querySelector("[data-dropzone]");
  if (!dropzone) return;

  const fileInput = document.querySelector("[data-file-input]");
  const form = document.querySelector("[data-upload-form]");
  const progressWrap = document.querySelector("[data-upload-progress]");
  const progressFill = progressWrap?.querySelector(".progress-fill");
  const fileNameLabel = document.querySelector("[data-file-name]");

  function showSelectedFile(file) {
    if (fileNameLabel && file) fileNameLabel.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
  }

  ["dragenter", "dragover"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragging");
    })
  );
  ["dragleave", "drop"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragging");
    })
  );
  dropzone.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files[0];
    if (file) {
      fileInput.files = e.dataTransfer.files;
      showSelectedFile(file);
    }
  });
  dropzone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => showSelectedFile(fileInput.files[0]));

  form?.addEventListener("submit", (e) => {
    if (!fileInput.files.length) return; // let native validation handle it
    e.preventDefault();

    const xhr = new XMLHttpRequest();
    const data = new FormData(form);

    progressWrap.style.display = "block";
    xhr.upload.addEventListener("progress", (evt) => {
      if (evt.lengthComputable) {
        const pct = Math.round((evt.loaded / evt.total) * 100);
        progressFill.style.width = pct + "%";
      }
    });
    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 400) {
        document.open();
        document.write(xhr.responseText);
        document.close();
      } else {
        StudyMind.toast("Upload failed. Please try again.", "error");
      }
    });
    xhr.open("POST", form.action);
    xhr.send(data);
  });
})();
