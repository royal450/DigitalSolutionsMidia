


const socket = io("https://digitalsolutionsmidia.onrender.com");
const fileInput = document.getElementById("fileInput");
const filePreview = document.getElementById("filePreview");
const extractedTextContent = document.getElementById("extractedTextContent");
const textPreview = document.getElementById("textPreview");
const audioPlayer = document.getElementById("audioPlayer");
const audioElement = document.getElementById("audioElement");
const downloadBtn = document.getElementById("downloadBtn");
const progressBar = document.getElementById("progressBar");
const progressPercent = document.getElementById("progressPercent");
const progressContainer = document.getElementById("progressContainer");

fileInput.addEventListener("change", function () {
    if (fileInput.files.length > 0) {
        const file = fileInput.files[0];
        filePreview.innerText = `Selected File: ${file.name}`;
        
        const reader = new FileReader();
        reader.readAsArrayBuffer(file);
        
        reader.onload = function () {
            const fileData = reader.result;
            socket.emit("upload_file", { file: fileData, filename: file.name });
        };

        progressContainer.style.display = "block";
    }
});

socket.on("progress_update", function (data) {
    progressBar.style.width = `${data.progress}%`;
    progressPercent.innerText = `${data.progress}%`;
});

socket.on("text_extracted", function (data) {
    extractedTextContent.innerText = data.text;
    textPreview.style.display = "block";
});

function convertToSpeech() {
    const text = extractedTextContent.innerText;
    const language = document.getElementById("language").value;
    const voice = document.getElementById("voice").value;

    socket.emit("convert_to_speech", { text, language, voice });
}

socket.on("audio_generated", function (data) {
    audioElement.src = data.audio_url;
    audioPlayer.style.display = "block";
    downloadBtn.disabled = false;
    downloadBtn.onclick = () => window.open(data.audio_url, "_blank");
});
          
