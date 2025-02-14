
// script.js
const socket = io();
let currentAudioUrl = '';

// Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const voiceSelect = document.getElementById('voiceSelect');
const progressBar = document.getElementById('progressBar');
const resultsSection = document.getElementById('results');
const extractedText = document.getElementById('extractedText');
const audioPlayer = document.getElementById('audioPlayer');
const downloadBtn = document.getElementById('downloadBtn');

// Socket.IO Handlers
socket.on('voices_available', voices => {
    voiceSelect.innerHTML = voices.map(v => `<option value="${v}">${v}</option>`).join('');
});

socket.on('text_extracted', ({ text }) => {
    resultsSection.classList.remove('d-none');
    extractedText.textContent = text;
});

socket.on('audio_ready', ({ url }) => {
    currentAudioUrl = url;
    audioPlayer.src = url;
    downloadBtn.href = url;
    downloadBtn.download = `audio_${Date.now()}.mp3`;
});

socket.on('progress', ({ percentage }) => {
    progressBar.style.width = `${percentage}%`;
    progressBar.textContent = `${Math.round(percentage)}%`;
});

// File Handling
dropZone.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', async e => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    handleFile(file);
});

fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    handleFile(file);
});

async function handleFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error('Upload failed');
    } catch (error) {
        alert(error.message);
    }
}

// Generate Audio
voiceSelect.addEventListener('change', async () => {
    const text = extractedText.textContent;
    const voice = voiceSelect.value;
    
    try {
        const response = await fetch('/generate-audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, voice })
        });
        
        if (!response.ok) throw new Error('Audio generation failed');
    } catch (error) {
        alert(error.message);
    }
});
